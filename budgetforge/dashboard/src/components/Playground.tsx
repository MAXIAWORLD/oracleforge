"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Play,
  Square,
  Zap,
  Settings,
  DollarSign,
  TrendingUp,
  AlertTriangle,
} from "lucide-react";

interface PlaygroundProps {
  apiKey: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

interface ProviderConfig {
  name: string;
  models: string[];
  costPer1kTokens: number;
}

const providers: ProviderConfig[] = [
  { name: "openai", models: ["gpt-4", "gpt-3.5-turbo"], costPer1kTokens: 0.03 },
  {
    name: "anthropic",
    models: ["claude-3-sonnet", "claude-3-haiku"],
    costPer1kTokens: 0.015,
  },
  { name: "google", models: ["gemini-pro"], costPer1kTokens: 0.01 },
];

export default function Playground({ apiKey }: PlaygroundProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Bonjour ! Je suis votre assistant BudgetForge. Je peux vous aider à tester vos prompts tout en respectant votre budget. Comment puis-je vous aider ?",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState("openai");
  const [selectedModel, setSelectedModel] = useState("gpt-4");
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(500);
  const [totalCost, setTotalCost] = useState(0);
  const [budgetAlert, setBudgetAlert] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const getCurrentProvider = () => {
    return providers.find((p) => p.name === selectedProvider);
  };

  const calculateCost = (tokens: number) => {
    const provider = getCurrentProvider();
    if (!provider) return 0;
    return (tokens / 1000) * provider.costPer1kTokens;
  };

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      role: "user",
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setStreaming(false);

    try {
      const response = await fetch(
        `/api/proxy/${selectedProvider}/v1/chat/completions`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${apiKey}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            model: selectedModel,
            messages: [
              ...messages.map((m) => ({ role: m.role, content: m.content })),
              userMessage,
            ],
            temperature,
            max_tokens: maxTokens,
            stream: true,
          }),
        },
      );

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No reader available");

      setStreaming(true);
      let assistantMessage = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = new TextDecoder().decode(value);
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ") && line.trim() !== "data: [DONE]") {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.choices?.[0]?.delta?.content) {
                assistantMessage += data.choices[0].delta.content;

                // Mettre à jour le message en temps réel
                setMessages((prev) => {
                  const newMessages = [...prev];
                  const lastMessage = newMessages[newMessages.length - 1];
                  if (lastMessage?.role === "assistant") {
                    newMessages[newMessages.length - 1] = {
                      ...lastMessage,
                      content: assistantMessage,
                    };
                  } else {
                    newMessages.push({
                      role: "assistant",
                      content: assistantMessage,
                      timestamp: new Date(),
                    });
                  }
                  return newMessages;
                });
              }
            } catch (error) {
              // Ignorer les erreurs de parsing
            }
          }
        }
      }

      // Calculer le coût estimé
      const estimatedTokens = assistantMessage.length / 4; // Estimation grossière
      const cost = calculateCost(estimatedTokens);
      setTotalCost((prev) => prev + cost);

      // Vérifier l'alerte budget
      if (totalCost + cost > 1.0) {
        // Seuil d'alerte à 1$
        setBudgetAlert(true);
      }
    } catch (error) {
      const errorMessage: Message = {
        role: "assistant",
        content: `❌ Erreur: ${error instanceof Error ? error.message : "Erreur inconnue"}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      setStreaming(false);
    }
  };

  const clearConversation = () => {
    setMessages([
      {
        role: "assistant",
        content: "Conversation réinitialisée. Comment puis-je vous aider ?",
        timestamp: new Date(),
      },
    ]);
    setTotalCost(0);
    setBudgetAlert(false);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex h-full bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Sidebar */}
      <div className="w-80 bg-slate-800/50 border-r border-slate-700 p-6">
        <div className="space-y-6">
          {/* En-tête */}
          <div className="text-center">
            <div className="inline-flex items-center gap-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white px-4 py-2 rounded-full text-sm font-semibold">
              <Zap className="w-4 h-4" />
              BudgetForge Playground
            </div>
          </div>

          {/* Configuration */}
          <div className="space-y-4">
            <h3 className="text-slate-300 font-semibold flex items-center gap-2">
              <Settings className="w-4 h-4" />
              Configuration
            </h3>

            {/* Provider */}
            <div>
              <label className="text-slate-400 text-sm block mb-2">
                Provider
              </label>
              <select
                value={selectedProvider}
                onChange={(e) => setSelectedProvider(e.target.value)}
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                {providers.map((provider) => (
                  <option key={provider.name} value={provider.name}>
                    {provider.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Modèle */}
            <div>
              <label className="text-slate-400 text-sm block mb-2">
                Modèle
              </label>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                {getCurrentProvider()?.models.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            </div>

            {/* Température */}
            <div>
              <label className="text-slate-400 text-sm block mb-2">
                Température: {temperature.toFixed(1)}
              </label>
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                className="w-full h-2 bg-slate-600 rounded-lg appearance-none cursor-pointer slider"
              />
              <div className="flex justify-between text-xs text-slate-500">
                <span>Précis</span>
                <span>Créatif</span>
              </div>
            </div>

            {/* Tokens max */}
            <div>
              <label className="text-slate-400 text-sm block mb-2">
                Tokens max: {maxTokens}
              </label>
              <input
                type="range"
                min="100"
                max="2000"
                step="100"
                value={maxTokens}
                onChange={(e) => setMaxTokens(parseInt(e.target.value))}
                className="w-full h-2 bg-slate-600 rounded-lg appearance-none cursor-pointer slider"
              />
            </div>
          </div>

          {/* Statistiques */}
          <div className="space-y-3">
            <h3 className="text-slate-300 font-semibold flex items-center gap-2">
              <TrendingUp className="w-4 h-4" />
              Statistiques
            </h3>

            <div className="grid grid-cols-2 gap-4">
              <div className="bg-slate-700/50 rounded-lg p-3">
                <div className="text-slate-400 text-xs">Messages</div>
                <div className="text-white font-semibold">
                  {messages.length}
                </div>
              </div>
              <div className="bg-slate-700/50 rounded-lg p-3">
                <div className="text-slate-400 text-xs">Coût total</div>
                <div className="text-white font-semibold">
                  ${totalCost.toFixed(4)}
                </div>
              </div>
            </div>

            {budgetAlert && (
              <div className="flex items-center gap-2 bg-yellow-500/20 border border-yellow-500/30 rounded-lg p-3">
                <AlertTriangle className="w-4 h-4 text-yellow-400" />
                <span className="text-yellow-400 text-sm">
                  Attention: Budget dépassé
                </span>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="space-y-3">
            <button
              onClick={clearConversation}
              className="w-full bg-slate-700 hover:bg-slate-600 text-white py-2 px-4 rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <Square className="w-4 h-4" />
              Nouvelle conversation
            </button>
          </div>
        </div>
      </div>

      {/* Zone de chat principale */}
      <div className="flex-1 flex flex-col">
        {/* En-tête */}
        <div className="border-b border-slate-700 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
              <span className="text-white font-semibold">
                {selectedProvider} - {selectedModel}
              </span>
              {streaming && (
                <span className="text-purple-400 text-sm flex items-center gap-1">
                  <div className="w-2 h-2 bg-purple-400 rounded-full animate-pulse"></div>
                  Streaming...
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 text-slate-400">
              <DollarSign className="w-4 h-4" />
              <span className="text-sm">${totalCost.toFixed(4)}</span>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex gap-4 ${
                message.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              {message.role === "assistant" && (
                <div className="w-8 h-8 bg-gradient-to-r from-purple-500 to-pink-500 rounded-full flex items-center justify-center flex-shrink-0">
                  <Zap className="w-4 h-4 text-white" />
                </div>
              )}

              <div
                className={`max-w-2xl rounded-2xl p-4 ${
                  message.role === "user"
                    ? "bg-gradient-to-r from-blue-500 to-purple-500 text-white"
                    : "bg-slate-700/50 text-slate-200 border border-slate-600"
                }`}
              >
                <div className="whitespace-pre-wrap">{message.content}</div>
                <div className="text-xs opacity-70 mt-2">
                  {message.timestamp.toLocaleTimeString()}
                </div>
              </div>

              {message.role === "user" && (
                <div className="w-8 h-8 bg-gradient-to-r from-blue-500 to-cyan-500 rounded-full flex items-center justify-center flex-shrink-0">
                  <span className="text-white text-sm font-semibold">U</span>
                </div>
              )}
            </div>
          ))}

          {isLoading && !streaming && (
            <div className="flex gap-4 justify-start">
              <div className="w-8 h-8 bg-gradient-to-r from-purple-500 to-pink-500 rounded-full flex items-center justify-center">
                <Zap className="w-4 h-4 text-white" />
              </div>
              <div className="bg-slate-700/50 rounded-2xl p-4">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></div>
                  <div
                    className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
                    style={{ animationDelay: "0.1s" }}
                  ></div>
                  <div
                    className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
                    style={{ animationDelay: "0.2s" }}
                  ></div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t border-slate-700 p-4">
          <div className="flex gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Tapez votre message... (Entrée pour envoyer, Maj+Entrée pour saut de ligne)"
              className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"
              rows={2}
            />
            <button
              onClick={sendMessage}
              disabled={isLoading || !input.trim()}
              className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-6 py-3 rounded-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed hover:from-purple-600 hover:to-pink-600 transition-all flex items-center gap-2"
            >
              {isLoading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  Envoi...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Envoyer
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      <style jsx global>{`
        .slider::-webkit-slider-thumb {
          appearance: none;
          height: 16px;
          width: 16px;
          border-radius: 50%;
          background: #8b5cf6;
          cursor: pointer;
        }

        .slider::-moz-range-thumb {
          height: 16px;
          width: 16px;
          border-radius: 50%;
          background: #8b5cf6;
          cursor: pointer;
          border: none;
        }
      `}</style>
    </div>
  );
}
