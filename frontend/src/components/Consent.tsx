"use client";
import { Clock, FileText, Target, Undo2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";
import { Btn } from "./ui";

type Notice = { purpose: string; data_used: string[]; retention: string; withdraw: string };

export function Consent() {
  const { t, guard, setKycSession, go, kycSession } = useStore();
  const [n, setN] = useState<Notice | null>(null);
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => { guard(() => api.consentNotice()).then((x) => x && setN(x)); }, [guard]);

  const rows = n && [
    { icon: Target, h: t("consent.purpose"), b: n.purpose },
    { icon: FileText, h: t("consent.data"), b: n.data_used.join(", ") },
    { icon: Clock, h: t("consent.retention"), b: n.retention },
    { icon: Undo2, h: t("consent.withdraw"), b: n.withdraw },
  ];
  const go2 = async () => {
    setBusy(true);
    if (!kycSession) { const r = await guard(() => api.consent()); if (r) setKycSession(r.kyc_session_id); else { setBusy(false); return; } }
    setBusy(false);
    go("kyc");
  };
  return (
    <section className="max-w-2xl">
      <h1 className="text-3xl font-extrabold text-ink">{t("consent.title")}</h1>
      <dl className="mt-6 divide-y divide-ink/10">
        {rows?.map(({ icon: Icon, h, b }) => (
          <div key={h} className="flex gap-4 py-4">
            <Icon className="mt-1 h-5 w-5 shrink-0 text-ink" aria-hidden />
            <div><dt className="font-display font-bold text-ink">{h}</dt><dd className="mt-0.5 text-slate2">{b}</dd></div>
          </div>
        ))}
      </dl>
      <label className="mt-6 flex cursor-pointer items-start gap-3 rounded-xl bg-white p-4 shadow-sm">
        <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="mt-1 h-5 w-5 accent-[#1E2A78]" />
        <span className="font-medium">{t("consent.agree")}</span>
      </label>
      <Btn className="mt-5" disabled={!agree || !n} busy={busy} onClick={go2}>{t("consent.continue")}</Btn>
    </section>
  );
}
