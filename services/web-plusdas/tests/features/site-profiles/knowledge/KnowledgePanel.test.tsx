// @vitest-environment jsdom
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { knowledgeApi } from '@/api';
import type { KnowledgeState } from '@/api/types/knowledge';
import type { ProfileVersion } from '@/api/types/siteProfiles';
import { KnowledgePanel } from '@/features/site-profiles/knowledge/KnowledgePanel';

const PROFILE: ProfileVersion = {
  site_id: 1002, version: 1, approved_at: '2026-11-07T10:00:00Z', approved_by: 'root@example.com', change_ids: [],
  catalog: {
    site: { site_id: 1002, name: 'Powerflow 2BESS 1PV', timezone: 'America/Phoenix' },
    devices: [{ device_id: 12, name: 'INV1', type: 'INVERTER' }],
    points: [
      { name: 'INV1.Power', device_id: 12, device_name: 'INV1', equipment: 'inverter', data_type: 'float32', point_class: 'ANALOG', unit: 'kW' },
      { name: 'INV1.State', device_id: 12, device_name: 'INV1', equipment: 'inverter', data_type: 'enum16', point_class: 'BINARY', enum_labels: { 0: 'STOPPED', 1: 'RUNNING' } },
    ],
    topology: { nodes: [], connections: [] },
  },
};
const EMPTY: KnowledgeState = {
  site_id: 1002, published_version: null, published_at: null, published_by: null, draft_revision: 0,
  draft_updated_at: null, draft_updated_by: null, changes: [], content: { point_guides: [], documents: [], device_facts: [] },
};
const WITH_DRAFT: KnowledgeState = {
  ...EMPTY,
  draft_revision: 1,
  draft_updated_at: '2026-11-07T10:05:00Z',
  draft_updated_by: 'root@example.com',
  changes: [{ item_key: 'point:12:State', item_kind: 'point_guide', kind: 'added', summary: 'added: guide for device 12 State' }],
  content: {
    point_guides: [{ site_id: 1002, device_id: 12, point_name: 'State', meaning: 'Inverter state', updated_at: '2026-11-07T10:05:00Z', related_points: [], limits: [], states: [] }],
    documents: [],
    device_facts: [],
  },
};

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});
afterEach(() => vi.restoreAllMocks());

function renderPanel() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><KnowledgePanel siteId={1002} profile={PROFILE} /></QueryClientProvider>);
}

describe('KnowledgePanel', () => {
  it('lists status points first and saves a guide with the states backend-ot labels', async () => {
    vi.spyOn(knowledgeApi, 'get').mockResolvedValue(EMPTY);
    const put = vi.spyOn(knowledgeApi, 'putPointGuide').mockResolvedValue(WITH_DRAFT);
    renderPanel();

    expect(await screen.findByText(/Nothing published yet/)).toBeTruthy();
    const rows = screen.getAllByRole('row').slice(1).map(row => within(row).getAllByRole('cell')[0].textContent);
    expect(rows).toEqual(['INV1.State', 'INV1.Power']);

    fireEvent.click(screen.getByRole('button', { name: 'Edit the guide of INV1.State' }));
    fireEvent.change(await screen.findByLabelText('Meaning'), { target: { value: 'Inverter state' } });
    fireEvent.change(screen.getByLabelText('Message of enum_value 0'), { target: { value: 'Inverter stopped' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save to draft' }));
    await waitFor(() => expect(put).toHaveBeenCalled());
    const [siteId, deviceId, pointName, body] = put.mock.calls[0];
    expect([siteId, deviceId, pointName]).toEqual([1002, 12, 'State']);
    expect(body.draft_revision).toBe(0);
    expect(body.states).toEqual([expect.objectContaining({ kind: 'enum_value', code: 0, label: 'STOPPED', message: 'Inverter stopped' })]);
  });

  it('reviews the draft: one change can be put back, and publish sends the reviewed revision', async () => {
    vi.spyOn(knowledgeApi, 'get').mockResolvedValue(WITH_DRAFT);
    const revert = vi.spyOn(knowledgeApi, 'revert').mockResolvedValue(EMPTY);
    const publish = vi.spyOn(knowledgeApi, 'publish').mockResolvedValue({
      site_id: 1002, version: 1, content: WITH_DRAFT.content, published_at: '2026-11-07T10:06:00Z', published_by: 'root@example.com', change_ids: ['point:12:State'],
    });
    renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: /Review & publish \(1\)/ }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('added: guide for device 12 State')).toBeTruthy();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Publish' }));
    await waitFor(() => expect(publish).toHaveBeenCalledWith(1002, 1));

    fireEvent.click(await screen.findByRole('button', { name: /Review & publish/ }));
    fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: /Put back added/ }));
    await waitFor(() => expect(revert).toHaveBeenCalledWith(1002, ['point:12:State'], 1));
  });

  it('asks to onboard the site first when there is no approved profile', () => {
    const queryClient = new QueryClient();
    render(<QueryClientProvider client={queryClient}><KnowledgePanel siteId={1002} profile={undefined} /></QueryClientProvider>);
    expect(screen.getByText(/Onboard the site first/)).toBeTruthy();
  });
});
