import type { StrategyConfig } from "@/types/trading";

export function validateStrategy(config: StrategyConfig): string | null {
  if (
    config.strategy_type === "moving_average_cross" &&
    config.short_period >= config.long_period
  ) {
    return "短期MAは長期MAより小さくしてください";
  }
  if (
    config.strategy_type === "rsi_reversal" &&
    config.oversold >= config.overbought
  ) {
    return "売られすぎラインは買われすぎラインより小さくしてください";
  }
  return null;
}
