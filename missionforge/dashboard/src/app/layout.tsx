import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import {
  Activity,
  Bot,
  LayoutDashboard,
  MessageSquare,
  Rocket,
} from "lucide-react";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "MissionForge",
  description: "AI Agent Framework — autonomous missions in YAML",
};

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/missions", label: "Missions", icon: Rocket },
  { href: "/chat", label: "Chat", icon: MessageSquare },
];

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex bg-gray-50 text-gray-900">
        {/* Sidebar */}
        <aside className="w-56 bg-white border-r border-gray-200 flex flex-col fixed h-full">
          <div className="p-5 border-b border-gray-200">
            <Link href="/" className="flex items-center gap-2">
              <Bot className="h-6 w-6 text-blue-600" />
              <span className="font-semibold text-lg">MissionForge</span>
            </Link>
            <p className="text-xs text-gray-400 mt-1">AI Agent Framework</p>
          </div>

          <nav className="flex-1 p-3 space-y-1">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-100 hover:text-gray-900 transition-colors"
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="p-4 border-t border-gray-200">
            <div className="flex items-center gap-2 text-xs text-gray-400">
              <Activity className="h-3 w-3" />
              <span>v0.1.0</span>
            </div>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 ml-56 p-6">{children}</main>
      </body>
    </html>
  );
}
