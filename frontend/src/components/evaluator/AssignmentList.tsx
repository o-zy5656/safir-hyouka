import { useMemo, useState } from "react";
import type { AssignmentSummary } from "../../types";

const statusLabel: Record<string, string> = {
  pending: "未着手",
  draft: "下書き",
  submitted: "提出済み",
  returned: "差し戻し",
};

const statusClass: Record<string, string> = {
  pending: "status-pending",
  draft: "status-draft",
  submitted: "status-submitted",
  returned: "status-returned",
};

type ListFilter = "all" | "action" | "waiting_self" | "submitted";

interface Props {
  assignments: AssignmentSummary[];
  userRole: string;
  isHqEvaluator?: boolean;
}

export function EvaluatorSummary({ assignments, userRole, isHqEvaluator }: Props) {
  const counts = { pending: 0, draft: 0, submitted: 0, returned: 0 };
  for (const a of assignments) {
    const key = a.my_status as keyof typeof counts;
    if (key in counts) counts[key] += 1;
  }
  const waitingSelf = assignments.filter((a) => a.self_eval_status !== "submitted").length;
  const needsAction = assignments.filter(
    (a) =>
      a.self_eval_status === "submitted" &&
      (a.my_status === "pending" || a.my_status === "draft" || a.my_status === "returned"),
  ).length;

  return (
    <section className="evaluator-summary">
      <h2>進捗サマリー</h2>
      <div className="summary-chips">
        <span className="summary-chip">担当 {assignments.length}名</span>
        <span className="summary-chip status-submitted">提出済 {counts.submitted}</span>
        <span className="summary-chip status-draft">下書き {counts.draft}</span>
        <span className="summary-chip status-pending">未着手 {counts.pending}</span>
        {needsAction > 0 && (
          <span className="summary-chip status-draft">要対応 {needsAction}</span>
        )}
      </div>
      {waitingSelf > 0 && <p className="summary-note">自己評価待ち {waitingSelf}名</p>}
      {userRole === "evaluator2" && !isHqEvaluator && (
        <p className="summary-note hint">評価者1の提出後に考課入力できます</p>
      )}
      {isHqEvaluator && assignments.some((a) => a.hq_review_only) && (
        <p className="summary-note hint">施設長が提出した一般職・リーダーの考課結果を確認できます</p>
      )}
    </section>
  );
}

interface ListProps {
  assignments: AssignmentSummary[];
  selectedId?: string;
  userRole: string;
  onSelect: (id: string) => void;
}

function matchesFilter(a: AssignmentSummary, filter: ListFilter, userRole: string): boolean {
  if (filter === "all") return true;
  if (filter === "waiting_self") return a.self_eval_status !== "submitted";
  if (filter === "submitted") return a.my_status === "submitted";
  if (filter === "action") {
    if (a.hq_review_only) return false;
    if (a.self_eval_status !== "submitted") return false;
    if (a.my_status === "draft" || a.my_status === "returned") return true;
    if (a.my_status === "pending") {
      if (userRole === "evaluator2") {
        return a.skips_eval1 || a.eval1_status === "submitted";
      }
      return true;
    }
  }
  return false;
}

export function AssignmentList({ assignments, selectedId, userRole, onSelect }: ListProps) {
  const [filter, setFilter] = useState<ListFilter>("all");

  const filtered = useMemo(
    () => assignments.filter((a) => matchesFilter(a, filter, userRole)),
    [assignments, filter, userRole],
  );

  return (
    <section>
      <h2>担当者一覧</h2>
      <div className="filter-tabs">
        {(
          [
            ["all", "すべて"],
            ["action", "要対応"],
            ["waiting_self", "自己評価待ち"],
            ["submitted", "提出済み"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={filter === key ? "active" : ""}
            onClick={() => setFilter(key)}
          >
            {label}
          </button>
        ))}
      </div>
      <ul className="assignment-list">
        {filtered.map((a) => {
          const disabled = a.evaluation_id === "00000000-0000-0000-0000-000000000000";
          const waitingSelf = a.self_eval_status !== "submitted";
          return (
            <li key={a.evaluation_id}>
              <button
                type="button"
                className={[
                  "assignment-card",
                  selectedId === a.evaluation_id ? "selected" : "",
                  waitingSelf ? "waiting-self" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                onClick={() => onSelect(a.evaluation_id)}
                disabled={disabled}
              >
                <div className="assignment-card-header">
                  <strong>{a.employee.name}</strong>
                  {a.uses_facility_director_form && (
                    <span className="director-form-tag">施設長用</span>
                  )}
                  {a.hq_review_only && (
                    <span className="director-form-tag">本部確認</span>
                  )}
                  <span className="employee-id-tag">{a.employee.employee_id}</span>
                  <span className={`status-pill ${statusClass[a.my_status] ?? ""}`}>
                    {statusLabel[a.my_status] ?? a.my_status}
                  </span>
                </div>
                <span className="assignment-meta">
                  {a.employee.job_title ? `${a.employee.job_title} · ` : ""}
                  {a.employee.job_type}
                </span>
                <div className="assignment-status-row">
                  <span className={`mini-tag ${statusClass[a.self_eval_status] ?? ""}`}>
                    自己:{statusLabel[a.self_eval_status] ?? a.self_eval_status}
                  </span>
                  {userRole === "evaluator2" && !a.skips_eval1 && !a.hq_review_only && (
                    <span className={`mini-tag ${statusClass[a.eval1_status] ?? ""}`}>
                      評1:{statusLabel[a.eval1_status] ?? a.eval1_status}
                    </span>
                  )}
                  {a.hq_review_only && (
                    <span className={`mini-tag ${statusClass[a.eval2_status] ?? ""}`}>
                      施設長:{statusLabel[a.eval2_status] ?? a.eval2_status}
                    </span>
                  )}
                </div>
              </button>
            </li>
          );
        })}
      </ul>
      {filtered.length === 0 && <p className="hint">該当する担当者がいません。</p>}
    </section>
  );
}
