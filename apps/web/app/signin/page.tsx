import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { LockKeyhole } from "lucide-react";
import { Brand } from "../../components/identity";
import { LoginForm } from "../../components/forms";
import { api } from "../../lib/api";

export default async function SignIn() {
  const token = (await cookies()).get("jody_session")?.value;
  if (
    token &&
    (await api
      .gate(token)
      .then(() => true)
      .catch(() => false))
  )
    redirect("/workspace");
  const ready = await api
    .ready()
    .then((r) => r.status === "ready")
    .catch(() => false);
  return (
    <main id="main-content" className="signin">
      <div className="signin-brand">
        <Brand />
      </div>
      <section className="panel login">
        <div className="feature-icon">
          <LockKeyhole />
        </div>
        <h1>
          Open your workspace<span>.</span>
        </h1>
        <p className="muted">Use your private owner key to sign in.</p>
        <LoginForm />
        <div className="system-note">
          <i className={ready ? "dot" : "dot warn"} />
          {ready ? "Services ready" : "Services unavailable"}
        </div>
      </section>
      <Link href="/">Back to JODY</Link>
    </main>
  );
}
