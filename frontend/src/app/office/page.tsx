"use client";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, Phone, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Btn, CountUp, ErrorNote, inr } from "@/components/ui";
import { Logo } from "@/components/Shell";
import { api, ApiError } from "@/lib/api";
import type { Lead, OfficeData, User } from "@/lib/types";

const BAND = {
  Hot: "bg-chilli-wash text-chilli border-chilli/30", Warm: "bg-haldi-wash text-haldi-deep border-haldi/50", Cold: "bg-ink-wash text-ink-soft border-ink/15",
} as const;
const STATUS: [Lead["follow_up_status"], string][] = [["new", "Not called"], ["called", "Called"], ["callback", "Call back"], ["not_interested", "Not interested"]];
const idle = (m: number) => (m < 60 ? `${m} min` : m < 1440 ? `${Math.round(m / 60)} h` : `${Math.round(m / 1440)} d`);

function Login({ onDone }: { onDone: (u: User) => void }) {
  const [email, setEmail] = useState(""), [pw, setPw] = useState(""), [err, setErr] = useState<string | null>(null), [busy, setBusy] = useState(false);
  const go = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try {
      const u = await api.login(email, pw);
      if (u.role !== "backoffice") { await api.logout(); setErr("This area is for Airtel sales and partner staff."); } else onDone(u);
    } catch (x) { setErr(x instanceof ApiError ? x.message : "Could not sign in."); }
    setBusy(false);
  };
  return (
    <form onSubmit={go} className="mx-auto mt-16 max-w-sm space-y-3">
      <h1 className="text-3xl font-extrabold text-ink">Back-office sign in</h1>
      <p className="text-slate2">Sales and channel-partner staff only.</p>
      <ErrorNote msg={err} />
      <input className="w-full rounded-xl border-2 border-ink/20 bg-white px-4 py-3 outline-none focus:border-ink" type="email" placeholder="Staff email" aria-label="Staff email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      <input className="w-full rounded-xl border-2 border-ink/20 bg-white px-4 py-3 outline-none focus:border-ink" type="password" placeholder="Password" aria-label="Password" value={pw} onChange={(e) => setPw(e.target.value)} required />
      <Btn type="submit" busy={busy} className="w-full">Sign in</Btn>
    </form>
  );
}

function Score({ p, band }: { p: number; band: Lead["band"] }) {
  const pct = Math.round(p * 100);
  const color = band === "Hot" ? "#D6342C" : band === "Warm" ? "#B88700" : "#4C58A8";
  const r = 22, c = 2 * Math.PI * r;
  return (
    <div className="relative h-16 w-16 shrink-0" role="img" aria-label={`${pct} percent chance to activate`}>
      <svg viewBox="0 0 56 56" className="h-16 w-16 -rotate-90">
        <circle cx="28" cy="28" r={r} fill="none" stroke="#E7EAF8" strokeWidth="6" />
        <motion.circle cx="28" cy="28" r={r} fill="none" stroke={color} strokeWidth="6" strokeLinecap="round" strokeDasharray={c}
          initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - Math.min(1, p)) }} transition={{ duration: 0.9, ease: "easeOut" }} />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center font-display text-lg font-extrabold tabular-nums text-ink">{pct}%</span>
    </div>
  );
}

function LeadCard({ l, rank, onSaved }: { l: Lead; rank: number; onSaved: () => void }) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState(l.follow_up_status), [note, setNote] = useState(l.follow_up_note), [saving, setSaving] = useState(false), [err, setErr] = useState<string | null>(null);
  const save = async () => {
    setSaving(true); setErr(null);
    try { await api.followUp(l.id, status, note); onSaved(); } catch (x) { setErr(x instanceof ApiError ? x.message : "Could not save."); }
    setSaving(false);
  };
  return (
    <motion.li layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ delay: Math.min(rank, 8) * 0.04 }}
      className="rounded-2xl border border-ink/10 bg-white p-4 shadow-sm sm:p-5">
      <div className="flex gap-4">
        <Score p={l.probability} band={l.band} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <h3 className="font-display text-lg font-bold text-ink">{l.name}</h3>
            <span className={`rounded-full border px-2.5 py-0.5 text-xs font-bold ${BAND[l.band]}`}>{l.band}</span>
            {l.demo && <span className="rounded-full bg-ink-wash px-2 py-0.5 text-xs font-semibold text-ink-soft">sample</span>}
          </div>
          <p className="text-sm text-slate2">{[l.business, l.city, l.employees ? `${l.employees} people` : null, l.sites && l.sites > 1 ? `${l.sites} sites` : null].filter(Boolean).join(" · ") || "No answers yet"}</p>
          <p className="mt-1 text-sm"><span className="font-semibold text-ink">{l.stage_text}</span> <span className="text-slate2">· idle {idle(l.idle_minutes)}{l.monthly_total ? ` · quote ${inr(l.monthly_total)}/mo` : ""}</span></p>
        </div>
        <a href={`tel:+91${l.phone}`} className="hidden h-11 shrink-0 items-center gap-2 self-start rounded-xl bg-leaf px-4 font-semibold text-white hover:opacity-90 sm:flex" aria-label={`Call ${l.name}`}>
          <Phone className="h-4 w-4" aria-hidden />{l.phone}
        </a>
      </div>

      <p className="mt-3 rounded-xl bg-haldi-wash px-3 py-2 text-sm"><span className="font-bold text-ink">Next step: </span>{l.next_action}</p>
      <a href={`tel:+91${l.phone}`} className="mt-2 flex items-center justify-center gap-2 rounded-xl bg-leaf py-2.5 font-semibold text-white sm:hidden"><Phone className="h-4 w-4" aria-hidden />Call {l.phone}</a>

      <button onClick={() => setOpen(!open)} aria-expanded={open} className="mt-3 flex items-center gap-1 text-sm font-semibold text-ink-soft hover:text-ink">
        Why this score, and follow-up <ChevronDown className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="grid gap-4 pt-3 md:grid-cols-2">
              <div>
                <p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate2">What moves the score</p>
                <ul className="flex flex-wrap gap-2">
                  {l.factors.map((f) => (
                    <li key={f.feature} className={`rounded-full px-3 py-1 text-sm ${f.direction === "up" ? "bg-leaf-wash text-leaf" : "bg-chilli-wash text-chilli"}`}>
                      {f.direction === "up" ? "▲" : "▼"} {f.value}
                    </li>
                  ))}
                </ul>
                <p className="mb-2 mt-4 text-xs font-bold uppercase tracking-wide text-slate2">Why they stalled</p>
                <ul className="space-y-1 text-sm text-ink">{l.blockers.map((b) => <li key={b.code}>• {b.text}</li>)}</ul>
              </div>
              <div>
                <p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate2">Your follow-up</p>
                <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Follow-up status">
                  {STATUS.map(([v, label]) => (
                    <button key={v} role="radio" aria-checked={status === v} onClick={() => setStatus(v)}
                      className={`rounded-full border-2 px-3 py-1 text-sm font-semibold ${status === v ? "border-ink bg-ink text-white" : "border-ink/20 text-ink hover:border-ink"}`}>{label}</button>
                  ))}
                </div>
                <textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} rows={2} placeholder="Note (no ID numbers please)" aria-label="Follow-up note"
                  className="mt-2 w-full rounded-xl border-2 border-ink/20 px-3 py-2 text-sm outline-none focus:border-ink" />
                <ErrorNote msg={err} />
                <Btn variant="ghost" busy={saving} onClick={save} className="mt-2 py-2">Save</Btn>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.li>
  );
}

export default function Office() {
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [data, setData] = useState<OfficeData | null>(null);
  const [band, setBand] = useState("all"), [sort, setSort] = useState("score"), [stalled, setStalled] = useState(false), [status, setStatus] = useState("all");
  const [err, setErr] = useState<string | null>(null), [showModel, setShowModel] = useState(false);

  useEffect(() => { api.me().then((u) => setUser(u.role === "backoffice" ? u : null)).catch(() => setUser(null)); }, []);
  const load = useCallback(async () => {
    setErr(null);
    try { setData(await api.officeLeads(`?band=${band}&sort=${sort}&status=${status}&min_idle_minutes=${stalled ? 60 : 0}`)); }
    catch (x) { setErr(x instanceof ApiError ? x.message : "Could not load leads."); }
  }, [band, sort, status, stalled]);
  useEffect(() => { if (user) load(); }, [user, load]);

  const chip = (active: boolean) => `rounded-full border-2 px-3 py-1 text-sm font-semibold transition-colors ${active ? "border-ink bg-ink text-white" : "border-ink/20 text-ink hover:border-ink"}`;
  return (
    <div className="min-h-screen bg-paper pb-16">
      <header className="border-b border-ink/10 bg-paper/90">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3"><Logo /><span className="rounded-full bg-ink px-3 py-0.5 text-xs font-bold uppercase tracking-wide text-white">Back-office</span></div>
          {user && <Btn variant="quiet" onClick={async () => { await api.logout(); setUser(null); setData(null); }}>Sign out</Btn>}
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 sm:px-6">
        {user === undefined && <p className="mt-16 text-center text-slate2">Loading…</p>}
        {user === null && <Login onDone={setUser} />}
        {user && (
          <>
            <div className="mt-8 flex flex-wrap items-end justify-between gap-3">
              <div>
                <h1 className="text-3xl font-extrabold text-ink">Leads to call</h1>
                <p className="text-slate2">People the advisor could not take all the way to activation, most likely to convert first.</p>
              </div>
              <Btn variant="ghost" onClick={load} icon={<RefreshCw className="h-4 w-4" aria-hidden />}>Refresh</Btn>
            </div>
            <ErrorNote msg={err} />
            {data && (
              <>
                <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
                  {[["Open leads", <CountUp key="a" value={data.summary.open} format={(n) => String(Math.round(n))} />],
                    ["Hot", <CountUp key="b" value={data.summary.hot} format={(n) => String(Math.round(n))} />],
                    ["Likely monthly value", <CountUp key="c" value={data.summary.expected_monthly_value} />],
                    ["Asked not to be called", <span key="d">{data.summary.opted_out}</span>]].map(([k, v]) => (
                    <div key={String(k)} className="rounded-2xl border border-ink/10 bg-white p-4">
                      <p className="text-xs font-bold uppercase tracking-wide text-slate2">{k}</p>
                      <p className="mt-1 font-display text-3xl font-extrabold text-ink">{v}</p>
                    </div>
                  ))}
                </div>

                <div className="mt-6 flex flex-wrap items-center gap-2" role="toolbar" aria-label="Filters">
                  {["all", "Hot", "Warm", "Cold"].map((b) => <button key={b} className={chip(band === b)} aria-pressed={band === b} onClick={() => setBand(b)}>{b === "all" ? "All" : b}</button>)}
                  <span className="mx-1 h-5 w-px bg-ink/15" aria-hidden />
                  <button className={chip(stalled)} aria-pressed={stalled} onClick={() => setStalled(!stalled)}>Idle 1h+</button>
                  <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Follow-up status" className="rounded-full border-2 border-ink/20 bg-white px-3 py-1 text-sm font-semibold text-ink">
                    <option value="all">Any status</option>{STATUS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                  <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort" className="ml-auto rounded-full border-2 border-ink/20 bg-white px-3 py-1 text-sm font-semibold text-ink">
                    <option value="score">Highest chance first</option><option value="value">Highest likely value first</option>
                  </select>
                </div>

                <ul className="mt-4 space-y-3">
                  <AnimatePresence>{data.leads.map((l, i) => <LeadCard key={`${l.id}-${l.follow_up_status}-${l.follow_up_note}`} l={l} rank={i} onSaved={load} />)}</AnimatePresence>
                </ul>
                {data.leads.length === 0 && <p className="mt-10 rounded-2xl border-2 border-dashed border-ink/20 p-10 text-center text-slate2">No open leads match. When someone signs up and stops before activating, they appear here.</p>}

                <button onClick={() => setShowModel(!showModel)} aria-expanded={showModel} className="mt-10 flex items-center gap-1 font-semibold text-ink-soft hover:text-ink">
                  How the score works <ChevronDown className={`h-4 w-4 transition-transform ${showModel ? "rotate-180" : ""}`} aria-hidden />
                </button>
                {showModel && (
                  <div className="mt-3 rounded-2xl border border-ink/10 bg-white p-5 text-sm text-slate2">
                    <p>Chance of activating is learnt from {data.model.trained_on}: how far a lead got, business type, city tier, team size, locations, GSTIN and current internet. It is checked on {data.model.test_leads.toLocaleString("en-IN")} leads the model never saw.</p>
                    <table className="mt-3 w-full text-left">
                      <thead><tr className="text-xs uppercase text-slate2"><th className="py-1">Stage</th><th>Leads</th><th>Activated</th><th>Ranking skill (AUC)</th></tr></thead>
                      <tbody>{Object.entries(data.model.by_stage).map(([k, v]) => <tr key={k} className="border-t border-ink/10"><td className="py-1 font-semibold text-ink">{k}</td><td>{v.n}</td><td>{Math.round(v.activation_rate * 100)}%</td><td>{v.auc.toFixed(2)}</td></tr>)}</tbody>
                    </table>
                    <p className="mt-3">{data.model.note}</p>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}
