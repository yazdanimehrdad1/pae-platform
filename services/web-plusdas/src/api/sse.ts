export interface SseEvent {
  event: string;
  data: string;
}

interface StreamSseInit {
  method: 'GET' | 'POST';
  body?: unknown;
  signal: AbortSignal;
}

function parseSseBlock(block: string): SseEvent {
  let event = 'message';
  const dataLines: string[] = [];

  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) event = line.slice('event:'.length).trim();
    else if (line.startsWith('data:')) dataLines.push(line.slice('data:'.length).trim());
  }

  return { event, data: dataLines.join('\n') };
}

export async function streamSse(url: string, init: StreamSseInit, onEvent: (evt: SseEvent) => void): Promise<void> {
  const response = await fetch(url, {
    method: init.method,
    headers: {
      Accept: 'text/event-stream',
      ...(init.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
    },
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    signal: init.signal,
  });

  if (!response.ok) {
    throw new Error(`Modbus stream request failed: ${response.status} ${response.statusText}`);
  }
  if (!response.body) {
    throw new Error('Modbus stream response has no body');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');

      let separatorIndex = buffer.indexOf('\n\n');
      while (separatorIndex !== -1) {
        const block = buffer.slice(0, separatorIndex);
        buffer = buffer.slice(separatorIndex + 2);
        if (block.trim()) onEvent(parseSseBlock(block));
        separatorIndex = buffer.indexOf('\n\n');
      }
    }
  } finally {
    reader.releaseLock();
  }
}
