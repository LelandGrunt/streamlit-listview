"""Switch the whole demo server between the theme files in ``demo/.streamlit``.

Streamlit has no per-session theme: every rerun builds the theme it sends the
browser from the process-global config (``AppSession._create_new_session_message``
→ ``_populate_theme_msg``). Overlaying a theme file's options onto that config and
rerunning therefore re-themes this session at once, and every other open session
on its next rerun. It is the pipeline a saved ``config.toml`` already takes —
Streamlit watches the file, reparses it and reruns — minus the file write.

``streamlit.config.set_option`` is internal API (the public ``st.set_option``
refuses theme options), which is why it is confined to this module.
"""
import json
import threading
from datetime import timedelta

# The parser Streamlit itself reads config.toml with, so a theme file overlays
# exactly as it would load from disk.
import toml
from streamlit import config
from streamlit.config_option import ConfigOption

THEME_GLOB = "config_theme_*.toml"
_THEME_PREFIX = "config_theme_"
# Display names for the picker, next to the theme files they describe.
THEME_LABELS_FILE = "config_themes.json"

# How long a picked theme stays before the server falls back to the default, so
# one visitor's pick on the hosted demo does not stay for everyone forever.
THEME_TTL = timedelta(hours=24)

# Recorded as each overlaid option's origin (what `streamlit config show` prints).
WHERE_DEFINED = "streamlit-listview demo theme switcher"

_VARIANTS = ("light", "dark")

# Turns the switcher off for one deployment, e.g. as a Community Cloud secret:
# Streamlit copies root-level secrets into os.environ at server start.
SWITCHER_ENV = "LISTVIEW_DEMO_THEME_SWITCHER"
_SWITCHED_OFF = {"0", "false", "off", "no"}


def switcher_enabled(environ):
    """False only when the deployment explicitly switched the theme picker off.

    Unset means on, so a local run and the e2e suite need no setup. More than
    ``"0"`` counts as off: a natural ``false`` must not leave it on unnoticed.
    """
    return environ.get(SWITCHER_ENV, "").strip().lower() not in _SWITCHED_OFF


def discover_themes(directory):
    """Map each ``config_theme_<name>.toml`` in *directory* to its path, by name.

    A new file shows up in the switcher with no code change; ``config.toml`` (what
    Streamlit reads at boot) is not one of them.
    """
    return {
        path.stem.removeprefix(_THEME_PREFIX): path
        for path in sorted(directory.glob(THEME_GLOB))
    }


def theme_labels(directory):
    """Map each theme's ``<name>`` to its ``DisplayName`` in config_themes.json.

    The theme files stay what decides which themes exist (:func:`discover_themes`);
    this only names them, so a file without an entry still shows up — under its
    bare ``<name>``.
    """
    manifest = json.loads((directory / THEME_LABELS_FILE).read_text(encoding="utf-8"))
    return {entry["Name"]: entry["DisplayName"] for entry in manifest["Themes"]}


def flatten_theme(text):
    """Spell a theme file's ``[theme]`` table as Streamlit option keys.

    Tables nest (``[theme.dark.sidebar]`` → ``theme.dark.sidebar.<option>``);
    anything else — an array of tables like ``[[theme.fontFaces]]`` included — is
    an option's value, the same walk Streamlit's own config.toml reader does. Only
    ``[theme]`` is read, so a theme file can never reach server or client options.
    """
    options = {}

    def walk(prefix, table):
        for key, value in table.items():
            if isinstance(value, dict):
                walk(f"{prefix}.{key}", value)
            else:
                options[f"{prefix}.{key}"] = value

    walk("theme", toml.loads(text).get("theme", {}))
    return options


def theme_variants(options):
    """The ``[theme.light]`` / ``[theme.dark]`` variants a flattened theme defines.

    With both, the viewer picks between them in the app menu (⋮ → Settings).
    """
    return [
        variant
        for variant in _VARIANTS
        if any(key.startswith(f"theme.{variant}.") for key in options)
    ]


class ServerTheme:
    """The one theme overlay the whole Streamlit server renders with.

    ``active`` names the applied theme (None: the Streamlit default, i.e. what the
    server booted with). The demo's picker reads it rather than session state,
    because another session may have switched since this one last ran.

    Each switch first restores the boot config, then overlays the new theme, so
    an option only the previous theme set never leaks into the next one.
    """

    def __init__(self, ttl=THEME_TTL):
        self.ttl = ttl
        self.active = None
        self.applied_at = None
        self._boot = None
        # Sessions rerun on their own threads; a switch is restore-then-overlay,
        # and two interleaved would mix both themes.
        self._lock = threading.Lock()

    @property
    def expires_at(self):
        """When the applied theme falls back to the default (None: nothing to)."""
        return None if self.applied_at is None else self.applied_at + self.ttl

    def apply(self, name, options, *, now):
        """Overlay *options* (from :func:`flatten_theme`) as theme *name*."""
        with self._lock:
            self._restore_boot()
            for key, value in options.items():
                config.set_option(key, value, WHERE_DEFINED)
            self.active, self.applied_at = name, now

    def reset(self):
        """Go back to the Streamlit default."""
        with self._lock:
            self._clear()

    def expire(self, *, now, enabled=True):
        """Reset once the applied theme is ``ttl`` old; True if it just did.

        With the switcher off (*enabled* False) any applied theme is due at once:
        a deployment that turns the picker off gets the default back on the next
        rerun, not after the rest of the TTL.

        No timer thread: Streamlit sends the theme only with a rerun, so checking
        on each rerun changes what anyone sees no later than a timer would.
        """
        with self._lock:
            if self.applied_at is None or (enabled and now < self.applied_at + self.ttl):
                return False
            self._clear()
            return True

    def _clear(self):
        self._restore_boot()
        self.active = self.applied_at = None

    def _restore_boot(self):
        # Snapshot lazily, at the first switch: every config source (config.toml,
        # env, CLI flags) is parsed by then. An option carrying WHERE_DEFINED is
        # a previous instance's overlay (themes.py was hot-reloaded), not boot
        # config, so it is recorded as unset.
        if self._boot is None:
            self._boot = {
                key: (None, ConfigOption.DEFAULT_DEFINITION)
                if opt.where_defined == WHERE_DEFINED
                else (opt.value, opt.where_defined)
                for key, opt in config.get_config_options().items()
                if key.startswith("theme.")
            }
        for key, (value, where_defined) in self._boot.items():
            config.set_option(key, value, where_defined)


# The instance the demo app switches. Module state lives as long as the server
# process — which is exactly as long as the config it overlays.
SERVER_THEME = ServerTheme()
