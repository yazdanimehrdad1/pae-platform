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
    functions: [],
  },
};
const NO_LINKS = { points: [], functions: [], documents: [], devices: [] };
const EMPTY: KnowledgeState = {
  site_id: 1002, published_version: null, published_at: null, published_by: null, draft_revision: 0,
  draft_updated_at: null, draft_updated_by: null, changes: [], content: { point_guides: [], documents: [], device_facts: [], site_prompts: [] },
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
    site_prompts: [],
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
  render(<QueryClientProvider client={queryClient}><KnowledgePanel siteId={1002} timeZone="America/Los_Angeles" profile={PROFILE} /></QueryClientProvider>);
}

describe('KnowledgePanel', () => {
  it('lists status points first and saves a guide with the states backend-ot labels', async () => {
    vi.spyOn(knowledgeApi, 'get').mockResolvedValue(EMPTY);
    const put = vi.spyOn(knowledgeApi, 'putPointGuide').mockResolvedValue(WITH_DRAFT);
    renderPanel();

    expect(await screen.findByText(/Nothing published yet/)).toBeTruthy();
    fireEvent.mouseDown(screen.getByRole('tab', { name: 'Point guides' }));
    const rows = screen.getAllByRole('row').slice(1).map(row => within(row).getAllByRole('cell').slice(0, 2).map(cell => cell.textContent));
    expect(rows).toEqual([['INV1', 'State'], ['INV1', 'Power']]);

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

  it('filters the point guides by device', async () => {
    vi.spyOn(knowledgeApi, 'get').mockResolvedValue(EMPTY);
    const twoDevices: ProfileVersion = {
      ...PROFILE,
      catalog: {
        ...PROFILE.catalog,
        devices: [...PROFILE.catalog.devices, { device_id: 31, name: 'BESS1', type: 'BESS' }],
        points: [
          ...PROFILE.catalog.points,
          { name: 'BESS1.SOC', device_id: 31, device_name: 'BESS1', equipment: 'bess', data_type: 'float32', point_class: 'ANALOG', unit: '%' },
        ],
      },
    };
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><KnowledgePanel siteId={1002} timeZone="America/Los_Angeles" profile={twoDevices} /></QueryClientProvider>);
    const pointRows = () => screen.getAllByRole('row').slice(1).map(row => within(row).getAllByRole('cell').slice(0, 2).map(cell => cell.textContent));

    expect(await screen.findByText(/Nothing published yet/)).toBeTruthy();
    fireEvent.mouseDown(screen.getByRole('tab', { name: 'Point guides' }));
    expect(pointRows()).toHaveLength(3);
    const deviceFilter = screen.getByLabelText('Filter by device');
    expect(within(deviceFilter).getAllByRole('option').map(option => option.textContent)).toEqual(['All devices', 'BESS1', 'INV1']);

    fireEvent.change(deviceFilter, { target: { value: '31' } });
    expect(pointRows()).toEqual([['BESS1', 'SOC']]);
    fireEvent.change(deviceFilter, { target: { value: 'all' } });
    expect(pointRows()).toHaveLength(3);
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

  it('site prompts: adds the next prompt, edits one and deletes one after confirming', async () => {
    const script = (prompt_id: string, name: string, text: string, position: number) => ({
      prompt_id, site_id: 1002, name, text, position, links: NO_LINKS, author: 'root@example.com', updated_at: '2026-11-09T10:00:00Z',
    });
    const withScripts: KnowledgeState = {
      ...EMPTY,
      draft_revision: 2,
      changes: [{ item_key: 'prompt:b', item_kind: 'site_prompt', kind: 'added', summary: "added: site prompt 'Startup'" }],
      content: { ...EMPTY.content, site_prompts: [script('a', 'Overview', 'A 5 MW solar site.', 1), script('b', 'Startup', 'Close the main breaker first.', 2)] },
    };
    vi.spyOn(knowledgeApi, 'get').mockResolvedValue(withScripts);
    const create = vi.spyOn(knowledgeApi, 'createSitePrompt').mockResolvedValue({ ...withScripts, prompt_id: 'c' });
    const update = vi.spyOn(knowledgeApi, 'updateSitePrompt').mockResolvedValue(withScripts);
    const remove = vi.spyOn(knowledgeApi, 'deleteSitePrompt').mockResolvedValue(withScripts);
    renderPanel();

    expect(await screen.findByRole('tab', { name: 'Site Prompts (2)', selected: true })).toBeTruthy();
    expect(screen.getAllByRole('heading', { level: 3 }).map(heading => heading.textContent)).toEqual(['Prompt 1:Overview', 'Prompt 2:Startup']);
    expect(screen.getByText('Draft: new')).toBeTruthy();

    expect(screen.getByText('Add prompt 3')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Operating modes' } });
    fireEvent.change(screen.getByLabelText('Information'), { target: { value: 'Peak shaving in summer.' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit to draft/ }));
    await waitFor(() => expect(create).toHaveBeenCalledWith(1002, { name: 'Operating modes', text: 'Peak shaving in summer.', links: NO_LINKS, draft_revision: 2 }));

    fireEvent.click(screen.getByRole('button', { name: 'Edit Overview' }));
    expect(screen.getByText('Edit prompt 1')).toBeTruthy();
    fireEvent.change(screen.getByDisplayValue('A 5 MW solar site.'), { target: { value: 'A 5 MW PV site.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save to draft' }));
    await waitFor(() => expect(update).toHaveBeenCalledWith(1002, 'a', { name: 'Overview', text: 'A 5 MW PV site.', links: NO_LINKS, draft_revision: 2 }));

    fireEvent.click(await screen.findByRole('button', { name: 'Delete Startup' }));
    const confirm = await screen.findByRole('alertdialog');
    expect(within(confirm).getByText(/never published/)).toBeTruthy();
    fireEvent.click(within(confirm).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith(1002, 'b', 2));
  });

  it('site prompts: links points, functions, documents and device ratings, and shows them', async () => {
    const withFunction: ProfileVersion = {
      ...PROFILE,
      catalog: { ...PROFILE.catalog, functions: [{ name: 'site-poi-active-power', kind: 'site', output: 'series', summary: 'POI active power', device_types: [], parameters: [] }] },
    };
    const state: KnowledgeState = {
      ...EMPTY,
      draft_revision: 3,
      content: {
        ...EMPTY.content,
        documents: [{ document_id: 'doc1', site_id: 1002, kind: 'procedure', title: 'Restore', body: 'Steps', point_names: [], updated_at: '2026-11-09T10:00:00Z' }],
        device_facts: [{ site_id: 1002, device_id: 12, ratings: [], notes: 'Spare fan', updated_at: '2026-11-09T10:00:00Z' }],
        site_prompts: [{
          prompt_id: 'a', site_id: 1002, name: 'Overview', text: 'PV site.', position: 1,
          links: { points: [{ device_id: 12, point_name: 'State' }], functions: ['site-poi-active-power'], documents: ['doc1'], devices: [12] },
          updated_at: '2026-11-09T10:00:00Z',
        }],
      },
    };
    vi.spyOn(knowledgeApi, 'get').mockResolvedValue(state);
    const create = vi.spyOn(knowledgeApi, 'createSitePrompt').mockResolvedValue({ ...state, prompt_id: 'b' });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><KnowledgePanel siteId={1002} timeZone="America/Los_Angeles" profile={withFunction} /></QueryClientProvider>);

    const shown = within((await screen.findAllByRole('list', { name: 'Links' }))[0]).getAllByRole('listitem').map(item => item.textContent);
    expect(shown).toEqual(['Points:INV1.State', 'Site functions:site-poi-active-power', 'Documents:Restore', 'Device ratings:INV1']);

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Export limit' } });
    fireEvent.change(screen.getByLabelText('Information'), { target: { value: 'POI export is capped.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Link points' }));
    fireEvent.click(await screen.findByRole('checkbox', { name: 'INV1.Power' }));
    fireEvent.click(screen.getByRole('button', { name: 'Link site functions' }));
    fireEvent.click(await screen.findByRole('checkbox', { name: /site-poi-active-power/ }));
    fireEvent.click(screen.getByRole('button', { name: /Submit to draft/ }));
    await waitFor(() => expect(create).toHaveBeenCalledWith(1002, {
      name: 'Export limit', text: 'POI export is capped.', draft_revision: 3,
      links: { points: [{ device_id: 12, point_name: 'Power' }], functions: ['site-poi-active-power'], documents: [], devices: [] },
    }));
  });

  it('deletes the selected older versions, never the one the AI uses', async () => {
    const summary = (version: number) => ({
      version, published_at: '2026-11-07T10:00:00Z', published_by: 'root@example.com', change_ids: [], restored_from: null,
      point_guides: 1, documents: 0, device_facts: 0, site_prompts: 0,
    });
    vi.spyOn(knowledgeApi, 'get').mockResolvedValue({ ...EMPTY, published_version: 3, published_at: '2026-11-07T10:00:00Z', published_by: 'root@example.com' });
    vi.spyOn(knowledgeApi, 'versions').mockResolvedValue([summary(3), summary(2), summary(1)]);
    const remove = vi.spyOn(knowledgeApi, 'deleteVersions').mockResolvedValue([summary(3)]);
    renderPanel();

    fireEvent.mouseDown(await screen.findByRole('tab', { name: 'Versions' }));
    expect(await screen.findByRole('checkbox', { name: 'Select version 2' })).toBeTruthy();
    expect(screen.queryByRole('checkbox', { name: 'Select version 3' })).toBeNull();
    const deleteButton = screen.getByRole('button', { name: /Delete selected \(0\)/ });
    expect(deleteButton).toHaveProperty('disabled', true);

    fireEvent.click(screen.getByRole('checkbox', { name: 'Select all older versions' }));
    fireEvent.click(screen.getByRole('button', { name: /Delete selected \(2\)/ }));
    const confirm = await screen.findByRole('alertdialog');
    expect(within(confirm).getByText(/v1, v2 will be gone/)).toBeTruthy();
    fireEvent.click(within(confirm).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith(1002, [1, 2]));
  });

  it('asks to onboard the site first when there is no approved profile', () => {
    const queryClient = new QueryClient();
    render(<QueryClientProvider client={queryClient}><KnowledgePanel siteId={1002} timeZone="America/Los_Angeles" profile={undefined} /></QueryClientProvider>);
    expect(screen.getByText(/Onboard the site first/)).toBeTruthy();
  });
});
