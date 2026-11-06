"use client";
import { AnimatePresence, motion } from "framer-motion";
import { Lock } from "lucide-react";
import { localize, unitLabel } from "@/lib/i18n";
import { useStore } from "@/lib/store";
import type { QuoteLine } from "@/lib/types";
import { Btn, CountUp, Switch, inr } from "./ui";

function Line({ l, busy, onToggle, lang }: { l: QuoteLine; busy: boolean; onToggle: (on: boolean) => void; lang: "en" | "hi" }) {
  return (
    <motion.li layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="flex items-center justify-between gap-4 border-b border-ink/10 py-3 last:border-0">
      <div className="min-w-0">
        <p className="font-semibold">{l.qty > 1 ? `${l.qty} × ` : ""}{l.product_name}</p>
        <p className="text-sm text-slate2">{inr(l.unit_price)} / {unitLabel(lang, l.unit)}{l.reason ? ` · ${localize(lang, l.reason)}` : ""}</p>
      </div>
      <div className="flex items-center gap-4">
        <span className={`font-display text-lg font-bold tabular-nums ${l.included ? "text-ink" : "text-slate2/60"}`}>{inr(l.line_monthly)}</span>
        <Switch on={l.included} disabled={busy} onChange={onToggle} label={l.product_name} />
      </div>
    </motion.li>
  );
}

export function QuoteScreen() {
  const { t, lang, quote, why, toggleAddon, quoteBusy, go } = useStore();
  if (!quote) return null;
  const inc = quote.lines.filter((l) => l.included);
  const opt = quote.lines.filter((l) => !l.included);
  return (
    <section>
      <h1 className="text-3xl font-extrabold text-ink">{t("quote.title")}</h1>
      <p className="mt-1 text-slate2">{quote.segment}</p>

      <div className="mt-6 flex flex-wrap items-end gap-x-8 gap-y-3 rounded-2xl bg-ink p-6 text-white">
        <div>
          <p className="text-sm text-white/70">{t("quote.total")}</p>
          <CountUp value={quote.monthly_total} className="font-display text-5xl font-extrabold tabular-nums" />
          <span className="ml-2 text-white/70">{t("monthly")}</span>
        </div>
        <dl className="flex gap-6 text-sm">
          <div><dt className="text-white/70">{t("setup")}</dt><dd className="text-lg font-semibold">{inr(quote.setup_total)}</dd></div>
          <div><dt className="text-white/70">{t("contract")}</dt><dd className="text-lg font-semibold">{quote.contract_months} {t("months")}</dd></div>
          <div><dt className="text-white/70">{t("goLive")}</dt><dd className="text-lg font-semibold">{quote.expected_install_days} {t("days")}</dd></div>
        </dl>
      </div>
      <p className="mt-2 text-xs text-slate2">{t("quote.tax")}</p>

      {why && (
        <div className="mt-6 border-l-4 border-haldi pl-4">
          <p className="text-sm font-semibold text-ink-soft">{t("quote.why")}</p>
          <p className="mt-1 text-[17px]">{why.split(/ (?:Open your quote|कोटेशन खोलकर)/)[0]}</p>
        </div>
      )}

      <h2 className="mt-8 text-xl font-bold text-ink">{t("quote.included")}</h2>
      <ul><AnimatePresence initial={false}>{inc.map((l) => <Line key={l.product_id} lang={lang} l={l} busy={quoteBusy} onToggle={(on) => toggleAddon(l.product_id, on)} />)}</AnimatePresence></ul>

      {opt.length > 0 && (<>
        <h2 className="mt-8 text-xl font-bold text-ink">{t("quote.optional")}</h2>
        <ul><AnimatePresence initial={false}>{opt.map((l) => <Line key={l.product_id} lang={lang} l={l} busy={quoteBusy} onToggle={(on) => toggleAddon(l.product_id, on)} />)}</AnimatePresence></ul>
      </>)}

      {quote.blocked.length > 0 && (<>
        <h2 className="mt-8 text-xl font-bold text-ink">{t("quote.unlock")}</h2>
        <ul className="mt-2 space-y-2">
          {quote.blocked.map((b) => (
            <li key={b.product_id} className="flex gap-3 rounded-xl bg-haldi-wash px-4 py-3">
              <Lock className="mt-1 h-4 w-4 shrink-0 text-haldi-deep" aria-hidden />
              <div><p className="font-semibold">{b.product_name}</p>
                <p className="text-sm text-slate2">{localize(lang, b.reasons.join("; "))}. {localize(lang, b.upgrade_path)}</p></div>
            </li>
          ))}
        </ul>
      </>)}

      {quote.notes.length > 0 && <ul className="mt-6 space-y-1 text-sm text-slate2">{quote.notes.map((n, i) => <li key={i}>{localize(lang, n)}</li>)}</ul>}

      <Btn className="mt-8 w-full sm:w-auto" disabled={inc.length === 0} onClick={() => go("consent")}>{t("quote.continue")}</Btn>
    </section>
  );
}
