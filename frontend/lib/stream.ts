import type { StreamEvent } from './types';

export async function readStream(response: Response, onEvent: (event: StreamEvent) => void): Promise<void> {
  if (!response.body) throw new Error('The answer stream is unavailable');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let completed = false;
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    let boundary = buffer.indexOf('\n\n');
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const type = block.split('\n').find(line => line.startsWith('event: '))?.slice(7);
      const data = block.split('\n').find(line => line.startsWith('data: '))?.slice(6);
      if (type && data) {
        const event = { type, data: JSON.parse(data) } as StreamEvent;
        onEvent(event);
        if (event.type === 'final' || event.type === 'error') completed = true;
      }
      boundary = buffer.indexOf('\n\n');
    }
    if (done) break;
  }
  if (!completed) throw new Error('The answer stream ended before completion');
}
