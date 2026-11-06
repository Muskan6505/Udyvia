"use client";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { useStore } from "@/lib/store";
import { Btn } from "./ui";

/** The one orchestrated moment: a sample slip that fills itself in, showing what the owner will get. */
function SampleSlip() {
  const lines: [string, string][] = [["Biz Fibre 100", "₹1,100"], ["2 × Postpaid 299", "₹700"], ["Secure Wi-Fi", "₹500"]];
  return (
    <div className="slip mx-auto w-full max-w-sm rounded-t-2xl px-6 pt-6 shadow-slip" aria-hidden>
      <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="font-display text-lg font-bold text-ink">
        Kirana store · Indore
      </motion.p>
      <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.7 }} className="text-sm text-slate2">3 people · 1 shop · no GST yet</motion.p>
      <ul className="mt-4 border-t-2 border-dashed border-ink/15 pt-3">
        {lines.map(([n, p], i) => (
          <motion.li key={n} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 1.2 + i * 0.5 }}
            className="flex justify-between py-1"><span>{n}</span><span className="tabular-nums text-slate2">{p}</span></motion.li>
        ))}
      </ul>
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 3 }} className="mt-3 flex items-end justify-between border-t-2 border-ink pt-3 pb-6">
        <span className="text-sm font-semibold">Monthly total</span>
        <span className="font-display text-3xl font-extrabold text-ink">₹2,300</span>
      </motion.div>
    </div>
  );
}

export function Welcome() {
  const { t, lang, setLang, go } = useStore();
  const points = ["welcome.p1", "welcome.p2", "welcome.p3", "welcome.p4"];
  return (
    <section className="grid min-h-[calc(100vh-70px)] items-center gap-12 py-10 lg:grid-cols-[1.1fr_0.9fr]">
      <div>
        <h1 className="max-w-xl text-4xl font-extrabold leading-[1.05] text-ink sm:text-6xl">{t("welcome.title")}</h1>
        <p className="mt-5 max-w-lg text-lg text-slate2">{t("welcome.sub")}</p>
        <p className="mt-8 text-sm font-semibold text-ink-soft">{t("welcome.pick")}</p>
        <div className="mt-2 flex flex-wrap gap-3" role="group" aria-label={t("welcome.pick")}>
          {([["en", "English"], ["hi", "हिन्दी"]] as const).map(([l, label]) => (
            <button key={l} onClick={() => setLang(l)} aria-pressed={lang === l}
              className={`rounded-2xl border-2 px-6 py-3 text-xl font-bold transition-all ${lang === l ? "border-ink bg-ink text-white shadow-[0_5px_0_0_#141C55]" : "border-ink/20 text-ink hover:border-ink"}`}>
              {label}
            </button>
          ))}
        </div>
        <Btn className="mt-6 text-lg" onClick={() => go("advisor")} icon={<ArrowRight className="h-5 w-5 order-last" aria-hidden />}>{t("welcome.start")}</Btn>
        <ul className="mt-10 grid max-w-lg gap-2 text-slate2 sm:grid-cols-2">
          {points.map((p) => <li key={p} className="flex items-start gap-2"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-haldi" aria-hidden />{t(p)}</li>)}
        </ul>
      </div>
      <SampleSlip />
    </section>
  );
}
