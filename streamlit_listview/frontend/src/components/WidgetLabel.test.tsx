import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WidgetLabel } from "./WidgetLabel";

describe("WidgetLabel", () => {
  it("renders the label through the restricted Markdown tier (bold -> <strong>)", () => {
    const { container } = render(
      <WidgetLabel
        label="**My label**"
        help={null}
        labelVisibility="visible"
        disabled={false}
        textId="lbl"
      />,
    );
    const labelSpan = container.querySelector(
      ".listview-widget-label__text",
    ) as HTMLElement;
    expect(labelSpan.getAttribute("aria-hidden")).toBe("true");
    const strong = labelSpan.querySelector("strong");
    expect(strong).not.toBeNull();
    expect(strong?.textContent).toBe("My label");
    // the raw asterisks are NOT present as literal text
    expect(screen.queryByText("**My label**")).not.toBeInTheDocument();
  });

  it("mirrors the label into a screen-reader-only span carrying textId, in every visibility", () => {
    // That span — not the visible one — supplies the listbox's accessible name:
    // the row is visibility:hidden at "hidden" (which inherits and suppresses a
    // name computed from it) and display:none at "collapsed".
    for (const visibility of ["visible", "hidden", "collapsed"] as const) {
      const { container, unmount } = render(
        <WidgetLabel
          label="**Pick** a fruit"
          help={null}
          labelVisibility={visibility}
          disabled={false}
          textId="name-src"
        />,
      );
      const nameSpan = container.querySelector("#name-src") as HTMLElement;
      expect(nameSpan).not.toBeNull();
      expect(nameSpan.className).toContain("listview-widget-label__a11y-name");
      // aria-hidden, so it is a name source only and never loose announced text
      expect(nameSpan.getAttribute("aria-hidden")).toBe("true");
      expect(nameSpan).toHaveTextContent("Pick a fruit");
      // it sits outside the (possibly hidden) label row
      const row = container.querySelector(
        '[data-testid="listview-widget-label"]',
      ) as HTMLElement;
      expect(row.contains(nameSpan)).toBe(false);
      unmount();
    }
  });

  it("puts STRIPPED text in the name span, not a second Markdown render", () => {
    // The name span used to re-render the label markdown, so every widget
    // rendered its label twice. It now carries the same stripped string the help
    // trigger names itself with, so there is one reduction of the label.
    const { container } = render(
      <WidgetLabel
        label="**Pick** a :red[fruit] :material/check:"
        help={null}
        labelVisibility="visible"
        disabled={false}
        textId="name-src"
      />,
    );
    const nameSpan = container.querySelector("#name-src") as HTMLElement;
    expect(nameSpan.textContent).toBe("Pick a fruit");
    expect(nameSpan.children.length).toBe(0);
    // the visible copy still goes through Markdown
    expect(
      container.querySelector(".listview-widget-label__text strong"),
    ).not.toBeNull();
  });

  it("hides the row with visibility:hidden when label_visibility=hidden", () => {
    const { container } = render(
      <WidgetLabel
        label="Hi"
        help={null}
        labelVisibility="hidden"
        disabled={false}
        textId="lbl"
      />,
    );
    const row = container.querySelector(
      '[data-testid="listview-widget-label"]',
    ) as HTMLElement;
    expect(row.style.visibility).toBe("hidden");
    expect(row.style.display).not.toBe("none");
  });

  it("removes the row from layout with display:none when collapsed", () => {
    const { container } = render(
      <WidgetLabel
        label="Hi"
        help={null}
        labelVisibility="collapsed"
        disabled={false}
        textId="lbl"
      />,
    );
    const row = container.querySelector(
      '[data-testid="listview-widget-label"]',
    ) as HTMLElement;
    expect(row.style.display).toBe("none");
  });

  it("delegates help to the HelpTooltip trigger only when help is set and visibility is visible", () => {
    const { rerender } = render(
      <WidgetLabel
        label="Hi"
        help="Some help"
        labelVisibility="visible"
        disabled={false}
        textId="lbl"
      />,
    );
    expect(
      screen.getByRole("button", { name: "Help for Hi" }),
    ).toBeInTheDocument();

    rerender(
      <WidgetLabel
        label="Hi"
        help="Some help"
        labelVisibility="hidden"
        disabled={false}
        textId="lbl"
      />,
    );
    expect(
      screen.queryByRole("button", { name: "Help for Hi" }),
    ).not.toBeInTheDocument();
  });

  it("does not render a help trigger when help is null", () => {
    render(
      <WidgetLabel
        label="Hi"
        help={null}
        labelVisibility="visible"
        disabled={false}
        textId="lbl"
      />,
    );
    expect(
      screen.queryByRole("button", { name: "Help for Hi" }),
    ).not.toBeInTheDocument();
  });

  it("no longer surfaces help via a title attribute or an inline help-text span", () => {
    const { container } = render(
      <WidgetLabel
        label="Hi"
        help="Some help"
        labelVisibility="visible"
        disabled={false}
        textId="lbl"
      />,
    );
    const trigger = screen.getByRole("button", { name: "Help for Hi" });
    // Milestone-A title tooltip is gone (HelpTooltip owns the popover now)
    expect(trigger.getAttribute("title")).toBeNull();
    // the hidden inline copy is gone too
    expect(container.querySelector(".listview-help-text")).toBeNull();
    // the popover is closed initially
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("adds the disabled class when disabled", () => {
    const { container } = render(
      <WidgetLabel
        label="Hi"
        help={null}
        labelVisibility="visible"
        disabled={true}
        textId="lbl"
      />,
    );
    const row = container.querySelector(
      '[data-testid="listview-widget-label"]',
    ) as HTMLElement;
    expect(row.className).toContain("listview-widget-label--disabled");
  });
});
