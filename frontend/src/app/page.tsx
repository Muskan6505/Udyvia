"use client";
import { useEffect } from "react";
import { Advisor } from "@/components/Advisor";
import { Consent } from "@/components/Consent";
import { Kyc } from "@/components/Kyc";
import { QuoteScreen } from "@/components/Quote";
import { Shell } from "@/components/Shell";
import { Sign } from "@/components/Sign";
import { Track } from "@/components/Track";
import { Welcome } from "@/components/Welcome";
import { StoreProvider, useStore } from "@/lib/store";

function Screen() {
  const { step, lang } = useStore();
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);
  return { welcome: <Welcome />, advisor: <Advisor />, quote: <QuoteScreen />, consent: <Consent />, kyc: <Kyc />, sign: <Sign />, track: <Track /> }[step];
}

export default function Page() {
  return (
    <StoreProvider>
      <Shell><Screen /></Shell>
    </StoreProvider>
  );
}
