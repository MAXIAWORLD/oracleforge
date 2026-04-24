/**
 * i18n configuration — 15 supported locales.
 * Source of truth: en.
 */

export const locales = [
  "en", // English
  "fr", // Francais
  "es", // Espanol
  "de", // Deutsch
  "pt", // Portugues
  "zh", // 中文
  "ja", // 日本語
  "it", // Italiano
  "nl", // Nederlands
  "pl", // Polski
  "ru", // Русский
  "ko", // 한국어
  "ar", // العربية
  "tr", // Turkce
  "hi", // हिन्दी
] as const;

export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = "en";

export const localeNames: Record<Locale, { native: string; english: string }> =
  {
    en: { native: "English", english: "English" },
    fr: { native: "Francais", english: "French" },
    es: { native: "Espanol", english: "Spanish" },
    de: { native: "Deutsch", english: "German" },
    pt: { native: "Portugues", english: "Portuguese" },
    zh: { native: "中文", english: "Chinese" },
    ja: { native: "日本語", english: "Japanese" },
    it: { native: "Italiano", english: "Italian" },
    nl: { native: "Nederlands", english: "Dutch" },
    pl: { native: "Polski", english: "Polish" },
    ru: { native: "Русский", english: "Russian" },
    ko: { native: "한국어", english: "Korean" },
    ar: { native: "العربية", english: "Arabic" },
    tr: { native: "Turkce", english: "Turkish" },
    hi: { native: "हिन्दी", english: "Hindi" },
  };

// Right-to-left locales (for dir attribute)
export const rtlLocales: readonly Locale[] = ["ar"] as const;

export function isRtl(locale: string): boolean {
  return rtlLocales.includes(locale as Locale);
}

export function isValidLocale(locale: string): locale is Locale {
  return (locales as readonly string[]).includes(locale);
}

/**
 * Detect best matching locale from Accept-Language header.
 * Matches primary tags only (fr-FR -> fr).
 */
export function detectLocaleFromHeader(acceptLanguage: string | null): Locale {
  if (!acceptLanguage) return defaultLocale;
  const preferred = acceptLanguage
    .split(",")
    .map((part) => part.split(";")[0].trim().split("-")[0].toLowerCase());
  const match = preferred.find((tag) => isValidLocale(tag));
  return (match as Locale) ?? defaultLocale;
}
