"use client";
import { AnimatePresence, motion } from "framer-motion";
import { Check, FastForward } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";
import { Btn } from "./ui";

function Confetti() {
  const bits = Array.from({ length: 36 }, (_, i) => i);
  const colors = ["#F2B705", "#1E2A78", "#1F8A57", "#D6342C"];
  return (
    <div className="pointer-events-none fixed inset-0 z-40 overflow-hidden" aria-hidden>
      {bits.map((i) => (
        <motion.span key={i} className="absolute top-0 h-3 w-2 rounded-sm" style={{ left: `${(i * 97) % 100}%`, background: colors[i % 4] }}
          initial={{ y: -20, rotate: 0, opacity: 1 }} animate={{ y: "105vh", rotate: 360 + i * 20, opacity: [1, 1, 0] }}
          transition={{ duration: 2.2 + (i % 5) * 0.3, delay: (i % 9) * 0.08, ease: "easeIn" }} />
      ))}
    </div>
  );
}

export function Track() {
  const { t, lang, order, setOrder, guard } = useStore();
  const [busy, setBusy] = useState(false);
  const [boom, setBoom] = useState(false);
  useEffect(() => { if (order?.status === "ACTIVATED") { setBoom(true); const id = setTimeout(() => setBoom(false), 4200); return () => clearTimeout(id); } }, [order?.status]);
  if (!order) return null;
  const fmt = (d: string) => new Date(d + "T00:00:00").toLocaleDateString(lang === "hi" ? "hi-IN" : "en-IN", { day: "numeric", month: "short" });
  const doneCount = order.steps.filter((s) => s.state === "done").length;
  const active = order.status === "ACTIVATED";

  return (
    <section>
      {boom && <Confetti />}
      <h1 className="text-3xl font-extrabold text-ink">{t("track.title")} <span className="text-lg font-semibold text-slate2">{order.order_id}</span></h1>

      <div className="mt-5 rounded-2xl bg-ink p-6 text-white">
        {active ? <p className="font-display text-2xl font-extrabold">{t("track.done")}</p> : (<>
          <p className="text-sm text-white/70">{t("track.live")}</p>
          <p className="font-display text-4xl font-extrabold">{fmt(order.expected_activation)}</p>
          <p className="text-white/80">{t("track.in")} {order.days_to_activation} {t("days")}</p></>)}
        <p className="mt-3 border-t border-white/20 pt-3 text-sm"><span className="text-white/70">{t("track.next")}: </span>{order.next_action}</p>
      </div>

      <ol className="relative mt-8 ml-3">
        <span className="absolute left-[11px] top-2 bottom-2 w-0.5 bg-ink/15" aria-hidden />
        <motion.span className="absolute left-[11px] top-2 w-0.5 origin-top bg-leaf" aria-hidden
          animate={{ height: `calc(${Math.max(0, doneCount - 1) / (order.steps.length - 1)} * (100% - 16px))` }} transition={{ duration: 0.8, ease: "easeInOut" }} />
        {order.steps.map((s) => (
          <li key={s.code} className="relative flex items-start gap-4 pb-6 last:pb-0">
            <span className={`relative z-10 mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 ${
              s.state === "done" ? "border-leaf bg-leaf text-white" : s.state === "failed" ? "border-chilli bg-chilli text-white"
              : s.state === "current" ? "border-ink bg-white" : "border-ink/20 bg-paper"}`}>
              {s.state === "done" && <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 600, damping: 20 }}><Check className="h-3.5 w-3.5" aria-hidden /></motion.span>}
              {s.state === "current" && <motion.span className="h-2.5 w-2.5 rounded-full bg-ink" animate={{ scale: [1, 1.5, 1], opacity: [1, 0.5, 1] }} transition={{ duration: 1.4, repeat: Infinity }} />}
              {s.state === "failed" && <span className="text-xs font-bold">!</span>}
            </span>
            <div>
              <p className={`font-semibold ${s.state === "upcoming" ? "text-slate2" : "text-ink"}`}>{s.label}</p>
              <p className="text-sm text-slate2">{s.done_on ? fmt(s.done_on) : `~ ${fmt(s.expected_on)}`}</p>
            </div>
          </li>
        ))}
      </ol>

      <h2 className="mt-8 text-xl font-bold text-ink">{t("track.items")}</h2>
      <ul className="mt-2 divide-y divide-ink/10">
        {order.items.map((i) => (
          <li key={i.product_id} className="flex justify-between gap-4 py-2"><span>{i.qty > 1 ? `${i.qty} × ` : ""}{i.name}</span><span className="tabular-nums text-slate2">{fmt(i.expected_live_on)}</span></li>
        ))}
      </ul>

      <h2 className="mt-8 text-xl font-bold text-ink">{t("track.msgs")}</h2>
      <div className="mt-3 space-y-2 rounded-2xl bg-leaf-wash p-4">
        <AnimatePresence initial={false}>
          {order.notifications.map((n, i) => (
            <motion.div key={i} layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="max-w-[90%] rounded-xl rounded-tl-sm bg-white px-3 py-2 shadow-sm">
              <p>{n.text}</p><p className="mt-0.5 text-right text-xs text-slate2">{n.channel === "whatsapp" ? "WhatsApp" : "In app"} · {fmt(n.date)}</p>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {!active && (
        <Btn variant="ghost" className="mt-6" busy={busy} icon={<FastForward className="h-4 w-4" aria-hidden />}
          onClick={async () => { setBusy(true); const o = await guard(() => api.advance(order.order_id)); setBusy(false); if (o) setOrder(o); }}>{t("track.advance")}</Btn>
      )}
    </section>
  );
}
