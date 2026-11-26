"use client";
import { Gmail } from "./gmail";
import Link from "next/link";
import { useState } from "react";
import {
  Activity,
  ArrowUpRight,
  BriefcaseBusiness,
  ChevronDown,
  ChevronRight,
  CirclePause,
  FileText,
  FolderGit2,
  Inbox,
  Layers,
  LayoutGrid,
  ListChecks,
  LockKeyhole,
  Mail,
  Menu,
  PanelLeft,
  Plug,
  ScanLine,
  Search,
  Send,
  ShieldCheck,
  SlidersHorizontal,
  UserRound,
  X,
  Plus,
  type LucideIcon,
} from "lucide-react";
import { Brand, Mark } from "./identity";
import { LogoutForm, IntakeForm, PauseForm } from "./forms";
import {
  Analysis,
  PolicyForm,
  Credentials,
  LinksForm,
  Preferences,
  Resumes,
  type ProfileView,
} from "./workspace-tools";
import type {
  WorkspaceData,
  WorkspaceJob,
  ProjectSource,
  WorkspaceEntry,
} from "../lib/api";

const groups: { title: string; links: [string, string, LucideIcon][] }[] = [
  {
    title: "Workspace",
    links: [
      ["overview", "Overview", LayoutGrid],
      ["discovery", "Job discovery", Search],
      ["applications", "Applications", Layers],
      ["approvals", "Approval inbox", Inbox],
    ],
  },
  {
    title: "Career profile",
    links: [
      ["resumes", "Resume manager", FileText],
      ["projects", "Projects & portfolio", FolderGit2],
      ["analysis", "Match analysis", ScanLine],
    ],
  },
  {
    title: "Communication",
    links: [
      ["outreach", "Recruiter outreach", Send],
      ["gmail", "Gmail updates", Mail],
    ],
  },
  {
    title: "Controls",
    links: [
      ["integrations", "Integrations", Plug],
      ["settings", "Settings", SlidersHorizontal],
      ["audit", "Audit history", Activity],
    ],
  },
];
const descriptions: Record<string, string> = {
  overview:
    "Your opportunities, applications, and recent activity in one place.",
  discovery:
    "Collect openings, inspect their sources, and review company trust.",
  applications:
    "Track the latest applications through each stage of your search.",
  approvals: "Review actions that require your explicit authorization.",
  resumes: "Manage your private PDFs and role-specific versions.",
  projects: "Keep your portfolio and source-backed project evidence together.",
  analysis: "Inspect qualification fit and available PDF evaluations.",
  outreach: "Follow the status of recruiter conversations.",
  gmail: "Review classified email events linked to your job search.",
  integrations: "Manage the credentials behind your workspace connections.",
  settings: "Set review targets and inspect your source policies.",
  audit: "A chronological record of actions in your private workspace.",
};
const url = (view: string) =>
  view === "overview" ? "/workspace" : "/workspace?view=" + view;
const pretty = (s: string) => s.replace(/[_.]/g, " ");
const date = (s: string) =>
  new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(s));
function title(j: WorkspaceJob) {
  return (
    j.role ||
    j.description
      .split("\n")[0]
      .replace(/^(job )?title:\s*/i, "")
      .slice(0, 100)
  );
}
function sourceHost(url: string | null) {
  try {
    const u = new URL(url || "");
    return ["https:", "http:"].includes(u.protocol) ? u.hostname : "";
  } catch {
    return "";
  }
}
function PanelHead({
  icon: Icon,
  title,
  href,
}: {
  icon: LucideIcon;
  title: string;
  href?: string;
}) {
  return (
    <div className="panel-heading">
      <Icon size={19} />
      <h2>{title}</h2>
      {href && (
        <Link className="panel-link" href={href}>
          View all <ChevronRight size={14} />
        </Link>
      )}
    </div>
  );
}
function Jobs({
  jobs,
  compact = false,
}: {
  jobs: WorkspaceJob[];
  compact?: boolean;
}) {
  const [filter, setFilter] = useState("");
  const [trust, setTrust] = useState("all");
  const list = jobs.filter(
    (j) =>
      [j.description, j.role, j.company, j.location, j.source_url]
        .join(" ")
        .toLowerCase()
        .includes(filter.toLowerCase()) &&
      (trust === "all" || (trust === "scored") === (j.trust_score !== null)),
  );
  return (
    <section className="surface">
      <PanelHead
        icon={BriefcaseBusiness}
        title={compact ? "Recent opportunities" : "Saved opportunities"}
        href={compact ? url("discovery") : undefined}
      />
      {!compact && (
        <div className="filters">
          <label className="field-search">
            <Search size={17} />
            <input
              aria-label="Filter saved jobs"
              placeholder="Filter jobs or companies"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </label>
          <select
            aria-label="Trust assessment"
            value={trust}
            onChange={(e) => setTrust(e.target.value)}
          >
            <option value="all">All trust states</option>
            <option value="scored">Assessed</option>
            <option value="pending">Unassessed</option>
          </select>
        </div>
      )}
      {list.length ? (
        (compact ? list.slice(0, 4) : list).map((j, i) => (
          <details className="job-detail" key={j.id}>
            <summary>
              <span
                className={`company-icon ${["peach", "sage", "lilac", "sky"][i % 4]}`}
              >
                <BriefcaseBusiness size={19} />
              </span>
              <span className="job-name">
                <b>{title(j)}</b>
                <small>
                  {j.company || sourceHost(j.source_url) || "Manual entry"} ·{" "}
                  {date(j.created_at)}
                </small>
              </span>
              <ChevronDown size={16} />
            </summary>
            <div className="detail-body">
              <p>{j.description}</p>
              <div className="detail-tags">
                <span className="tag">
                  <ShieldCheck size={13} />
                  {j.trust_score === null
                    ? "Trust not assessed"
                    : `Trust score · ${j.trust_score}/100`}
                </span>
                <span className="tag">{pretty(j.status)}</span>
              </div>
              {j.gmail_platform && (
                <p>
                  Gmail alert · {j.gmail_platform} ·{" "}
                  {j.employment_type || "Employment type unspecified"} ·{" "}
                  {j.gmail_review ? "Needs review" : "Extracted from alert"}
                </p>
              )}
              {j.location && <p>{j.location}</p>}
              {sourceHost(j.source_url) && (
                <a
                  className="text-link"
                  href={j.source_url!}
                  target="_blank"
                  rel="noreferrer"
                >
                  View original source <ArrowUpRight size={14} />
                </a>
              )}
            </div>
          </details>
        ))
      ) : (
        <div className="empty">
          <Search />
          <h3>
            {jobs.length
              ? "No matching roles"
              : "Your opportunity list is empty"}
          </h3>
          <p>
            {jobs.length
              ? "Change your filters to see more roles."
              : "Save a job description to begin tracking it here."}
          </p>
          {compact && (
            <Link href={url("discovery")} className="text-link">
              Go to job discovery
            </Link>
          )}
        </div>
      )}
    </section>
  );
}
function Records({
  icon,
  title,
  items,
  empty,
  sample,
  humanize = false,
  children,
}: {
  icon: LucideIcon;
  title: string;
  items: WorkspaceEntry[];
  empty: string;
  sample?: string;
  humanize?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <section className="surface">
      <PanelHead icon={icon} title={title} />
      {items.length ? (
        <ul className="record-list">
          {items.map((r) => (
            <li key={r.id}>
              <div>
                <b>{humanize ? pretty(r.title) : r.title}</b>
                {r.detail && <p>{r.detail}</p>}
                <small>{date(r.created_at)}</small>
              </div>
              {r.status && <span className="tag">{pretty(r.status)}</span>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="empty">{empty}</p>
      )}
      {children}
      {sample && (
        <details className="sample-note">
          <summary>
            View example <span className="demo-tag">Fixture</span>
          </summary>
          <p>{sample}</p>
        </details>
      )}
    </section>
  );
}
function Board({ data }: { data: WorkspaceEntry[] }) {
  const columns = [
    ["Saved", ["discovered"]],
    ["Preparing", ["pending_approval", "tailoring"]],
    [
      "In progress",
      ["applied", "outreach_active", "shortlisted", "assessment", "interview"],
    ],
    ["Closed", ["offer", "rejected", "scam_blocked", "skipped"]],
  ] as const;
  return (
    <div className="board">
      {columns.map(([stage, statuses], i) => {
        const cards = data.filter((a) =>
          (statuses as readonly string[]).includes(a.status || ""),
        );
        return (
          <section key={stage}>
            <h2>
              <i className={`stage-dot s${i}`} />
              {stage}
              <small>{cards.length}</small>
            </h2>
            {cards.length ? (
              cards.map((a) => (
                <article key={a.id}>
                  <span className="tag">{pretty(a.status || "")}</span>
                  <h3>{a.title}</h3>
                  <p>
                    {pretty(a.detail || "")} · {date(a.created_at)}
                  </p>
                </article>
              ))
            ) : (
              <p className="empty-lane">No applications here</p>
            )}
          </section>
        );
      })}
    </div>
  );
}
function Overview({ data }: { data: WorkspaceData }) {
  return (
    <>
      <div className="metric-grid">
        {[
          [
            BriefcaseBusiness,
            "Saved opportunities",
            data.total_jobs,
            "discovery",
          ],
          [Layers, "Applications", data.total_applications, "applications"],
          [Inbox, "Awaiting approval", data.pending_approvals, "approvals"],
        ].map(([I, l, n, v], i) => {
          const Icon = I as LucideIcon;
          return (
            <Link className="metric" href={url(String(v))} key={String(v)}>
              <span className={`icon-tile ${["peach", "lilac", "sage"][i]}`}>
                <Icon size={20} />
              </span>
              <span>{String(l)}</span>
              <strong>{String(n).padStart(2, "0")}</strong>
              <ChevronRight size={16} />
            </Link>
          );
        })}
      </div>
      <div className="work-split wide-left">
        <Jobs jobs={data.jobs} compact />
        <section className="surface">
          <PanelHead
            icon={Activity}
            title="Recent activity"
            href={url("audit")}
          />
          <ol className="timeline">
            {data.audit.slice(0, 5).map((a) => (
              <li key={a.id}>
                <i />
                <div>
                  <b>{pretty(a.title)}</b>
                  <small>{date(a.created_at)}</small>
                </div>
              </li>
            ))}
          </ol>
          {!data.audit.length && (
            <p className="empty">No activity recorded yet.</p>
          )}
        </section>
      </div>
      <div className="profile-callout">
        <div className="callout-symbol">
          <Mark size={42} />
        </div>
        <div>
          <h2>Build your evidence library.</h2>
          <p>
            Keep your role-specific resumes ready for your next opportunity.
          </p>
        </div>
        <Link href={url("resumes")}>
          Resume manager <ChevronRight size={16} />
        </Link>
      </div>
    </>
  );
}
export function Dashboard({
  sources,
  view,
  data,
  profile,
  paused,
  locked,
  uploadLimitMiB,
  command,
}: {
  view: string;
  data: WorkspaceData;
  sources: ProjectSource[];
  profile: ProfileView;
  paused: boolean;
  locked: boolean;
  uploadLimitMiB: number;
  command: string;
}) {
  const [mobile, setMobile] = useState(false);
  const current =
    groups.flatMap((g) => g.links).find(([id]) => id === view) ??
    groups[0].links[0];
  const [id, label, Icon] = current;
  const navigation = (
    <>
      {groups.map((g) => (
        <div className="nav-group" key={g.title}>
          <span className="side-caption">{g.title}</span>
          {g.links.map(([key, text, Glyph]) => (
            <Link
              key={key}
              href={url(key)}
              onClick={() => setMobile(false)}
              aria-current={key === id ? "page" : undefined}
            >
              <Glyph size={17} />
              {text}
            </Link>
          ))}
        </div>
      ))}
    </>
  );
  return (
    <div className="shell">
      <aside className="sidebar">
        <Brand />
        <nav aria-label="Workspace navigation">{navigation}</nav>
        <div className="side-foot">
          <LockKeyhole size={15} /> Owner workspace
        </div>
      </aside>
      <div className="work-main">
        <header className="work-top">
          <button
            aria-expanded={mobile}
            className="work-menu"
            onClick={() => setMobile(!mobile)}
            aria-label="Workspace menu"
          >
            {mobile ? <X /> : <Menu />}
          </button>
          <span className="breadcrumb">
            <PanelLeft size={16} /> Workspace <ChevronRight size={13} />{" "}
            <b>{label}</b>
          </span>
          <span className="private-label">
            <LockKeyhole size={13} /> Private
          </span>
          <span className="avatar" aria-hidden="true">
            <UserRound size={16} />
          </span>
          <LogoutForm />
        </header>
        {mobile && (
          <nav
            className="mobile-drawer"
            aria-label="Mobile workspace navigation"
          >
            {navigation}
          </nav>
        )}
        <main id="main-content" className="work-body">
          <div className="work-intro">
            <span className="eyebrow">
              <Icon size={15} /> Private workspace
            </span>
            <h1>
              {id === "overview" ? "Workspace overview" : label}
              <em>.</em>
            </h1>
            <p>{descriptions[id]}</p>
          </div>
          {id === "overview" && <Overview data={data} />}
          {id === "discovery" && (
            <div className="work-split wide-left">
              <Jobs jobs={data.jobs} />
              <section className="surface">
                <PanelHead icon={Plus} title="Add a job" />
                <IntakeForm />
              </section>
            </div>
          )}
          {id === "applications" && <Board data={data.applications} />}
          {id === "approvals" && (
            <Records
              icon={Inbox}
              title="Approval requests"
              items={data.approvals}
              humanize
              empty="Your approval inbox is clear. External actions require a separate, explicit decision."
              sample="A recruiter email draft awaits review of its recipient, message and attachment. This example sends no email."
            />
          )}
          {id === "outreach" && (
            <Records
              icon={Send}
              title="Outreach log"
              items={data.outreach}
              empty="No recruiter outreach has been recorded. Delivery is unavailable in this release."
              sample="Queued · A role-specific introduction is ready for owner review."
            />
          )}
          {id === "gmail" && (
            <>
              <Gmail data={data.gmail} paused={paused} />
              <Records
                icon={Mail}
                title="Email updates"
                items={data.mail}
                humanize
                empty="No recruitment events recorded. Discovered openings appear in Job discovery."
                sample="Interview invitation · An employer has requested a first conversation."
              />
            </>
          )}
          {id === "resumes" && (
            <Resumes
              profile={profile}
              command={command}
              uploadLimitMiB={uploadLimitMiB}
            />
          )}
          {id === "projects" && (
            <div className="work-split">
              <div className="vertical">
                <Records
                  icon={FolderGit2}
                  title="GitHub projects"
                  items={data.projects}
                  empty="No indexed repositories yet. Saved profile links do not verify project claims."
                />
                <section className="surface">
                  <PanelHead icon={FileText} title="Imported sources" />
                  {sources.length ? (
                    <ul className="record-list">
                      {sources.map((s) => (
                        <li key={s.id}>
                          <div>
                            <b>{s.label}</b>
                            <small>
                              {s.kind === "github"
                                ? "GitHub document"
                                : "Portfolio snapshot"}
                            </small>
                            {sourceHost(s.reference) && (
                              <a
                                className="text-link"
                                target="_blank"
                                rel="noreferrer"
                                href={s.reference}
                              >
                                Open source <ArrowUpRight size={14} />
                              </a>
                            )}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="empty">
                      Imported GitHub documents and portfolio snapshots appear
                      here for review.
                    </p>
                  )}
                </section>
              </div>
              <LinksForm profile={profile} command={command} />
            </div>
          )}
          {id === "analysis" && <Analysis jobs={data.jobs} />}
          {id === "integrations" && (
            <div className="work-split">
              <section className="surface">
                <PanelHead icon={Plug} title="Integration status" />
                <Link href="/workspace?view=gmail">
                  Gmail · {data.gmail.state}
                </Link>
                {data.integration_cards
                  .filter((card) => card.provider !== "gmail")
                  .map((card) => (
                    <div className="connection" key={card.provider}>
                      <div>
                        <b>{card.label}</b>
                        <p className="muted">{card.instruction}</p>
                      </div>
                      <span className="tag">{card.state}</span>
                    </div>
                  ))}
              </section>
              {locked ? (
                <p className="surface">
                  External integrations are disabled for this private preview.
                </p>
              ) : (
                <Credentials stored={data.integrations} />
              )}
            </div>
          )}
          {id === "settings" && (
            <div className="work-split">
              <Preferences trust={data.trust_threshold} ats={data.ats_target} />
              <div className="vertical">
                <Records
                  icon={ListChecks}
                  title="Source allowlist"
                  items={data.allowlist}
                  empty="No external sources are allowlisted."
                >
                  <PolicyForm block={false} />
                </Records>
                <Records
                  icon={ShieldCheck}
                  title="Blocklist"
                  items={data.blocklist}
                  empty="No domains, companies, or addresses are blocked."
                >
                  <PolicyForm block />
                </Records>
              </div>
            </div>
          )}
          {id === "audit" && (
            <Records
              icon={Activity}
              title="Latest 100 events"
              items={data.audit}
              humanize
              empty="No audit events recorded."
            />
          )}
          <div className="pause-control">
            <CirclePause size={18} />
            {locked ? (
              <p role="status">
                External automation is locked for this preview. Background tasks
                are paused.
              </p>
            ) : (
              <PauseForm
                key={String(paused)}
                paused={paused}
                command={command}
              />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
