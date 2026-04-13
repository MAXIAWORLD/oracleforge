import { getRequestConfig } from "next-intl/server";
import { cookies, headers } from "next/headers";
import { defaultLocale, detectLocaleFromHeader, isValidLocale } from "./config";

/**
 * Per-request locale resolution:
 *   1. NEXT_LOCALE cookie (user choice)
 *   2. Accept-Language header (browser default)
 *   3. Fallback to defaultLocale (en)
 */
export default getRequestConfig(async () => {
  const cookieStore = await cookies();
  const cookieLocale = cookieStore.get("NEXT_LOCALE")?.value;

  let locale: string;
  if (cookieLocale && isValidLocale(cookieLocale)) {
    locale = cookieLocale;
  } else {
    const headersList = await headers();
    locale = detectLocaleFromHeader(headersList.get("accept-language"));
  }

  const messages = (await import(`../messages/${locale}.json`)).default;

  return {
    locale,
    messages,
  };
});
