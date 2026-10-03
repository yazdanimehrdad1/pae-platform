import { useCallback, useEffect, useRef, useState, type PointerEvent, type RefObject } from "react";

const MIDDLE_BUTTON = 1;
const LEFT_BUTTON = 0;

interface DragStart {
  pointerId: number;
  clientX: number;
  clientY: number;
  scrollLeft: number;
  scrollTop: number;
}

const isTypingTarget = (target: EventTarget | null) =>
  target instanceof HTMLElement &&
  (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));

/**
 * Hand tool for a scrollable container: dragging moves the view by scrolling the container.
 * The left button pans while the hand tool is on or Space is held; the middle button always pans.
 */
export function useDragToPan(containerRef: RefObject<HTMLElement>, handToolActive: boolean) {
  const dragStart = useRef<DragStart | null>(null);
  const [isPanning, setIsPanning] = useState(false);
  const [isSpaceHeld, setIsSpaceHeld] = useState(false);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.code !== "Space" || isTypingTarget(event.target)) return;
      event.preventDefault(); // Space would otherwise scroll the page
      setIsSpaceHeld(true);
    };
    const handleKeyUp = (event: KeyboardEvent) => {
      if (event.code === "Space") setIsSpaceHeld(false);
    };
    const handleBlur = () => setIsSpaceHeld(false);
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    window.addEventListener("blur", handleBlur);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
      window.removeEventListener("blur", handleBlur);
    };
  }, []);

  const canPan = handToolActive || isSpaceHeld;

  const onPointerDown = useCallback(
    (event: PointerEvent<HTMLElement>) => {
      const container = containerRef.current;
      const panButton = event.button === MIDDLE_BUTTON || (event.button === LEFT_BUTTON && canPan);
      if (!container || !panButton) return;
      event.preventDefault(); // no text selection or middle-click autoscroll
      container.setPointerCapture?.(event.pointerId);
      dragStart.current = {
        pointerId: event.pointerId,
        clientX: event.clientX,
        clientY: event.clientY,
        scrollLeft: container.scrollLeft,
        scrollTop: container.scrollTop,
      };
      setIsPanning(true);
    },
    [containerRef, canPan],
  );

  const onPointerMove = useCallback(
    (event: PointerEvent<HTMLElement>) => {
      const container = containerRef.current;
      const start = dragStart.current;
      if (!container || !start || start.pointerId !== event.pointerId) return;
      container.scrollLeft = start.scrollLeft - (event.clientX - start.clientX);
      container.scrollTop = start.scrollTop - (event.clientY - start.clientY);
    },
    [containerRef],
  );

  const endPan = useCallback(
    (event: PointerEvent<HTMLElement>) => {
      const start = dragStart.current;
      if (!start || start.pointerId !== event.pointerId) return;
      containerRef.current?.releasePointerCapture?.(event.pointerId);
      dragStart.current = null;
      setIsPanning(false);
    },
    [containerRef],
  );

  const cursor = isPanning ? "grabbing" : canPan ? "grab" : undefined;

  return {
    isPanning,
    cursor,
    panHandlers: { onPointerDown, onPointerMove, onPointerUp: endPan, onPointerCancel: endPan },
  };
}
