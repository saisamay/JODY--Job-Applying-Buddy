import type { components } from "../../../packages/shared/api";

type Schema = components["schemas"];
export type SavedJob = Schema["Job"];
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function fetchApi(
  path: string,
  method = "GET",
  token?: string,
  body?: unknown,
  key?: string,
  metadata?: Record<string, string>,
): Promise<Response> {
  const origin = process.env.API_BASE_URL;
  if (process.env.VERCEL && (!origin || !/^https:\/\//.test(origin))) {
    throw new ApiError(503, "Configure the HTTPS preview API.");
  }
  const headers = new Headers(metadata);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (key) headers.set("Idempotency-Key", key);
  if (body)
    headers.set(
      "Content-Type",
      body instanceof Blob ? "application/pdf" : "application/json",
    );
  let response: Response;
  try {
    response = await fetch(new URL(path, origin || "http://127.0.0.1:8000"), {
      method,
      headers,
      body:
        body instanceof Blob ? body : body ? JSON.stringify(body) : undefined,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(
        process.env.VERCEL
          ? 90_000
          : path.endsWith("/compare")
            ? 600_000
            : 10_000,
      ),
    });
  } catch {
    throw new ApiError(
      503,
      "The API is unavailable or waking up. Try again shortly.",
    );
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      typeof error.detail === "string"
        ? error.detail
        : "Service temporarily unavailable.",
    );
  }
  return response;
}

async function request<T>(...args: Parameters<typeof fetchApi>): Promise<T> {
  return (await fetchApi(...args)).json();
}

export const api = {
  gate: (token: string) =>
    request<Schema["GateState"]>("/api/v1/system/kill-switch", "GET", token),
  setGate: (token: string, paused: boolean, key: string) =>
    request<Schema["Pause"]>(
      "/api/v1/system/kill-switch",
      "POST",
      token,
      { paused },
      key,
    ),
  ready: () => request<Schema["Ready"]>("/health/ready"),
  login: (body: Schema["Login"]) =>
    request<Schema["SessionToken"]>("/api/v1/session", "POST", undefined, body),
  logout: (token: string) => fetchApi("/api/v1/session", "DELETE", token),
  jobs: (token: string) => request<SavedJob[]>("/api/v1/jobs", "GET", token),
  save: (token: string, body: Schema["ManualJob"]) =>
    request<SavedJob>("/api/v1/jobs/manual", "POST", token, body),
};

// Server-side client for the onboarding UI. Keep bearer tokens in the server session.
const candidatePath = "/api/v1/candidate";
export const candidateApi = {
  read: (token: string) =>
    request<Schema["Candidate"]>(candidatePath, "GET", token),
  edit: (token: string, body: Schema["Edit"], key: string) =>
    request<Schema["Version"]>(candidatePath, "PATCH", token, body, key),
  suggest: (token: string, body: Schema["Suggest"], key: string) =>
    request<Schema["Version"]>(
      candidatePath + "/suggestions",
      "PATCH",
      token,
      body,
      key,
    ),
  verify: (token: string, body: Schema["Review"], key: string) =>
    request<Schema["Version"]>(
      candidatePath + "/review",
      "POST",
      token,
      body,
      key,
    ),
  advance: (token: string, body: Schema["Advance"], key: string) =>
    request<Schema["Version"]>(
      candidatePath + "/onboarding",
      "POST",
      token,
      body,
      key,
    ),
  permissions: (
    token: string,
    body: Partial<Schema["Permissions"]>,
    key: string,
  ) =>
    request<Partial<Schema["Permissions"]>>(
      "/api/v1/profile/settings",
      "PATCH",
      token,
      body,
      key,
    ),
  preview: (token: string, body: Schema["PreviewRequest"]) =>
    request<Schema["Preview"]>(
      candidatePath + "/application-preview",
      "POST",
      token,
      body,
    ),
  upload: (
    token: string,
    pdf: Blob,
    label: string,
    role: string | null,
    revision: number,
    key: string,
  ) => {
    const metadata: Record<string, string> = {
      "X-Resume-Label": encodeURIComponent(label),
    };
    if (role) metadata["X-Resume-Role"] = encodeURIComponent(role);
    return request<Schema["Uploaded"]>(
      candidatePath + "/resumes?revision=" + revision,
      "POST",
      token,
      pdf,
      key,
      metadata,
    );
  },
  download: (token: string, id: string) =>
    fetchApi(
      candidatePath + "/resumes/" + encodeURIComponent(id),
      "GET",
      token,
    ),
  editResume: (
    token: string,
    id: string,
    body: Schema["ResumeEdit"],
    key: string,
  ) =>
    request<Schema["Version"]>(
      candidatePath + "/resumes/" + encodeURIComponent(id),
      "PATCH",
      token,
      body,
      key,
    ),
  removeResume: (token: string, id: string, revision: number, key: string) =>
    request<Schema["Version"]>(
      candidatePath +
        "/resumes/" +
        encodeURIComponent(id) +
        "?revision=" +
        revision,
      "DELETE",
      token,
      undefined,
      key,
    ),
};

export type ProjectSource = Pick<
  Schema["SourceInfo"],
  "id" | "label" | "reference" | "kind"
>;
export const workspaceApi = {
  projectSources: async (token: string): Promise<ProjectSource[]> => {
    const profile = await request<Schema["CareerProfile"]>(
      "/api/v1/career/profile",
      "GET",
      token,
    );
    return profile.sources
      .filter((s) => ["github", "portfolio", "portfolio_html"].includes(s.kind))
      .map(({ id, label, reference, kind }) => ({
        id,
        label,
        reference,
        kind,
      }));
  },
  read: (token: string) =>
    request<Schema["Workspace"]>("/api/v1/workspace", "GET", token),
  compare: (token: string, id: string) =>
    request<Schema["Comparison"]>(
      "/api/v1/career/jobs/" + encodeURIComponent(id) + "/compare",
      "POST",
      token,
    ),
  settings: (token: string, trust: number, ats: number, key: string) =>
    request(
      "/api/v1/profile/settings",
      "PATCH",
      token,
      { min_trust_score_auto_apply: trust, min_ats_score_threshold: ats },
      key,
    ),
  forgetCredential: (token: string, provider: string, key: string) =>
    request(
      "/api/v1/integrations/" + encodeURIComponent(provider),
      "DELETE",
      token,
      undefined,
      key,
    ),
  credential: (token: string, provider: string, value: string, key: string) =>
    request(
      "/api/v1/integrations/" + encodeURIComponent(provider),
      "PUT",
      token,
      { credential: value },
      key,
    ),
};
export type WorkspaceData = Schema["Workspace"];
export type WorkspaceJob = Schema["JobView"];
export type WorkspaceEntry = Schema["Entry"];
export type ResumeInfo = Schema["ResumeInfo"];
export type Comparison = Schema["Comparison"];
export const policyApi = {
  allow: (t: string, body: Schema["SourcePolicy"], k: string) =>
    request("/api/v1/workspace/source-policy", "PUT", t, body, k),
  block: (t: string, body: Schema["BlockPolicy"], k: string) =>
    request("/api/v1/workspace/block-policy", "PUT", t, body, k),
};
