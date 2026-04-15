"use client";

import { useState } from "react";

/**
 * Renders a finding's `data` dict as readable tables / lists when we recognize
 * the shape. Everything still has a "raw JSON" fallback via a <details>.
 *
 * The patterns are tied to what the seven built-in modules emit. Unknown shapes
 * fall through to a generic key/value table.
 */
export function FindingData({ data }: { data: Record<string, unknown> }) {
  if (!data || Object.keys(data).length === 0) return null;

  return (
    <div style={{ marginTop: 8 }}>
      <KeyValueTable data={data} />
      <details style={{ marginTop: 6 }}>
        <summary style={{ cursor: "pointer", fontSize: 11, color: "#7a8899" }}>
          raw JSON
        </summary>
        <pre
          style={{
            marginTop: 4,
            padding: 8,
            background: "#0b0d10",
            fontSize: 11,
            overflow: "auto",
            border: "1px solid #1a1f26",
            borderRadius: 4,
          }}
        >
          {JSON.stringify(data, null, 2)}
        </pre>
      </details>
    </div>
  );
}

function KeyValueTable({ data }: { data: Record<string, unknown> }) {
  return (
    <table
      style={{
        width: "100%",
        borderCollapse: "collapse",
        fontSize: 13,
        background: "#0b0d10",
        border: "1px solid #1a1f26",
        borderRadius: 4,
        overflow: "hidden",
      }}
    >
      <tbody>
        {Object.entries(data).map(([k, v]) => (
          <tr key={k} style={{ borderTop: "1px solid #1a1f26" }}>
            <th
              style={{
                padding: "6px 10px",
                textAlign: "left",
                verticalAlign: "top",
                width: 180,
                color: "#90a0b2",
                fontWeight: 500,
                background: "#0f1318",
                fontSize: 12,
                textTransform: "uppercase",
                letterSpacing: 0.3,
              }}
            >
              {k}
            </th>
            <td style={{ padding: "6px 10px", verticalAlign: "top" }}>
              <Value value={v} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Value({ value }: { value: unknown }) {
  if (value === null || value === undefined)
    return <span style={{ color: "#556" }}>—</span>;

  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean")
    return <span>{String(value)}</span>;

  if (Array.isArray(value)) {
    if (value.length === 0) return <span style={{ color: "#556" }}>empty</span>;
    if (value.every((x) => typeof x === "string" || typeof x === "number")) {
      return <StringList items={value.map((x) => String(x))} />;
    }
    if (value.every((x) => typeof x === "object" && x !== null && !Array.isArray(x))) {
      return <ObjectListTable rows={value as Record<string, unknown>[]} />;
    }
    return (
      <pre style={{ margin: 0, fontSize: 12 }}>
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }

  if (typeof value === "object") {
    return <KeyValueTable data={value as Record<string, unknown>} />;
  }

  return <span>{String(value)}</span>;
}

function StringList({ items }: { items: string[] }) {
  const [expanded, setExpanded] = useState(false);
  const limit = 25;
  const shown = expanded ? items : items.slice(0, limit);
  return (
    <div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
        {shown.map((s, i) => (
          <code
            key={i}
            style={{
              background: "#12161c",
              border: "1px solid #1f2833",
              padding: "1px 6px",
              borderRadius: 3,
              fontSize: 12,
            }}
          >
            {s}
          </code>
        ))}
      </div>
      {items.length > limit && (
        <button
          onClick={() => setExpanded((e) => !e)}
          style={{
            marginTop: 4,
            fontSize: 11,
            background: "transparent",
            color: "#6aa6ff",
            border: 0,
            cursor: "pointer",
            padding: 0,
          }}
        >
          {expanded ? "show less" : `show all ${items.length}`}
        </button>
      )}
    </div>
  );
}

function ObjectListTable({ rows }: { rows: Record<string, unknown>[] }) {
  const [expanded, setExpanded] = useState(false);
  const limit = 10;
  const shown = expanded ? rows : rows.slice(0, limit);
  const keys = Array.from(
    shown.reduce<Set<string>>((acc, r) => {
      Object.keys(r).forEach((k) => acc.add(k));
      return acc;
    }, new Set()),
  );

  return (
    <div>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: 12,
          border: "1px solid #1a1f26",
          borderRadius: 4,
        }}
      >
        <thead>
          <tr style={{ background: "#0f1318" }}>
            {keys.map((k) => (
              <th
                key={k}
                style={{
                  textAlign: "left",
                  padding: "4px 8px",
                  fontWeight: 500,
                  color: "#90a0b2",
                  textTransform: "uppercase",
                  fontSize: 11,
                  letterSpacing: 0.3,
                }}
              >
                {k}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((r, i) => (
            <tr key={i} style={{ borderTop: "1px solid #1a1f26" }}>
              {keys.map((k) => (
                <td
                  key={k}
                  style={{
                    padding: "4px 8px",
                    verticalAlign: "top",
                    fontFamily: "ui-monospace, monospace",
                  }}
                >
                  {r[k] === null || r[k] === undefined
                    ? ""
                    : typeof r[k] === "object"
                      ? JSON.stringify(r[k])
                      : String(r[k])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > limit && (
        <button
          onClick={() => setExpanded((e) => !e)}
          style={{
            marginTop: 4,
            fontSize: 11,
            background: "transparent",
            color: "#6aa6ff",
            border: 0,
            cursor: "pointer",
            padding: 0,
          }}
        >
          {expanded ? "show less" : `show all ${rows.length}`}
        </button>
      )}
    </div>
  );
}
