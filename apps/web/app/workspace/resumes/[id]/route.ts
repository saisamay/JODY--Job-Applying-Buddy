import { cookies } from "next/headers";
import { ApiError, candidateApi } from "../../../../lib/api";
export async function GET(
  _: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const token = (await cookies()).get("jody_session")?.value;
  if (!token)
    return new Response("Sign in to preview this resume.", { status: 401 });
  try {
    const pdf = await candidateApi.download(token, (await params).id);
    return new Response(pdf.body, {
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": 'inline; filename="resume.pdf"',
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "frame-ancestors 'self'",
      },
    });
  } catch (e) {
    return new Response("Resume unavailable.", {
      status: e instanceof ApiError ? e.status : 503,
      headers: { "Cache-Control": "no-store" },
    });
  }
}
