export function StatusPill({
  status
}: {
  status: "stopped" | "running" | "error" | "risk" | string;
}) {
  const labels: Record<string, string> = {
    stopped: "停止中",
    running: "稼働中",
    error: "エラー停止",
    error_stopped: "エラー停止",
    risk: "リスク制限停止",
    risk_stopped: "リスク制限停止"
  };
  return (
    <span className={`status-pill status-${status}`}>
      <i />
      {labels[status] ?? status}
    </span>
  );
}
