export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ScanStatus = "pending" | "running" | "done" | "failed";
export type Severity = "info" | "low" | "medium" | "high" | "critical";

export interface Scan {
  id: string;
  domain: string;
  status: ScanStatus;
  created_at: string;
  finished_at: string | null;
}

export interface Finding {
  id: string;
  scan_id: string;
  module: string;
  severity: Severity;
  title: string;
  data: Record<string, unknown>;
  created_at: string;
}

export interface ModuleRun {
  id: string;
  module: string;
  status: "pending" | "running" | "done" | "failed" | "skipped";
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface ScanDetail extends Scan {
  findings: Finding[];
  module_runs: ModuleRun[];
}

export async function createScan(domain: string): Promise<Scan> {
  const res = await fetch(`${API_URL}/api/v1/scans`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ domain }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `request failed: ${res.status}`);
  }
  return res.json();
}

export async function getScan(id: string): Promise<ScanDetail> {
  const res = await fetch(`${API_URL}/api/v1/scans/${id}`);
  if (!res.ok) throw new Error(`request failed: ${res.status}`);
  return res.json();
}

export function streamScanUrl(id: string): string {
  return `${API_URL}/api/v1/scans/${id}/stream`;
}

export type ExportFormat = "json" | "csv" | "xlsx" | "md" | "html";

export function exportScanUrl(id: string, format: ExportFormat = "json"): string {
  return `${API_URL}/api/v1/scans/${id}/export.${format}`;
}

export function viewReportUrl(id: string): string {
  // HTML report opens inline (no download param) — nice for sharing / printing.
  return `${API_URL}/api/v1/scans/${id}/export.html`;
}
