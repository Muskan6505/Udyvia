"use client";
import { motion } from "framer-motion";
import { useState } from "react";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";
import { Btn } from "./ui";

const field = "w-full rounded-xl border-2 border-ink/20 bg-white px-4 py-3 text-[17px] outline-none focus:border-ink";

export function Auth() {
  const { t, signedIn, guard, go } = useStore();
  const [mode, setMode] = useState<"in" | "up">("up");
  const [f, setF] = useState({ name: "", email: "", phone: "", password: "" });
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    const u = await guard(() => mode === "up"
      ? api.register({ ...f, contact_consent: consent })
      : api.login(f.email, f.password));
    setBusy(false);
    if (u) await signedIn(u);
  };

  return (
    <section className="mx-auto max-w-md py-10">
      <h1 className="text-3xl font-extrabold text-ink">{t(`auth.title.${mode}`)}</h1>
      <p className="mt-2 text-slate2">{t("auth.sub")}</p>
      <div className="mt-6 flex rounded-xl bg-ink-wash p-1" role="tablist">
        {(["up", "in"] as const).map((m) => (
          <button key={m} role="tab" aria-selected={mode === m} onClick={() => setMode(m)}
            className={`relative flex-1 rounded-lg py-2 font-semibold transition-colors ${mode === m ? "text-ink" : "text-ink-soft"}`}>
            {mode === m && <motion.span layoutId="authTab" className="absolute inset-0 rounded-lg bg-white shadow-sm" />}
            <span className="relative">{t(`auth.tab.${m}`)}</span>
          </button>
        ))}
      </div>
      <form onSubmit={submit} className="mt-5 space-y-3">
        {mode === "up" && <input className={field} placeholder={t("auth.name")} aria-label={t("auth.name")} value={f.name} onChange={set("name")} required minLength={2} autoComplete="name" />}
        <input className={field} type="email" placeholder={t("auth.email")} aria-label={t("auth.email")} value={f.email} onChange={set("email")} required autoComplete="email" />
        {mode === "up" && <input className={field} inputMode="numeric" placeholder={t("auth.phone")} aria-label={t("auth.phone")} value={f.phone} onChange={set("phone")} required autoComplete="tel" />}
        <input className={field} type="password" placeholder={t("auth.password")} aria-label={t("auth.password")} value={f.password} onChange={set("password")} required minLength={mode === "up" ? 8 : 1}
          autoComplete={mode === "up" ? "new-password" : "current-password"} />
        {mode === "up" && (
          <label className="flex cursor-pointer items-start gap-3 rounded-xl bg-white p-3 text-sm text-slate2">
            <input type="checkbox" className="mt-0.5 h-5 w-5 accent-[#1E2A78]" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            <span>{t("auth.consent")}</span>
          </label>
        )}
        <Btn type="submit" busy={busy} className="w-full text-lg">{t(`auth.submit.${mode}`)}</Btn>
      </form>
      <p className="mt-4 text-xs text-slate2">{t("auth.privacy")}</p>
      <Btn variant="quiet" className="mt-2" onClick={() => go("welcome")}>←</Btn>
    </section>
  );
}
