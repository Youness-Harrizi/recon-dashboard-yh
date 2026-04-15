"use client";

import { use, useEffect, useState } from "react";

import {
  exportScanUrl,
  getScan,
  streamScanUrl,
  viewReportUrl,
  type Finding,
  type ModuleRun,
  type ScanDetail,
  type ScanStatus,
} from "@/lib/api";
import { FindingData } from "./FindingData";

const STATUS_COLORS: Record<string, string> = {
  pending: "#666",
  running: "#e0a43b",
  done: "#3bc275",
  failed: "#e0573b",
  skipped: "#888",
};

const SEVERITY_COLORS: Record<string, string> = {
  info: "#5a8dee",
  low: "#3bc275",
  medium: "#e0a43b",
  high: "#e0573b",
  critical: "#b91c1c",
};

function exportBtn(primary = false): React.CSSProperties {
  return {
    fontSize: 12,
    textDecoration: "none",
    padding: "4px 10px",
    borderRadius: 4,
    border: "1px solid " + (primary ? "#2a5caa" : "#1f2933"),
    background: primary ? "#132642" : "transparent",
    color: primary ? "#9ac2ff" : "#cfd8e3",
  };
}

type ScanPatch = {
  status?: ScanStatus;
  finished_at?: string | null;
};

function mergeModuleRun(runs: ModuleRun[], incoming: ModuleRun): ModuleRun[] {
  const idx = runs.findIndex((r) => r.id === incoming.id);
  if (idx === -1) return [...runs, incoming];
  const copy = runs.slice();
  copy[idx] = { ...copy[idx], ...incoming };
  return copy;
}

function mergeFinding(findings: Finding[], incoming: Finding): Finding[] {
  if (findings.some((f) => f.id === incoming.id)) return findings;
  return [...findings, incoming];
}

export default function ScanPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let es: EventSource | null = null;
    let pollTimer: ReturnType<typeof setInterval> | null = null;

    async function fallbackPoll() {
      // If SSE fails (network / proxy / old browser), fall back to polling.
      async function tick() {
        try {
          const data = await getScan(id);
          if (!cancelled) setScan(data);
          if (!cancelled && (data.status === "done" || data.status === "failed")) {
            if (pollTimer) clearInterval(pollTimer);
          }
        } catch (err) {
          if (!cancelled)
            setError(err instanceof Error ? err.message : String(err));
        }
      }
      await tick();
      pollTimer = setInterval(tick, 2000);
    }

    es = new EventSource(streamScanUrl(id));

    es.addEventListener("snapshot", (ev) => {
      if (cancelled) return;
      try {
        const data = JSON.parse((ev as MessageEvent).data) as ScanDetail;
        setScan(data);
        setLive(true);
      } catch {}
    });

    es.addEventListener("module_run", (ev) => {
      if (cancelled) return;
      try {
        const run = JSON.parse((ev as MessageEvent).data) as ModuleRun;
        setScan((prev) =>
          prev ? { ...prev, module_runs: mergeModuleRun(prev.module_runs, run) } : prev,
        );
      } catch {}
    });

    es.addEventListener("finding", (ev) => {
      if (cancelled) return;
      try {
        const finding = JSON.parse((ev as MessageEvent).data) as Finding;
        setScan((prev) =>
          prev ? { ...prev, findings: mergeFinding(prev.findings, finding) } : prev,
        );
      } catch {}
    });

    es.addEventListener("scan", (ev) => {
      if (cancelled) return;
      try {
        const patch = JSON.parse((ev as MessageEvent).data) as ScanPatch;
        setScan((prev) => (prev ? { ...prev, ...patch } : prev));
      } catch {}
    });

    es.addEventListener("end", () => {
      es?.close();
    });

    es.onerror = () => {
      // Browser will auto-retry, but if it never opened we start polling as a
      // fallback so the user still sees progress.
      if (!cancelled && es && es.readyState === EventSource.CLOSED) {
        setLive(false);
        fallbackPoll();
      }
    };

    return () => {
      cancelled = true;
      es?.close();
      if (pollTimer) clearInterval(pollTimer);
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
            {live && (
              <span style={{ marginLeft: 10, fontSize: 12, color: "#6aa6ff" }}>
                ● live
              </span>
            )}
          </div>

          <div
            style={{
              marginTop: 14,
              display: "flex",
              gap: 8,
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <span style={{ fontSize: 12, opacity: 0.6, marginRight: 4 }}>
              Export:
            </span>
            <a
              href={viewReportUrl(scan.id)}
              target="_blank"
              rel="noreferrer"
              style={exportBtn(true)}
            >
              HTML report ↗
            </a>
            <a href={exportScanUrl(scan.id, "xlsx")} style={exportBtn()}>
              Excel (.xlsx)
            </a>
            <a href={exportScanUrl(scan.id, "csv")} style={exportBtn()}>
              CSV
            </a>
            <a href={exportScanUrl(scan.id, "md")} style={exportBtn()}>
              Markdown
            </a>
            <a href={exportScanUrl(scan.id, "json")} style={exportBtn()}>
              JSON
            </a>
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
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        marginBottom: 4,
                      }}
                    >
                      <span
                        style={{
                          fontSize: 10,
                          textTransform: "uppercase",
                          letterSpacing: 0.5,
                          padding: "2px 6px",
                          borderRadius: 3,
                          background: SEVERITY_COLORS[f.severity] ?? "#555",
                          color: "#fff",
                          fontWeight: 600,
                        }}
                      >
                        {f.severity}
                      </span>
                      <span style={{ fontSize: 12, opacity: 0.6 }}>
                        {f.module}
                      </span>
                    </div>
                    <div style={{ fontWeight: 500 }}>{f.title}</div>
                    <FindingData data={f.data} />
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
