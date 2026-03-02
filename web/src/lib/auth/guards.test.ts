import { describe, expect, it } from "vitest";
import { canAccessOps, canConfirmEvents, canUseDebugPanel, isReadOnly } from "./guards";

describe("guards", () => {
  it("grants admin/operator access to ops and debug actions", () => {
    expect(canAccessOps("admin")).toBe(true);
    expect(canAccessOps("operator")).toBe(true);
    expect(canConfirmEvents("admin")).toBe(true);
    expect(canUseDebugPanel("operator")).toBe(true);
  });

  it("keeps viewer read-only", () => {
    expect(canAccessOps("viewer")).toBe(false);
    expect(canConfirmEvents("viewer")).toBe(false);
    expect(isReadOnly("viewer")).toBe(true);
  });
});
