import { describe, expect, it } from "vitest";
import { parseSseText } from "./parseSse";

describe("parseSseText", () => {
  it("parses primary, delta and done events", () => {
    const text = [
      'event: primary\ndata: {"text":"开场已生成"}',
      "",
      'event: delta\ndata: {"text":"你踏入了黎明原野。"}',
      "",
      'event: done\ndata: {"turn_id":"1","turn_index":2,"usage":{"prompt_tokens":1}}',
      "",
    ].join("\n");
    const events = parseSseText(text);
    expect(events).toHaveLength(3);
    expect(events[0].event).toBe("primary");
    expect(events[0].data.text).toBe("开场已生成");
    expect(events[1].event).toBe("delta");
    expect(events[1].data.text).toBe("你踏入了黎明原野。");
    expect(events[2].event).toBe("done");
    expect(events[2].data.turn_id).toBe("1");
  });
});
