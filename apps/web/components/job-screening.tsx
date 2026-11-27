"use client";
import { useActionState } from "react";
import { readJobSources, screenJobs } from "../app/actions";
import type { WorkspaceJob } from "../lib/api";
export const screenLabels: Record<string, string> = {
  eligible: "Eligible for further evaluation",
  needs_review: "Needs review",
  ineligible: "Ineligible",
  outside_preferences: "Outside preferences",
  expired_or_closed: "Expired or closed",
  blocklisted: "Blocklisted",
  pending: "Awaiting evaluation",
  legacy: "Historical · needs review",
  duplicate: "Possible duplicate",
};
export function screenKey(j: WorkspaceJob) {
  return j.screening?.decision ?? (j.canonical ? "pending" : "legacy");
}

export function BatchEvaluation() {
  const [result, action, pending] = useActionState(async () => screenJobs(), {
    message: "",
  });
  return (
    <form action={action}>
      <button className="text-link" disabled={pending}>
        Evaluate pending jobs (up to 25)
      </button>
      <span role="status">{result.message}</span>
    </form>
  );
}
export function JobScreening({ job }: { job: WorkspaceJob }) {
  const [result, action, busy] = useActionState(
    async () => screenJobs(job.id, !job.canonical),
    { message: "" },
  );
  const [source, read, loading] = useActionState(
    async () => readJobSources(job.id),
    { message: "" },
  );
  const screen = ("screen" in result && result.screen) || job.screening;
  return (
    <section className="job-screening">
      <h3>{screenLabels[screen?.decision ?? screenKey(job)]}</h3>
      {screen && (
        <>
          <p>
            Mandatory criteria · {screen.mandatory.replaceAll("_", " ")}.
            Preferences · {screen.preference}.
          </p>
          {screen.inferred_roles.length > 0 && (
            <p>Inferred roles · {screen.inferred_roles.join(", ")}</p>
          )}
          {screen.reasons.length > 0 && (
            <ul>
              {screen.reasons.map((r, i) => (
                <li key={i}>
                  {r.explanation} <q>{r.evidence}</q>
                </li>
              ))}
            </ul>
          )}
          {screen.missing.length > 0 && (
            <p>Missing · {screen.missing.join(", ").replaceAll("_", " ")}</p>
          )}
        </>
      )}
      {job.canonical && (
        <dl>
          {Object.entries(job.canonical)
            .filter(
              ([k, v]) =>
                typeof v === "string" &&
                !["description", "observed_path"].includes(k),
            )
            .map(([k, v]) => (
              <div key={k}>
                <dt>{k.replaceAll("_", " ")}</dt>
                <dd>{String(v)}</dd>
              </div>
            ))}
        </dl>
      )}
      {job.possible_duplicates.length > 0 && (
        <p>
          Possible duplicate · {job.possible_duplicates.length} similar
          record(s) for review.
        </p>
      )}
      <form action={action}>
        <button className="text-link" disabled={busy}>
          {job.canonical ? "Evaluate this job" : "Review historical facts"}
        </button>
        <span role="status">{result.message}</span>
      </form>
      <form action={read}>
        <button className="text-link" disabled={loading}>
          View source evidence ({job.sightings})
        </button>
        <span role="status">{source.message}</span>
      </form>
      {"sources" in source &&
        source.sources?.map((s, i) => (
          <details key={i}>
            <summary>
              {s.source} · {s.identifier} ·{" "}
              {new Date(s.created_at).toLocaleDateString()}
            </summary>
            <pre>
              {s.facts
                ? JSON.stringify(s.facts, null, 2)
                : "Historical sighting; original intake payload unavailable."}
            </pre>
          </details>
        ))}
    </section>
  );
}
