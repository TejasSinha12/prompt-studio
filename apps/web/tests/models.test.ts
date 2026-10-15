import { describe, expect, it } from "vitest";
import { fit, recommend } from "@/lib/models";
import type { ModelInfo } from "@/lib/types";

const m = (name: string, gb: number): ModelInfo => ({ name, size_bytes: gb * 1024 ** 3, parameter_size: null, quantization: null, family: null, modified_at: null });
const MEM = 16 * 1024 ** 3;

describe("model fit heuristic", () => {
  it("classifies by size vs memory and handles unknowns", () => {
    expect(fit(m("a", 2), MEM).label).toBe("likely fits");
    expect(fit(m("b", 8), MEM).label).toBe("tight");
    expect(fit(m("c", 20), MEM).label).toBe("may not fit");
    expect(fit(m("d", 2), null).label).toBe("unknown");
  });

  it("recommends by preference among models that fit", () => {
    const models = [m("small", 2), m("mid", 4.5), m("big", 8), m("huge", 40)];
    expect(recommend(models, MEM, "speed")?.name).toBe("small");
    expect(recommend(models, MEM, "quality")?.name).toBe("big");
    expect(recommend(models, MEM, "balanced")?.name).toBe("mid");
    expect(recommend([m("huge", 40)], MEM, "speed")).toBeNull();
  });
});
