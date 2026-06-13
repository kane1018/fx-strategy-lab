import { describe, expect, it } from "vitest";
import { validateStrategy } from "./validation";

const base = {
  strategy_type: "moving_average_cross" as const,
  short_period: 10,
  long_period: 30,
  rsi_period: 14,
  oversold: 30,
  overbought: 70,
  breakout_period: 20
};

describe("validateStrategy", () => {
  it("accepts valid moving average periods", () => {
    expect(validateStrategy(base)).toBeNull();
  });

  it("rejects a short period that is not shorter", () => {
    expect(validateStrategy({ ...base, short_period: 30 })).toContain("短期MA");
  });

  it("rejects reversed RSI thresholds", () => {
    expect(
      validateStrategy({
        ...base,
        strategy_type: "rsi_reversal",
        oversold: 75,
        overbought: 70
      })
    ).toContain("売られすぎ");
  });
});
