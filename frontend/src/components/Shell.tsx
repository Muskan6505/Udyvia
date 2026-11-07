"use client";
import { AnimatePresence, motion } from "framer-motion";
import { useStore } from "@/lib/store";
import type { Step } from "@/lib/types";
import { MobileSlip, Slip } from "./Slip";
import { Btn, ErrorNote } from "./ui";

const NAV: { step: Step[]; key: string }[] = [
  { step: ["advisor"], key: "nav.advisor" }, { step: ["quote"], key: "nav.quote" }, { step: ["consent", "kyc"], key: "nav.kyc" },
  { step: ["sign"], key: "nav.sign" }, { step: ["track"], key: "nav.track" },
];

export function Logo() {
  return (
    <span className="flex items-center gap-2 font-display text-xl font-extrabold text-ink">
      <svg viewBox="0 0 64 64" className="h-8 w-8" aria-hidden><rect width="64" height="64" rx="14" fill="#1E2A78" />
        <path d="M18 16v20a14 14 0 0 0 28 0V16" fill="none" stroke="#F5F6FB" strokeWidth="7" strokeLinecap="round" /><circle cx="46" cy="16" r="4.5" fill="#F2B705" /></svg>
      Udyvia
    </span>
  );
}

export function Shell({ children }: { children: (step: Step) => React.ReactNode }) {
  const { step, t, lang, setLang, reset, error, setError, user, signOut, deleteAccount, notice } = useStore();
  const idx = NAV.findIndex((n) => n.step.includes(step));
  return (
    <div className="min-h-screen pb-20 lg:pb-0">
      <header className="sticky top-0 z-20 border-b border-ink/10 bg-paper/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <Logo />
          {step !== "welcome" && step !== "auth" && (
            <ol className="hidden items-center gap-1 md:flex" aria-label="Progress">
              {NAV.map((n, i) => (
                <li key={n.key} aria-current={i === idx ? "step" : undefined}
                  className={`flex items-center gap-2 rounded-full px-3 py-1 text-sm font-semibold transition-colors ${i === idx ? "bg-ink text-white" : i < idx ? "text-leaf" : "text-slate2/70"}`}>
                  {i < idx ? "✓" : i + 1}<span>{t(n.key)}</span>
                </li>
              ))}
            </ol>
          )}
          <div className="flex items-center gap-1">
            <div className="flex rounded-full border border-ink/15 p-0.5 text-sm font-semibold" role="group" aria-label="Language">
              {(["en", "hi"] as const).map((l) => (
                <button key={l} onClick={() => setLang(l)} aria-pressed={lang === l}
                  className={`rounded-full px-3 py-1 transition-colors ${lang === l ? "bg-ink text-white" : "text-ink-soft hover:bg-ink-wash"}`}>
                  {l === "en" ? "EN" : "हिं"}
                </button>
              ))}
            </div>
            {step !== "welcome" && step !== "auth" && <Btn variant="quiet" onClick={reset}>{t("reset")}</Btn>}
            {user && (
              <details className="relative">
                <summary className="flex h-9 w-9 cursor-pointer list-none items-center justify-center rounded-full bg-ink font-display font-bold text-white" aria-label={user.name} title={user.name}>
                  {user.name.trim()[0]?.toUpperCase()}
                </summary>
                <div className="absolute right-0 z-30 mt-2 w-56 rounded-xl border border-ink/10 bg-white p-2 shadow-slip">
                  <p className="truncate px-3 py-1 text-sm font-semibold text-ink">{user.name}</p>
                  <p className="truncate px-3 pb-2 text-xs text-slate2">{user.email}</p>
                  <button onClick={signOut} className="w-full rounded-lg px-3 py-2 text-left text-sm font-semibold hover:bg-ink-wash">{t("me.signout")}</button>
                  <button onClick={deleteAccount} className="w-full rounded-lg px-3 py-2 text-left text-sm font-semibold text-chilli hover:bg-chilli-wash">{t("me.delete")}</button>
                </div>
              </details>
            )}
          </div>
        </div>
      </header>
      <main className={`mx-auto max-w-6xl px-4 sm:px-6 ${step === "welcome" || step === "auth" ? "" : "grid gap-10 py-8 lg:grid-cols-[minmax(0,1fr)_340px]"}`}>
        <div className="min-w-0">
          <ErrorNote msg={error} onClose={() => setError(null)} />
          {notice && <p role="status" className="mb-4 rounded-xl border-2 border-haldi/50 bg-haldi-wash px-4 py-3 text-sm text-ink">{notice}</p>}
          <AnimatePresence mode="wait">
            <motion.div key={step} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25 }}>
              {children(step)}
            </motion.div>
          </AnimatePresence>
        </div>
        {step !== "welcome" && step !== "auth" && <Slip />}
      </main>
      {step !== "welcome" && step !== "auth" && <MobileSlip />}
    </div>
  );
}
