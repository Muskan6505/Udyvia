"use client";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronUp } from "lucide-react";
import { useState } from "react";
import { useStore } from "@/lib/store";
import { CountUp, Stamp, inr } from "./ui";

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <motion.div layout initial={{ opacity: 0, clipPath: "inset(0 100% 0 0)" }} animate={{ opacity: 1, clipPath: "inset(0 0% 0 0)" }}
      transition={{ duration: 0.45, ease: "easeOut" }} className="flex items-baseline justify-between gap-4 py-1">
      <dt className="text-sm text-slate2">{k}</dt>
      <dd className="text-right font-medium">{children}</dd>
    </motion.div>
  );
}

function SlipBody() {
  const { t, slots, quote, kycResult, order } = useStore();
  const filled = slots && (slots.business_type || slots.employees || slots.sites || slots.city || slots.has_gstin !== null);
  const included = quote?.lines.filter((l) => l.included) ?? [];
  const stampFor = () => {
    if (order?.status === "ACTIVATED") return <Stamp text="LIVE" tone="leaf" />;
    if (!kycResult) return null;
    const m = { PASS: ["VERIFIED", "leaf"], NEEDS_FIX: ["FIX", "haldi"], MANUAL_REVIEW: ["IN REVIEW", "ink"], RESTRICTED: ["LIMITED", "haldi"] } as const;
    const [txt, tone] = m[kycResult.decision];
    return <Stamp key={kycResult.decision} text={txt} tone={tone} />;
  };
  return (
    <div className="relative">
      <div className="flex items-start justify-between">
        <h2 className="text-lg font-bold text-ink">{t("slip.title")}</h2>
        {order && <span className="text-xs font-semibold text-slate2">{order.order_id}</span>}
      </div>
      {stampFor() && <div className="mt-2 flex h-12 items-center justify-end pr-1">{stampFor()}</div>}
      {!filled && <p className="mt-6 text-sm text-slate2">{t("slip.empty")}</p>}
      {filled && slots && (
        <dl className="mt-4 border-t-2 border-dashed border-ink/15 pt-3">
          {slots.business_type && <Row k={t("slot.business_type")}>{slots.business_type}</Row>}
          {slots.employees != null && <Row k={t("slot.employees")}>{slots.employees}</Row>}
          {slots.sites != null && <Row k={t("slot.sites")}>{slots.sites}</Row>}
          {slots.city && <Row k={t("slot.city")}>{slots.city}</Row>}
          {slots.has_gstin !== null && <Row k={t("slot.has_gstin")}>{slots.has_gstin ? t("gst.yes") : t("gst.no")}</Row>}
        </dl>
      )}
      <AnimatePresence>
        {quote && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mt-4 border-t-2 border-dashed border-ink/15 pt-3">
            <p className="mb-1 text-sm font-semibold text-ink-soft">{t("slip.bundle")}</p>
            <ul>
              <AnimatePresence initial={false}>
                {included.map((l) => (
                  <motion.li key={l.product_id} layout initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, height: 0 }}
                    className="flex justify-between gap-3 py-0.5 text-sm">
                    <span>{l.qty > 1 ? `${l.qty} × ` : ""}{l.product_name}</span>
                    <span className="tabular-nums text-slate2">{inr(l.line_monthly)}</span>
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
            <div className="mt-3 flex items-end justify-between border-t-2 border-ink pt-3">
              <span className="text-sm font-semibold">{t("quote.total")}</span>
              <span className="text-right">
                <CountUp value={quote.monthly_total} className="font-display text-3xl font-extrabold tabular-nums text-ink" />
                <span className="block text-xs text-slate2">{t("monthly")}</span>
              </span>
            </div>
            {quote.setup_total > 0 && <p className="mt-1 text-right text-xs text-slate2">+ {inr(quote.setup_total)} {t("setup").toLowerCase()}</p>}
          </motion.div>
        )}
      </AnimatePresence>
      <div className="h-5" />
    </div>
  );
}

export function Slip() {
  return (
    <aside className="sticky top-24 hidden self-start lg:block" aria-label="Your slip">
      <div className="slip rounded-t-2xl px-6 pt-6 shadow-slip"><SlipBody /></div>
    </aside>
  );
}

/** On phones the slip folds into a bottom bar that shows the running total and opens on tap. */
export function MobileSlip() {
  const { quote, t, slots } = useStore();
  const [open, setOpen] = useState(false);
  if (!quote && !slots?.business_type) return null;
  return (
    <div className="fixed inset-x-0 bottom-0 z-30 lg:hidden">
      <AnimatePresence>
        {open && (
          <motion.div initial={{ y: "100%" }} animate={{ y: 0 }} exit={{ y: "100%" }} transition={{ type: "spring", stiffness: 380, damping: 36 }}
            className="slip max-h-[70vh] overflow-y-auto rounded-t-2xl px-5 pt-5 shadow-slip"><SlipBody /></motion.div>
        )}
      </AnimatePresence>
      <button onClick={() => setOpen(!open)} aria-expanded={open}
        className="flex w-full items-center justify-between bg-ink px-5 py-3 text-white">
        <span className="font-semibold">{t("slip.title")}</span>
        <span className="flex items-center gap-2">
          {quote && <CountUp value={quote.monthly_total} className="font-display text-lg font-bold tabular-nums" />}
          <ChevronUp className={`h-5 w-5 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
        </span>
      </button>
    </div>
  );
}
