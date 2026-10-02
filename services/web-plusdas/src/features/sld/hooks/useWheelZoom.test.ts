// @vitest-environment jsdom
import { useState } from "react";
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { useWheelZoom } from "./useWheelZoom";

const clampZoom = (zoom: number) => Math.max(0.2, Math.min(3, zoom));

function setup() {
  const container = document.createElement("div");
  const content = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  content.setAttribute("data-zoomed", "");
  container.appendChild(content);
  document.body.appendChild(container);
  const ref = { current: container };
  // The zoom of the latest render. renderHook updates result.current in an effect, after the
  // hook's layout effect has run, so the mocked layout below reads this instead.
  const rendered = { zoom: 1 };

  const hook = renderHook(() => {
    const [zoom, setZoom] = useState(1);
    rendered.zoom = zoom;
    useWheelZoom(ref, "[data-zoomed]", zoom, setZoom, clampZoom);
    return zoom;
  });
  return { container, content, hook, rendered };
}

function wheel(container: HTMLElement, init: WheelEventInit) {
  const event = new WheelEvent("wheel", { bubbles: true, cancelable: true, ...init });
  act(() => {
    container.dispatchEvent(event);
  });
  return event;
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("useWheelZoom", () => {
  it("zooms in on ctrl + wheel up and blocks the browser's page zoom", () => {
    const { container, hook } = setup();
    const event = wheel(container, { ctrlKey: true, deltaY: -100 });
    expect(event.defaultPrevented).toBe(true);
    expect(hook.result.current).toBeGreaterThan(1);
  });

  it("zooms out on ctrl + wheel down, and cmd works like ctrl", () => {
    const { container, hook } = setup();
    wheel(container, { metaKey: true, deltaY: 100 });
    expect(hook.result.current).toBeLessThan(1);
  });

  it("leaves a plain wheel alone so it scrolls", () => {
    const { container, hook } = setup();
    const event = wheel(container, { deltaY: 100 });
    expect(event.defaultPrevented).toBe(false);
    expect(hook.result.current).toBe(1);
  });

  it("clamps the zoom", () => {
    const { container, hook } = setup();
    for (let step = 0; step < 50; step++) wheel(container, { ctrlKey: true, deltaY: -100 });
    expect(hook.result.current).toBe(3);
  });

  it("scrolls so the point under the cursor stays put", () => {
    const { container, content, hook, rendered } = setup();
    // Content 1000×500 at zoom 1, scaled by the rendered zoom, its left/top edge 10px from the viewport.
    const sizeAt = () => ({ width: 1000 * rendered.zoom, height: 500 * rendered.zoom });
    content.getBoundingClientRect = () => {
      const { width, height } = sizeAt();
      return { left: 10, top: 10, width, height, right: 10 + width, bottom: 10 + height, x: 10, y: 10, toJSON: () => ({}) };
    };
    wheel(container, { ctrlKey: true, deltaY: -100, clientX: 510, clientY: 260 }); // cursor at the center
    const zoom = hook.result.current;
    // The center now sits at 10 + 500·zoom; the container scrolled by the difference.
    expect(container.scrollLeft).toBeCloseTo(500 * zoom - 500, 5);
    expect(container.scrollTop).toBeCloseTo(250 * zoom - 250, 5);
  });
});
