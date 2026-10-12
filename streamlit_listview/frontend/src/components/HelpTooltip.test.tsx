import { describe, it, expect, vi, afterEach } from "vitest";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HelpTooltip } from "./HelpTooltip";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("HelpTooltip", () => {
  it("renders a borderless trigger button with the accessible name 'Help for <label>'", () => {
    render(<HelpTooltip help="Some help" label="My field" />);
    const trigger = screen.getByRole("button", { name: "Help for My field" });
    expect(trigger).toBeInTheDocument();
    expect(trigger.className).toContain("listview-help-trigger");
    expect(trigger.getAttribute("type")).toBe("button");
  });

  it("renders the HelpCircle SVG (aria-hidden, focusable=false) inside the trigger", () => {
    const { container } = render(
      <HelpTooltip help="Some help" label="My field" />,
    );
    const svg = container.querySelector(
      "svg.listview-help-icon",
    ) as SVGSVGElement;
    expect(svg).not.toBeNull();
    expect(svg.getAttribute("viewBox")).toBe("0 0 24 24");
    expect(svg.getAttribute("aria-hidden")).toBe("true");
    expect(svg.getAttribute("focusable")).toBe("false");
    // react-feather HelpCircle geometry (locked contract)
    expect(container.querySelector('circle[r="10"]')).not.toBeNull();
    expect(
      container.querySelector('path[d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"]'),
    ).not.toBeNull();
    expect(
      container.querySelector('line[x1="12"][y1="17"][x2="12.01"][y2="17"]'),
    ).not.toBeNull();
  });

  it("keeps the popover hidden until the trigger is interacted with", () => {
    render(<HelpTooltip help="Some help" label="My field" />);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("wires aria-describedby on the trigger to the popover id only while open", async () => {
    const user = userEvent.setup();
    render(<HelpTooltip help="Some help" label="My field" />);
    const trigger = screen.getByRole("button", { name: "Help for My field" });
    expect(trigger.getAttribute("aria-describedby")).toBeNull();

    trigger.focus();
    const popover = await screen.findByRole("tooltip");
    expect(trigger.getAttribute("aria-describedby")).toBe(popover.id);
    expect(popover.id).not.toBe("");

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    expect(trigger.getAttribute("aria-describedby")).toBeNull();
  });

  it("leaves the popover open on a key other than Escape", async () => {
    const user = userEvent.setup();
    render(<HelpTooltip help="Some help" label="My field" />);
    const trigger = screen.getByRole("button", { name: "Help for My field" });

    trigger.focus();
    await screen.findByRole("tooltip");

    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
  });

  it("opens on keyboard focus and closes on blur", async () => {
    render(<HelpTooltip help="Some help" label="My field" />);
    const trigger = screen.getByRole("button", { name: "Help for My field" });

    trigger.focus();
    expect(await screen.findByRole("tooltip")).toBeInTheDocument();

    trigger.blur();
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("opens on pointer hover and closes on mouse leave", async () => {
    const user = userEvent.setup();
    render(<HelpTooltip help="Some help" label="My field" />);
    const trigger = screen.getByRole("button", { name: "Help for My field" });

    await user.hover(trigger);
    expect(await screen.findByRole("tooltip")).toBeInTheDocument();

    await user.unhover(trigger);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("stays open on mouse-leave while the trigger is still keyboard-focused", async () => {
    const user = userEvent.setup();
    render(<HelpTooltip help="Some help" label="My field" />);
    const trigger = screen.getByRole("button", { name: "Help for My field" });

    // open via keyboard focus
    trigger.focus();
    expect(await screen.findByRole("tooltip")).toBeInTheDocument();

    // hovering and leaving must NOT close it while focus remains
    await user.hover(trigger);
    await user.unhover(trigger);
    expect(screen.getByRole("tooltip")).toBeInTheDocument();

    // only when focus is also released does it close
    trigger.blur();
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("keeps intraword underscores in the accessible name while stripping emphasis markers", () => {
    // CommonMark does not treat intraword underscores as emphasis, so an
    // identifier like user_id must survive in the accessible name; only the
    // emphasis delimiters (_the_, **) are stripped.
    render(<HelpTooltip help="h" label="Edit _the_ **user_id** field" />);
    expect(
      screen.getByRole("button", { name: "Help for Edit the user_id field" }),
    ).toBeInTheDocument();
  });

  it("strips leading and trailing emphasis underscores from the accessible name", () => {
    // A label that is entirely emphasized (_em_) has an underscore at the very
    // start and very end — both must be stripped (word boundary at string
    // edges), unlike intraword underscores.
    render(<HelpTooltip help="h" label="_em_" />);
    expect(
      screen.getByRole("button", { name: "Help for em" }),
    ).toBeInTheDocument();
  });

  it("strips a directive attribute block ({foreground=...}) from the accessible name", () => {
    // The arbitrary-color directive :color[text]{foreground=… background=…}
    // carries a trailing attribute block; it must not leak into the screen-reader
    // name (which previously read "Help for Fruit{foreground=#ff0000}").
    render(<HelpTooltip help="h" label=":color[Fruit]{foreground=#ff0000}" />);
    expect(
      screen.getByRole("button", { name: "Help for Fruit" }),
    ).toBeInTheDocument();
  });

  it("renders the help body through the full Markdown tier (bold -> <strong>)", async () => {
    render(<HelpTooltip help="**bold help**" label="My field" />);
    const trigger = screen.getByRole("button", { name: "Help for My field" });
    trigger.focus();
    const popover = await screen.findByRole("tooltip");
    expect(popover.className).toContain("listview-help-popover");
    const strong = popover.querySelector("strong");
    expect(strong).not.toBeNull();
    expect(strong?.textContent).toBe("bold help");
  });
});

describe("HelpTooltip with a link in the help", () => {
  // The trigger's blur closed the popover before the focus reached the link,
  // so the link left the page and the focus fell to <body>.
  function renderWithLink() {
    render(
      <>
        <HelpTooltip
          help="See the [documentation](https://example.test/docs)."
          label="My field"
        />
        <button type="button">After</button>
      </>,
    );
    return screen.getByRole("button", { name: "Help for My field" });
  }

  it("keeps the help open while Tab moves the focus to the link", async () => {
    const user = userEvent.setup();
    renderWithLink().focus();
    await user.tab();
    expect(document.activeElement).toBe(
      screen.getByRole("link", { name: "documentation" }),
    );
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
  });

  it("stays open when Shift+Tab returns from the link to the trigger", async () => {
    const user = userEvent.setup();
    const trigger = renderWithLink();
    trigger.focus();
    await user.tab();
    await user.tab({ shift: true });
    expect(document.activeElement).toBe(trigger);
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
  });

  it("closes when the focus leaves the trigger and the popover", async () => {
    const user = userEvent.setup();
    renderWithLink().focus();
    await user.tab();
    await user.tab();
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "After" }),
    );
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("closes on Escape from the link and hands the focus back to the trigger", async () => {
    const user = userEvent.setup();
    const trigger = renderWithLink();
    trigger.focus();
    await user.tab();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    expect(document.activeElement).toBe(trigger);
  });
});

describe("HelpTooltip placement", () => {
  // jsdom lays nothing out, so each test states the geometry: where the
  // trigger sits, how big the help is and how big the viewport is. The
  // popover's own box follows its horizontal shift, as a browser's would.
  interface Layout {
    viewport: { width: number; height: number };
    anchor: { top: number; bottom: number; right: number };
    help: { width: number; height: number };
    /** A scroll container around the widget, such as Streamlit's sidebar. */
    clip?: { left: number; right: number; top: number; bottom: number };
    /** What the document root reports as its font size; jsdom's own otherwise. */
    rootFont?: string;
  }

  const BODY = "listview-help-popover__body";
  const CLIP = "clip";

  function stubLayout(layout: Layout) {
    // The one clipping ancestor is the test's own `.clip` wrapper; jsdom
    // reports no overflow for anything else.
    const realComputedStyle = window.getComputedStyle.bind(window);
    vi.spyOn(window, "getComputedStyle").mockImplementation((el) => {
      const style = realComputedStyle(el as Element);
      if ((el as Element).classList.contains(CLIP)) {
        return { ...style, overflowX: "auto", overflowY: "auto" };
      }
      if (el === document.documentElement && layout.rootFont !== undefined) {
        return { ...style, fontSize: layout.rootFont };
      }
      return style;
    });
    // The body's box moves with the shift its popover renders with.
    const shiftOf = (body: Element) =>
      Number(
        /translateX\((-?[\d.]+)px\)/.exec(
          (body.parentElement as HTMLElement).style.transform,
        )?.[1] ?? 0,
      );
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(
      function (this: Element) {
        const { anchor, help, clip } = layout;
        if (this.classList.contains(CLIP)) {
          const c = clip as NonNullable<Layout["clip"]>;
          return DOMRect.fromRect({
            x: c.left,
            y: c.top,
            width: c.right - c.left,
            height: c.bottom - c.top,
          });
        }
        if (this.classList.contains(BODY)) {
          const right = anchor.right + shiftOf(this);
          return DOMRect.fromRect({
            x: right - help.width,
            y: 0,
            width: help.width,
            height: help.height,
          });
        }
        return DOMRect.fromRect({
          x: anchor.right - 16,
          y: anchor.top,
          width: 16,
          height: anchor.bottom - anchor.top,
        });
      },
    );
    vi.spyOn(HTMLElement.prototype, "scrollHeight", "get").mockImplementation(
      function (this: HTMLElement) {
        return this.classList.contains(BODY) ? layout.help.height : 0;
      },
    );
    vi.spyOn(Element.prototype, "clientHeight", "get").mockImplementation(
      function (this: Element) {
        return this === document.documentElement ? layout.viewport.height : 0;
      },
    );
    vi.spyOn(Element.prototype, "clientWidth", "get").mockImplementation(
      function (this: Element) {
        return this === document.documentElement ? layout.viewport.width : 0;
      },
    );
  }

  function focusTrigger() {
    const trigger = screen.getByRole("button", { name: "Help for My field" });
    act(() => {
      trigger.focus();
    });
    const popover = screen.getByRole("tooltip");
    return { popover, body: popover.querySelector(`.${BODY}`) as HTMLElement };
  }

  function open(layout: Layout) {
    stubLayout(layout);
    const tooltip = <HelpTooltip help="Some help" label="My field" />;
    render(
      layout.clip === undefined ? (
        tooltip
      ) : (
        <div className={CLIP}>{tooltip}</div>
      ),
    );
    return focusTrigger();
  }

  const viewport = { width: 1000, height: 800 };

  it("caps its width to the viewport, 8 px off each edge", () => {
    const { popover } = open({
      viewport,
      anchor: { top: 600, bottom: 616, right: 900 },
      help: { width: 300, height: 200 },
    });
    expect(popover.style.getPropertyValue("--listview-popover-max-width")).toBe(
      "984px",
    );
  });

  it("opens below the trigger when the help does not fit above and more room is below", () => {
    // 100 px above the trigger leave 88 px after the 4 px gap and the 8 px
    // margin to the viewport's edge; below there are 800 - 116 - 12 = 672.
    const { popover, body } = open({
      viewport,
      anchor: { top: 100, bottom: 116, right: 900 },
      help: { width: 300, height: 500 },
    });
    expect(popover).toHaveAttribute("data-placement", "below");
    expect(body.style.maxHeight).toBe("672px");
    expect(body).not.toHaveAttribute("tabindex");
  });

  it("stays above the trigger when the help fits there", () => {
    const { popover, body } = open({
      viewport,
      anchor: { top: 600, bottom: 616, right: 900 },
      help: { width: 300, height: 200 },
    });
    expect(popover).toHaveAttribute("data-placement", "above");
    expect(body.style.maxHeight).toBe("588px");
  });

  it("scrolls help that fits on neither side, and takes the keyboard focus for it", () => {
    // 128 px above, 132 px below: the larger side, and the help scrolls in it.
    const { popover, body } = open({
      viewport: { width: 1000, height: 300 },
      anchor: { top: 140, bottom: 156, right: 900 },
      help: { width: 300, height: 900 },
    });
    expect(popover).toHaveAttribute("data-placement", "below");
    expect(body.style.maxHeight).toBe("132px");
    expect(body).toHaveAttribute("tabindex", "0");
  });

  it("moves right to keep clear of the viewport's left edge", () => {
    // Right-aligned to a trigger at x = 100, a 320 px popover would start at
    // -220; 228 px to the right it starts at the 8 px margin.
    const { popover } = open({
      viewport,
      anchor: { top: 600, bottom: 616, right: 100 },
      help: { width: 320, height: 100 },
    });
    expect(popover.style.transform).toBe("translateX(228px)");
  });

  it("moves left to keep clear of the viewport's right edge", () => {
    const { popover } = open({
      viewport,
      anchor: { top: 600, bottom: 616, right: 995 },
      help: { width: 300, height: 100 },
    });
    expect(popover.style.transform).toBe("translateX(-3px)");
  });

  it("stays inside a scroll container around the widget, such as the sidebar", () => {
    // A 300 px sidebar: the width cap follows it, and the shift keeps the
    // popover off its edges, not the viewport's. The help is 320 px wide
    // when first measured; the cap then narrows it to 284, and the shift
    // measured on the narrowed box lands its left edge at the 8 px margin.
    const layout: Layout = {
      viewport,
      anchor: { top: 600, bottom: 616, right: 270 },
      help: { width: 320, height: 200 },
      clip: { left: 0, right: 300, top: 0, bottom: 720 },
    };
    const { popover } = open(layout);
    expect(popover.style.getPropertyValue("--listview-popover-max-width")).toBe(
      "284px",
    );
    layout.help.width = 284;
    act(() => {
      fireEvent.scroll(document.body);
    });
    expect(popover.style.transform).toBe("translateX(22px)");
  });

  it("measures again after its width cap has applied", () => {
    // The first measurement sees the uncapped width, so the shift it gives is
    // for a box the cap then narrows; the second measurement corrects it.
    const layout: Layout = {
      viewport,
      anchor: { top: 600, bottom: 616, right: 200 },
      help: { width: 400, height: 100 },
      clip: { left: 0, right: 300, top: 0, bottom: 720 },
    };
    stubLayout(layout);
    const { rerender } = render(
      <div className={CLIP}>
        <HelpTooltip help="Some help" label="My field" />
      </div>,
    );
    const { popover } = focusTrigger();
    // From a 400 px box: shift = min(8 - (200 - 400), 300 - 8 - 200) = 92.
    expect(popover.style.transform).toBe("translateX(92px)");
    layout.help.width = 284; // the cap applied
    rerender(
      <div className={CLIP}>
        <HelpTooltip help="Some help" label="My field" />
      </div>,
    );
    // From the 284 px box: shift = min(8 - (200 - 284), 92) = 92; the same
    // here, which also shows the equal placement re-rendering nothing.
    expect(popover.style.transform).toBe("translateX(92px)");
  });

  it("reads the trigger gap from the document root's font size", () => {
    // 0.25rem at a 20 px root is 5 px: 100 px above leave 100 - 5 - 8 = 87.
    document.documentElement.style.fontSize = "20px";
    try {
      const { body } = open({
        viewport,
        anchor: { top: 100, bottom: 116, right: 900 },
        help: { width: 300, height: 50 },
      });
      expect(body.style.maxHeight).toBe("87px");
    } finally {
      document.documentElement.style.fontSize = "";
    }
  });

  it("takes a 16 px root when the document reports no font size", () => {
    // 100 px above the trigger, a 4 px gap and the 8 px margin leave 88.
    const { body } = open({
      viewport,
      anchor: { top: 100, bottom: 116, right: 900 },
      help: { width: 300, height: 50 },
      rootFont: "",
    });
    expect(body.style.maxHeight).toBe("88px");
  });

  it("finds a scroll container beyond the shadow boundary, through the host", () => {
    // The widget renders in a shadow root; the sidebar's scroll box is an
    // ancestor of the host. closest() stops at the boundary, the walk hops it.
    const layout: Layout = {
      viewport,
      anchor: { top: 600, bottom: 616, right: 270 },
      help: { width: 320, height: 200 },
      clip: { left: 0, right: 300, top: 0, bottom: 720 },
    };
    stubLayout(layout);
    const host = document.createElement("div");
    host.className = CLIP;
    document.body.appendChild(host);
    const shadow = host.attachShadow({ mode: "open" });
    try {
      render(<HelpTooltip help="Some help" label="My field" />, {
        container: shadow as unknown as HTMLElement,
      });
      const trigger = within(shadow as unknown as HTMLElement).getByRole(
        "button",
        { name: "Help for My field" },
      );
      act(() => {
        trigger.focus();
      });
      const popover = within(shadow as unknown as HTMLElement).getByRole(
        "tooltip",
      );
      expect(
        popover.style.getPropertyValue("--listview-popover-max-width"),
      ).toBe("284px");
    } finally {
      host.remove();
    }
  });

  it("measures again when the help's size changes after it opened", () => {
    // An image that loads after the first measurement grows the help; a
    // ResizeObserver on the body reports it, and the popover moves below.
    const observers: { callback: () => void; observed: Element[] }[] = [];
    class FakeResizeObserver {
      observed: Element[] = [];
      constructor(readonly callback: () => void) {
        observers.push(this);
      }
      observe(el: Element) {
        this.observed.push(el);
      }
      disconnect() {
        this.observed = [];
      }
    }
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);
    try {
      const layout: Layout = {
        viewport,
        anchor: { top: 300, bottom: 316, right: 900 },
        help: { width: 300, height: 100 },
      };
      const { popover, body } = open(layout);
      expect(popover).toHaveAttribute("data-placement", "above");
      // The effect ran twice: once on open, once after the width cap applied;
      // the first observer is disconnected, the last one watches the body.
      expect(observers).toHaveLength(2);
      expect(observers[0]!.observed).toEqual([]);
      const observer = observers[1]!;
      expect(observer.observed).toEqual([body]);
      layout.help.height = 400;
      act(() => {
        observer.callback();
      });
      expect(popover).toHaveAttribute("data-placement", "below");
      act(() => {
        screen.getByRole("button", { name: "Help for My field" }).blur();
      });
      expect(observer.observed).toEqual([]);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("places itself again when the page scrolls or the window resizes", () => {
    const layout: Layout = {
      viewport,
      anchor: { top: 600, bottom: 616, right: 900 },
      help: { width: 300, height: 200 },
    };
    const { popover } = open(layout);
    expect(popover).toHaveAttribute("data-placement", "above");
    layout.anchor = { top: 100, bottom: 116, right: 900 };
    act(() => {
      fireEvent.scroll(document.body);
    });
    expect(popover).toHaveAttribute("data-placement", "below");
    layout.anchor = { top: 600, bottom: 616, right: 900 };
    act(() => {
      window.dispatchEvent(new Event("resize"));
    });
    expect(popover).toHaveAttribute("data-placement", "above");
  });

  it("stops listening once it closes", () => {
    const layout: Layout = {
      viewport,
      anchor: { top: 600, bottom: 616, right: 900 },
      help: { width: 300, height: 200 },
    };
    open(layout);
    const remove = vi.spyOn(window, "removeEventListener");
    act(() => {
      screen.getByRole("button", { name: "Help for My field" }).blur();
    });
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    expect(remove).toHaveBeenCalledWith("scroll", expect.any(Function), true);
    expect(remove).toHaveBeenCalledWith("resize", expect.any(Function));
  });

  it("leaves the height alone without a laid-out viewport", () => {
    render(<HelpTooltip help="Some help" label="My field" />);
    const { popover, body } = focusTrigger();
    expect(body.style.maxHeight).toBe("");
    expect(popover.style.transform).toBe("");
  });
});
