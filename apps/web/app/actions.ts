"use server";
import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { randomUUID } from "node:crypto";
import {
  ApiError,
  api,
  candidateApi,
  workspaceApi,
  gmailApi,
  policyApi,
  type Comparison,
} from "../lib/api";

function message(error: unknown) {
  return error instanceof ApiError
    ? error.message
    : "Request failed. Please try again.";
}

export async function signIn(
  previous: string,
  form: FormData,
): Promise<string> {
  try {
    const session = await api.login({ key: String(form.get("key") || "") });
    (await cookies()).set("jody_session", session.token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "strict",
      path: "/",
      maxAge: session.max_age,
    });
  } catch (error) {
    return message(error);
  }
  redirect("/workspace");
}

export async function signOut(): Promise<string> {
  const jar = await cookies();
  const token = jar.get("jody_session")?.value;
  try {
    if (token) await api.logout(token);
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 401))
      return message(error);
  }
  jar.delete("jody_session");
  redirect("/signin");
}

export async function saveJob(
  previous: string,
  form: FormData,
): Promise<string> {
  const token = (await cookies()).get("jody_session")?.value;
  if (!token) return "Sign in again to save this job.";
  try {
    await api.save(token, {
      description: String(form.get("description") || ""),
      source_url: String(form.get("source_url") || "").trim() || null,
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      (await cookies()).delete("jody_session");
      revalidatePath("/workspace");
    }
    return message(error);
  }
  revalidatePath("/workspace");
  return "Job saved.";
}

export async function changePause(
  previous: string,
  form: FormData,
): Promise<string> {
  const token = (await cookies()).get("jody_session")?.value;
  if (!token) return "Sign in to change the global pause.";
  const desired = form.get("paused");
  if (desired !== "true" && desired !== "false")
    return "Invalid pause setting.";
  try {
    await api.setGate(token, desired === "true", String(form.get("command")));
  } catch (error) {
    return message(error);
  }
  revalidatePath("/workspace");
  return "";
}

async function ownerToken() {
  const t = (await cookies()).get("jody_session")?.value;
  if (!t) throw new ApiError(401, "Sign in again to continue.");
  return t;
}
export async function uploadResume(_: string, form: FormData) {
  try {
    const token = await ownerToken();
    const pdf = form.get("file");
    const limit = process.env.VERCEL ? 4 : 5;
    if (!(pdf instanceof File) || !pdf.size || pdf.size > limit * 1048576)
      return `Select a PDF up to ${limit} MiB.`;
    await candidateApi.upload(
      token,
      pdf,
      String(form.get("label") || ""),
      String(form.get("role") || "") || null,
      Number(form.get("revision")),
      String(form.get("command")),
    );
  } catch (e) {
    return message(e);
  }
  revalidatePath("/workspace");
  return "Resume uploaded.";
}
export async function saveLinks(_: string, form: FormData) {
  try {
    await candidateApi.edit(
      await ownerToken(),
      {
        revision: Number(form.get("revision")),
        fields: {
          github: String(form.get("github") || "") || null,
          portfolio: String(form.get("portfolio") || "") || null,
        },
      },
      String(form.get("command")),
    );
  } catch (e) {
    return message(e);
  }
  revalidatePath("/workspace");
  return "Profile links saved.";
}
export async function savePreferences(_: string, form: FormData) {
  try {
    await workspaceApi.settings(
      await ownerToken(),
      Number(form.get("trust")),
      Number(form.get("ats")),
      randomUUID(),
    );
  } catch (e) {
    return message(e);
  }
  revalidatePath("/workspace");
  return "Settings saved.";
}
export async function storeCredential(_: string, form: FormData) {
  const provider = String(form.get("provider"));
  if (
    !["github", "gmail", "resume_git", "gemini", "groq", "openrouter"].includes(
      provider,
    )
  )
    return "Unknown provider.";
  try {
    await workspaceApi.credential(
      await ownerToken(),
      provider,
      String(form.get("credential") || ""),
      randomUUID(),
    );
  } catch (e) {
    return message(e);
  }
  revalidatePath("/workspace");
  return "Credential stored.";
}
export async function forgetCredential(_: string, form: FormData) {
  const provider = String(form.get("provider"));
  if (!form.get("confirmed")) return "Confirm removal first.";
  try {
    await workspaceApi.forgetCredential(
      await ownerToken(),
      provider,
      randomUUID(),
    );
  } catch (error) {
    return message(error);
  }
  revalidatePath("/workspace");
  return "Credential removed from JODY.";
}

export async function compareJob(
  id: string,
): Promise<{ result?: Comparison; error?: string }> {
  try {
    return { result: await workspaceApi.compare(await ownerToken(), id) };
  } catch (e) {
    return { error: message(e) };
  }
}
export async function changePolicy(_: string, form: FormData) {
  const kind = form.get("kind"),
    value = String(form.get("value") || ""),
    enabled = form.get("operation") === "add";
  try {
    const t = await ownerToken();
    if (kind === "company" || kind === "domain" || kind === "email")
      await policyApi.block(
        t,
        {
          kind,
          value,
          reason: String(form.get("reason") || "Owner policy"),
          enabled,
        },
        randomUUID(),
      );
    else if (
      kind === "whatsapp" ||
      kind === "linkedin_feed" ||
      kind === "linkedin_post" ||
      kind === "manual"
    )
      await policyApi.allow(
        t,
        { kind, identifier: value, enabled },
        randomUUID(),
      );
    else return "Choose a valid policy type.";
  } catch (e) {
    return message(e);
  }
  revalidatePath("/workspace");
  return enabled ? "Policy saved." : "Policy removed.";
}

export async function editUpload(_: string, form: FormData) {
  try {
    const t = await ownerToken(),
      id = String(form.get("id")),
      revision = Number(form.get("revision"));
    if (form.get("operation") === "remove") {
      if (form.get("confirm") !== "yes")
        return "Confirm removal of the selected upload.";
      await candidateApi.removeResume(t, id, revision, randomUUID());
    } else {
      await candidateApi.editResume(
        t,
        id,
        {
          label: String(form.get("label") || ""),
          target_role: String(form.get("role") || "") || null,
          revision,
        },
        randomUUID(),
      );
    }
  } catch (e) {
    return message(e);
  }
  revalidatePath("/workspace");
  return form.get("operation") === "remove"
    ? "Upload removed."
    : "Resume details saved.";
}

export async function gmailAction(_: string, form: FormData) {
  const action = form.get("action");
  let url = "";
  try {
    const t = await ownerToken();
    if (action === "connect") {
      url = (await gmailApi.connect(t)).url;
      (await cookies()).set("jody_gmail_return", t, {
        httpOnly: true,
        sameSite: "lax",
        secure: process.env.NODE_ENV === "production",
        path: "/gmail/callback",
        maxAge: 300,
      });
    } else if (action === "policy") {
      await gmailApi.policy(t, {
        senders: String(form.get("senders")).split(","),
        label: String(form.get("label") || ""),
        subject: String(form.get("subject") || ""),
        days: Number(form.get("days")),
        limit: Number(form.get("limit")),
        providers: [],
      });
    } else if (action === "sync" || action === "disconnect") {
      await gmailApi.action(t, action);
    } else return "Unknown action.";
  } catch (e) {
    return message(e);
  }
  if (url) redirect(url);
  revalidatePath("/workspace");
  return "Gmail settings and status refreshed.";
}
