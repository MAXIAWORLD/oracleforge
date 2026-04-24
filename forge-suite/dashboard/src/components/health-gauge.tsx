"use client";

import { motion } from "framer-motion";
import { useTranslations } from "next-intl";

interface HealthGaugeProps {
  readonly percent: number;
  readonly healthyCount: number;
  readonly totalCount: number;
}

export function HealthGauge({
  percent,
  healthyCount,
  totalCount,
}: HealthGaugeProps) {
  const t = useTranslations("hub");
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percent / 100) * circumference;

  const color =
    percent === 100 ? "#0afe7e" : percent >= 50 ? "#ffb800" : "#ff3b5c";

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative w-[100px] h-[100px]">
        <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
          <circle cx="50" cy="50" r={radius} className="gauge-track" />
          <motion.circle
            cx="50"
            cy="50"
            r={radius}
            className="gauge-value"
            stroke={color}
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 1.2, ease: "easeOut" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="text-xl font-bold font-mono neon-value"
            style={{ "--glow": color } as React.CSSProperties}
          >
            {percent}%
          </span>
        </div>
      </div>
      <div className="text-center">
        <p className="text-sm font-semibold">
          {healthyCount}/{totalCount} {t("healthy")}
        </p>
        <p className="text-[11px] text-muted-foreground">{t("suiteHealth")}</p>
      </div>
    </div>
  );
}
