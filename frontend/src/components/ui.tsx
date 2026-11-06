"use client";
import { useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";

export const inr = (n: number) => "₹" + Math.round(n).toLocaleString("en-IN");

/** Numbers glide to their new value, so a changed total is noticed rather than just replaced. */
export function CountUp({ value, className, format = inr }: { value: number; className?: string; format?: (n: number) => string }) {
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  useEffect(() => {
    const reduce = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || from.current === value) { setShown(value); from.current = value; return; }
    const start = performance.now(), a = from.current, dur = 650;
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / dur), e = 1 - Math.pow(1 - p, 3);
      setShown(a + (value - a) * e);
      if (p < 1) raf = requestAnimationFrame(tick); else from.current = value;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return <span className={className}>{format(shown)}</span>;
}

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "quiet"; busy?: boolean; icon?: ReactNode };
export function Btn({ variant = "primary", busy, icon, children, className = "", disabled, ...rest }: BtnProps) {
  const base = "inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 font-semibold transition-[transform,background-color,box-shadow] duration-150 active:translate-y-px disabled:opacity-50 disabled:cursor-not-allowed select-none";
  const look = {
    primary: "bg-ink text-white hover:bg-ink-deep shadow-[0_6px_0_0_#141C55] active:shadow-[0_2px_0_0_#141C55] active:translate-y-1",
    ghost: "border-2 border-ink/20 text-ink hover:border-ink hover:bg-ink-wash",
    quiet: "text-ink-soft hover:text-ink hover:bg-ink-wash px-3 py-2",
  }[variant];
  return (
    <button className={`${base} ${look} ${className}`} disabled={disabled || busy} {...rest}>
      {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
}

export function Switch({ on, onChange, label, disabled }: { on: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <button role="switch" aria-checked={on} aria-label={label} disabled={disabled} onClick={() => onChange(!on)}
      className={`relative h-7 w-12 shrink-0 rounded-full transition-colors duration-200 disabled:opacity-50 ${on ? "bg-leaf" : "bg-ink/20"}`}>
      <motion.span layout transition={{ type: "spring", stiffness: 600, damping: 32 }}
        className="absolute top-0.5 h-6 w-6 rounded-full bg-white shadow" style={{ left: on ? 22 : 2 }} />
    </button>
  );
}

export function ErrorNote({ msg, onClose }: { msg: string | null; onClose?: () => void }) {
  if (!msg) return null;
  return (
    <div role="alert" className="flex items-start justify-between gap-3 rounded-xl border-2 border-chilli/30 bg-chilli-wash px-4 py-3 text-sm text-chilli">
      <span>{msg}</span>
      {onClose && <button onClick={onClose} className="font-semibold underline">OK</button>}
    </div>
  );
}

export function Stamp({ text, tone, className = "" }: { text: string; tone: "leaf" | "chilli" | "ink" | "haldi"; className?: string }) {
  const c = { leaf: "text-leaf", chilli: "text-chilli", ink: "text-ink", haldi: "text-haldi-deep" }[tone];
  return (
    <motion.div
      initial={{ scale: 2.4, opacity: 0, rotate: -2 }}
      animate={{ scale: 1, opacity: 0.92, rotate: -9 }}
      transition={{ type: "spring", stiffness: 520, damping: 22, mass: 0.7 }}
      className={`stamp relative inline-block px-4 py-1.5 font-display text-xl font-extrabold ${c} ${className}`}
    >{text}</motion.div>
  );
}
