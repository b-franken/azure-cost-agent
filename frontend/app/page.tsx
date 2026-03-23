"use client";

import { CopilotChat } from "@copilotkit/react-ui";

export default function Page() {
  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "#0a0a0f",
      }}
    >
      <header
        style={{
          padding: "1rem 2rem",
          borderBottom: "1px solid #1e1e2e",
          display: "flex",
          alignItems: "center",
          gap: "0.75rem",
        }}
      >
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: "#3b82f6",
          }}
        />
        <span
          style={{
            fontSize: "0.875rem",
            fontWeight: 600,
            color: "#e4e4e7",
            letterSpacing: "0.02em",
          }}
        >
          Azure Cost Agent
        </span>
      </header>
      <CopilotChat
        labels={{
          initial:
            "Ask me about your Azure costs, waste, budgets, tags, or generate a full optimization report.",
          placeholder: "Ask about your Azure costs...",
        }}
        className="flex-1"
      />
    </div>
  );
}
