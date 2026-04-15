"use client";

import { use, useEffect, useState } from "react";

import { getScan, type ScanDetail } from "@/lib/api";

const STATUS_COLORS: Record<string, string> = {
  pending: "#666",
  running: "#e0a43b",
  done: "#3bc275",
  failed: "#e0573b",
  skipped: "#888",
};

export default function ScanPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await getScan(id);
        if (!cancelled) setScan(data);
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : String(err));
      }
    }

    load();
    // Polling — step 4 replaces this with SSE.
    const t = setInterval(load, 1500);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [id]);

  return (
    <main style={{ maxWidth: 920, margin: "40px auto", padding: "0 24px" }}>
      <a href="/" style={{ color: "#6aa6ff", textDecoration: "none" }}>
        ← new scan
      </a>

      {error && <p style={{ color: "#f77", marginTop: 16 }}>Error: {error}</p>}
      {!scan && !error && <p>Loading…</p>}

      {scan && (
        <>
          <h1 style={{ fontSize: 28, marginTop: 20 }}>{scan.domain}</h1>
          <div style={{ opacity: 0.7, fontSize: 14 }}>
            scan {scan.id} — status:{" "}
            <strong style={{ color: STATUS_COLORS[scan.status] }}>
              {scan.status}
            </strong>{" "}
            — started {new Date(scan.created_at).toLocaleString()}
          </div>

          <section style={{ marginTop: 32 }}>
            <h2 style={{ fontSize: 18 }}>Modules</h2>
            {scan.module_runs.length === 0 ? (
              <p style={{ opacity: 0.6 }}>No modules running.</p>
            ) : (
              <ul style={{ padding: 0, listStyle: "none" }}>
                {scan.module_runs.map((m) => (
                  <li
                    key={m.id}
                    style={{
                      padding: "8px 12px",
                      margin: "4px 0",
                      border: "1px solid #222",
                      borderRadius: 6,
                      background: "#12151a",
                      display: "flex",
                      justifyContent: "space-between",
                    }}
                  >
                    <span>{m.module}</span>
                    <span style={{ color: STATUS_COLORS[m.status] }}>
                      {m.status}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section style={{ marginTop: 32 }}>
            <h2 style={{ fontSize: 18 }}>Findings ({scan.findings.length})</h2>
            {scan.findings.length === 0 ? (
              <p style={{ opacity: 0.6 }}>No findings yet.</p>
            ) : (
              <ul style={{ padding: 0, listStyle: "none" }}>
                {scan.findings.map((f) => (
                  <li
                    key={f.id}
                    style={{
                      padding: 12,
                      margin: "8px 0",
                      border: "1px solid #222",
                      borderRadius: 6,
                      background: "#12151a",
                    }}
                  >
                    <div style={{ fontSize: 12, opacity: 0.6 }}>
                      {f.module} · {f.severity}
                    </div>
                    <div>{f.title}</div>
                    {Object.keys(f.data).length > 0 && (
                      <pre
                        style={{
                          marginTop: 6,
                          padding: 8,
                          background: "#0b0d10",
                          fontSize: 12,
                          overflow: "auto",
                        }}
                      >
                        {JSON.stringify(f.data, null, 2)}
                      </pre>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </main>
  );
}
