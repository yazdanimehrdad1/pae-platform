// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { TimeZoneToggle } from '@/shared/components/TimeZoneToggle';
import { BROWSER_TIME_ZONE } from '@/shared/hooks/useDisplayTimeZone';

const SITE_ZONE = BROWSER_TIME_ZONE === 'Asia/Tokyo' ? 'Europe/Berlin' : 'Asia/Tokyo';

describe('TimeZoneToggle', () => {
  it('says which zone times are in and switches to the user\'s own', () => {
    const onDisplayChange = vi.fn();
    render(<TimeZoneToggle siteTimeZone={SITE_ZONE} display="site" onDisplayChange={onDisplayChange} />);
    expect(screen.getByText(`Times in ${SITE_ZONE} (site time)`)).toBeTruthy();
    fireEvent.click(screen.getByRole('switch', { name: 'Show times in my time zone' }));
    expect(onDisplayChange).toHaveBeenCalledWith('browser');
  });

  it("shows the user's zone when switched", () => {
    render(<TimeZoneToggle siteTimeZone={SITE_ZONE} display="browser" onDisplayChange={vi.fn()} />);
    expect(screen.getByText(`Times in ${BROWSER_TIME_ZONE} (your time)`)).toBeTruthy();
  });

  it('has no switch when the site is in the user\'s zone', () => {
    render(<TimeZoneToggle siteTimeZone={BROWSER_TIME_ZONE} display="site" onDisplayChange={vi.fn()} />);
    expect(screen.queryByRole('switch')).toBeNull();
    expect(screen.getByText(`Times in ${BROWSER_TIME_ZONE}`, { exact: false })).toBeTruthy();
  });
});
