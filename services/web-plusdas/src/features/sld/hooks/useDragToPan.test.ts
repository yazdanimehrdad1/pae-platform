// @vitest-environment jsdom
import type { PointerEvent } from "react";
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useDragToPan } from "./useDragToPan";

function pointer(button: number, clientX: number, clientY: number, pointerId = 1) {
  return { button, clientX, clientY, pointerId, preventDefault: vi.fn() } as unknown as PointerEvent<HTMLElement>;
}

function setup(handToolActive: boolean) {
  const container = document.createElement("div");
  container.scrollLeft = 100;
  container.scrollTop = 50;
  const ref = { current: container };
  const hook = renderHook(({ active }) => useDragToPan(ref, active), { initialProps: { active: handToolActive } });
  return { container, hook };
}

describe("useDragToPan", () => {
  it("scrolls opposite to a left-button drag while the hand tool is on", () => {
    const { container, hook } = setup(true);
    expect(hook.result.current.cursor).toBe("grab");

    act(() => hook.result.current.panHandlers.onPointerDown(pointer(0, 200, 200)));
    expect(hook.result.current.cursor).toBe("grabbing");
    act(() => hook.result.current.panHandlers.onPointerMove(pointer(0, 170, 220)));
    expect(container.scrollLeft).toBe(130);
    expect(container.scrollTop).toBe(30);

    act(() => hook.result.current.panHandlers.onPointerUp(pointer(0, 170, 220)));
    act(() => hook.result.current.panHandlers.onPointerMove(pointer(0, 0, 0)));
    expect(container.scrollLeft).toBe(130); // no longer dragging
    expect(hook.result.current.cursor).toBe("grab");
  });

  it("ignores a left-button drag when the hand tool is off", () => {
    const { container, hook } = setup(false);
    expect(hook.result.current.cursor).toBeUndefined();
    act(() => hook.result.current.panHandlers.onPointerDown(pointer(0, 200, 200)));
    act(() => hook.result.current.panHandlers.onPointerMove(pointer(0, 100, 100)));
    expect(container.scrollLeft).toBe(100);
  });

  it("always pans with the middle button", () => {
    const { container, hook } = setup(false);
    act(() => hook.result.current.panHandlers.onPointerDown(pointer(1, 200, 200)));
    act(() => hook.result.current.panHandlers.onPointerMove(pointer(1, 150, 200)));
    expect(container.scrollLeft).toBe(150);
  });

  it("pans with the left button while Space is held, and stops when it is released", () => {
    const { container, hook } = setup(false);
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { code: "Space" }));
    });
    expect(hook.result.current.cursor).toBe("grab");
    act(() => hook.result.current.panHandlers.onPointerDown(pointer(0, 200, 200)));
    act(() => hook.result.current.panHandlers.onPointerMove(pointer(0, 190, 200)));
    expect(container.scrollLeft).toBe(110);
    act(() => hook.result.current.panHandlers.onPointerUp(pointer(0, 190, 200)));

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keyup", { code: "Space" }));
    });
    expect(hook.result.current.cursor).toBeUndefined();
  });

  it("ignores moves from a different pointer", () => {
    const { container, hook } = setup(true);
    act(() => hook.result.current.panHandlers.onPointerDown(pointer(0, 200, 200, 1)));
    act(() => hook.result.current.panHandlers.onPointerMove(pointer(0, 0, 0, 2)));
    expect(container.scrollLeft).toBe(100);
  });
});
