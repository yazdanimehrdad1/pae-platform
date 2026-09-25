import { describe, expect, it, vi } from 'vitest';
import { client, getErrorMessage } from './client';

function stubFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(typeof body === 'string' ? body : JSON.stringify(body), {
      status,
      statusText: status === 200 ? 'OK' : 'Error',
      headers: { 'Content-Type': 'application/json' },
    }),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('client', () => {
  it('calls the API on the same origin under /api, uncached', async () => {
    const fetchMock = stubFetch(200, [{ site_id: 1 }]);

    await expect(client.get('/sites')).resolves.toEqual([{ site_id: 1 }]);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/sites');
    expect(init.cache).toBe('no-store');
  });

  it('sends JSON bodies for writes', async () => {
    const fetchMock = stubFetch(200, { site_id: 1 });

    await client.post('/sites', { name: 'Alpha' });

    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe('POST');
    expect(init.body).toBe('{"name":"Alpha"}');
    expect(init.headers['Content-Type']).toBe('application/json');
  });

  it('throws the FastAPI error body on a non-2xx response', async () => {
    stubFetch(404, { detail: 'Site 9 not found' });

    const error = await client.get('/sites/9').catch((caught: unknown) => caught);

    expect(error).toEqual({ detail: 'Site 9 not found' });
    expect(getErrorMessage(error)).toBe('Site 9 not found');
  });

  it('throws a code/message fallback when the error body is not JSON', async () => {
    stubFetch(502, '<html>Bad Gateway</html>');

    await expect(client.get('/sites')).rejects.toEqual({ code: '502', message: 'Error' });
  });
});

describe('getErrorMessage', () => {
  it('reads a structured detail message', () => {
    expect(getErrorMessage({ detail: { error: 'ConfirmationRequired', message: 'Set confirm=true' } }))
      .toBe('Set confirm=true');
  });

  it('falls back when the error has no usable message', () => {
    expect(getErrorMessage({ something: 'else' }, 'Save failed')).toBe('Save failed');
  });
});
