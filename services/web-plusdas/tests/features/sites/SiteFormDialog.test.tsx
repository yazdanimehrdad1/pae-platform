// @vitest-environment jsdom
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { SiteProfileInfo, SiteRecord } from '@/api/types/sites';
import { SiteFormDialog } from '@/features/sites/SiteFormDialog';
import { BROWSER_TIME_ZONE } from '@/shared/hooks/useDisplayTimeZone';

const SITE: SiteRecord = {
  site_id: 1001, client_id: 'alpha-corp', name: 'Alpha Solar Farm', operator: 'PAE', capacity: '5 MW', device_count: 3,
  description: null, profile: null, timezone: 'America/Los_Angeles',
  location: { street: '100 Solar Way', city: 'San Diego', state: 'CA', zip_code: 92101 },
  created_at: '2026-09-24T00:00:00Z', updated_at: '2026-09-25T00:00:00Z', last_update: '2026-09-25T00:00:00Z',
};

beforeAll(() => {
  Element.prototype.scrollIntoView ??= () => {}; // cmdk scrolls the active option into view
  Element.prototype.hasPointerCapture ??= () => false; // Radix Select
  Element.prototype.releasePointerCapture ??= () => {};
});

const PROFILES: SiteProfileInfo[] = [{ key: 'alpha_solar', site_id: 1002 }, { key: 'powerflow_2bess_1pv', site_id: null }];

function renderForm(site?: SiteRecord, profiles: SiteProfileInfo[] = PROFILES) {
  const onSubmit = vi.fn().mockResolvedValue(undefined);
  render(<SiteFormDialog open onOpenChange={() => {}} site={site} profiles={profiles} onSubmit={onSubmit} />);
  return onSubmit;
}

const timeZoneButton = () => screen.getByRole('combobox', { name: 'Time zone' });

describe('SiteFormDialog time zone', () => {
  it("starts a new site in the browser's zone", () => {
    renderForm();
    expect(timeZoneButton().textContent).toContain(BROWSER_TIME_ZONE);
  });

  it('lists the zones to choose from, searchable, and sends the chosen one', async () => {
    const onSubmit = renderForm(SITE);
    expect(timeZoneButton().textContent).toContain('America/Los_Angeles');

    fireEvent.click(timeZoneButton());
    expect(await screen.findByText('Europe')).toBeTruthy(); // region headings
    fireEvent.change(screen.getByPlaceholderText('Search a city, zone or offset'), { target: { value: 'berlin' } });
    fireEvent.click(await screen.findByRole('option', { name: /Europe\/Berlin/ }));
    expect(timeZoneButton().textContent).toContain('Europe/Berlin');

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ timezone: 'Europe/Berlin', name: 'Alpha Solar Farm' })));
  });
});

describe('SiteFormDialog coordinates', () => {
  it('shows and sends the elevation with the coordinates', async () => {
    const onSubmit = renderForm({ ...SITE, coordinates: { lat: 33.45, lng: -112.07, elevation_m: 331 } });
    expect((screen.getByLabelText('Elevation (m)') as HTMLInputElement).value).toBe('331');

    fireEvent.change(screen.getByLabelText('Elevation (m)'), { target: { value: '340' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      coordinates: { lat: 33.45, lng: -112.07, elevation_m: 340 },
    })));
  });

  it('omits a blank elevation', async () => {
    const onSubmit = renderForm({ ...SITE, coordinates: { lat: 33.45, lng: -112.07 } });

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      coordinates: { lat: 33.45, lng: -112.07 },
    })));
  });

  it('refuses an elevation without coordinates', async () => {
    const onSubmit = renderForm(SITE);

    fireEvent.change(screen.getByLabelText('Elevation (m)'), { target: { value: '300' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Needs latitude and longitude')).toBeTruthy();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});

describe('SiteFormDialog site profile', () => {
  const profileSelect = () => screen.getByRole('combobox', { name: 'Site profile' });

  it('sends no profile for a new site by default', async () => {
    const onSubmit = renderForm();
    expect(profileSelect().textContent).toContain('None');
    for (const [label, value] of [['Client ID', 'c'], ['Name', 'n'], ['Operator', 'o'], ['Capacity', '1 MW'], ['Street', 's'], ['City', 'c'], ['State', 'st']]) {
      fireEvent.change(screen.getByLabelText(label), { target: { value } });
    }
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ profile: null })));
  });

  it('offers the free profiles, not one held by another site, and sends the chosen one', async () => {
    const onSubmit = renderForm(SITE);

    fireEvent.pointerDown(profileSelect(), { button: 0, ctrlKey: false, pointerType: 'mouse' });
    expect((await screen.findByRole('option', { name: 'alpha_solar (used by site 1002)' })).getAttribute('aria-disabled')).toBe('true');
    fireEvent.click(screen.getByRole('option', { name: 'powerflow_2bess_1pv' }));
    expect(profileSelect().textContent).toContain('powerflow_2bess_1pv');

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ profile: 'powerflow_2bess_1pv' })));
  });

  it("keeps the site's own profile on edit, even before the list has loaded", async () => {
    const onSubmit = renderForm({ ...SITE, profile: 'alpha_solar' }, []);
    expect(profileSelect().textContent).toContain('alpha_solar');

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ profile: 'alpha_solar' })));
  });
});

describe('SiteFormDialog field markers', () => {
  const markOf = (label: string) => screen.getByText(label, { selector: 'label' }).nextElementSibling?.textContent ?? null;

  it('marks required fields with * and recommended ones with †, and explains both', () => {
    renderForm();
    for (const label of ['Client ID', 'Name', 'Operator', 'Capacity', 'Time zone', 'Street', 'City', 'State', 'Zip Code']) {
      expect(markOf(label), label).toBe('*');
    }
    for (const label of ['Site profile', 'Latitude', 'Longitude', 'Elevation (m)']) {
      expect(markOf(label), label).toBe('†');
    }
    expect(['*', '†']).not.toContain(markOf('Description'));
    expect(screen.getByText('Required')).toBeTruthy();
    expect(screen.getByText('Recommended')).toBeTruthy();
  });
});
