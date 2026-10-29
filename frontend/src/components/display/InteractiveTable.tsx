import { useMemo, useState } from "react";
import type { DisplayColumn } from "@/types/api";

type Props = {
  columns: DisplayColumn[];
  rows: Record<string, unknown>[];
  totalCount?: number;
  tableClass?: string;
};

function cellText(row: Record<string, unknown>, col: DisplayColumn): string {
  const v = row[col.key];
  return String(v === undefined || v === null || v === "" ? "—" : v);
}

function ColorCell({ value }: { value: unknown }) {
  const text = String(value === undefined || value === null || value === "" ? "—" : value);
  const showSwatch = text !== "—" && /^#?[0-9a-f]{3,8}$/i.test(text.trim());
  const color = text.startsWith("#") ? text : `#${text}`;
  return (
    <span className="color-cell">
      {showSwatch ? <span className="color-swatch" style={{ backgroundColor: color }} title={color} /> : null}
      {text}
    </span>
  );
}

export function InteractiveTable({ columns, rows, totalCount, tableClass = "data-table" }: Props) {
  const allRows = rows ?? [];
  const total = totalCount ?? allRows.length;
  const [globalQ, setGlobalQ] = useState("");
  const [colFilters, setColFilters] = useState<Record<string, string>>({});

  const visibleRows = useMemo(() => {
    const g = globalQ.trim().toLowerCase();
    return allRows.filter((row) => {
      if (g) {
        const hay = columns.map((c) => cellText(row, c).toLowerCase()).join(" ");
        if (!hay.includes(g)) return false;
      }
      for (const col of columns) {
        const q = (colFilters[col.key] || "").trim().toLowerCase();
        if (!q) continue;
        if (!cellText(row, col).toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [allRows, columns, globalQ, colFilters]);

  return (
    <>
      <div className="table-toolbar">
        <input
          type="search"
          className="table-search-global"
          placeholder="Search all columns…"
          aria-label="Search all columns"
          value={globalQ}
          onChange={(e) => setGlobalQ(e.target.value)}
        />
        <span className="table-row-count muted">
          Showing {visibleRows.length} of {total} row(s)
        </span>
      </div>
      <div className="table-wrap table-wrap-scroll">
        <table className={tableClass} role="table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.key} data-col={col.key}>{col.label}</th>
              ))}
            </tr>
            <tr className="table-filter-row">
              {columns.map((col) => (
                <th key={`f-${col.key}`}>
                  <input
                    type="search"
                    className="table-col-filter"
                    placeholder={`Filter ${col.label}`}
                    aria-label={`Filter ${col.label}`}
                    value={colFilters[col.key] || ""}
                    onChange={(e) => setColFilters((prev) => ({ ...prev, [col.key]: e.target.value }))}
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, idx) => (
              <tr key={idx}>
                {columns.map((col) => {
                  const isId = col.key === "id" || col.key.endsWith("Id");
                  return (
                    <td key={col.key} data-col={col.key} className={isId ? "cell-mono" : undefined}>
                      {col.cellType === "color" || col.key === "color" ? (
                        <ColorCell value={row[col.key]} />
                      ) : (
                        cellText(row, col)
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
