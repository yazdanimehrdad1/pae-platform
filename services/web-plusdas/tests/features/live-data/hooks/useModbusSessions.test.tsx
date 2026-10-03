// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { modbusStreamApi } from '@/api';
import type { SseEvent } from '@/api/sse';
import type { ModbusLiveStreamRequest, ModbusSessionSummary } from '@/api/types/modbusStream';
import { AuthProvider } from '@/shared/contexts/auth';
import { useModbusSessions } from '@/features/live-data/hooks/useModbusSessions';

const request = {
  host: 'mock-modbus', port: 502, server_address: 1, kind: 'holding', start_address: 1, end_address: 2,
  modbus_address_mode: 'one_based', interval: 1, duration: 30, byte_order: 'big', word_order: 'msw_first',
  register_configs: {},
} as ModbusLiveStreamRequest;

const summary = (status: string): ModbusSessionSummary => ({
  session_id: 'session-1', status, host: 'mock-modbus', port: 502, server_address: 1, kind: 'holding',
  start_address: 1, end_address: 2, modbus_address_mode: 'one_based', interval: 1, duration: 30,
} as ModbusSessionSummary);

const poll = (n: number): SseEvent => ({
  event: 'poll',
  data: JSON.stringify({ timestamp: '2026-09-27T07:00:00Z', poll: n, registers: {} }),
});

// A stream the test drives: `emit` sends an event, and the stream stays open until aborted.
function fakeStream() {
  let emit: (evt: SseEvent) => void = () => {};
  const open = vi.fn((onEvent: (evt: SseEvent) => void, signal: AbortSignal) => {
    emit = onEvent;
    return new Promise<void>((_, reject) => {
      signal.addEventListener('abort', () => reject(Object.assign(new Error('aborted'), { name: 'AbortError' })));
    });
  });
  return { open, emit: (evt: SseEvent) => act(() => emit(evt)) };
}

const wrapper = ({ children }: { children: ReactNode }) => <AuthProvider>{children}</AuthProvider>;

describe('useModbusSessions stop and resume', () => {
  it('stops through the stop endpoint before closing the stream, then resumes and can stop again', async () => {
    let serverStatus = 'active';
    vi.spyOn(modbusStreamApi, 'list').mockImplementation(async () => [summary(serverStatus)]);
    const calls: string[] = [];
    const stop = vi.spyOn(modbusStreamApi, 'stop').mockImplementation(async () => {
      calls.push('stop');
      serverStatus = 'stopped';
    });
    const started = fakeStream();
    vi.spyOn(modbusStreamApi, 'start').mockImplementation((_request, onEvent, signal) => {
      signal.addEventListener('abort', () => calls.push('abort'));
      return started.open(onEvent, signal);
    });
    const resumed = fakeStream();
    const resume = vi.spyOn(modbusStreamApi, 'resume').mockImplementation((_id, onEvent, signal) => resumed.open(onEvent, signal));

    const { result } = renderHook(() => useModbusSessions(), { wrapper });
    const session = () => result.current.sessions.find(s => s.sessionId === 'session-1')!;

    // Start: `connected` names the session.
    let sessionIdPromise: Promise<string>;
    act(() => { sessionIdPromise = result.current.relaunchSlot(1, request, 'live'); });
    await started.emit({ event: 'connected', data: JSON.stringify({ session_id: 'session-1' }) });
    await act(async () => { await sessionIdPromise; });
    await started.emit(poll(1));
    expect(session().attachment).toBe('streaming');

    // Stop: the endpoint first (backend-ot cancels the polling), then the local stream closes.
    await act(async () => { await result.current.stopSession('session-1'); });
    expect(stop).toHaveBeenCalledWith('session-1');
    expect(calls).toEqual(['stop', 'abort']);
    expect(session().serverStatus).toBe('stopped');
    expect(session().attachment).toBe('idle');

    // Resume: `connected` marks it active again, so Stop is possible again.
    act(() => result.current.resumeSession('session-1'));
    expect(resume).toHaveBeenCalledWith('session-1', expect.any(Function), expect.any(AbortSignal));
    serverStatus = 'active';
    await resumed.emit({ event: 'connected', data: JSON.stringify({ session_id: 'session-1' }) });
    expect(session().serverStatus).toBe('active');
    expect(session().attachment).toBe('streaming');
    await resumed.emit(poll(1));
    await resumed.emit({ event: 'error', data: JSON.stringify({ error: 'Read timed out', poll: 1 }) });
    expect(session().error).toBe('Read timed out');

    await act(async () => { await result.current.stopSession('session-1'); });
    expect(stop).toHaveBeenCalledTimes(2);
    await waitFor(() => expect(session().serverStatus).toBe('stopped'));
  });
});
