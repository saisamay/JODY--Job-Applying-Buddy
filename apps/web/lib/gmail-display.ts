export function gmailSource(domain: string) {
  return domain === "linkedin.com"
    ? "Gmail · LinkedIn Job Alerts"
    : "Gmail · " + domain;
}

export function runState(
  state: string,
  result: string | null | undefined,
  paused: boolean,
  syncing: boolean,
  finalizing: boolean,
) {
  if (paused && (syncing || result === "pending" || result === "retry"))
    return "Paused by owner";
  if (syncing) return finalizing ? "Finalizing" : "Processing messages";
  if (result === "pending")
    return finalizing ? "Ready to finalize" : "Waiting for continuation";
  return state;
}
