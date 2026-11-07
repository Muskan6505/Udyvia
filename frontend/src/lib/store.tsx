"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError } from "./api";
import { translate } from "./i18n";
import type { Lang, Order, Quote, Slots, Step, KycResult, DocType, User } from "./types";

export interface Msg { id: number; role: "bot" | "user"; text: string }

interface Store {
  lang: Lang; setLang: (l: Lang) => void; t: (k: string, v?: Record<string, string | number>) => string;
  step: Step; go: (s: Step) => void; reset: () => void;
  msgs: Msg[]; slots: Slots | null; ready: boolean; typing: boolean; basicMode: boolean; why: string;
  say: (text: string, display?: string) => Promise<void>; startChat: () => Promise<void>;
  quote: Quote | null; toggleAddon: (pid: string, on: boolean) => Promise<void>; quoteBusy: boolean;
  kycSession: string | null; kycResult: KycResult | null; kycDocs: Partial<Record<DocType, string>>;
  setKycResult: (r: KycResult | null) => void; setKycDocs: (d: Partial<Record<DocType, string>>) => void; setKycSession: (s: string | null) => void;
  setQuote: (q: Quote) => void;
  order: Order | null; setOrder: (o: Order | null) => void;
  voiceEnabled: boolean; voiceAuto: boolean; setVoiceAuto: (v: boolean) => void; playingId: number | null; speak: (id: number, text: string) => Promise<void>; stopSpeech: () => void;
  user: User | null; hasProgress: boolean; signedIn: (u: User) => Promise<void>; signOut: () => Promise<void>; deleteAccount: () => Promise<void>;
  resume: () => Promise<void>; notice: string | null;
  error: string | null; setError: (e: string | null) => void; guard: <T>(fn: () => Promise<T>) => Promise<T | undefined>;
}
const Ctx = createContext<Store | null>(null);
export const useStore = () => {
  const c = useContext(Ctx);
  if (!c) throw new Error("useStore outside provider");
  return c;
};

export function StoreProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>("en");
  const [step, setStep] = useState<Step>("welcome");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [slots, setSlots] = useState<Slots | null>(null);
  const [ready, setReady] = useState(false);
  const [typing, setTyping] = useState(false);
  const [basicMode, setBasic] = useState(false);
  const [why, setWhy] = useState("");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [quoteBusy, setQuoteBusy] = useState(false);
  const [kycSession, setKycSession] = useState<string | null>(null);
  const [kycResult, setKycResult] = useState<KycResult | null>(null);
  const [kycDocs, setKycDocs] = useState<Partial<Record<DocType, string>>>({});
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [hasProgress, setHasProgress] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [voiceAuto, setVoiceAuto] = useState(false);
  const [playingId, setPlayingId] = useState<number | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const autoRef = useRef(false);
  autoRef.current = voiceAuto;
  const sid = useRef<string | undefined>(undefined);
  const mid = useRef(0);
  const t = useCallback((k: string, v?: Record<string, string | number>) => translate(lang, k, v), [lang]);

  const guard = useCallback(async <T,>(fn: () => Promise<T>) => {
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : translate(lang, "err.generic"));
    }
  }, [lang]);

  useEffect(() => { if (step !== "consent" && step !== "kyc") setNotice(null); }, [step]);

  const wipe = useCallback(() => {
    sid.current = undefined;
    setMsgs([]); setSlots(null); setReady(false); setQuote(null); setWhy(""); setKycSession(null); setKycResult(null);
    setKycDocs({}); setOrder(null); setError(null); setNotice(null);
  }, []);

  // A returning visitor with a valid session cookie is recognised straight away.
  useEffect(() => {
    api.me().then((u) => { setUser(u); if (u.role === "customer") api.resume().then((r) => setHasProgress(!r.fresh)).catch(() => {}); }).catch(() => {});
  }, []);

  useEffect(() => { api.voiceStatus().then((v) => setVoiceEnabled(v.enabled)).catch(() => {}); }, []);

  const stopSpeech = useCallback(() => {
    const a = audio.current;
    if (a) { a.pause(); if (a.src.startsWith("blob:")) URL.revokeObjectURL(a.src); audio.current = null; }
    setPlayingId(null);
  }, []);

  const speak = useCallback(async (id: number, text: string) => {
    stopSpeech();
    setPlayingId(id);                                               // show the sound bars right away, while the audio loads
    const clip = text.length > 600 ? text.slice(0, text.lastIndexOf(".", 600) + 1 || 600) : text;
    const blob = await guard(() => api.speak(clip, lang));
    if (!blob) { setPlayingId(null); return; }
    const a = new Audio(URL.createObjectURL(blob));
    audio.current = a;
    a.onended = () => stopSpeech();
    a.onerror = () => stopSpeech();
    try { await a.play(); } catch { stopSpeech(); }                 // the browser may block autoplay until the person taps something
  }, [lang, guard, stopSpeech]);

  useEffect(() => { stopSpeech(); }, [lang, stopSpeech]);

  const push = (role: Msg["role"], text: string) => {
    const id = ++mid.current;
    setMsgs((m) => [...m, { id, role, text }]);
    if (role === "bot" && autoRef.current) setTimeout(() => speakRef.current?.(id, text), 0);
  };
  const speakRef = useRef<typeof speak | null>(null);
  speakRef.current = speak;

  const apply = (r: Awaited<ReturnType<typeof api.advisor>>) => {
    sid.current = r.session_id;
    setSlots(r.slots);
    setReady(r.ready);
    setBasic(r.source === "offline");
    if (r.quote) { setQuote(r.quote); setWhy(r.reply); }
    push("bot", r.reply);
  };

  const startChat = useCallback(async () => {
    if (sid.current) return;
    setTyping(true);
    await guard(async () => apply(await api.advisor("", lang)));
    setTyping(false);
  }, [lang, guard]); // eslint-disable-line

  const say = useCallback(async (text: string, display?: string) => {
    push("user", display ?? text);
    setTyping(true);
    await new Promise((r) => setTimeout(r, 450));      // a beat, so the reply feels like a person answering
    await guard(async () => apply(await api.advisor(text, lang, sid.current)));
    setTyping(false);
  }, [lang, guard]); // eslint-disable-line

  const resume = useCallback(async () => {
    const r = await guard(() => api.resume());
    if (!r) return;
    wipe();
    sid.current = r.session_id ?? undefined;
    if (r.lang !== lang) setLang(r.lang);
    setSlots(r.slots); setReady(!!r.quote); setBasic(false);
    if (r.quote) { setQuote(r.quote); setWhy(""); }
    setKycSession(r.kyc_session_id); setKycResult(r.kyc_result); setOrder(r.order);
    if (!r.fresh && user) push("bot", translate(r.lang, "resume.back", { name: user.name.split(" ")[0] }) + (r.reply ? " " + r.reply : ""));
    if (r.note === "kyc_expired") setNotice(translate(r.lang, "resume.kycExpired"));
    setStep(r.fresh ? "advisor" : r.step);
  }, [guard, wipe, lang, user]); // eslint-disable-line

  const signedIn = useCallback(async (u: User) => {
    setUser(u);
    if (u.role === "backoffice") { window.location.href = "/office"; return; }
    const r = await api.resume().catch(() => null);
    const progress = !!r && !r.fresh;
    setHasProgress(progress);
    if (progress) setStep("welcome");        // returning: offer "continue where I left off"
    else await resume();                     // brand new: straight into the first question
  }, [resume]);

  const signOut = useCallback(async () => {
    await api.logout().catch(() => {});
    stopSpeech(); wipe(); setUser(null); setHasProgress(false); setStep("welcome");
  }, [wipe, stopSpeech]);

  const deleteAccount = useCallback(async () => {
    if (!window.confirm(translate(lang, "me.deleteConfirm"))) return;
    await guard(() => api.deleteAccount());
    stopSpeech(); wipe(); setUser(null); setHasProgress(false); setStep("welcome");
  }, [guard, wipe, stopSpeech, lang]);

  const toggleAddon = useCallback(async (pid: string, on: boolean) => {
    if (!quote) return;
    setQuoteBusy(true);
    const q = await guard(() => api.patchAddon(quote.quote_id, pid, on));
    if (q) setQuote(q);
    setQuoteBusy(false);
  }, [quote, guard]);

  const reset = useCallback(() => {
    if (kycSession) api.withdraw(kycSession).catch(() => {});
    if (user) api.restart().catch(() => {});          // the saved progress is cleared too, not just the screen
    stopSpeech(); wipe(); setHasProgress(false); setStep("welcome");
  }, [kycSession, stopSpeech, wipe, user]);

  const value = useMemo<Store>(() => ({
    lang, setLang, t, step, go: setStep, reset, msgs, slots, ready, typing, basicMode, why, say, startChat,
    quote, setQuote, toggleAddon, quoteBusy, kycSession, setKycSession, kycResult, setKycResult, kycDocs, setKycDocs,
    order, setOrder, error, setError, guard, user, hasProgress, signedIn, signOut, deleteAccount, resume, notice, voiceEnabled, voiceAuto, setVoiceAuto, playingId, speak, stopSpeech,
  }), [lang, t, step, reset, msgs, slots, ready, typing, basicMode, why, say, startChat, quote, toggleAddon, quoteBusy,
       kycSession, kycResult, kycDocs, order, error, guard, user, hasProgress, signedIn, signOut, deleteAccount, resume, notice, voiceEnabled, voiceAuto, playingId, speak, stopSpeech]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
