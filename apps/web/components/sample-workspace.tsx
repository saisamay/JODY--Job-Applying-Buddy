"use client";
import { useState } from "react";
import {
  BriefcaseBusiness,
  Layers,
  LayoutGrid,
  ScanSearch,
  Search,
  Sparkles,
  FileText,
  MapPin,
  Shapes,
  Orbit,
  Triangle,
  PanelsTopLeft,
  ShieldCheck,
} from "lucide-react";
import { Mark } from "./identity";
export const examples = [
  {
    title: "Product Designer",
    company: "Forma Studio",
    place: "Remote",
    type: "Full-time",
    skill: "Design systems · Figma",
    score: 94,
    icon: Shapes,
    color: "peach",
    stage: "In review",
  },
  {
    title: "Machine Learning Engineer",
    company: "Orbit Labs",
    place: "Hybrid",
    type: "Full-time",
    skill: "Python · ML",
    score: 89,
    icon: Orbit,
    color: "lilac",
    stage: "Saved",
  },
  {
    title: "Backend Engineer",
    company: "Northline",
    place: "Remote",
    type: "Full-time",
    skill: "Python · APIs",
    score: 86,
    icon: Triangle,
    color: "sage",
    stage: "Saved",
  },
  {
    title: "Software Engineering Intern",
    company: "Forma Studio",
    place: "Onsite",
    type: "Internship",
    skill: "Web · TypeScript",
    score: 82,
    icon: PanelsTopLeft,
    color: "sky",
    stage: "Preparing",
  },
];
export function SampleWorkspace({
  query,
  tab,
  onTab,
}: {
  query: string;
  tab: string;
  onTab: (t: string) => void;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const words = query
    .toLowerCase()
    .replace(/work(?:ing)? from home|wfh/g, "remote")
    .replace(/machine learning|artificial intelligence|\bai\b/g, "ml")
    .replace(/developers?/g, "engineer")
    .split(/[^a-z0-9+#]+/)
    .filter(
      (w) =>
        w &&
        ![
          "jobs",
          "roles",
          "in",
          "for",
          "with",
          "a",
          "an",
          "the",
          "and",
        ].includes(w),
    );
  const rows = examples.filter((j) =>
    words.every((w) =>
      [j.title, j.company, j.place, j.skill, j.type]
        .join(" ")
        .toLowerCase()
        .includes(w),
    ),
  );
  const items = tab === "Overview" ? examples.slice(0, 3) : rows;
  return (
    <section
      id="preview"
      className="demo-window"
      aria-label="Interactive workspace preview"
    >
      <div className="window-bar">
        <div className="window-dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </div>
        <span>
          <PanelsTopLeft size={14} /> Workspace preview
        </span>
        <span className="demo-tag">Sample data</span>
      </div>
      <div className="demo-grid">
        <aside className="demo-side">
          <div className="demo-brand">
            <Mark size={23} /> Jody.
          </div>
          <span className="side-caption">Workspace</span>
          <div className="demo-tabs">
            {[
              [LayoutGrid, "Overview"],
              [ScanSearch, "Discovery"],
              [Layers, "Applications"],
            ].map(([I, label]) => {
              const Icon = I as typeof Layers;
              return (
                <button
                  key={String(label)}
                  aria-pressed={tab === label}
                  onClick={() => {
                    onTab(String(label));
                    setOpen(null);
                  }}
                >
                  <Icon size={16} />
                  {String(label)}
                </button>
              );
            })}
          </div>
          <div className="demo-private">
            <ShieldCheck size={16} /> Private workspace
          </div>
        </aside>
        <div className="demo-content">
          <div className="demo-title">
            <div>
              <p className="crumb">Workspace / {tab}</p>
              <h2>
                {tab === "Overview"
                  ? "Opportunity overview"
                  : tab === "Discovery"
                    ? "Job discovery"
                    : "Application board"}
              </h2>
            </div>
            <span className="icon-tile">
              <Sparkles size={20} />
            </span>
          </div>
          {tab === "Overview" && (
            <div className="demo-metrics">
              {[
                [BriefcaseBusiness, "Saved roles", "04"],
                [Sparkles, "Strong matches", "03"],
                [FileText, "In review", "01"],
              ].map(([I, label, value]) => {
                const Icon = I as typeof FileText;
                return (
                  <div key={String(label)}>
                    <span>
                      <Icon size={14} />
                      {String(label)}
                    </span>
                    <b>{String(value)}</b>
                  </div>
                );
              })}
            </div>
          )}
          {tab === "Applications" ? (
            <div className="mini-board">
              {["Saved", "Preparing", "In review"].map((stage) => (
                <div key={stage}>
                  <h3>{stage}</h3>
                  {examples
                    .filter((j) => j.stage === stage)
                    .map((j) => (
                      <p key={j.title}>
                        <b>{j.title}</b>
                        <small>{j.company}</small>
                      </p>
                    ))}
                </div>
              ))}
            </div>
          ) : (
            <>
              <div className="list-heading">
                <h3>
                  {tab === "Overview"
                    ? "Top opportunities"
                    : query
                      ? `Results for “${query}”`
                      : "All opportunities"}
                </h3>
                <span>{items.length} roles</span>
              </div>
              <div className="example-list">
                {items.map((j) => (
                  <div key={j.title}>
                    <button
                      className="example-row"
                      onClick={() => setOpen(open === j.title ? null : j.title)}
                      aria-expanded={open === j.title}
                    >
                      <span className={`company-icon ${j.color}`}>
                        <j.icon size={21} />
                      </span>
                      <span className="example-name">
                        <b>{j.title}</b>
                        <small>
                          {j.company}
                          <span> · {j.place}</span>
                        </small>
                      </span>
                      <span className="match">
                        <i />
                        {j.score}% match
                      </span>
                    </button>
                    {open === j.title && (
                      <div className="example-detail">
                        <MapPin size={15} />
                        {j.place} · {j.type}
                        <span>{j.skill}</span>
                      </div>
                    )}
                  </div>
                ))}
                {!items.length && (
                  <p className="empty-mini">
                    <Search size={20} />
                    No sample roles match this search. Try Python, design, or
                    remote.
                  </p>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
