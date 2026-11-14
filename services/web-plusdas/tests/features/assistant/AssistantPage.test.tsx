// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { assistantApi, authApi, meApi } from '@/api';
import type {
  AskResponse, AssistantSite, Conversation, ConversationSummary, ConversationTurn,
} from '@/api/types/assistant';
import type { MeResponse } from '@/api/types/me';
import { AuthProvider } from '@/shared/contexts/auth';
import AssistantPage from '@/features/assistant/AssistantPage';

// The AI Assistant page: ask about one of the user's sites, see what the AI read and the tokens it
// used, rate the answer, and reopen a saved conversation.

const ENGINEER: MeResponse = { id: 3, email: 'ana@example.com', display_name: 'Ana', role: 'engineer' };
const SITES: AssistantSite[] = [
  { site_id: 1002, name: 'Powerflow 2BESS 1PV', description: null, capacity_kw: null, timezone: 'America/Los_Angeles' },
  { site_id: 1001, name: 'Mock site', description: null, capacity_kw: null, timezone: 'UTC' },
];
const TURN: ConversationTurn = {
  turn_id: 7, position: 0, question: 'BESS 1 state?', answer: 'BESS 1 is discharging at 250 kW.',
  stop_reason: 'end_turn', model: 'claude-test',
  tool_calls: [{ name: 'get_point_values', args: { point_names: ['bess1.active_power'] }, summary: '250', duration_ms: 12, is_error: false }],
  usage: { input_tokens: 1200, output_tokens: 80, cache_read_input_tokens: 9000, cache_creation_input_tokens: 0 },
  duration_ms: 3100, created_at: '2026-11-09T22:21:06Z', site_local_time: '2026-11-09T14:21:06-08:00',
  feedback: null, feedback_comment: null, feedback_at: null,
};
const CONVERSATION: Conversation = {
  conversation_id: 'c1', site_id: 1002, title: 'BESS 1 state?',
  created_at: TURN.created_at, updated_at: TURN.created_at, turns: [TURN],
};
const SUMMARY: ConversationSummary = {
  conversation_id: 'c1', site_id: 1002, title: 'BESS 1 state?', created_at: TURN.created_at, updated_at: TURN.created_at, turns: 1,
};
const ASKED: AskResponse = {
  conversation_id: 'c1', turn_id: 7, created_at: TURN.created_at, answer: TURN.answer, stop_reason: 'end_turn',
  iterations: 2, model: 'claude-test', tool_calls: TURN.tool_calls, usage: TURN.usage,
};

afterEach(() => vi.restoreAllMocks());

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname + location.search}</span>;
}

function renderAt(path: string, sites: AssistantSite[] = SITES) {
  vi.spyOn(authApi, 'me').mockResolvedValue(ENGINEER);
  vi.spyOn(meApi, 'listPreferences').mockResolvedValue([]);
  vi.spyOn(meApi, 'putPreference').mockImplementation(async (key, value) => ({ key, value: value as never, updated_at: '' }));
  vi.spyOn(assistantApi, 'sites').mockResolvedValue(sites);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes><Route path="/assistant" element={<><AssistantPage /><LocationProbe /></>} /></Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe('AssistantPage', () => {
  it('asks about the chosen site and shows the answer, what the AI read and its tokens', async () => {
    const conversations = vi.spyOn(assistantApi, 'conversations').mockResolvedValue([]);
    const ask = vi.spyOn(assistantApi, 'ask').mockResolvedValue(ASKED);
    vi.spyOn(assistantApi, 'conversation').mockResolvedValue(CONVERSATION);
    renderAt('/assistant');

    expect(await screen.findByText('No conversations yet.')).toBeTruthy();
    expect(conversations).toHaveBeenCalledWith(1002);
    fireEvent.change(screen.getByLabelText('Your question'), { target: { value: 'BESS 1 state?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
    // Sent: the box empties right away, and the button waits for the answer.
    expect((screen.getByLabelText('Your question') as HTMLTextAreaElement).value).toBe('');
    expect((await screen.findByRole('status')).textContent).toContain('Thinking');

    expect(await screen.findByText('BESS 1 is discharging at 250 kW.')).toBeTruthy();
    expect(ask).toHaveBeenCalledWith(1002, { question: 'BESS 1 state?', conversation_id: null });
    expect(screen.getByText('Tokens: 1,200 in · 80 out · 9,000 cached')).toBeTruthy();
    // Shown in the site's time zone.
    expect(screen.getByText('09 Nov, 14:21 PST')).toBeTruthy();
    expect(screen.getByText('What the AI read (1)')).toBeTruthy();
    expect(screen.getByText('get_point_values({"point_names":["bess1.active_power"]})')).toBeTruthy();

    // The next question continues the same conversation.
    fireEvent.change(screen.getByLabelText('Your question'), { target: { value: 'and BESS 2?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
    await waitFor(() => expect(ask).toHaveBeenLastCalledWith(1002, { question: 'and BESS 2?', conversation_id: 'c1' }));
  });

  it('puts the question back in the box when the ask fails', async () => {
    vi.spyOn(assistantApi, 'conversations').mockResolvedValue([]);
    vi.spyOn(assistantApi, 'ask').mockRejectedValue(new Error('The AI is not available'));
    renderAt('/assistant');

    const box = (await screen.findByLabelText('Your question')) as HTMLTextAreaElement;
    fireEvent.change(box, { target: { value: 'BESS 1 state?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));

    expect((await screen.findByRole('alert')).textContent).toContain('The AI is not available');
    expect(box.value).toBe('BESS 1 state?');
  });

  it('reopens a saved conversation and rates an answer with a comment', async () => {
    vi.spyOn(assistantApi, 'conversations').mockResolvedValue([
      { conversation_id: 'c1', site_id: 1002, title: 'BESS 1 state?', created_at: TURN.created_at, updated_at: TURN.created_at, turns: 1 },
    ]);
    const open = vi.spyOn(assistantApi, 'conversation').mockResolvedValue(CONVERSATION);
    const feedback = vi.spyOn(assistantApi, 'setFeedback').mockResolvedValue({ ...TURN, feedback: 'down' });
    renderAt('/assistant');

    fireEvent.click(await screen.findByRole('button', { name: /BESS 1 state\?.*1 question/ }));
    expect(await screen.findByText('BESS 1 is discharging at 250 kW.')).toBeTruthy();
    expect(open).toHaveBeenCalledWith('c1');

    fireEvent.click(screen.getByRole('button', { name: 'Not helpful' }));
    await waitFor(() => expect(feedback).toHaveBeenCalledWith('c1', 7, { rating: 'down', comment: null }));
  });

  it('saves a comment on a rated answer, and a second click on the same rating clears it', async () => {
    vi.spyOn(assistantApi, 'conversations').mockResolvedValue([
      { conversation_id: 'c1', site_id: 1002, title: 'BESS 1 state?', created_at: TURN.created_at, updated_at: TURN.created_at, turns: 1 },
    ]);
    vi.spyOn(assistantApi, 'conversation').mockResolvedValue({ ...CONVERSATION, turns: [{ ...TURN, feedback: 'down' }] });
    const feedback = vi.spyOn(assistantApi, 'setFeedback').mockResolvedValue(TURN);
    renderAt('/assistant');

    fireEvent.click(await screen.findByRole('button', { name: /^BESS 1 state\?/ }));
    const comment = await screen.findByLabelText('Feedback comment');
    fireEvent.change(comment, { target: { value: 'wrong BESS' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(feedback).toHaveBeenCalledWith('c1', 7, { rating: 'down', comment: 'wrong BESS' }));
    fireEvent.click(screen.getByRole('button', { name: 'Not helpful' }));
    await waitFor(() => expect(feedback).toHaveBeenLastCalledWith('c1', 7, { rating: null, comment: null }));
  });

  it('renames a conversation in place: Enter saves, Escape cancels', async () => {
    vi.spyOn(assistantApi, 'conversations').mockResolvedValue([SUMMARY]);
    const rename = vi.spyOn(assistantApi, 'rename').mockResolvedValue({ ...SUMMARY, title: 'BESS 1 check' });
    renderAt('/assistant');

    fireEvent.click(await screen.findByRole('button', { name: 'Rename BESS 1 state?' }));
    const box = screen.getByLabelText<HTMLInputElement>('Conversation name');
    expect(box.value).toBe('BESS 1 state?');
    fireEvent.change(box, { target: { value: 'ignored' } });
    fireEvent.keyDown(box, { key: 'Escape' });
    expect(screen.queryByLabelText('Conversation name')).toBeNull();
    expect(rename).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Rename BESS 1 state?' }));
    fireEvent.change(screen.getByLabelText('Conversation name'), { target: { value: '  BESS 1   check ' } });
    fireEvent.keyDown(screen.getByLabelText('Conversation name'), { key: 'Enter' });
    await waitFor(() => expect(rename).toHaveBeenCalledWith('c1', { title: 'BESS 1 check' }));
  });

  it('deletes a conversation only after confirming, and closes it if it was open', async () => {
    const conversations = vi.spyOn(assistantApi, 'conversations').mockResolvedValue([SUMMARY]);
    vi.spyOn(assistantApi, 'conversation').mockResolvedValue(CONVERSATION);
    const remove = vi.spyOn(assistantApi, 'remove').mockResolvedValue(undefined);
    renderAt('/assistant');

    fireEvent.click(await screen.findByRole('button', { name: /^BESS 1 state\?/ }));
    expect(await screen.findByText('BESS 1 is discharging at 250 kW.')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Delete BESS 1 state?' }));
    expect(await screen.findByText(/deleted permanently/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(remove).not.toHaveBeenCalled();

    conversations.mockResolvedValue([]);
    fireEvent.click(screen.getByRole('button', { name: 'Delete BESS 1 state?' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith('c1'));
    expect(await screen.findByText('No conversations yet.')).toBeTruthy();
    expect(screen.queryByText('BESS 1 is discharging at 250 kW.')).toBeNull();
  });

  it("asks the sidebar's question on arrival and drops it from the address", async () => {
    vi.spyOn(assistantApi, 'conversations').mockResolvedValue([]);
    vi.spyOn(assistantApi, 'conversation').mockResolvedValue(CONVERSATION);
    const ask = vi.spyOn(assistantApi, 'ask').mockResolvedValue(ASKED);
    renderAt('/assistant?q=BESS%201%20state%3F');

    await waitFor(() => expect(ask).toHaveBeenCalledTimes(1));
    expect(ask).toHaveBeenCalledWith(1002, { question: 'BESS 1 state?', conversation_id: null });
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/assistant'));
    expect(await screen.findByText('BESS 1 is discharging at 250 kW.')).toBeTruthy();
  });

  it('switches site and remembers it', async () => {
    const conversations = vi.spyOn(assistantApi, 'conversations').mockResolvedValue([]);
    renderAt('/assistant');
    const picker = await screen.findByLabelText('Site');
    fireEvent.change(picker, { target: { value: '1001' } });
    await waitFor(() => expect(conversations).toHaveBeenCalledWith(1001));
    expect(meApi.putPreference).toHaveBeenCalledWith('site-devices.last-site', '1001');
    expect(screen.getByLabelText('Your question').getAttribute('placeholder')).toBe('Ask about Mock site...');
  });

  it('says so when the user has no site to ask about', async () => {
    renderAt('/assistant', []);
    expect(await screen.findByText('You have no site to ask about.')).toBeTruthy();
    expect(screen.queryByLabelText('Your question')).toBeNull();
  });
});
