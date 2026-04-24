"use client";

import React from "react";
import Playground from "@/components/Playground";

export default function PlaygroundPage() {
  // En production, l'API key serait récupérée depuis l'authentification utilisateur
  // Pour la démo, nous utilisons une clé factice
  const apiKey = process.env.NEXT_PUBLIC_BUDGETFORGE_API_KEY || "demo-key";

  return (
    <div className="h-screen">
      <Playground apiKey={apiKey} />
    </div>
  );
}
