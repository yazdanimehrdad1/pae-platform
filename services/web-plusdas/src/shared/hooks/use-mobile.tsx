import * as React from "react"

const MOBILE_BREAKPOINT = 768

export function useIsMobile() {
  const [isMobile, setIsMobile] = React.useState<boolean | undefined>(undefined)

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)
    const onChange = () => {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
    }
    mql.addEventListener("change", onChange)
    setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
    return () => mql.removeEventListener("change", onChange)
  }, [])

  return !!isMobile
}

// The app's three layouts, on Tailwind's default breakpoints: phone below `md` (768px), tablet from
// `md` to below `xl` (1280px, so 1024 landscape is a tablet), laptop from `xl`. Prefer `md:`/`xl:`
// classes; use this only where the DOM itself differs (a drawer instead of an inline panel).
export type Breakpoint = "phone" | "tablet" | "laptop"

const TABLET_MIN_WIDTH = 768
const LAPTOP_MIN_WIDTH = 1280

function currentBreakpoint(): Breakpoint {
  // No matchMedia (jsdom, server): the full laptop layout.
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return "laptop"
  if (window.matchMedia(`(min-width: ${LAPTOP_MIN_WIDTH}px)`).matches) return "laptop"
  if (window.matchMedia(`(min-width: ${TABLET_MIN_WIDTH}px)`).matches) return "tablet"
  return "phone"
}

export function useBreakpoint(): Breakpoint {
  const [breakpoint, setBreakpoint] = React.useState<Breakpoint>(currentBreakpoint)

  React.useEffect(() => {
    if (typeof window.matchMedia !== "function") return
    const queries = [TABLET_MIN_WIDTH, LAPTOP_MIN_WIDTH].map((width) =>
      window.matchMedia(`(min-width: ${width}px)`),
    )
    const onChange = () => setBreakpoint(currentBreakpoint())
    queries.forEach((query) => query.addEventListener("change", onChange))
    onChange()
    return () => queries.forEach((query) => query.removeEventListener("change", onChange))
  }, [])

  return breakpoint
}
