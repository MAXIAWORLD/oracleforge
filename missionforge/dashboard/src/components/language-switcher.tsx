"use client";

import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { Languages, Check } from "lucide-react";
import { locales, localeNames, type Locale } from "@/i18n/config";

// Alphabetical order by native name — computed once at module load
const sortedLocales = [...locales].sort((a, b) =>
  localeNames[a].native.localeCompare(localeNames[b].native),
);

export function LanguageSwitcher() {
  const currentLocale = useLocale() as Locale;
  const router = useRouter();
  const t = useTranslations("shell");
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [position, setPosition] = useState<{
    top: number;
    right: number;
  } | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Hydration guard for createPortal
  useEffect(() => {
    setMounted(true);
  }, []);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Node;
      if (
        buttonRef.current &&
        !buttonRef.current.contains(target) &&
        dropdownRef.current &&
        !dropdownRef.current.contains(target)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  // Close on escape
  useEffect(() => {
    if (!open) return;
    function handleEscape(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [open]);

  // Recompute position when opening, on scroll, on resize
  useEffect(() => {
    if (!open) return;

    const updatePosition = () => {
      if (!buttonRef.current) return;
      const rect = buttonRef.current.getBoundingClientRect();
      setPosition({
        top: rect.bottom + 8,
        right: window.innerWidth - rect.right,
      });
    };

    updatePosition();
    window.addEventListener("scroll", updatePosition, true);
    window.addEventListener("resize", updatePosition);
    return () => {
      window.removeEventListener("scroll", updatePosition, true);
      window.removeEventListener("resize", updatePosition);
    };
  }, [open]);

  const handleSelect = (locale: Locale) => {
    document.cookie = `NEXT_LOCALE=${locale};path=/;max-age=31536000;samesite=lax`;
    setOpen(false);
    router.refresh();
  };

  const dropdown =
    open && position ? (
      <div
        ref={dropdownRef}
        style={{
          position: "fixed",
          top: position.top,
          right: position.right,
          zIndex: 9999,
        }}
        className="w-56 max-h-[400px] overflow-y-auto scrollbar-thin rounded-xl border border-border bg-white dark:bg-[#0b0e1a] shadow-2xl py-1"
      >
        <div className="px-3 py-2 border-b border-border sticky top-0 bg-white dark:bg-[#0b0e1a]">
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
            {t("language")}
          </p>
        </div>
        {sortedLocales.map((locale) => {
          const info = localeNames[locale];
          const active = locale === currentLocale;
          return (
            <button
              key={locale}
              type="button"
              onClick={() => handleSelect(locale)}
              className={`w-full flex items-center justify-between gap-3 px-3 py-2 text-xs transition-colors ${
                active
                  ? "bg-primary/10 text-primary dark:bg-primary/15 dark:text-blue-400"
                  : "hover:bg-accent"
              }`}
            >
              <div className="flex flex-col items-start">
                <span className="font-medium">{info.native}</span>
                <span className="text-[10px] text-muted-foreground">
                  {info.english}
                </span>
              </div>
              {active && <Check className="w-3.5 h-3.5 shrink-0" />}
            </button>
          );
        })}
      </div>
    ) : null;

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-10 h-10 rounded-xl border border-border flex items-center justify-center hover:bg-accent transition-colors"
        aria-label={t("language")}
      >
        <Languages className="w-4 h-4" />
      </button>
      {mounted && dropdown && createPortal(dropdown, document.body)}
    </>
  );
}
