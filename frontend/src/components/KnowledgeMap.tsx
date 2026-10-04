import { Background, Controls, ReactFlow, MarkerType } from "@xyflow/react";
import type { Node, Edge } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useState } from "react";
import type { Rule, Session } from "../contracts";
import { Button } from "./ui/button";

export function KnowledgeMap({
  session,
  onEvidence,
  onCorrect,
  busy,
}: {
  session: Session;
  onEvidence: (id: string) => void;
  onCorrect: (id: string, reason: string) => void;
  busy: boolean;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [edit, setEdit] = useState("");
  const rules = session.work_map.rules;
  const rule = rules.find((r) => r.id === selected);
  const nodes: Node[] = rules.map((rule, index) => ({
    id: rule.id,
    position: { x: index * 310, y: 30 },
    data: {
      label: (
        <div className="map-node">
          <span className="eyebrow">
            0{index + 1} · {rule.status.replaceAll("_", " ")}
          </span>
          <strong>{rule.title}</strong>
          <span className="muted">
            {rule.reason
              ? "Open reasoning & evidence →"
              : "Awaiting expert reasoning"}
          </span>
        </div>
      ),
    },
    style: {
      width: 260,
      background: rule.status === "expert_confirmed" ? "#eefaf6" : "#fff",
      borderColor: "#92b9b3",
    },
  }));
  nodes.push({
    id: "hold",
    position: { x: 310, y: 210 },
    data: { label: "Missing or ambiguous → Hold / Escalate" },
    style: { width: 260, background: "#fff7e8", borderColor: "#d9b16a" },
  });
  const edges: Edge[] = [
    ...rules.slice(0, 2).map((r, i) => ({
      id: `next-${r.id}`,
      source: r.id,
      target: rules[i + 1].id,
      label: "Evidence matches",
      markerEnd: { type: MarkerType.ArrowClosed },
    })),
    ...rules.map((r) => ({
      id: `hold-${r.id}`,
      source: r.id,
      target: "hold",
      label: "Check fails",
      style: { stroke: "#b88542" },
      markerEnd: { type: MarkerType.ArrowClosed },
    })),
  ];
  return (
    <>
      <div className="row spread">
        <div>
          <h2>How judgment becomes teachable</h2>
          <p className="muted">
            Map v{session.work_map.version} · {session.work_map.status}. Click a
            step to inspect its evidence.
          </p>
        </div>
        <span className="badge neutral">Fictional company policies</span>
      </div>
      <div className="map-canvas" aria-label="Interactive Work Map">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          nodesDraggable={false}
          onNodeClick={(_, node) => {
            setSelected(node.id);
            setEdit(rules.find((r) => r.id === node.id)?.reason ?? "");
          }}
        >
          <Background gap={24} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <div className="rule-list">
        {rules.map((rule) => (
          <button
            className="rule-card"
            key={rule.id}
            onClick={() => {
              setSelected(rule.id);
              setEdit(rule.reason);
            }}
          >
            <strong>{rule.title}</strong>
            <span className="badge neutral">
              {rule.status.replaceAll("_", " ")}
            </span>
            <p>
              {rule.reason ||
                "This condition has not yet been explained by the expert."}
            </p>
          </button>
        ))}
      </div>
      {rule && (
        <section className="card">
          <h3>{rule.title}</h3>
          <p className="eyebrow">
            Expert words · {rule.status.replaceAll("_", " ")}
          </p>
          <blockquote>{rule.reason || "No expert answer recorded."}</blockquote>
          <p className="muted">Exceptions: {rule.exceptions || "Unresolved"}</p>
          <p className="muted">
            Escalation: {rule.escalation_owner || "Unresolved"}
          </p>
          <p className="muted">
            Decision: {rule.decision ?? "Not observed"} · Confirmed:{" "}
            {rule.confirmation
              ? new Date(rule.confirmation).toLocaleString()
              : "Awaiting explicit confirmation"}
          </p>
          <p className="muted">
            Guardrails: {rule.guardrails.join(", ") || "Unresolved"}
          </p>
          <div className="row wrap">
            {rule.screen_evidence_ids.map((id, index) => (
              <Button
                variant="secondary"
                key={id}
                onClick={() => onEvidence(id)}
              >
                Screen moment {index + 1}
              </Button>
            ))}
            {rule.evidence_ids.map((id, index) => (
              <Button
                variant="secondary"
                key={id}
                onClick={() => onEvidence(id)}
              >
                Evidence {index + 1}
              </Button>
            ))}
          </div>
          <label className="field">
            Correct this reasoning
            <textarea
              value={edit}
              onChange={(event) => setEdit(event.target.value)}
            />
          </label>
          <Button
            disabled={busy || !edit.trim() || edit === rule.reason}
            onClick={() => onCorrect(rule.id, edit)}
          >
            Save expert correction
          </Button>
          <p className="muted">
            Changes to an approved map create a new version and require
            confirmation.
          </p>
        </section>
      )}
      {!rule && (
        <p className="notice">
          Observed actions remain candidate knowledge. Confirmed rules can
          support approved challenges. Unresolved situations need escalation.
        </p>
      )}
    </>
  );
}

export function RuleEvidence({
  rules,
  onEvidence,
}: {
  rules: Rule[];
  onEvidence: (id: string) => void;
}) {
  return (
    <>
      {rules.map((rule) => (
        <div className="hint" key={rule.id}>
          <strong>{rule.title}</strong>
          <blockquote>{rule.reason}</blockquote>
          <div className="row wrap">
            {[...rule.screen_evidence_ids, ...rule.evidence_ids]
              .slice(0, 2)
              .map((id, index) => (
                <Button
                  variant="secondary"
                  key={id}
                  onClick={() => onEvidence(id)}
                >
                  Replay evidence {index + 1}
                </Button>
              ))}
          </div>
        </div>
      ))}
    </>
  );
}
