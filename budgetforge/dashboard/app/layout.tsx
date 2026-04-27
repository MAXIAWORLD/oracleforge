import type { Metadata } from "next";
import { Syne, DM_Sans, JetBrains_Mono } from "next/font/google";
import Script from "next/script";
import "./globals.css";

const syne = Syne({
  subsets: ["latin"],
  variable: "--font-syne",
  weight: ["400", "500", "600", "700", "800"],
});

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
  weight: ["300", "400", "500", "600"],
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  weight: ["300", "400", "500", "600"],
});

export const metadata: Metadata = {
  title: "LLM BudgetForge — Hard Budget Limits",
  description: "Hard limits for your LLM spend. No surprises.",
  icons: { icon: "/logo.png", apple: "/logo.png" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${syne.variable} ${dmSans.variable} ${jetbrains.variable} h-full`}
    >
      <body className="h-full">
        {children}
        <Script
          async
          defer
          src="https://analytics.maxiaworld.app/script.js"
          data-website-id="befd0e49-8570-4c0d-b420-66f4cebbfe3b"
        />
      </body>
    </html>
  );
}
