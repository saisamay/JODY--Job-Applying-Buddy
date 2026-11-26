import { cookies } from "next/headers";
import { gmailApi } from "../../../lib/api";
export async function GET(request: Request) {
  const jar = await cookies();
  const t = jar.get("jody_gmail_return")?.value;
  jar.set("jody_gmail_return", "", { path: "/gmail/callback", maxAge: 0 });
  const params = new URL(request.url).searchParams;
  const headers = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
  };
  try {
    if (!t) throw Error();
    await gmailApi.callback(
      t,
      params.get("state") || "",
      params.get("code") || "",
    );
    return new Response(null, {
      status: 303,
      headers: { ...headers, Location: "/gmail/complete" },
    });
  } catch {
    return new Response(
      "Gmail authorization incomplete. Return to the workspace and reconnect.",
      { status: 409, headers },
    );
  }
}
