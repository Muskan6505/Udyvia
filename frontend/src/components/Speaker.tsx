"use client";
import { motion } from "framer-motion";
import { Square, Volume2 } from "lucide-react";
import { useStore } from "@/lib/store";

/** Listen button with a small animated sound bar while the clip plays. Renders nothing if speech isn't set up. */
export function Speaker({ id, text, dark = false }: { id: number; text: string; dark?: boolean }) {
  const { t, voiceEnabled, playingId, speak, stopSpeech } = useStore();
  if (!voiceEnabled) return null;
  const playing = playingId === id;
  return (
    <button onClick={() => (playing ? stopSpeech() : speak(id, text))} aria-pressed={playing}
      aria-label={playing ? t("voice.stop") : t("voice.listen")}
      className={`mt-1 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-sm font-semibold transition-colors ${
        playing ? "bg-haldi text-ink-deep" : dark ? "text-white/80 hover:bg-white/10" : "text-ink-soft hover:bg-ink-wash"}`}>
      {playing ? (
        <span className="flex h-4 items-end gap-0.5" aria-hidden>
          {[0, 1, 2, 3].map((i) => (
            <motion.span key={i} className="w-0.5 rounded-full bg-ink-deep" animate={{ height: ["30%", "100%", "45%", "85%", "30%"] }}
              transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.12 }} />
          ))}
        </span>
      ) : <Volume2 className="h-4 w-4" aria-hidden />}
      {playing ? <><Square className="h-3 w-3 fill-current" aria-hidden />{t("voice.stop")}</> : t("voice.listen")}
    </button>
  );
}
