"use client";
import { useActionState } from "react";
import { gmailAction } from "../app/actions";
import type { WorkspaceData } from "../lib/api";
export function Gmail({
  data,
  paused,
}: {
  data: WorkspaceData["gmail"];
  paused: boolean;
}) {
  const [message, act, pending] = useActionState(gmailAction, "");
  return (
    <section className="surface">
      <h2>Gmail job alerts</h2>
      <p>
        {data.state} {data.account}
      </p>
      <p>
        {data.last_success
          ? "Last successful sync · " +
            new Date(data.last_success).toLocaleString()
          : "No successful synchronization yet."}
      </p>
      {data.result && <p>Latest run · {data.result}</p>}
      {data.retry_at && (
        <p>Retry after {new Date(data.retry_at).toLocaleString()}</p>
      )}
      <dl>
        {Object.entries(data.counts || {}).map(([k, v]) => (
          <div key={k}>
            <dt>{k.replaceAll("_", " ")}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      {!data.enabled && (
        <p>Gmail requires the local Google client configuration.</p>
      )}
      {paused && <p>External reads are paused.</p>}
      <form action={act} className="vertical">
        <fieldset disabled={pending || !data.enabled}>
          <legend>Authorized sources</legend>
          <label>
            Sender addresses, comma separated
            <input
              name="senders"
              defaultValue={data.policy?.senders.join(", ")}
              required
            />
          </label>
          <label>
            Gmail label ID
            <input name="label" defaultValue={data.policy?.label} />
          </label>
          <label>
            Subject phrase
            <input name="subject" defaultValue={data.policy?.subject} />
          </label>
          <label>
            Lookback days
            <input
              type="number"
              min="1"
              max="7"
              name="days"
              defaultValue={data.policy?.days || 3}
            />
          </label>
          <label>
            Maximum initial messages
            <input
              type="number"
              min="1"
              max="25"
              name="limit"
              defaultValue={data.policy?.limit || 10}
            />
          </label>
          <button name="action" value="policy">
            Save filters · deterministic extraction
          </button>
        </fieldset>
      </form>
      <form action={act}>
        <button
          disabled={pending || paused || !data.enabled}
          name="action"
          value="connect"
        >
          {data.account || data.reconnect ? "Reconnect Gmail" : "Connect Gmail"}
        </button>
        <button
          disabled={
            pending ||
            paused ||
            !data.enabled ||
            !data.account ||
            !data.policy ||
            data.reconnect
          }
          name="action"
          value="sync"
        >
          {data.result === "pending" ? "Continue sync" : "Sync now"}
        </button>
        <button
          disabled={pending || !data.account}
          name="action"
          value="disconnect"
        >
          Disconnect Gmail
        </button>
      </form>
      <p role="status">{pending ? "Working…" : message}</p>
    </section>
  );
}
