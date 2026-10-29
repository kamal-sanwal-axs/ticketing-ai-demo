import type { UiDisplay } from "@/types/api";
import { InteractiveTable } from "./InteractiveTable";

type Props = { display: UiDisplay };

export function DisplayView({ display }: Props) {
  const levelClass =
    display.level === "error" ? "display-error" : display.level === "warning" ? "display-warning" : "";

  const showTable =
    (display.type === "table" || display.type === "dashboard") &&
    display.rows &&
    display.columns?.length;

  return (
    <div className={`display ${levelClass}`}>
      <div className="display-head">
        {display.badge ? <span className="badge">{display.badge}</span> : null}
        {display.title ? <h3 className="display-title">{display.title}</h3> : null}
        {display.subtitle ? <p className="display-subtitle muted">{display.subtitle}</p> : null}
      </div>

      {showTable ? (
        <InteractiveTable
          columns={display.columns!}
          rows={display.rows!}
          totalCount={display.count ?? display.rows!.length}
        />
      ) : null}

      {display.charts?.map((chart, i) => {
        const max = Math.max(...(chart.values || [1]), 1);
        return (
          <div key={i} className="chart-block">
            {chart.title ? <h4 className="display-section-title">{chart.title}</h4> : null}
            {(chart.labels || []).map((label, idx) => {
              const val = chart.values?.[idx] ?? 0;
              return (
                <div key={label} className="chart-bar-row">
                  <span className="chart-label">{label}</span>
                  <div className="chart-bar-track">
                    <div className="chart-bar-fill" style={{ width: `${Math.round((val / max) * 100)}%` }} />
                  </div>
                  <span className="chart-value">{String(val)}</span>
                </div>
              );
            })}
          </div>
        );
      })}

      {display.sections?.map((section, si) => (
        <section key={si} className="display-section">
          {section.title ? <h4 className="display-section-title">{section.title}</h4> : null}
          {section.paragraphs?.map((p, pi) => (p ? <p key={pi} className="display-p">{p}</p> : null))}
          {section.fields?.length ? (
            <dl className="field-list field-list-compact">
              {section.fields.flatMap((f, fi) => [
                <dt key={`dt-${fi}`}>{f.label}</dt>,
                <dd key={`dd-${fi}`}>{String(f.value ?? "—")}</dd>,
              ])}
            </dl>
          ) : null}
          {section.table?.columns?.length && section.table.rows ? (
            <InteractiveTable
              columns={section.table.columns}
              rows={section.table.rows}
              totalCount={section.table.rows.length}
              tableClass="data-table data-table-compact"
            />
          ) : null}
          {section.items?.length ? (
            <ul className="display-list">
              {section.items.map((item) => <li key={item}>{item}</li>)}
            </ul>
          ) : null}
          {section.links?.length ? (
            <ul className="display-links">
              {section.links.map((link) => (
                <li key={link.href}>
                  <a className="display-link" href={link.href} target="_blank" rel="noopener noreferrer">
                    {link.label}
                  </a>
                  {link.note ? <span className="display-link-note muted"> — {link.note}</span> : null}
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ))}

      {display.fields?.length ? (
        <dl className="field-list">
          {display.fields.flatMap((f, i) => [
            <dt key={`f-dt-${i}`}>{f.label}</dt>,
            <dd key={`f-dd-${i}`}>{String(f.value ?? "—")}</dd>,
          ])}
        </dl>
      ) : null}

      {display.paragraphs?.map((p, i) => (p ? <p key={i} className="display-p">{p}</p> : null))}

      {display.items?.length ? (
        <>
          {display.itemsTitle ? <h4 className="display-items-title">{display.itemsTitle}</h4> : null}
          <ul className="display-list">
            {display.items.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </>
      ) : null}

      {display.footnote ? <p className="display-footnote muted">{display.footnote}</p> : null}

      {display.citations?.length ? (
        <div className="display-citations">
          <h4 className="display-section-title">Sources</h4>
          <ul className="display-citations-list">
            {display.citations.map((cite, i) => (
              <li key={i} className="display-citation-item">
                {cite.href ? (
                  <a href={cite.href} target="_blank" rel="noopener noreferrer">
                    {cite.label || cite.href}
                  </a>
                ) : (
                  cite.label || "—"
                )}
                {cite.status ? <span className="muted"> · {cite.status}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
