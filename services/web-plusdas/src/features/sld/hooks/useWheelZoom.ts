import { useEffect, useLayoutEffect, useRef, type Dispatch, type RefObject, type SetStateAction } from "react";

// Zoom factor per wheel delta unit: one mouse-wheel notch (deltaY ≈ 100) zooms by about 16%.
const ZOOM_SENSITIVITY = 0.0015;

interface ZoomAnchor {
  // Where the cursor was, as a fraction of the content's width/height, and in client px.
  fractionX: number;
  fractionY: number;
  clientX: number;
  clientY: number;
}

/**
 * Ctrl/Cmd + wheel (and trackpad pinch, which browsers send as ctrl + wheel) zooms the
 * content of a scroll container, keeping the point under the cursor in place. The listener
 * is native and non-passive: React's onWheel is passive, so it can't stop the browser from
 * zooming the whole page.
 *
 * `contentSelector` finds the zoomed element (whose rendered size follows `zoom`) inside
 * the container.
 */
export function useWheelZoom(
  containerRef: RefObject<HTMLElement>,
  contentSelector: string,
  zoom: number,
  setZoom: Dispatch<SetStateAction<number>>,
  clampZoom: (zoom: number) => number,
) {
  const pendingAnchor = useRef<ZoomAnchor | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const handleWheel = (event: WheelEvent) => {
      if (!event.ctrlKey && !event.metaKey) return;
      event.preventDefault();
      const content = container.querySelector(contentSelector);
      if (content) {
        const rect = content.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
          pendingAnchor.current = {
            fractionX: (event.clientX - rect.left) / rect.width,
            fractionY: (event.clientY - rect.top) / rect.height,
            clientX: event.clientX,
            clientY: event.clientY,
          };
        }
      }
      setZoom((previous) => clampZoom(previous * Math.exp(-event.deltaY * ZOOM_SENSITIVITY)));
    };
    container.addEventListener("wheel", handleWheel, { passive: false });
    return () => container.removeEventListener("wheel", handleWheel);
  }, [containerRef, contentSelector, setZoom, clampZoom]);

  // After the new zoom is laid out, scroll so the anchored point is back under the cursor.
  useLayoutEffect(() => {
    const anchor = pendingAnchor.current;
    pendingAnchor.current = null;
    const container = containerRef.current;
    const content = container?.querySelector(contentSelector);
    if (!anchor || !container || !content) return;
    const rect = content.getBoundingClientRect();
    container.scrollLeft += rect.left + anchor.fractionX * rect.width - anchor.clientX;
    container.scrollTop += rect.top + anchor.fractionY * rect.height - anchor.clientY;
  }, [zoom, containerRef, contentSelector]);
}
