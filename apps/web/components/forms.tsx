"use client";
import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import { signIn, signOut, saveJob } from "../app/actions";

function Submit({ label, waiting }: { label: string; waiting: string }) {
  const { pending } = useFormStatus();
  return (
    <button type="submit" disabled={pending} className="primary">
      {pending ? waiting : label}
      <span aria-hidden="true"> →</span>
    </button>
  );
}
function Feedback({ message }: { message: string }) {
  return (
    <p role="status" className="feedback">
      {message}
    </p>
  );
}
export function LoginForm() {
  const [state, action] = useActionState(signIn, "");
  return (
    <form action={action} className="stack">
      <label htmlFor="key">Owner access key</label>
      <input
        id="key"
        name="key"
        type="password"
        autoComplete="current-password"
        required
        maxLength={512}
      />
      <Submit label="Open workspace" waiting="Opening…" />
      <Feedback message={state} />
    </form>
  );
}
export function LogoutForm() {
  const [state, action, pending] = useActionState(signOut, "");
  return (
    <form action={action}>
      <button className="quiet" disabled={pending}>
        Sign out
      </button>
      <Feedback message={state} />
    </form>
  );
}
export function IntakeForm() {
  const [state, action] = useActionState(saveJob, "");
  return (
    <form action={action} className="stack">
      <label htmlFor="description">Job description</label>
      <textarea
        name="description"
        id="description"
        rows={5}
        maxLength={12000}
        required
        placeholder="Paste the role and its requirements"
      />
      <label htmlFor="source_url">
        Source URL <span className="optional">(optional)</span>
      </label>
      <input
        name="source_url"
        id="source_url"
        type="url"
        placeholder="https://"
        maxLength={2083}
      />
      <Submit label="Save job" waiting="Saving…" />
      <Feedback message={state} />
    </form>
  );
}
