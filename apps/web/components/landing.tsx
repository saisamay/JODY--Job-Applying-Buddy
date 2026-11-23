"use client";
import { useState } from "react";
import {
  ArrowUpRight,
  Search,
  Sparkles,
  ScanSearch,
  Fingerprint,
  Send,
  ShieldCheck,
  Menu,
  X,
  LockKeyhole,
  Layers,
  ListChecks,
  UserRound,
} from "lucide-react";
import { Brand, Mark } from "./identity";
import { Terrain } from "./terrain";
import { SampleWorkspace } from "./sample-workspace";

const features = [
  {
    icon: ScanSearch,
    title: "Find opportunities worth your time.",
    text: "Keep job descriptions and their sources together. Review trust signals and flag suspicious opportunities.",
  },
  {
    icon: Fingerprint,
    title: "Match on real experience.",
    text: "Compare a role with verified skills, resume versions, and evidence from your projects and portfolio.",
  },
  {
    icon: Send,
    title: "Prepare a thoughtful application.",
    text: "Bring tailored drafts and recruiter outreach into one review workflow. You decide what leaves your workspace.",
  },
];
export function Landing() {
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState("Overview");
  const [menu, setMenu] = useState(false);
  function search(value: string) {
    setInput(value);
    setQuery(value.trim());
    setTab("Discovery");
    document.getElementById("preview")?.scrollIntoView({ block: "start" });
  }
  const nav = (
    <>
      <a href="#how" onClick={() => setMenu(false)}>
        How it works
      </a>
      <a href="#features" onClick={() => setMenu(false)}>
        Features
      </a>
      <a href="#preview" onClick={() => setMenu(false)}>
        Product preview
      </a>
    </>
  );
  return (
    <main id="main-content" className="landing">
      <div className="night">
        <header className="public-nav wrap">
          <Brand />
          <nav aria-label="Main navigation">{nav}</nav>
          <div className="nav-actions">
            <a className="workspace-link" href="/signin">
              Open workspace <ArrowUpRight size={16} />
            </a>
            <button
              className="mobile-menu"
              aria-label="Navigation menu"
              aria-expanded={menu}
              onClick={() => setMenu(!menu)}
            >
              {menu ? <X /> : <Menu />}
            </button>
          </div>
          {menu && (
            <nav className="menu-pop" aria-label="Mobile navigation">
              {nav}
            </nav>
          )}
        </header>
        <section className="hero">
          <Terrain />
          <div className="hero-copy">
            <span className="hero-badge">
              <Sparkles size={14} /> Your AI job applying buddy
            </span>
            <h1>
              Your Job Hunt.
              <br />
              Smarter with <em>JODY.</em>
            </h1>
            <p>
              Discover the right roles, match them to your experience,
              <br className="desktop-break" /> and prepare every application
              with confidence.
            </p>
            <form
              className="hero-search"
              onSubmit={(e) => {
                e.preventDefault();
                search(input);
              }}
            >
              <Search size={20} />
              <label className="sr-only" htmlFor="explore">
                Search sample roles by title, skill, or location
              </label>
              <input
                id="explore"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Job title, skill, or location"
                maxLength={120}
              />
              <button>Explore roles</button>
            </form>
            <div className="suggestions">
              <span>Try</span>
              {["Product design", "Python", "Remote"].map((s) => (
                <button key={s} onClick={() => search(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        </section>
        <div className="preview-holder wrap">
          <SampleWorkspace query={query} tab={tab} onTab={setTab} />
        </div>
      </div>
      <section id="features" className="wrap content-section">
        <p className="eyebrow">
          <Mark size={15} /> Career intelligence
        </p>
        <h2>
          A better way to job hunt<span>.</span>
        </h2>
        <div className="feature-grid">
          {features.map(({ icon: Icon, title, text }) => (
            <article key={title}>
              <span className="feature-icon">
                <Icon size={24} />
              </span>
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
      </section>
      <section id="how" className="how">
        <div className="wrap how-grid">
          <div>
            <p className="eyebrow">
              <Layers size={16} /> How JODY works
            </p>
            <h2>
              From discovery
              <br />
              to a considered <em>application.</em>
            </h2>
          </div>
          <div>
            {[
              [
                UserRound,
                "Build your profile",
                "Add your resume and portfolio. Review the facts JODY can use.",
              ],
              [
                Search,
                "Compare a role",
                "Save a job and see where its requirements meet your experience.",
              ],
              [
                ListChecks,
                "Review your next step",
                "Inspect the evidence, resolve missing details, and review the draft.",
              ],
            ].map(([I, t, s]) => {
              const Icon = I as typeof UserRound;
              return (
                <article className="how-step" key={String(t)}>
                  <Icon size={23} />
                  <div>
                    <h3>{String(t)}</h3>
                    <p>{String(s)}</p>
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      </section>
      <section id="privacy" className="wrap privacy">
        <span className="feature-icon">
          <ShieldCheck />
        </span>
        <h2>
          Your search. <em>Your say.</em>
        </h2>
        <p>
          Your profile stays in your private workspace. JODY uses reviewed
          evidence and asks for approval before sending an email or submitting
          an application.
        </p>
        <a href="/signin" className="primary">
          Open private workspace <LockKeyhole size={16} />
        </a>
      </section>
      <footer>
        <div className="wrap footer-inner">
          <Brand />
          <span>Your AI Job Applying Buddy</span>
          <a href="#privacy">Privacy & approvals</a>
          <a href="#main-content">Back to top</a>
        </div>
      </footer>
    </main>
  );
}
