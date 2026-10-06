// The Sites tab is a plain list: each site's name and details, sorted by name, with no alarm state.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react-native";

import type { Site } from "@/api/types";
import { siteDetails, SitesScreen } from "@/features/sites/SitesScreen";

jest.mock("expo-router", () => ({ useRouter: () => ({ push: jest.fn() }) }));
jest.mock("@/api/backendOt", () => ({ fetchSites: jest.fn() }));

const { fetchSites } = jest.requireMock("@/api/backendOt") as { fetchSites: jest.Mock };

function site(siteId: number, name: string, overrides: Partial<Site> = {}): Site {
  const now = "2026-10-06T12:00:00Z";
  return {
    site_id: siteId,
    client_id: "client",
    name,
    operator: "PAE",
    capacity: "5 MW",
    device_count: 9,
    created_at: now,
    updated_at: now,
    last_update: now,
    ...overrides,
  };
}

async function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  await render(
    <QueryClientProvider client={client}>
      <SitesScreen />
    </QueryClientProvider>,
  );
}

describe("siteDetails", () => {
  it("joins place, capacity and device count", () => {
    expect(
      siteDetails(site(1, "A", { location: { city: "Austin", state: "TX", street: "1 Main", zip_code: 1 } })),
    ).toBe("Austin, TX · 5 MW · 9 devices");
  });

  it("leaves out what is missing and keeps one device singular", () => {
    expect(siteDetails(site(1, "A", { capacity: "", device_count: 1 }))).toBe("1 device");
  });
});

describe("SitesScreen", () => {
  it("lists the sites by name", async () => {
    fetchSites.mockResolvedValue([site(2, "Bravo"), site(1, "Alpha")]);
    await renderScreen();
    const names = (await screen.findAllByText(/^(Alpha|Bravo)$/)).map((node) => node.props.children);
    expect(names).toEqual(["Alpha", "Bravo"]);
  });

  it("shows no alarm state", async () => {
    fetchSites.mockResolvedValue([site(1, "Alpha")]);
    await renderScreen();
    await screen.findByText("Alpha");
    expect(screen.queryByText(/fault|warning|normal/i)).toBeNull();
  });

  it("says when the server can't be reached", async () => {
    fetchSites.mockRejectedValue(new Error("Can't reach http://10.0.0.5:8000 (timed out)"));
    await renderScreen();
    expect(await screen.findByText("Can't load sites")).toBeTruthy();
    expect(screen.getByText("Can't reach http://10.0.0.5:8000 (timed out)")).toBeTruthy();
  });
});
