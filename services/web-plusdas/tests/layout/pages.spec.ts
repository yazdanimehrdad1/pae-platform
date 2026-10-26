import { expect, test, type Page } from "@playwright/test";

// Every page must fit its width: nothing may make the page itself scroll sideways (wide tables
// and grids scroll inside their own box), and the shell must match the breakpoint.
const VIEWPORTS = [
  { name: "phone", width: 390, height: 844, shell: "phone" },
  { name: "tablet-portrait", width: 768, height: 1024, shell: "tablet" },
  { name: "tablet-landscape", width: 1024, height: 768, shell: "tablet" },
  { name: "laptop", width: 1366, height: 768, shell: "laptop" },
  { name: "desktop", width: 1440, height: 900, shell: "laptop" },
] as const;

const STATIC_ROUTES = [
  "/sites",
  "/sites/manage",
  "/historian",
  "/live-data",
  "/alarms",
  "/reports",
  "/sld",
  "/simulation",
  "/optimization",
  "/task-builder",
  "/notes",
  "/settings",
  "/users",
];

const ENGINEER = { id: "layout", email: "layout@example.com", name: "Layout Check", role: "engineer" };

// The report builder needs a site id from the running backend.
async function seededRoutes(page: Page): Promise<string[]> {
  const sites = await (await page.request.get("/api/sites")).json();
  if (!Array.isArray(sites) || sites.length === 0) return [];
  return [`/reports/${sites[0].site_id}/builder`];
}

// Fails when the page scrolls sideways, or when any visible element sticks out past the page's
// left or right edge (scrolled out of reach or clipped by an overflow-hidden card). Elements
// inside a box that scrolls sideways itself (tables, grids, diagrams) are fine.
async function expectNoSidewaysScroll(page: Page) {
  const overflow = await page.evaluate(() => {
    const main = document.querySelector("main");
    const root = document.documentElement;
    if (!main) return { page: root.scrollWidth - root.clientWidth, main: 0, offenders: [] as string[] };
    const area = main.getBoundingClientRect();
    const scrollsSideways = (element: Element) => {
      for (let ancestor = element.parentElement; ancestor && ancestor !== main; ancestor = ancestor.parentElement) {
        const overflowX = getComputedStyle(ancestor).overflowX;
        if (overflowX === "auto" || overflowX === "scroll") return true;
      }
      return false;
    };
    const sticksOut = (element: Element) => {
      const box = element.getBoundingClientRect();
      if (box.width === 0 || box.height === 0) return false;
      if (box.right <= area.right + 1 && box.left >= area.left - 1) return false;
      const style = getComputedStyle(element);
      return style.visibility !== "hidden" && style.opacity !== "0" && !scrollsSideways(element);
    };
    const describe = (element: Element) => {
      const text = (element.textContent ?? "").trim().replace(/\s+/g, " ").slice(0, 40);
      const classes = (element.getAttribute("class") ?? "").split(" ").slice(0, 4).join(".");
      return `<${element.tagName.toLowerCase()} .${classes}> "${text}"`;
    };
    // A box whose content is wider than itself: it spills over its neighbours or gets clipped.
    // Boxes that scroll sideways and ellipsis-truncated text are meant to.
    const spills = (element: Element) => {
      if (!(element instanceof HTMLElement) || element.clientWidth === 0) return false;
      if (element.scrollWidth <= element.clientWidth + 1) return false;
      const style = getComputedStyle(element);
      if (style.overflowX === "auto" || style.overflowX === "scroll" || style.textOverflow === "ellipsis") return false;
      return style.visibility !== "hidden" && !scrollsSideways(element);
    };
    const offending = (element: Element) => sticksOut(element) || spills(element);
    // Report the outermost elements only.
    const offenders = [...main.querySelectorAll("*")]
      .filter((element) => offending(element) && !(element.parentElement && element.parentElement !== main && offending(element.parentElement)))
      .slice(0, 5)
      .map(describe);
    return { page: root.scrollWidth - root.clientWidth, main: main.scrollWidth - main.clientWidth, offenders };
  });
  expect(overflow.page, "the document scrolls sideways").toBeLessThanOrEqual(1);
  expect(overflow.main, "the page content is wider than its area").toBeLessThanOrEqual(1);
  expect(overflow.offenders, `content sticks out: ${overflow.offenders.join(" | ")}`).toEqual([]);
}

for (const viewport of VIEWPORTS) {
  test.describe(viewport.name, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    test.beforeEach(async ({ page }) => {
      await page.addInitScript((user) => localStorage.setItem("user", JSON.stringify(user)), ENGINEER);
    });

    test("login page", async ({ page }) => {
      await page.goto("/login");
      await page.waitForLoadState("load");
      await expectNoSidewaysScroll(page);
      await page.screenshot({ path: `test-results/layout/${viewport.name}/login.png`, fullPage: true });
    });

    test("every page fits", async ({ page }) => {
      test.setTimeout(180_000);
      const routes = [...STATIC_ROUTES, ...(await seededRoutes(page))];
      const failures: string[] = [];
      for (const route of routes) {
        await page.goto(route);
        await page.waitForLoadState("load");
        await expect(page.locator(`[data-shell="${viewport.shell}"]`)).toBeVisible();
        // Let the queries settle (the live pages stream, so the network never goes idle).
        await page.waitForTimeout(1500);
        const file = route.replace(/^\//, "").replace(/\//g, "_");
        await page.screenshot({ path: `test-results/layout/${viewport.name}/${file}.png` });
        try {
          await expectNoSidewaysScroll(page);
        } catch (error) {
          failures.push(`${route}: ${(error as Error).message.split("\n")[0].replace(/^Error: /, "")}`);
        }
      }
      expect(failures, failures.join("\n")).toEqual([]);
    });

    // Below laptop width the navigation and Notes are drawers; following a link closes the drawer.
    if (viewport.shell !== "laptop") {
      test("navigation and notes drawers", async ({ page }) => {
        await page.goto("/sites");
        await page.getByRole("button", { name: viewport.shell === "phone" ? "Open navigation" : "Expand navigation" }).click();
        const drawer = page.getByRole("dialog", { name: "Navigation" });
        await expect(drawer).toBeVisible();
        await page.waitForTimeout(700); // the slide-in animation
        await page.screenshot({ path: `test-results/layout/${viewport.name}/drawer-navigation.png` });
        await drawer.getByRole("link", { name: "Reports" }).click();
        await expect(page).toHaveURL(/\/reports/);
        await expect(drawer).toBeHidden();

        await page.getByRole("button", { name: viewport.shell === "phone" ? "Open notes" : "Toggle notes" }).click();
        await expect(page.getByRole("dialog", { name: "Notes" })).toBeVisible();
        await page.waitForTimeout(700); // the slide-in animation
        await page.screenshot({ path: `test-results/layout/${viewport.name}/drawer-notes.png` });
      });
    }

    // A site's devices and a device's details get their site and device from the link that
    // opens them (router state), so they are reached by clicking through from Sites.
    test("site devices and device details fit", async ({ page }) => {
      await page.goto("/sites");
      await page.getByRole("button", { name: "Devices" }).first().click();
      await expect(page).toHaveURL(/\/site-devices$/);
      await page.waitForTimeout(1500);
      await page.screenshot({ path: `test-results/layout/${viewport.name}/site-devices.png` });
      await expectNoSidewaysScroll(page);
      // On phones the status cards fold into a summary line that opens them.
      const statusCards = page.locator("#site-device-status-cards");
      if (viewport.shell === "phone") {
        await expect(statusCards).toBeHidden();
        await page.getByRole("button", { name: /devices.*online/ }).click();
        await page.screenshot({ path: `test-results/layout/${viewport.name}/site-devices-status-open.png` });
      }
      await expect(statusCards).toBeVisible();

      await page.getByRole("button", { name: "Metadata" }).first().click();
      await expect(page).toHaveURL(/\/devices\/\d+$/);
      await page.waitForTimeout(1500);
      await page.screenshot({ path: `test-results/layout/${viewport.name}/device-details.png` });
      await expectNoSidewaysScroll(page);
    });
  });
}
