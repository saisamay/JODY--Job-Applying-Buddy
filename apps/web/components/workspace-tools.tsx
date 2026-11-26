"use client";
import { useActionState, useState, useTransition } from "react";
import {
  FileText,
  ScanLine,
  LockKeyhole,
  Link2,
  SlidersHorizontal,
  KeyRound,
  ExternalLink,
  SearchCheck,
} from "lucide-react";
import {
  changePolicy,
  compareJob,
  editUpload,
  saveLinks,
  savePreferences,
  storeCredential,
  forgetCredential,
  uploadResume,
} from "../app/actions";
import type { Comparison, ResumeInfo, WorkspaceJob } from "../lib/api";

export type ProfileView = {
  revision: number;
  resumes: ResumeInfo[];
  github: string;
  portfolio: string;
};
export function ActionForm({
  action,
  children,
  label,
}: {
  action: (_: string, f: FormData) => Promise<string>;
  children: React.ReactNode;
  label: string;
}) {
  const [feedback, submit, pending] = useActionState(action, "");
  return (
    <form action={submit} className="stack" aria-busy={pending}>
      {children}
      <button className="primary" disabled={pending}>
        {pending ? "Saving…" : label}
      </button>
      <p role="status" className="feedback">
        {feedback}
      </p>
    </form>
  );
}
export function Resumes({
  uploadLimitMiB,
  profile,
  command,
}: {
  uploadLimitMiB: number;
  profile: ProfileView;
  command: string;
}) {
  const [selected, setSelected] = useState("");
  const file = profile.resumes.find((r) => r.id === selected);
  return (
    <div className="work-split">
      <section className="surface">
        <div className="panel-heading">
          <FileText />
          <h2>Resume library</h2>
        </div>
        {profile.resumes.length ? (
          profile.resumes.map((r) => (
            <button
              className="library-row"
              key={r.id}
              aria-expanded={selected === r.id}
              onClick={() => setSelected(selected === r.id ? "" : r.id)}
            >
              <FileText />
              <span>
                <b>{r.label}</b>
                <small>
                  {r.target_role || "General resume"} ·{" "}
                  {Math.ceil(r.byte_size / 1024)} KB
                </small>
              </span>
              <span>Preview</span>
            </button>
          ))
        ) : (
          <p className="empty">Upload a PDF to start your resume library.</p>
        )}
        {file && (
          <div className="pdf-preview">
            <iframe
              title="Private resume PDF preview"
              src={`/workspace/resumes/${selected}`}
            />
            <a
              className="text-link"
              target="_blank"
              rel="noreferrer"
              href={`/workspace/resumes/${selected}`}
            >
              Open PDF in a new tab <ExternalLink size={14} />
            </a>
            <details className="sample-note" key={file.id}>
              <summary>Edit resume details</summary>
              <ActionForm action={editUpload} label="Save resume details">
                <input type="hidden" name="id" value={file.id} />
                <input type="hidden" name="revision" value={profile.revision} />
                <label>
                  Display label
                  <input
                    name="label"
                    maxLength={160}
                    defaultValue={file.label}
                    required
                  />
                </label>
                <label>
                  Role label
                  <input
                    name="role"
                    maxLength={160}
                    defaultValue={file.target_role || ""}
                  />
                </label>
              </ActionForm>
            </details>
            <details className="sample-note">
              <summary>Remove this upload</summary>
              <ActionForm action={editUpload} label="Remove selected PDF">
                <input type="hidden" name="operation" value="remove" />
                <input type="hidden" name="id" value={file.id} />
                <input type="hidden" name="revision" value={profile.revision} />
                <label className="check-label">
                  <input type="checkbox" name="confirm" value="yes" required />
                  Remove this PDF from my resume library
                </label>
              </ActionForm>
            </details>
          </div>
        )}
      </section>
      <section className="surface">
        <div className="panel-heading">
          <LockKeyhole />
          <h2>Upload a resume</h2>
        </div>
        <ActionForm action={uploadResume} label="Upload PDF">
          <input type="hidden" name="command" value={command} />
          <input type="hidden" name="revision" value={profile.revision} />
          <label>
            Resume label
            <input
              name="label"
              placeholder="General resume"
              maxLength={160}
              required
            />
          </label>
          <label>
            Target role (optional)
            <input name="role" maxLength={160} />
          </label>
          <label>
            PDF file · up to {uploadLimitMiB} MiB
            <input
              type="file"
              name="file"
              onChange={(e) => {
                const input = e.currentTarget;
                input.setCustomValidity(
                  (input.files?.[0]?.size ?? 0) > uploadLimitMiB * 1048576
                    ? `Select a PDF up to ${uploadLimitMiB} MiB.`
                    : "",
                );
                input.reportValidity();
              }}
              accept="application/pdf,.pdf"
              required
            />
          </label>
        </ActionForm>
      </section>
    </div>
  );
}
export function LinksForm({
  profile,
  command,
}: {
  profile: ProfileView;
  command: string;
}) {
  return (
    <section className="surface">
      <div className="panel-heading">
        <Link2 />
        <h2>Profile links</h2>
      </div>
      <ActionForm action={saveLinks} label="Save links">
        <input type="hidden" name="revision" value={profile.revision} />
        <input type="hidden" name="command" value={command} />
        <label>
          GitHub profile
          <input
            name="github"
            type="url"
            defaultValue={profile.github}
            placeholder="https://github.com/username"
          />
        </label>
        <label>
          Portfolio URL
          <input
            name="portfolio"
            type="url"
            defaultValue={profile.portfolio}
            placeholder="https://"
          />
        </label>
      </ActionForm>
    </section>
  );
}
export function Preferences({ trust, ats }: { trust: number; ats: number }) {
  return (
    <section className="surface">
      <div className="panel-heading">
        <SlidersHorizontal />
        <h2>Review thresholds</h2>
      </div>
      <p className="muted">
        These targets guide reviews. External actions need separate
        authorization.
      </p>
      <ActionForm action={savePreferences} label="Save settings">
        <label>
          Company trust target
          <input
            name="trust"
            type="number"
            min="0"
            max="100"
            defaultValue={trust}
            required
          />
        </label>
        <label>
          ATS target
          <input
            name="ats"
            type="number"
            min="0"
            max="100"
            defaultValue={ats}
            required
          />
        </label>
      </ActionForm>
    </section>
  );
}
export function Credentials({ stored }: { stored: string[] }) {
  const [provider, setProvider] = useState("github");
  return (
    <section className="surface">
      <div className="panel-heading">
        <KeyRound />
        <h2>Private credentials</h2>
      </div>
      <p className="muted">
        Save a credential in the encrypted vault. Live sync and delivery require
        a supported connector.
      </p>
      <label>
        Provider
        <select value={provider} onChange={(e) => setProvider(e.target.value)}>
          {[
            ["github", "GitHub"],
            ["gmail", "Gmail (legacy vault entry)"],
            ["gemini", "Gemini"],
            ["groq", "Groq"],
            ["openrouter", "OpenRouter"],
            ["resume_git", "Resume Git"],
          ].map(([v, t]) => (
            <option key={v} value={v}>
              {t}
              {stored.includes(v) ? " · credential stored" : ""}
            </option>
          ))}
        </select>
      </label>
      <ActionForm
        key={provider}
        action={storeCredential}
        label={
          stored.includes(provider) ? "Replace credential" : "Store credential"
        }
      >
        <input type="hidden" name="provider" value={provider} />
        <label>
          Access credential
          <input
            type="password"
            name="credential"
            autoComplete="new-password"
            required
            maxLength={16384}
          />
        </label>
      </ActionForm>
      {stored.includes(provider) && (
        <ActionForm
          key={"remove-" + provider}
          action={forgetCredential}
          label="Remove stored credential"
        >
          <input type="hidden" name="provider" value={provider} />
          <label>
            <input type="checkbox" name="confirmed" required /> Remove this
            credential from my JODY vault
          </label>
        </ActionForm>
      )}
    </section>
  );
}
export function Analysis({ jobs }: { jobs: WorkspaceJob[] }) {
  const [id, setId] = useState(jobs[0]?.id || "");
  const [result, setResult] = useState<Comparison>();
  const [error, setError] = useState("");
  const [busy, start] = useTransition();
  return (
    <div className="work-split">
      <section className="surface">
        <div className="panel-heading">
          <SearchCheck />
          <h2>Qualification match</h2>
        </div>
        <p className="muted">
          Compare a saved description with reviewed candidate evidence.
        </p>
        <label>
          Saved opportunity
          <select
            value={id}
            disabled={!jobs.length || busy}
            onChange={(e) => {
              setId(e.target.value);
              setResult(undefined);
              setError("");
            }}
          >
            {!jobs.length && <option>No saved jobs</option>}
            {jobs.map((j) => (
              <option key={j.id} value={j.id}>
                {(j.role || j.description).slice(0, 80)}
              </option>
            ))}
          </select>
        </label>
        <button
          className="primary"
          disabled={!id || busy}
          onClick={() =>
            start(async () => {
              setError("");
              const r = await compareJob(id);
              setResult(r.result);
              setError(r.error || "");
            })
          }
        >
          {busy ? "Comparing evidence…" : "Compare qualifications"}
        </button>
        <p role="status">{error}</p>
        {result && (
          <div className="analysis-result" role="status">
            <span className="tag">{result.recommendation}</span>
            <h3>{result.qualification_estimate}/100</h3>
            <p>
              Internal qualification estimate · {result.confidence} confidence
            </p>
            {(
              [
                ["Matched", result.matched],
                ["Transferable", result.transferable],
                ["Missing required", result.missing_required],
                ["Preferred gaps", result.preferred_unmet],
                ["Eligibility blockers", result.eligibility_blockers],
              ] as const
            ).map(
              ([label, rows]) =>
                rows.length > 0 && (
                  <div key={label}>
                    <h4>{label}</h4>
                    {rows.map((r, i) => (
                      <div key={i}>
                        <p>{r.text}</p>
                        {r.evidence_id && (
                          <small>
                            {
                              result.evidence.find(
                                (f) => f.id === r.evidence_id,
                              )?.quote
                            }
                          </small>
                        )}
                      </div>
                    ))}
                  </div>
                ),
            )}
          </div>
        )}
      </section>
      <section className="surface">
        <div className="panel-heading">
          <ScanLine />
          <h2>ATS analysis</h2>
        </div>
        {jobs.find((j) => j.id === id)?.ats_score != null ? (
          <p>
            Recorded PDF score · {jobs.find((j) => j.id === id)?.ats_score}/100
          </p>
        ) : (
          <>
            <p className="empty">
              No PDF evaluation is available for this role.
            </p>
            <button disabled className="secondary">
              PDF scoring unavailable
            </button>
            <details className="sample-note">
              <summary>
                Preview evaluation <span className="demo-tag">Fixture</span>
              </summary>
              <p>
                Example PDF · 82/100. Section headings parsed successfully.
                Review the extracted text for missing dates before export.
              </p>
            </details>
          </>
        )}
      </section>
    </div>
  );
}
export function PolicyForm({ block }: { block: boolean }) {
  return (
    <details className="sample-note">
      <summary>Manage {block ? "blocklist" : "allowlist"}</summary>
      <ActionForm action={changePolicy} label="Apply policy">
        <label>
          Action
          <select name="operation">
            <option value="add">Add entry</option>
            <option value="remove">Remove matching entry</option>
          </select>
        </label>
        <label>
          Type
          <select name="kind">
            {(block
              ? ["domain", "company", "email"]
              : ["manual", "whatsapp", "linkedin_feed", "linkedin_post"]
            ).map((v) => (
              <option key={v} value={v}>
                {v.replace("_", " ")}
              </option>
            ))}
          </select>
        </label>
        <label>
          {block ? "Value" : "Source identifier"}
          <input name="value" required maxLength={250} />
        </label>
        {block && (
          <label>
            Reason
            <input name="reason" required maxLength={300} />
          </label>
        )}
      </ActionForm>
    </details>
  );
}
