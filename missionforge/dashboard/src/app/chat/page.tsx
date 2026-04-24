"use client";

import { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { Bot, Send, User, Zap, Database } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  DashboardShell,
  NEON,
  containerVariants,
  itemVariants,
} from "@/components/dashboard-shell";
import { api, type ChatResponse } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  meta?: {
    tier_used: string;
    latency_ms: number;
    rag_context_used: boolean;
    tokens_estimated: number;
  };
}

export default function ChatPage() {
  const t = useTranslations();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setError(null);

    const userMsg: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const resp: ChatResponse = await api.chat(text);
      const assistantMsg: Message = {
        role: "assistant",
        content: resp.reply,
        meta: {
          tier_used: resp.tier_used,
          latency_ms: resp.latency_ms,
          rag_context_used: resp.rag_context_used,
          tokens_estimated: resp.tokens_estimated,
        },
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("chat.error"));
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <DashboardShell>
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="flex flex-col h-[calc(100vh-7rem)] max-w-[1600px] mx-auto"
      >
        {/* Description */}
        <motion.div variants={itemVariants} className="mb-4">
          <p className="text-sm text-muted-foreground">{t("chat.subtitle")}</p>
        </motion.div>

        {/* Messages area */}
        <motion.div
          variants={itemVariants}
          className="flex-1 glass-card neon-card overflow-hidden"
          style={{ "--glow": NEON.blue } as React.CSSProperties}
        >
          <ScrollArea className="h-full p-4">
            <div className="space-y-4 pb-4">
              {messages.length === 0 && (
                <div className="text-center py-16">
                  <Bot className="h-12 w-12 mx-auto mb-3 text-muted-foreground/40" />
                  <p className="text-muted-foreground">
                    {t("chat.empty.title")}
                  </p>
                  <p className="text-sm mt-1 text-muted-foreground/60">
                    {t("chat.empty.subtitle")}
                  </p>
                </div>
              )}

              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex gap-3 ${
                    msg.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  {msg.role === "assistant" && (
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-cyan-500/15 flex items-center justify-center">
                      <Bot className="h-4 w-4 text-cyan-400" />
                    </div>
                  )}
                  <div
                    className={`max-w-[70%] rounded-xl p-3 ${
                      msg.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted/40 border border-border text-foreground"
                    }`}
                  >
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    {msg.meta && (
                      <div className="flex items-center gap-2 mt-2 flex-wrap">
                        <Badge
                          variant="outline"
                          className="text-xs border-border"
                        >
                          <Zap className="h-3 w-3 mr-1" />
                          {msg.meta.tier_used}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {msg.meta.latency_ms}ms
                        </span>
                        {msg.meta.rag_context_used && (
                          <Badge
                            variant="outline"
                            className="text-xs border-border"
                          >
                            <Database className="h-3 w-3 mr-1" />
                            RAG
                          </Badge>
                        )}
                        <span className="text-xs text-muted-foreground">
                          ~{msg.meta.tokens_estimated} {t("chat.tokensSuffix")}
                        </span>
                      </div>
                    )}
                  </div>
                  {msg.role === "user" && (
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary flex items-center justify-center">
                      <User className="h-4 w-4 text-primary-foreground" />
                    </div>
                  )}
                </div>
              ))}

              {loading && (
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-cyan-500/15 flex items-center justify-center">
                    <Bot className="h-4 w-4 text-cyan-400 animate-pulse" />
                  </div>
                  <div className="bg-muted/40 border border-border rounded-xl p-3">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-muted-foreground/40 rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-muted-foreground/40 rounded-full animate-bounce [animation-delay:0.1s]" />
                      <div className="w-2 h-2 bg-muted-foreground/40 rounded-full animate-bounce [animation-delay:0.2s]" />
                    </div>
                  </div>
                </div>
              )}

              <div ref={scrollRef} />
            </div>
          </ScrollArea>
        </motion.div>

        {/* Error */}
        {error && <p className="text-red-400 text-sm mt-2">{error}</p>}

        {/* Input */}
        <motion.div variants={itemVariants} className="flex gap-2 mt-3">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("chat.placeholder")}
            className="resize-none min-h-[44px] max-h-[120px] bg-card border-border"
            rows={1}
            disabled={loading}
          />
          <Button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="bg-primary hover:bg-primary/90"
          >
            <Send className="h-4 w-4" />
          </Button>
        </motion.div>
      </motion.div>
    </DashboardShell>
  );
}
