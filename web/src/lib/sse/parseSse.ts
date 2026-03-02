export type ParsedSseEvent = {
  event: string;
  data: Record<string, unknown>;
};

function parseBlock(block: string): ParsedSseEvent | null {
  const lines = block
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) return null;
  let eventName = "message";
  let data = "";
  for (const line of lines) {
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      data += line.slice("data:".length).trim();
    }
  }
  if (!data) return { event: eventName, data: {} };
  try {
    return { event: eventName, data: JSON.parse(data) as Record<string, unknown> };
  } catch {
    return { event: eventName, data: { raw: data } };
  }
}

export function parseSseText(text: string): ParsedSseEvent[] {
  return text
    .split(/\r?\n\r?\n/)
    .map(parseBlock)
    .filter((event): event is ParsedSseEvent => Boolean(event));
}

export async function parseSseStream(
  response: Response,
  onEvent: (event: ParsedSseEvent) => void,
): Promise<void> {
  if (!response.body) {
    throw new Error("SSE response missing body");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split(/\r?\n\r?\n/);
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const event = parseBlock(part);
      if (event) onEvent(event);
    }
  }
  const tail = buffer.trim();
  if (tail) {
    const finalEvent = parseBlock(tail);
    if (finalEvent) onEvent(finalEvent);
  }
}
