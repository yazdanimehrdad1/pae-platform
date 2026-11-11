import { afterEach, describe, expect, it, vi } from 'vitest';
import { assistantApi } from '@/api/assistant';

function stubFetch(status = 200, body: unknown = {}) {
  const fetchMock = vi.fn().mockImplementation(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

const calls = (fetchMock: ReturnType<typeof stubFetch>) =>
  fetchMock.mock.calls.map(([url, init]) => ({ request: `${init.method ?? 'GET'} ${url}`, body: init.body ? JSON.parse(init.body) : undefined }));

afterEach(() => vi.unstubAllGlobals());

const BASE = '/intelli-gateway-api/v1';

describe('assistantApi (intelli-gateway, same origin)', () => {
  it('lists the sites the user may ask about and asks one', async () => {
    const fetchMock = stubFetch(200, {});
    await assistantApi.sites();
    await assistantApi.ask(1002, { question: 'BESS 1 state?', conversation_id: 'c1' });
    expect(calls(fetchMock)).toEqual([
      { request: `GET ${BASE}/sites`, body: undefined },
      { request: `POST ${BASE}/sites/1002/ask`, body: { question: 'BESS 1 state?', conversation_id: 'c1' } },
    ]);
  });

  it('reads the saved conversations and rates an answer (ids escaped)', async () => {
    const fetchMock = stubFetch(200, {});
    await assistantApi.conversations(1002);
    await assistantApi.conversations();
    await assistantApi.conversation('c/1');
    await assistantApi.setFeedback('c/1', 7, { rating: 'down', comment: 'wrong device' });
    expect(calls(fetchMock)).toEqual([
      { request: `GET ${BASE}/conversations?site_id=1002`, body: undefined },
      { request: `GET ${BASE}/conversations`, body: undefined },
      { request: `GET ${BASE}/conversations/c%2F1`, body: undefined },
      { request: `PUT ${BASE}/conversations/c%2F1/turns/7/feedback`, body: { rating: 'down', comment: 'wrong device' } },
    ]);
  });
});
