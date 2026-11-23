import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { randomUUID } from "node:crypto";
import { api, ApiError, candidateApi, workspaceApi } from "../../lib/api";
import { Dashboard } from "../../components/dashboard";
import { Brand } from "../../components/identity";
import { LogoutForm } from "../../components/forms";
export const dynamic = "force-dynamic";
export default async function Workspace({
  searchParams,
}: {
  searchParams: Promise<{ view?: string }>;
}) {
  const token = (await cookies()).get("jody_session")?.value;
  if (!token) redirect("/signin");
  const { view } = await searchParams;
  const result = await Promise.all([
    workspaceApi.read(token),
    candidateApi.read(token),
    api.gate(token),
    view === "projects"
      ? workspaceApi.projectSources(token)
      : Promise.resolve([]),
  ]).catch((e) => {
    if (e instanceof ApiError && e.status === 401) redirect("/signin");
    return null;
  });
  if (!result) {
    return (
      <main id="main-content" className="signin">
        <Brand />
        <div className="panel login">
          <h1>Workspace unavailable.</h1>
          <p role="alert">
            We couldn’t load your private data. Check the API connection and try
            again.
          </p>
          <a className="primary" href="/workspace">
            Try again
          </a>
          <LogoutForm />
        </div>
      </main>
    );
  }
  const [data, candidate, gate, sources] = result;
  return (
    <Dashboard
      view={view || "overview"}
      data={data}
      sources={sources}
      profile={{
        github: candidate.fields.github ?? "",
        portfolio: candidate.fields.portfolio ?? "",
        revision: candidate.revision,
        resumes: candidate.resumes,
      }}
      paused={gate.paused}
      command={randomUUID()}
    />
  );
}
