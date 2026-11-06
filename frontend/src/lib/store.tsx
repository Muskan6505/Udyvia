"use client";
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError } from "./api";
import { translate } from "./i18n";
import type { Lang, Order, Quote, Slots, Step, KycResult, DocType } from "./types";

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

  const push = (role: Msg["role"], text: string) => setMsgs((m) => [...m, { id: ++mid.current, role, text }]);

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

  const toggleAddon = useCallback(async (pid: string, on: boolean) => {
    if (!quote) return;
    setQuoteBusy(true);
    const q = await guard(() => api.patchAddon(quote.quote_id, pid, on));
    if (q) setQuote(q);
    setQuoteBusy(false);
  }, [quote, guard]);

  const reset = useCallback(() => {
    if (kycSession) api.withdraw(kycSession).catch(() => {});
    sid.current = undefined;
    setMsgs([]); setSlots(null); setReady(false); setQuote(null); setWhy(""); setKycSession(null); setKycResult(null);
    setKycDocs({}); setOrder(null); setError(null); setStep("welcome");
  }, [kycSession]);

  const value = useMemo<Store>(() => ({
    lang, setLang, t, step, go: setStep, reset, msgs, slots, ready, typing, basicMode, why, say, startChat,
    quote, setQuote, toggleAddon, quoteBusy, kycSession, setKycSession, kycResult, setKycResult, kycDocs, setKycDocs,
    order, setOrder, error, setError, guard,
  }), [lang, t, step, reset, msgs, slots, ready, typing, basicMode, why, say, startChat, quote, toggleAddon, quoteBusy,
       kycSession, kycResult, kycDocs, order, error, guard]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
