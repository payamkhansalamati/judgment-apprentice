import type { Case } from "../contracts";
import { CheckCircle2, FileCheck2, GitBranch } from "lucide-react";
export function CaseCard({ value }: { value: Case }) {
  const fields = [
    ["Release version", value.software_version],
    ["Report version", value.report_version],
    ["Changed functionality", value.functionality.join(", ")],
    ["Test scope", value.test_scope.join(", ")],
    ["Change author", value.author],
    ["Independent reviewer", value.reviewer],
  ];
  return (
    <section className="card case-card" aria-label="Review case">
      <div className="row spread">
        <span className="eyebrow">
          <GitBranch size={14} /> Review portal · {value.id}
        </span>
        <span className="badge">
          <CheckCircle2 size={14} />
          {value.test_results === "passed"
            ? "All tests passed"
            : value.test_results}
        </span>
      </div>
      <h2>{value.title}</h2>
      <p className="muted">{value.description}</p>
      <dl className="case-fields">
        {fields.map(([label, content]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{content || "Missing information"}</dd>
          </div>
        ))}
      </dl>
      <div className="case-footer">
        <FileCheck2 size={18} />
        <span>
          Fictional company policies apply. Passing tests are one part of the
          evidence.
        </span>
      </div>
      {value.decision && (
        <p className="notice">
          Saved: {value.decision} · {value.justification}
        </p>
      )}
    </section>
  );
}
