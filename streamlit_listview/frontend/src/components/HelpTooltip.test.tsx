import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HelpTooltip } from "./HelpTooltip";

describe("HelpTooltip", () => {
  it("renders a borderless trigger button with the accessible name 'Help for <label>'", () => {
    render(<HelpTooltip help="Some help" label="My field" />);
    const trigger = screen.getByRole("button", { name: "Help for My field" });
    expect(trigger).toBeInTheDocument();
    expect(trigger.className).toContain("listview-help-trigger");
    expect(trigger.getAttribute("type")).toBe("button");
  });

  it("renders the HelpCircle SVG (aria-hidden, focusable=false) inside the trigger", () => {
    const { container } = render(<HelpTooltip help="Some help" label="My field" />);
    const svg = container.querySelector("svg.listview-help-icon") as SVGSVGElement;
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
