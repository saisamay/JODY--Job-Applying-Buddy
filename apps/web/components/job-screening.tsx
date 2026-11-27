"use client";
import { useActionState } from "react";
import { readJobSources, screenJobs, reviewTrust } from "../app/actions";
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
function TrustReview({ job }: { job: WorkspaceJob }) {
  const [result, action, pending] = useActionState(
    reviewTrust.bind(null, job.id, job.trust_id),
    "",
  );
  const report = job.trust_report;
  const stale = report && job.trust_stale;
  return (
    <section>
      <h4>Employer legitimacy</h4>
      {!report && (
        <p>
          {job.trust_score !== null
            ? "Historical score · current rubric pending"
            : "Current assessment pending"}
        </p>
      )}
      {report && (
        <>
          <p>
            {stale ? "Reassessment due" : report.state.replaceAll("_", " ")} ·{" "}
            {report.score}/100 · threshold {report.threshold}
          </p>
          <p>
            Evidence coverage {report.coverage}% · {report.confidence}{" "}
            confidence · {new Date(report.assessed_at).toLocaleDateString()} ·{" "}
            {report.version}
          </p>
          {report.review && <p>Owner decision · {report.review}</p>}
          <ul>
            {report.signals.map((s) => (
              <li key={s.code}>
                {s.kind} · {s.severity} · {s.explanation}{" "}
                <small>{s.reference}</small>
              </li>
            ))}
          </ul>
        </>
      )}
      <form className="vertical" action={action}>
        <button name="action" value="reassess" disabled={pending}>
          Reassess trust
        </button>
        {report && (
          <>
            <label>
              Independent official vacancy URL for approval
              <input type="url" name="reference" />
            </label>
            <label>
              Review evidence or reason
              <input name="note" maxLength={500} />
            </label>
            <div>
              <button
                name="action"
                value="approve"
                disabled={
                  pending ||
                  !!stale ||
                  ["high_risk", "confirmed_scam"].includes(report.state)
                }
              >
                Approve verified vacancy
              </button>{" "}
              <button name="action" value="skip" disabled={pending}>
                Skip opportunity
              </button>{" "}
              <button name="action" value="block" disabled={pending}>
                Block opportunity
              </button>{" "}
              <button name="action" value="confirmed_scam" disabled={pending}>
                Record confirmed scam
              </button>
            </div>
          </>
        )}
        <span role="status">{result}</span>
      </form>
    </section>
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
      <TrustReview job={job} />
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
