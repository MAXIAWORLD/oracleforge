"use client";

import { useState } from "react";

interface TimeFilterProps {
  selectedPeriod: string;
  onPeriodChange: (period: string) => void;
}

export default function TimeFilter({
  selectedPeriod,
  onPeriodChange,
}: TimeFilterProps) {
  const periods = [
    { value: "today", label: "Aujourd'hui" },
    { value: "7d", label: "7 jours" },
    { value: "month", label: "Ce mois" },
    { value: "all", label: "All time" },
  ];

  return (
    <div className="flex gap-2 bg-slate-800/50 rounded-lg p-1 border border-slate-700">
      {periods.map((period) => (
        <button
          key={period.value}
          onClick={() => onPeriodChange(period.value)}
          className={`px-4 py-2 rounded-md transition-colors ${
            selectedPeriod === period.value
              ? "bg-slate-700 text-white"
              : "text-slate-300 hover:text-white hover:bg-slate-700"
          }`}
        >
          {period.label}
        </button>
      ))}
    </div>
  );
}
