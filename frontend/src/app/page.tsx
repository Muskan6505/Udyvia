"use client";
import { useEffect } from "react";
import { Auth } from "@/components/Auth";
import { Advisor } from "@/components/Advisor";
import { Consent } from "@/components/Consent";
import { Kyc } from "@/components/Kyc";
import { QuoteScreen } from "@/components/Quote";
import { Shell } from "@/components/Shell";
import { Sign } from "@/components/Sign";
import { Track } from "@/components/Track";
import { Welcome } from "@/components/Welcome";
import { StoreProvider, useStore } from "@/lib/store";
import type { Step } from "@/lib/types";

/** Each step's screen is created for that step and handed to the transition wrapper, so a screen that is
 *  animating out keeps showing itself instead of turning into the next one (which would remount and
 *  wipe whatever the person had typed). */
const screenFor = (step: Step) =>
  ({ welcome: <Welcome />, auth: <Auth />, advisor: <Advisor />, quote: <QuoteScreen />, consent: <Consent />, kyc: <Kyc />, sign: <Sign />, track: <Track /> })[step];

function LangSync() {
  const { lang } = useStore();
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);
  return null;
}

export default function Page() {
  return (
    <StoreProvider>
      <LangSync />
      <Shell>{screenFor}</Shell>
    </StoreProvider>
  );
}
