import { randomUUID } from "node:crypto";
import { cookies } from "next/headers";
import { ApiError, api, type SavedJob } from "../lib/api";
import {
  IntakeForm,
  LoginForm,
  LogoutForm,
  PauseForm,
} from "../components/forms";

export const dynamic = "force-dynamic";

function JobList({ jobs }: { jobs: SavedJob[] }) {
  return (
    <section className="panel" aria-labelledby="saved">
      <div className="section-title">
        <h2 id="saved">Saved jobs</h2>
        <span aria-label={`${jobs.length} shown`}>{jobs.length}</span>
      </div>
      {jobs.length ? (
        <ul className="jobs">
          {jobs.map((job) => (
            <li key={job.id}>
              <p className="whitespace-pre-wrap break-words">
                {job.description}
              </p>
              <div className="job-meta">
                <time dateTime={job.created_at}>
                  {new Intl.DateTimeFormat("en", {
                    dateStyle: "medium",
                    timeZone: "UTC",
                  }).format(new Date(job.created_at))}
                </time>
                {job.source_url && (
                  <a href={job.source_url} rel="noreferrer" target="_blank">
                    View source ↗
                  </a>
                )}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">Jobs you save will appear here.</p>
      )}
      {jobs.length === 100 && (
        <p className="muted">Showing the 100 most recent jobs.</p>
      )}
    </section>
  );
}
export default async function Home() {
  const token = (await cookies()).get("jody_session")?.value;
  const healthy = await api
    .ready()
    .then((result) => result.status === "ready")
    .catch(() => false);
  let jobs: SavedJob[] | undefined;
  let paused: boolean | undefined;
  let problem = "";
  if (token) {
    try {
      const [items, gate] = await Promise.all([
        api.jobs(token),
        api.gate(token),
      ]);
      jobs = items;
      paused = gate.paused;
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 401))
        problem = "Saved jobs are unavailable. Refresh after the API recovers.";
    }
  }
  return (
    <>
      <a className="skip" href="#workspace">
        Skip to workspace
      </a>
      <header>
        <div className="frame nav">
          <span className="brand">
            jody<span>.</span>
          </span>
          <div className="nav-right">
            <span role="status" className="health">
              <i data-ready={healthy} />
              {healthy ? "Services ready" : "Services unavailable"}
            </span>
            {(jobs || problem) && <LogoutForm />}
          </div>
        </div>
      </header>
      <main id="workspace">
        <div className="mast">
          <div className="frame">
            <h1>
              {jobs || problem ? "Your job pipeline" : "Your private workspace"}
              <span>.</span>
            </h1>
            <p>
              {jobs || problem
                ? "Save opportunities and keep their original details in one place."
                : "Sign in to collect job descriptions and keep track of their sources."}
            </p>
          </div>
        </div>
        <div className="frame workspace">
          {paused !== undefined && (
            <PauseForm paused={paused} command={randomUUID()} />
          )}
          {problem ? (
            <p role="alert" className="panel">
              {problem}
            </p>
          ) : jobs ? (
            <div className="columns">
              <section className="panel">
                <h2>Add a job</h2>
                <IntakeForm />
              </section>
              <JobList jobs={jobs} />
            </div>
          ) : (
            <section className="panel login">
              <h2>Owner sign-in</h2>
              <LoginForm />
            </section>
          )}
        </div>
      </main>
    </>
  );
}
