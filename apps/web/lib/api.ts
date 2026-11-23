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
): Promise<Response> {
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (body) headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(
      new URL(path, process.env.API_BASE_URL || "http://127.0.0.1:8000"),
      {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        cache: "no-store",
        signal: AbortSignal.timeout(10000),
      },
    );
  } catch {
    throw new ApiError(
      503,
      "The API is unreachable. Check the local services and try again.",
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
  ready: () => request<Schema["Ready"]>("/health/ready"),
  login: (body: Schema["Login"]) =>
    request<Schema["SessionToken"]>("/api/v1/session", "POST", undefined, body),
  logout: (token: string) => fetchApi("/api/v1/session", "DELETE", token),
  jobs: (token: string) => request<SavedJob[]>("/api/v1/jobs", "GET", token),
  save: (token: string, body: Schema["ManualJob"]) =>
    request<SavedJob>("/api/v1/jobs/manual", "POST", token, body),
};
