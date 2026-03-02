import { describe, expect, it } from "vitest";
import { parseSseText } from "./parseSse";

describe("parseSseText", () => {
  it("parses delta and done events", () => {
    const text = [
      'event: delta\ndata: {"text":"你好"}',
      "",
      'event: done\ndata: {"turn_id":"1","turn_index":2,"usage":{"prompt_tokens":1}}',
      "",
    ].join("\n");
    const events = parseSseText(text);
    expect(events).toHaveLength(2);
    expect(events[0].event).toBe("delta");
    expect(events[0].data.text).toBe("你好");
    expect(events[1].event).toBe("done");
    expect(events[1].data.turn_id).toBe("1");
  });
});
