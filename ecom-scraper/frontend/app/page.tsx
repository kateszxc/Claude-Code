"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { COUNTRIES, REGIONS } from "@/lib/locations";
import type { BrandResult, Job, Options, ScrapeRequest } from "@/lib/types";

const CUSTOM = "__custom__";

const PROVIDER_LABEL: Record<string, string> = {
  brave: "Brave Search API",
  serpapi: "SerpAPI (Google)",
  duckduckgo: "DuckDuckGo (free fallback – add a search API key for bigger runs)",
};

export default function Home() {
  const [options, setOptions] = useState<Options | null>(null);
  const [backendError, setBackendError] = useState("");

  // Form state
  const [count, setCount] = useState(10);
  const [niche, setNiche] = useState("beauty-skincare");
  const [customNiche, setCustomNiche] = useState("");
  const [keywords, setKeywords] = useState("");
  const [country, setCountry] = useState("");
  const [customCountry, setCustomCountry] = useState("");
  const [region, setRegion] = useState("");
  const [city, setCity] = useState("");
  const [onlyThere, setOnlyThere] = useState(false);
  const [minAge, setMinAge] = useState("");
  const [maxAge, setMaxAge] = useState("");
  const [seedUrls, setSeedUrls] = useState("");
  const [strict, setStrict] = useState(false);
  const [useAi, setUseAi] = useState(true);

  // Job state
  const [job, setJob] = useState<Job | null>(null);
  const [submitError, setSubmitError] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("/api/options")
      .then((r) => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then(setOptions)
      .catch(() =>
        setBackendError("Can't reach the Python backend on port 8000. Start it with `python server.py` in ecom-scraper/backend."),
      );
  }, []);

  const poll = useCallback(async (id: string) => {
    const r = await fetch(`/api/jobs/${id}?log_tail=80`);
    if (r.ok) setJob(await r.json());
  }, []);

  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    const t = setInterval(() => poll(job.id), 1500);
    return () => clearInterval(t);
  }, [job, poll]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [job?.logs.length]);

  const running = job?.status === "running" || job?.status === "queued";

  async function start(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError("");
    const nicheValue = niche === CUSTOM ? customNiche.trim() : niche;
    if (!nicheValue) {
      setSubmitError("Type the niche you want to target.");
      return;
    }
    const body: ScrapeRequest = {
      count,
      niche: nicheValue,
      keywords,
      country: countryValue,
      state: region.trim(),
      city: city.trim(),
      location_required: onlyThere && hasLocation,
      min_age_years: minAge === "" ? null : Number(minAge),
      max_age_years: maxAge === "" ? null : Number(maxAge),
      seed_urls: seedUrls.split(/[\s,]+/).filter(Boolean),
      strict_filters: strict,
      use_ai: useAi,
    };
    const r = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      setSubmitError(typeof data.detail === "string" ? data.detail : "Could not start the scrape – check the inputs.");
      return;
    }
    setExpanded(null);
    await poll(data.id);
  }

  async function cancel() {
    if (!job) return;
    await fetch(`/api/jobs/${job.id}/cancel`, { method: "POST" });
    poll(job.id);
  }

  const countryValue = (country === CUSTOM ? customCountry : country).trim();
  const hasLocation = Boolean(countryValue || region.trim() || city.trim());
  const regionOptions = REGIONS[country];

  const pct = job ? Math.round((100 * job.found) / Math.max(job.request.count, 1)) : 0;

  return (
    <main className="shell">
      <header className="hero">
        <h1>E-com Brand Scraper</h1>
        <p>
          Find e-commerce brands in your niche and get each one's domain, what they sell, founder email,
          location, age and specific growth ideas, exported to CSV.
        </p>
      </header>

      {backendError && <div className="alert error">{backendError}</div>}
      {options && (
        <div className="providers">
          <span>Search: <b>{PROVIDER_LABEL[options.providers.search]}</b></span>
          <span className={options.providers.hunter ? "on" : "off"}>Hunter.io emails: {options.providers.hunter ? "on" : "off"}</span>
          <span className={options.providers.ai ? "on" : "off"}>Claude insights: {options.providers.ai ? "on" : "off"}</span>
        </div>
      )}

      <form className="card form" onSubmit={start}>
        <div className="field">
          <label htmlFor="count">How many brands do you want to scrape?</label>
          <input id="count" type="number" min={1} max={200} value={count}
            onChange={(e) => setCount(Math.max(1, Math.min(200, Number(e.target.value) || 1)))} />
        </div>

        <div className="field">
          <label htmlFor="niche">Niche</label>
          <select id="niche" value={niche} onChange={(e) => setNiche(e.target.value)}>
            {options?.niches.map((n) => (
              <option key={n.id} value={n.id}>{n.label}</option>
            ))}
            <option value={CUSTOM}>Other – type my own…</option>
          </select>
          {niche === CUSTOM && (
            <input placeholder="e.g. eyewear, golf apparel, hot sauce" value={customNiche}
              onChange={(e) => setCustomNiche(e.target.value)} />
          )}
        </div>

        <div className="field">
          <label htmlFor="kw">Extra keywords <span className="hint">(optional)</span></label>
          <input id="kw" placeholder="vegan, clean, women-owned" value={keywords} onChange={(e) => setKeywords(e.target.value)} />
        </div>

        <fieldset className="field">
          <legend>Location <span className="hint">(optional – fill in as much or as little as you like)</span></legend>
          <div className="row">
            <div className="field">
              <label htmlFor="country">Country</label>
              <select id="country" value={country} onChange={(e) => { setCountry(e.target.value); setRegion(""); }}>
                <option value="">Anywhere</option>
                {COUNTRIES.map((c) => <option key={c} value={c}>{c}</option>)}
                <option value={CUSTOM}>Other – type it…</option>
              </select>
              {country === CUSTOM && (
                <input placeholder="Country name" value={customCountry} onChange={(e) => setCustomCountry(e.target.value)} />
              )}
            </div>
            <div className="field">
              <label htmlFor="region">State / province / region</label>
              {regionOptions ? (
                <select id="region" value={region} onChange={(e) => setRegion(e.target.value)}>
                  <option value="">Any</option>
                  {regionOptions.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              ) : (
                <input id="region" placeholder="e.g. Bavaria, Metro Manila" value={region} onChange={(e) => setRegion(e.target.value)} />
              )}
            </div>
            <div className="field">
              <label htmlFor="city">City</label>
              <input id="city" placeholder="e.g. Los Angeles" value={city} onChange={(e) => setCity(e.target.value)} />
            </div>
          </div>
          {hasLocation && (
            <label className="check">
              <input type="checkbox" checked={onlyThere} onChange={(e) => setOnlyThere(e.target.checked)} />
              Only keep brands whose website confirms they&apos;re based there
            </label>
          )}
        </fieldset>

        <div className="row">
          <div className="field">
            <label htmlFor="minAge">Brand age from (years)</label>
            <input id="minAge" type="number" min={0} step="0.5" placeholder="any" value={minAge} onChange={(e) => setMinAge(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="maxAge">to (years)</label>
            <input id="maxAge" type="number" min={0} step="0.5" placeholder="any" value={maxAge} onChange={(e) => setMaxAge(e.target.value)} />
          </div>
        </div>

        <details className="advanced">
          <summary>Advanced</summary>
          <div className="field">
            <label htmlFor="seeds">Brand URLs to include <span className="hint">(optional – one per line, scraped first)</span></label>
            <textarea id="seeds" rows={3} placeholder={"glossier.com\nhttps://www.allbirds.com"} value={seedUrls}
              onChange={(e) => setSeedUrls(e.target.value)} />
          </div>
          <label className="check">
            <input type="checkbox" checked={strict} onChange={(e) => setStrict(e.target.checked)} />
            Strict age filter: drop brands whose age can&apos;t be confirmed
          </label>
          <label className="check">
            <input type="checkbox" checked={useAi && !!options?.providers.ai} disabled={!options?.providers.ai} onChange={(e) => setUseAi(e.target.checked)} />
            Use Claude for summaries &amp; tailored improvement ideas
            {!options?.providers.ai && <span className="hint"> (set ANTHROPIC_API_KEY in backend/.env to enable)</span>}
          </label>
        </details>

        {submitError && <div className="alert error">{submitError}</div>}
        <div className="actions">
          <button className="primary" type="submit" disabled={running || !options}>
            {running ? "Scraping…" : `Find ${count} brand${count === 1 ? "" : "s"}`}
          </button>
          {running && <button type="button" className="ghost" onClick={cancel}>Cancel</button>}
        </div>
      </form>

      {job && (
        <section className="card">
          <div className="status">
            <div>
              <h2>{options?.niches.find((n) => n.id === job.request.niche)?.label ?? job.request.niche} · {statusLabel(job.status)}</h2>
              <p className="muted">
                {job.found}/{job.request.count} found · {job.scanned} sites checked · {job.candidates} candidates
              </p>
            </div>
            <a className={`primary ${job.results.length ? "" : "disabled"}`} href={`/api/jobs/${job.id}/csv`}>
              Download CSV{running ? " (so far)" : ""}
            </a>
          </div>
          <div className="bar"><div style={{ width: `${pct}%` }} /></div>
          <div className="log" ref={logRef}>
            {job.logs.map((l, i) => (
              <div key={i} className={l.startsWith("✓") ? "ok" : l.startsWith("✗") ? "skip" : ""}>{l}</div>
            ))}
          </div>
        </section>
      )}

      {job && job.results.length > 0 && (
        <section className="card">
          <h2>Results</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Brand</th><th>What they do</th><th>Founder</th><th>Email</th>
                  <th>Location</th><th>Age</th><th>Mktg score</th><th />
                </tr>
              </thead>
              <tbody>
                {job.results.map((r) => (
                  <ResultRows key={r.domain} r={r} open={expanded === r.domain}
                    onToggle={() => setExpanded(expanded === r.domain ? null : r.domain)} />
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <footer className="muted foot">
        Uses only publicly available information and respects robots.txt.
        Follow CAN-SPAM / GDPR rules when contacting anyone.
      </footer>
    </main>
  );
}

function statusLabel(s: Job["status"]) {
  return { queued: "Queued", running: "Running", done: "Done", cancelled: "Cancelled", error: "Error" }[s];
}

function ResultRows({ r, open, onToggle }: { r: BrandResult; open: boolean; onToggle: () => void }) {
  return (
    <>
      <tr>
        <td>
          <a href={r.website_url} target="_blank" rel="noreferrer"><b>{r.brand_name}</b></a>
          <div className="muted small">{r.domain} · {r.platform}</div>
        </td>
        <td className="about">{r.what_they_do || <span className="muted">–</span>}</td>
        <td>{r.founder_name || <span className="muted">–</span>}</td>
        <td>
          {r.founder_email ? <a href={`mailto:${r.founder_email}`}>{r.founder_email}</a> : <span className="muted">none found</span>}
          {r.founder_email && <span className={`badge ${r.email_confidence}`}>{r.email_confidence}</span>}
        </td>
        <td>
          {r.location || <span className="muted">not stated</span>}
          {r.location_match && <span className={`badge ${r.location_match === "confirmed" ? "high" : ""}`}>{r.location_match}</span>}
        </td>
        <td>{r.brand_age_years != null ? `${r.brand_age_years} yrs` : "?"}</td>
        <td><span className="score">{r.marketing_score}</span></td>
        <td><button className="ghost small" onClick={onToggle}>{open ? "Hide" : "Ideas"}</button></td>
      </tr>
      {open && (
        <tr className="detail">
          <td colSpan={8}>
            <div className="ideas">
              <IdeaList title="Website" items={r.website_improvements} />
              <IdeaList title="Marketing" items={r.marketing_improvements} />
              <IdeaList title="Brand / company" items={r.brand_improvements} />
            </div>
            <div className="facts muted small">
              <span><b>Age source:</b> {r.age_source}{r.founded_year ? ` (${r.founded_year})` : ""}</span>
              {r.product_count && <span><b>Products:</b> {r.product_count} · {r.price_range}</span>}
              {r.filter_notes.length > 0 && <span><b>Notes:</b> {r.filter_notes.join("; ")}</span>}
              {r.marketing_stack.length > 0 && <span><b>Stack:</b> {r.marketing_stack.join(", ")}</span>}
              {Object.keys(r.socials).length > 0 && (
                <span><b>Socials:</b>{" "}
                  {Object.entries(r.socials).map(([k, v]) => (
                    <a key={k} href={v} target="_blank" rel="noreferrer">{k} </a>
                  ))}
                </span>
              )}
              {r.other_emails.length > 0 && <span><b>Other emails:</b> {r.other_emails.join(", ")}</span>}
              {r.email_source && <span><b>Email found on:</b> {r.email_source}</span>}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function IdeaList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h4>{title}</h4>
      {items.length ? <ul>{items.map((i) => <li key={i}>{i}</li>)}</ul> : <p className="muted">Looks solid.</p>}
    </div>
  );
}
