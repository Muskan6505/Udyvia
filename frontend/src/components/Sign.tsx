"use client";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";
import { Btn, inr } from "./ui";

export function Sign() {
  const { t, lang, guard, quote, kycSession, order, setOrder, go } = useStore();
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [otp, setOtp] = useState("");
  const [method, setMethod] = useState("upi");
  const [fail, setFail] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (order && order.status === "INSTALL_SCHEDULED") { const id = setTimeout(() => go("track"), 900); return () => clearTimeout(id); } }, [order, go]);

  const run = async (fn: () => Promise<any>) => { setBusy(true); const o = await guard(fn); setBusy(false); if (o) setOrder(o); };
  const stage = !order ? 0 : order.status === "KYC_VERIFIED" ? 1 : order.status === "ESIGNED" ? 2 : 3;
  const labels = ["Order", "Sign", "Pay"];
  const input = "w-full rounded-xl border-2 border-ink/20 bg-white px-4 py-3 text-[17px] outline-none focus:border-ink";

  return (
    <section className="max-w-xl">
      <h1 className="text-3xl font-extrabold text-ink">{t("sign.title")}</h1>
      <ol className="mt-5 flex items-center gap-2" aria-label="Steps">
        {labels.map((l, i) => (
          <li key={l} className="flex flex-1 items-center gap-2">
            <span className={`flex h-7 w-7 items-center justify-center rounded-full text-sm font-bold transition-colors ${i < stage ? "bg-leaf text-white" : i === stage ? "bg-ink text-white" : "bg-ink/10 text-slate2"}`}>{i < stage ? "✓" : i + 1}</span>
            <span className={`text-sm font-semibold ${i === stage ? "text-ink" : "text-slate2"}`}>{l}</span>
            {i < 2 && <span className="h-0.5 flex-1 overflow-hidden rounded bg-ink/10"><motion.span className="block h-full bg-leaf" animate={{ width: i < stage ? "100%" : "0%" }} /></span>}
          </li>
        ))}
      </ol>

      <div className="mt-6 space-y-4">
        {stage === 0 && (<>
          <label className="block"><span className="mb-1 block font-medium">{t("sign.phone")}</span>
            <input className={input} inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+91" /></label>
          <Btn busy={busy} onClick={() => quote && kycSession && run(() => api.createOrder(quote.quote_id, kycSession, lang, phone))}>{t("sign.create")}</Btn>
        </>)}

        {stage === 1 && (<>
          <label className="block"><span className="mb-1 block font-medium">{t("sign.name")}</span>
            <input className={input} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></label>
          <label className="block"><span className="mb-1 block font-medium">{t("sign.otp")}</span>
            <input className={`${input} tracking-[0.4em]`} inputMode="numeric" maxLength={6} value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))} />
            <span className="mt-1 block text-sm text-slate2">{t("sign.otpHint")}</span></label>
          <Btn busy={busy} disabled={name.trim().length < 2 || otp.length !== 6} onClick={() => order && run(() => api.esign(order.order_id, name, otp))}>{t("sign.sign")}</Btn>
        </>)}

        {stage >= 2 && order && (<>
          <div className="rounded-2xl bg-ink p-5 text-white">
            <p className="text-sm text-white/70">{t("sign.due")}</p>
            <p className="font-display text-4xl font-extrabold tabular-nums">{inr(order.amount_due)}</p>
            <p className="text-sm text-white/70">{t("sign.dueNote")}</p>
          </div>
          {order.payment.last_result === "failed" && (
            <motion.div initial={{ x: -8 }} animate={{ x: [0, -8, 8, -5, 5, 0] }} transition={{ duration: 0.4 }} role="alert"
              className="rounded-xl bg-chilli-wash px-4 py-3 text-chilli"><b>{t("track.failed")}.</b> {order.help}</motion.div>
          )}
          <fieldset><legend className="mb-1 font-medium">{t("sign.method")}</legend>
            <div className="flex gap-2">{["upi", "card", "netbanking"].map((m) => (
              <button key={m} onClick={() => setMethod(m)} aria-pressed={method === m}
                className={`rounded-full border-2 px-4 py-1.5 font-semibold capitalize ${method === m ? "border-ink bg-ink text-white" : "border-ink/20 text-ink"}`}>{m === "upi" ? "UPI" : m}</button>))}
            </div></fieldset>
          <label className="flex items-center gap-2 text-sm text-slate2"><input type="checkbox" checked={fail} onChange={(e) => setFail(e.target.checked)} className="h-4 w-4 accent-[#1E2A78]" />{t("sign.simFail")}</label>
          <Btn busy={busy || order.status === "INSTALL_SCHEDULED"} onClick={() => run(() => api.pay(order.order_id, method, fail))}>
            {order.payment.last_result === "failed" ? t("sign.retry") : `${t("sign.pay")} ${inr(order.amount_due)}`}</Btn>
        </>)}
      </div>
    </section>
  );
}
