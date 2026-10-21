// @vitest-environment jsdom
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { SiteRecord } from '@/api/types/sites';
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
});

function renderForm(site?: SiteRecord) {
  const onSubmit = vi.fn().mockResolvedValue(undefined);
  render(<SiteFormDialog open onOpenChange={() => {}} site={site} onSubmit={onSubmit} />);
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
    expect((screen.getByLabelText('Elevation (m, optional)') as HTMLInputElement).value).toBe('331');

    fireEvent.change(screen.getByLabelText('Elevation (m, optional)'), { target: { value: '340' } });
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

    fireEvent.change(screen.getByLabelText('Elevation (m, optional)'), { target: { value: '300' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Needs latitude and longitude')).toBeTruthy();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
