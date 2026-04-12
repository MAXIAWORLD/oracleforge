import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { Bot, LayoutDashboard, MessageSquare, Rocket } from "lucide-react";
import { ThemeProvider } from "@/components/theme-provider";
import { ThemeToggle } from "@/components/theme-toggle";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = { title: "MissionForge", description: "AI Agent Framework" };

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/missions", label: "Missions", icon: Rocket },
  { href: "/chat", label: "Chat", icon: MessageSquare },
];

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex overflow-hidden">
        <ThemeProvider>
          {/* Sidebar */}
          <aside className="w-[72px] bg-white dark:bg-[#0d1025] border-r border-gray-200 dark:border-[#1f2340] flex flex-col items-center fixed h-full z-20 py-4">
            {/* Logo */}
            <Link href="/" className="mb-8">
              <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-blue-500 via-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-blue-500/30 hover:shadow-blue-500/50 transition-shadow">
                <Bot className="h-5 w-5 text-white" />
              </div>
            </Link>

            {/* Nav icons */}
            <nav className="flex-1 flex flex-col items-center gap-2">
              {NAV.map((item) => (
                <Link key={item.href} href={item.href} title={item.label}
                  className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 dark:text-gray-500 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-500/10 transition-all duration-200 group">
                  <item.icon className="h-5 w-5 group-hover:scale-110 transition-transform" />
                </Link>
              ))}
            </nav>

            {/* Theme toggle */}
            <div className="mt-auto">
              <ThemeToggle />
            </div>
          </aside>

          {/* Main */}
          <main className="flex-1 ml-[72px] min-h-screen overflow-y-auto p-6 bg-[#f5f6fa] dark:bg-[#0b0e1a]">
            {children}
          </main>
        </ThemeProvider>
      </body>
    </html>
  );
}
