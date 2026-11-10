import { afterEach, describe, expect, it, vi } from 'vitest';
import { knowledgeApi } from '@/api/knowledge';

function stubFetch(status = 200, body: unknown = {}) {
  const fetchMock = vi.fn().mockImplementation(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

const calls = (fetchMock: ReturnType<typeof stubFetch>) =>
  fetchMock.mock.calls.map(([url, init]) => ({ request: `${init.method ?? 'GET'} ${url}`, body: init.body ? JSON.parse(init.body) : undefined }));

afterEach(() => vi.unstubAllGlobals());

const BASE = '/intelli-gateway-api/v1/sites/1002/knowledge';

describe('knowledgeApi (intelli-gateway, same origin, admins only)', () => {
  it('reads the knowledge and its coverage', async () => {
    const fetchMock = stubFetch(200, {});
    await knowledgeApi.get(1002);
    await knowledgeApi.coverage(1002);
    expect(calls(fetchMock).map(call => call.request)).toEqual([`GET ${BASE}`, `GET ${BASE}/coverage`]);
  });

  it('writes and removes a point guide by device and point name (escaped), with the draft revision', async () => {
    const fetchMock = stubFetch(200, {});
    await knowledgeApi.putPointGuide(1002, 12, 'Fault/Code', { meaning: 'x', draft_revision: 3 });
    await knowledgeApi.deletePointGuide(1002, 12, 'Fault/Code', 4);
    expect(calls(fetchMock)).toEqual([
      { request: `PUT ${BASE}/point-guides/12/Fault%2FCode`, body: { meaning: 'x', draft_revision: 3 } },
      { request: `DELETE ${BASE}/point-guides/12/Fault%2FCode?draft_revision=4`, body: undefined },
    ]);
  });

  it('adds, edits and removes documents and device facts', async () => {
    const fetchMock = stubFetch(200, {});
    const document = { kind: 'procedure' as const, title: 'Reset', body: 'Press reset' };
    await knowledgeApi.createDocument(1002, document);
    await knowledgeApi.updateDocument(1002, 'abc', document);
    await knowledgeApi.deleteDocument(1002, 'abc');
    await knowledgeApi.putDeviceFacts(1002, 12, { ratings: [{ name: 'Power', value: 5, unit: 'MW' }] });
    await knowledgeApi.deleteDeviceFacts(1002, 12, 0);
    expect(calls(fetchMock).map(call => call.request)).toEqual([
      `POST ${BASE}/documents`,
      `PUT ${BASE}/documents/abc`,
      `DELETE ${BASE}/documents/abc`,
      `PUT ${BASE}/device-facts/12`,
      `DELETE ${BASE}/device-facts/12?draft_revision=0`,
    ]);
  });

  it('reverts, discards, publishes and restores', async () => {
    const fetchMock = stubFetch(200, {});
    await knowledgeApi.revert(1002, ['point:12:Fault'], 5);
    await knowledgeApi.discardDraft(1002);
    await knowledgeApi.publish(1002, 5);
    await knowledgeApi.versions(1002);
    await knowledgeApi.restore(1002, 1);
    expect(calls(fetchMock)).toEqual([
      { request: `POST ${BASE}/draft/revert`, body: { item_keys: ['point:12:Fault'], draft_revision: 5 } },
      { request: `DELETE ${BASE}/draft`, body: undefined },
      { request: `POST ${BASE}/publish`, body: { draft_revision: 5 } },
      { request: `GET ${BASE}/versions`, body: undefined },
      { request: `POST ${BASE}/versions/1/restore`, body: {} },
    ]);
  });
});
