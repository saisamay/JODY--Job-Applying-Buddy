"use server";
import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { ApiError, api } from "../lib/api";

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
  revalidatePath("/");
  return "";
}

export async function signOut(): Promise<string> {
  const jar = await cookies();
  const token = jar.get("jody_session")?.value;
  try {
    if (token) await api.logout(token);
  } catch (error) {
    return message(error);
  }
  jar.delete("jody_session");
  revalidatePath("/");
  return "";
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
      revalidatePath("/");
    }
    return message(error);
  }
  revalidatePath("/");
  return "Job saved.";
}
