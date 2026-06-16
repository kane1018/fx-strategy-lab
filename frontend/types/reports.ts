// Shapes returned by the read-only GET /api/reports endpoint (backend
// scripts.fx_eval_common.list_report_index). Mirrors docs §14 / §15.

export type ReportIndexItem = {
  status?: string;
  run_id: string;
  kind?: string | null;
  strategy?: string | null;
  timeframe?: string | null;
  cost_scenario?: string | null;
  verdict?: string | null;
  median_expectancy?: number | null;
  median_pf?: number | null;
  total_pnl?: number | null;
  max_drawdown_max?: number | null;
  created_at?: string | null;
  summary_file?: string | null;
  safety?: Record<string, boolean | null>;
  safety_complete?: boolean;
  safety_conflicts?: string[];
  read_only_confirmed?: boolean;
  warnings_count?: number;
  has_warnings?: boolean;
  has_error?: boolean;
  error?: string | null;
};

export type ReportsResponse = {
  items: ReportIndexItem[];
  count: number;
};
