"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { createScan } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [domain, setDomain] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const scan = await createScan(domain);
      router.push(`/scan/${scan.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main style={{ maxWidth: 720, margin: "80px auto", padding: "0 24px" }}>
      <h1 style={{ fontSize: 32, marginBottom: 8 }}>Recon</h1>
      <p style={{ opacity: 0.7, marginTop: 0 }}>
        Domain reconnaissance dashboard.
      </p>

      <form onSubmit={onSubmit} style={{ marginTop: 32, display: "flex", gap: 8 }}>
        <input
          type="text"
          placeholder="example.com"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          required
          style={{
            flex: 1,
            padding: "10px 14px",
            fontSize: 16,
            borderRadius: 6,
            border: "1px solid #333",
            background: "#12151a",
            color: "#e6e8eb",
          }}
        />
        <button
          type="submit"
          disabled={submitting || !domain}
          style={{
            padding: "10px 20px",
            fontSize: 16,
            borderRadius: 6,
            border: "1px solid #3b82f6",
            background: submitting ? "#1e3a5f" : "#2563eb",
            color: "white",
            cursor: submitting ? "wait" : "pointer",
          }}
        >
          {submitting ? "Starting…" : "Scan"}
        </button>
      </form>

      {error && (
        <p style={{ color: "#f77", marginTop: 16 }}>Error: {error}</p>
      )}
    </main>
  );
}
