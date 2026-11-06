"use client";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, FileImage, ShieldAlert, UserSearch, Wrench } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";
import { DOC_TYPES, type DocType, type Finding } from "@/lib/types";
import { Btn } from "./ui";

function DocSlot({ doc, url, flag, scanning, onFile, label, dropLabel, replaceLabel }: {
  doc: DocType; url?: string; flag?: Finding; scanning: boolean; onFile: (f: File) => void; label: string; dropLabel: string; replaceLabel: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <div>
      <p className="mb-1.5 font-display font-bold text-ink">{label}</p>
      <div role="button" tabIndex={0} aria-label={label}
        onClick={() => input.current?.click()} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files?.[0]; if (f) onFile(f); }}
        className={`relative flex aspect-[4/3] cursor-pointer items-center justify-center overflow-hidden rounded-xl border-2 border-dashed transition-colors
          ${flag ? "border-chilli bg-chilli-wash" : over ? "border-ink bg-ink-wash" : url ? "border-leaf/60 bg-white" : "border-ink/25 bg-white hover:border-ink"}`}>
        {url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={url} alt={label} className="h-full w-full object-cover object-top" />
        ) : (
          <span className="flex flex-col items-center gap-2 px-4 text-center text-sm text-slate2"><FileImage className="h-7 w-7 text-ink-soft" aria-hidden />{dropLabel}</span>
        )}
        {url && <span className="absolute bottom-2 right-2 rounded-full bg-ink/85 px-3 py-1 text-xs font-semibold text-white">{replaceLabel}</span>}
        {scanning && url && (
          <motion.div className="scanline absolute inset-x-0 h-16" initial={{ top: "-20%" }} animate={{ top: "100%" }}
            transition={{ duration: 1.1, repeat: Infinity, ease: "linear" }} aria-hidden />
        )}
        <input ref={input} type="file" accept="image/png,image/jpeg" className="sr-only" tabIndex={-1}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
      </div>
      {flag && <p className="mt-1.5 text-sm font-medium text-chilli">{flag.message}</p>}
    </div>
  );
}

export function Kyc() {
  const { t, guard, kycSession, setKycSession, kycResult, setKycResult, kycDocs, setKycDocs, quote, setQuote, go } = useStore();
  const [samples, setSamples] = useState<{ id: string; label: string; expected: string }[]>([]);
  const [scanning, setScanning] = useState(false);
  const [waived, setWaived] = useState(false);
  const [busy, setBusy] = useState(false);
  const docsRef = useRef(kycDocs);
  docsRef.current = kycDocs;
  useEffect(() => { api.samples().then(setSamples).catch(() => {}); }, []);

  const uploadOne = async (sid: string, doc: DocType, blob: Blob, name: string) => {
    const ok = await guard(() => api.upload(sid, doc, blob, name));
    if (ok) {
      const old = docsRef.current[doc];
      if (old?.startsWith("blob:")) URL.revokeObjectURL(old);
      setKycDocs({ ...docsRef.current, [doc]: URL.createObjectURL(blob) });
      docsRef.current = { ...docsRef.current, [doc]: "x" };
    }
    setKycResult(null);
  };
  const onFile = async (doc: DocType, f: File) => { if (kycSession) await uploadOne(kycSession, doc, f, f.name); };

  const loadSample = async (id: string) => {
    setBusy(true);
    if (kycSession) await api.withdraw(kycSession).catch(() => {});      // a fresh session per specimen set
    const s = await guard(() => api.consent());
    if (!s) { setBusy(false); return; }
    setKycSession(s.kyc_session_id);
    Object.values(docsRef.current).forEach((u) => u?.startsWith("blob:") && URL.revokeObjectURL(u));
    setKycDocs({}); docsRef.current = {}; setKycResult(null);
    for (const d of DOC_TYPES) {
      const blob = await api.sampleDoc(id, d);
      if (blob) await uploadOne(s.kyc_session_id, d, blob, `${id}_${d}.png`);
    }
    setBusy(false);
  };

  const check = async () => {
    if (!kycSession) return;
    setBusy(true); setScanning(true);
    const [res] = await Promise.all([guard(() => api.validate(kycSession, waived)), new Promise((r) => setTimeout(r, 1800))]);
    setScanning(false);
    if (res) setKycResult(res);
    setBusy(false);
  };

  const proceed = async () => {
    if (!quote || !kycSession) return;
    setBusy(true);
    const q = await guard(() => api.applyKyc(quote.quote_id, kycSession));
    setBusy(false);
    if (q) { setQuote(q); go("sign"); }
  };

  const flags = new Map<string, Finding>();
  kycResult?.findings.filter((f) => f.severity === "fix" && f.doc).forEach((f) => !flags.has(f.doc!) && flags.set(f.doc!, f));
  const uploaded = Object.keys(kycDocs).length;
  const d = kycResult?.decision;
  const head = d && {
    PASS: { Icon: CheckCircle2, c: "text-leaf", bg: "bg-leaf-wash", h: t("kyc.pass"), m: t("kyc.passMsg") },
    NEEDS_FIX: { Icon: Wrench, c: "text-haldi-deep", bg: "bg-haldi-wash", h: t("kyc.fix"), m: t("kyc.fixMsg") },
    MANUAL_REVIEW: { Icon: UserSearch, c: "text-ink", bg: "bg-ink-wash", h: t("kyc.review"), m: t("kyc.reviewMsg") },
    RESTRICTED: { Icon: ShieldAlert, c: "text-haldi-deep", bg: "bg-haldi-wash", h: t("kyc.restricted"), m: t("kyc.restrictedMsg") },
  }[d];
  const tone = (s: Finding["severity"]) => ({ fix: "border-haldi", review: "border-ink", restrict: "border-haldi", info: "border-ink/20" })[s];

  return (
    <section>
      <h1 className="text-3xl font-extrabold text-ink">{t("kyc.title")}</h1>
      <p className="mt-2 max-w-xl text-slate2">{t("kyc.sub")}</p>

      <div className="mt-6 grid gap-5 sm:grid-cols-2">
        {DOC_TYPES.map((doc) => (
          <DocSlot key={doc} doc={doc} url={kycDocs[doc]} flag={flags.get(doc)} scanning={scanning} onFile={(f) => onFile(doc, f)}
            label={t(`kyc.${doc}`)} dropLabel={t("kyc.drop")} replaceLabel={t("kyc.replace")} />
        ))}
      </div>
      {!kycDocs.udyam_certificate && (
        <label className="mt-4 flex items-center gap-2 text-sm text-slate2">
          <input type="checkbox" checked={waived} onChange={(e) => setWaived(e.target.checked)} className="h-4 w-4 accent-[#1E2A78]" />{t("kyc.noUdyam")}
        </label>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Btn onClick={check} busy={busy && scanning} disabled={busy || uploaded === 0}>{scanning ? t("kyc.checking") : kycResult ? t("kyc.recheck") : t("kyc.check")}</Btn>
      </div>

      <AnimatePresence>
        {kycResult && head && (
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-6">
            <div className={`flex items-start gap-3 rounded-2xl p-5 ${head.bg}`}>
              <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 500, damping: 18, delay: 0.1 }}>
                <head.Icon className={`h-8 w-8 ${head.c}`} aria-hidden />
              </motion.span>
              <div><h2 className={`text-xl font-extrabold ${head.c}`}>{head.h}</h2><p className="mt-0.5 text-slate2">{head.m}</p></div>
            </div>
            <ul className="mt-4 space-y-2">
              {kycResult.findings.map((f, i) => (
                <motion.li key={i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.15 + i * 0.07 }}
                  className={`border-l-4 bg-white px-4 py-2.5 ${tone(f.severity)}`}>
                  <p className={f.severity === "info" ? "text-slate2" : "font-medium"}>{f.message}</p>
                  {f.doc && <p className="text-xs text-slate2">{t("kyc.forDoc")} {t(`kyc.${f.doc}`)}</p>}
                </motion.li>
              ))}
            </ul>
            {Object.keys(kycResult.autofill).length > 0 && (d === "PASS" || d === "RESTRICTED") && (
              <div className="mt-4 rounded-xl border border-ink/10 bg-white p-4 text-sm">
                <p className="mb-1 font-semibold text-ink-soft">{t("kyc.autofill")}</p>
                <p className="font-medium">{kycResult.autofill.trade_name}</p>
                <p className="text-slate2">{kycResult.autofill.address}</p>
              </div>
            )}
            {(d === "PASS" || d === "RESTRICTED") && <Btn className="mt-5" busy={busy} onClick={proceed}>{t("kyc.continue")}</Btn>}
          </motion.div>
        )}
      </AnimatePresence>

      {samples.length > 0 && (
        <div className="mt-10 border-t-2 border-dashed border-ink/15 pt-5">
          <h2 className="font-display text-lg font-bold text-ink">{t("kyc.demo")}</h2>
          <p className="text-sm text-slate2">{t("kyc.demoSub")}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {samples.map((s) => (
              <button key={s.id} disabled={busy} onClick={() => loadSample(s.id)} title={s.label}
                className="rounded-xl border-2 border-ink/15 bg-white px-3 py-2 text-left text-sm transition-colors hover:border-ink disabled:opacity-50">
                <span className="block font-semibold text-ink">{s.id}</span><span className="text-slate2">{s.label}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
