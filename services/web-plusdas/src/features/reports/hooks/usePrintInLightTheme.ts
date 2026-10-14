import { useEffect } from "react";

/**
 * While the page prints (Export PDF, or the browser's own Print), switch to the light theme so a
 * dark-mode report doesn't print as white on black; switch back after. Mounted only on the report
 * page, so other pages print as they are.
 */
export function usePrintInLightTheme(): void {
  useEffect(() => {
    const root = document.documentElement;
    let wasDark = false;
    const beforePrint = () => {
      wasDark = root.classList.contains("dark");
      if (wasDark) root.classList.remove("dark");
    };
    const afterPrint = () => {
      if (wasDark) root.classList.add("dark");
      wasDark = false;
    };
    window.addEventListener("beforeprint", beforePrint);
    window.addEventListener("afterprint", afterPrint);
    return () => {
      window.removeEventListener("beforeprint", beforePrint);
      window.removeEventListener("afterprint", afterPrint);
      afterPrint();
    };
  }, []);
}
