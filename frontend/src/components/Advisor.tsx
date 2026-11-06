"use client";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useStore } from "@/lib/store";
import { Speaker } from "./Speaker";
import { Btn, Switch } from "./ui";

const ORDER = ["business_type", "employees", "sites", "city", "has_gstin"] as const;

type Chip = { label: string; send: string };
function chipsFor(slot: string, lang: "en" | "hi"): Chip[] {
  const hi = lang === "hi";
  switch (slot) {
    case "business_type": return [
      { label: hi ? "किराना दुकान" : "Kirana store", send: "Kirana store" }, { label: hi ? "क्लिनिक" : "Dental clinic", send: "Dental clinic" },
      { label: hi ? "टेक्सटाइल यूनिट" : "Textile unit", send: "Textile unit" }, { label: hi ? "रेस्टोरेंट चेन" : "Restaurant chain", send: "Restaurant chain" }];
    case "employees": return ["2", "5", "10", "25", "60"].map((n) => ({ label: n, send: n }));
    case "sites": return ["1", "2", "5", "10"].map((n) => ({ label: n, send: n }));
    case "city": return ["Mumbai", "Pune", "Indore", "Surat", "Chennai", "Lucknow"].map((c) => ({ label: c, send: c }));
    case "has_gstin": return [{ label: hi ? "हाँ" : "Yes", send: "yes" }, { label: hi ? "नहीं" : "No", send: "no" }];
    case "needs": return [
      { label: hi ? "बिलिंग / POS" : "Billing / POS", send: "billing" }, { label: "CCTV", send: "cctv" }, { label: "Wi-Fi", send: "wifi" },
      { label: hi ? "बिज़नेस ईमेल" : "Business email", send: "email" }, { label: hi ? "नहीं, धन्यवाद" : "No thanks", send: "no" }];
    default: return [];
  }
}

function Typing({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-1 rounded-2xl rounded-bl-sm bg-white px-4 py-3 shadow-sm" role="status" aria-label={label}>
      {[0, 1, 2].map((i) => (
        <motion.span key={i} className="h-2 w-2 rounded-full bg-ink-soft" animate={{ y: [0, -5, 0], opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.15 }} />
      ))}
    </div>
  );
}

export function Advisor() {
  const { t, lang, msgs, slots, ready, typing, say, startChat, go, quote, basicMode, voiceEnabled, voiceAuto, setVoiceAuto, stopSpeech } = useStore();
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { startChat(); }, [startChat]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs, typing, ready]);

  const expecting = !slots ? "business_type" : ORDER.find((k) => slots[k] === null) ?? (slots.asked_needs ? null : "needs");
  const chips = !typing && expecting ? chipsFor(expecting, lang) : [];
  const done = slots ? ORDER.filter((k) => slots[k] !== null).length : 0;

  const submit = () => { const v = text.trim(); if (v && !typing) { setText(""); say(v); } };

  return (
    <section className="flex min-h-[70vh] flex-col">
      <div className="mb-4 flex items-center gap-3" aria-label={`${done} / ${ORDER.length}`}>
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-ink/10">
          <motion.div className="h-full rounded-full bg-haldi" animate={{ width: `${(done / ORDER.length) * 100}%` }} transition={{ type: "spring", stiffness: 140, damping: 20 }} />
        </div>
        <span className="text-sm font-semibold tabular-nums text-ink-soft">{done}/{ORDER.length}</span>
      </div>
      {voiceEnabled && (
        <div className="mb-3 flex items-center justify-end gap-3 text-sm font-medium text-ink-soft">
          <span id="auto-voice">{t("voice.auto")}</span>
          <Switch on={voiceAuto} onChange={(v) => { setVoiceAuto(v); if (!v) stopSpeech(); }} label={t("voice.auto")} />
        </div>
      )}
      {basicMode && msgs.length > 0 && <p className="mb-3 text-xs text-slate2">{t("advisor.fallback")}</p>}

      <div className="flex-1 space-y-3" aria-live="polite">
        {msgs.map((m) => (
          <motion.div key={m.id} initial={{ opacity: 0, y: 10, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ type: "spring", stiffness: 420, damping: 30 }}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className="max-w-[85%]">
              <p className={`whitespace-pre-line rounded-2xl px-4 py-3 text-[17px] leading-snug ${
                m.role === "user" ? "rounded-br-sm bg-ink text-white" : "rounded-bl-sm bg-white shadow-sm"}`}>{m.text}</p>
              {m.role === "bot" && <Speaker id={m.id} text={m.text} />}
            </div>
          </motion.div>
        ))}
        {typing && <div className="flex"><Typing label={t("advisor.typing")} /></div>}
        <AnimatePresence>
          {ready && quote && !typing && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="pt-2">
              <Btn onClick={() => go("quote")} icon={<ArrowRight className="h-5 w-5 order-last" aria-hidden />}>{t("advisor.seeQuote")}</Btn>
            </motion.div>
          )}
        </AnimatePresence>
        <div className="h-40 lg:h-24" aria-hidden />
        <div ref={end} />
      </div>

      <div className="sticky bottom-14 mt-4 bg-gradient-to-t from-paper via-paper to-transparent pb-2 pt-4 lg:bottom-0">
        {chips.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {chips.map((c) => (
              <motion.button key={c.label} whileTap={{ scale: 0.94 }} onClick={() => say(c.send, c.label)}
                className="rounded-full border-2 border-ink/20 bg-white px-4 py-1.5 font-semibold text-ink transition-colors hover:border-ink hover:bg-ink-wash">{c.label}</motion.button>
            ))}
          </div>
        )}
        <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="flex gap-2">
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t("advisor.placeholder")} aria-label={t("advisor.placeholder")}
            maxLength={500} className="min-w-0 flex-1 rounded-xl border-2 border-ink/20 bg-white px-4 py-3 text-[17px] outline-none focus:border-ink" />
          <Btn type="submit" disabled={!text.trim() || typing} aria-label={t("advisor.send")} icon={<Send className="h-5 w-5" aria-hidden />}><span className="hidden sm:inline">{t("advisor.send")}</span></Btn>
        </form>
      </div>
    </section>
  );
}
