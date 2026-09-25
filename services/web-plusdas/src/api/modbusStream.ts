import { BASE_URL, client } from './client';
import { streamSse, type SseEvent } from './sse';
import type { ModbusLiveStreamRequest, ModbusSessionSummary } from '@/shared/types/modbusLiveStream';

const STREAM_PATH = '/modbus-live-stream-raw-registers/stream';
const SESSIONS_PATH = '/modbus-live-stream-raw-registers/sessions';

export const modbusStreamApi = {
  start: (request: ModbusLiveStreamRequest, onEvent: (evt: SseEvent) => void, signal: AbortSignal) =>
    streamSse(`${BASE_URL}${STREAM_PATH}`, { method: 'POST', body: request, signal }, onEvent),

  resume: (sessionId: string, onEvent: (evt: SseEvent) => void, signal: AbortSignal) =>
    streamSse(`${BASE_URL}${STREAM_PATH}/${sessionId}/resume`, { method: 'GET', signal }, onEvent),

  list: async (status?: 'active'): Promise<ModbusSessionSummary[]> => {
    const query = status ? `?status=${status}` : '';
    const data = await client.get<{ sessions: ModbusSessionSummary[] }>(`${SESSIONS_PATH}${query}`);
    return data.sessions;
  },

  stop: (sessionId: string) => client.action(`${STREAM_PATH}/${sessionId}/stop`, 'GET'),

  delete: (sessionId: string) => client.delete(`${STREAM_PATH}/${sessionId}`),

  deleteAll: () => client.delete(SESSIONS_PATH),
};
