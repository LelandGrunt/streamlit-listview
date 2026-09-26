# e2e/test_markdown.py
import re
from pathlib import Path

from playwright.sync_api import Page, expect

# The harness e2e/conftest.py serves for this module (no EXTRA_ARGS: the default
# theme is fine here — the themed instance of the same harness is test_core's).
APP_FILE = Path(__file__).with_name("app.py")


# Accessible name of the markdown instance in app.py: its label
# "**Pick** a :red[fruit] :material/check:" reduces via plainTextLabel to
# "Pick a fruit" (bold unwrapped, :red[] unwrapped, the icon dropped), which
# names the listbox via aria-labelledby.
_MARKDOWN_NAME = "Pick a fruit"


def _markdown_listview(page: Page):
    """The markdown-label / markdown-help instance's stListview root (the label
    and help popover live outside the listbox), found via its named listbox."""
    return page.get_by_test_id("stListview").filter(
        has=page.get_by_role("listbox", name=_MARKDOWN_NAME, exact=True)
    )


def _label(page: Page):
    """The widget-label container of the markdown listview."""
    return _markdown_listview(page).get_by_test_id("listview-widget-label")


def _help_trigger(page: Page):
    """The help-icon trigger button inside the markdown listview's label."""
    return _markdown_listview(page).locator("button.listview-help-trigger")


def _popover(page: Page):
    """The hand-rolled help popover (rendered when the trigger is hovered/focused)."""
    return _markdown_listview(page).locator(".listview-help-popover")


def test_label_renders_bold_not_literal_asterisks(page: Page):
    """`**Pick**` in the label renders a <strong>, and the literal `**` is gone."""
    label = _label(page)
    # The restricted (label) tier renders bold as <strong> with text "Pick".
    strong = label.locator("strong", has_text="Pick")
    expect(strong).to_have_count(1)
    # The raw asterisks must NOT survive into the rendered text.
    expect(label).not_to_contain_text("**Pick**")


def test_label_renders_colored_span(page: Page):
    """`:red[fruit]` in the label renders a colored span with text 'fruit'.

    Per the locked class scheme the span carries the base class
    `listview-md-color` plus the per-color modifier `listview-md-color--red`.
    """
    label = _label(page)
    colored = label.locator(".listview-md-color")
    expect(colored).to_have_count(1)
    expect(colored).to_have_text("fruit")
    expect(colored).to_have_class(re.compile(r"\blistview-md-color--red\b"))


def test_label_renders_material_icon(page: Page):
    """`:material/check:` in the label renders a material-icon span.

    Markdown.tsx runs materialIconPreprocess on the (escaped) label source, so
    the icon survives the restricted label tier. createRemarkMaterialIcons emits
    a `<span role="img" aria-label="check icon">` (Material Symbols Rounded font)
    whose text is the icon ligature name ("check"). The literal token must be gone.
    """
    label = _label(page)
    icon = label.locator('span[role="img"][aria-label="check icon"]')
    expect(icon).to_have_count(1)
    expect(icon).to_have_text("check")
    expect(label).not_to_contain_text(":material/check:")
    expect(label).not_to_contain_text(":material_check:")


def test_help_trigger_button_exists(page: Page):
    """The markdown listview exposes exactly one help-trigger button (help= is set),
    and while the popover is CLOSED it has no aria-describedby (the attribute is
    only present while the tooltip is open)."""
    trigger = _help_trigger(page)
    expect(trigger).to_have_count(1)
    # HelpTooltip renders aria-describedby={open ? popoverId : undefined}; closed
    # state omits it entirely. Assert it is ABSENT (no value matches `.+`).
    expect(trigger).not_to_have_attribute("aria-describedby", re.compile(r".+"))


def test_help_popover_opens_on_hover_with_rendered_markdown(page: Page):
    """Hovering the trigger opens .listview-help-popover containing rendered
    full-tier markdown: a <strong> ('best') AND an <a> (the [docs] link). While
    open, the trigger's aria-describedby points at the popover's id."""
    trigger = _help_trigger(page)
    popover = _popover(page)
    # Closed before any interaction.
    expect(popover).to_have_count(0)

    trigger.hover()

    expect(popover).to_have_count(1)
    expect(popover).to_have_attribute("role", "tooltip")

    # aria-describedby wiring is meaningful only while open: it equals the id
    # of the now-visible popover (per the locked HelpTooltip contract).
    popover_id = popover.get_attribute("id")
    assert popover_id, "open popover must carry an id for aria-describedby wiring"
    expect(trigger).to_have_attribute("aria-describedby", popover_id)

    # Full-tier markdown rendered inside: bold text + a real anchor.
    expect(popover.locator("strong", has_text="best")).to_have_count(1)
    link = popover.locator("a", has_text="docs")
    expect(link).to_have_count(1)
    expect(link).to_have_attribute("href", "https://example.com")
    # Links in our markdown open in a new tab, sanitized.
    expect(link).to_have_attribute("target", "_blank")
    expect(link).to_have_attribute("rel", "noopener noreferrer")


def test_help_popover_opens_on_focus_and_closes_on_escape(page: Page):
    """Keyboard focus on the trigger opens the popover; Escape closes it."""
    trigger = _help_trigger(page)
    popover = _popover(page)
    expect(popover).to_have_count(0)

    trigger.focus()
    expect(popover).to_have_count(1)

    # Escape closes the popover.
    page.keyboard.press("Escape")
    expect(popover).to_have_count(0)
