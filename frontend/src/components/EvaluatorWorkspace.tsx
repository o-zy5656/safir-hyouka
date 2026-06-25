import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { AssignmentSummary, EvaluatorWorkspaceResponse, FormTemplate } from "../types";
import { AttributePanel } from "./AttributePanel";
import { EvaluationForm } from "./EvaluationForm";
import { SubmissionPanel } from "./SubmissionPanel";
import { ThreePaneLayout } from "./ThreePaneLayout";
import { validateFormData } from "../utils/formValidation";

const statusLabel: Record<string, string> = {
  pending: "未着手",
  draft: "下書き",
  submitted: "提出済",
  returned: "差戻",
};

function AssignmentList({
  assignments,
  selectedId,
  onSelect,
}: {
  assignments: AssignmentSummary[];
  selectedId?: string;
  onSelect: (id: string) => void;
}) {
  return (
    <section>
      <h2>担当者一覧</h2>
      <ul className="assignment-list">
        {assignments.map((a) => (
          <li key={a.evaluation_id}>
            <button
              type="button"
              className={selectedId === a.evaluation_id ? "selected" : ""}
              onClick={() => onSelect(a.evaluation_id)}
              disabled={a.evaluation_id === "00000000-0000-0000-0000-000000000000"}
            >
              <strong>{a.employee.name}</strong>
              <span>{a.employee.assignment}</span>
              <span className="mini-status">自己:{statusLabel[a.self_eval_status] ?? a.self_eval_status}</span>
              <span className="mini-status">自分:{statusLabel[a.my_status] ?? a.my_status}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ReferencePanel({
  reference,
  template,
}: {
  reference?: Record<string, unknown>;
  template?: FormTemplate;
}) {
  if (!reference || Object.keys(reference).length === 0) {
    return (
      <section>
        <h2>参照</h2>
        <p className="hint">担当者を選択すると、自己評価などが表示されます。</p>
      </section>
    );
  }

  const labelFor = (itemId: string) => {
    const item = template?.items.find((i) => i.id === itemId);
    return item ? `${item.label} ${item.name}` : itemId;
  };

  const selfEval = reference.self_evaluation as {
    scores?: Record<string, number>;
    text_fields?: Record<string, string>;
  };
  const eval1 = reference.evaluator1 as { scores?: Record<string, number> } | undefined;

  return (
    <section>
      <h2>参照</h2>
      <h3>自己評価（採点）</h3>
      <ul className="ref-scores">
        {selfEval?.scores &&
          Object.entries(selfEval.scores).map(([id, score]) => (
            <li key={id}>
              {labelFor(id)}: {score}点
            </li>
          ))}
      </ul>
      {eval1 && (
        <>
          <h3>第1評価者（採点）</h3>
          <ul className="ref-scores">
            {eval1.scores &&
              Object.entries(eval1.scores).map(([id, score]) => (
                <li key={id}>
                  {labelFor(id)}: {score}点
                </li>
              ))}
          </ul>
        </>
      )}
    </section>
  );
}

export function EvaluatorWorkspace() {
  const [workspace, setWorkspace] = useState<EvaluatorWorkspaceResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [formData, setFormData] = useState<Record<string, unknown>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [userRole, setUserRole] = useState<string>("evaluator1");

  const loadList = async () => {
    const data = await api.evaluatorWorkspace();
    setWorkspace(data);
  };

  const loadDetail = async (id: string) => {
    const data = await api.evaluatorAssignment(id);
    setWorkspace((prev) => ({ ...data, assignments: prev?.assignments ?? data.assignments }));
    setSelectedId(id);
    setFormData(data.selected?.form_data ?? {});
  };

  useEffect(() => {
    api.me().then((u) => setUserRole(u.role)).catch(() => {});
    loadList().catch((e: Error) => setError(e.message));
  }, []);

  const handleSave = async () => {
    if (!selectedId) return;
    setSaving(true);
    setError(null);
    try {
      await api.saveEvaluatorAssignment(selectedId, formData);
      await loadDetail(selectedId);
      await loadList();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  const handleSubmit = async () => {
    if (!selectedId) return;
    setSaving(true);
    setError(null);
    try {
      await api.saveEvaluatorAssignment(selectedId, formData);
      await api.submitEvaluatorAssignment(selectedId);
      await loadDetail(selectedId);
      await loadList();
    } catch (e) {
      setError(e instanceof Error ? e.message : "提出に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  if (!workspace) return <p className="loading">{error ?? "読み込み中..."}</p>;

  const selected = workspace.selected;
  const waitingForEval1 =
    userRole === "evaluator2" &&
    selected &&
    !selected.submission.can_edit &&
    selected.submission.status === "pending";

  return (
    <div className="workspace-page">
      <header className="topbar">
        <h1>考課ワークスペース</h1>
        {workspace.period_name && <span className="period">{workspace.period_name}</span>}
      </header>
      {error && <p className="error">{error}</p>}
      <ThreePaneLayout
        left={
          <div className="left-stack">
            <AssignmentList
              assignments={workspace.assignments}
              selectedId={selectedId ?? undefined}
              onSelect={(id) => loadDetail(id).catch((e: Error) => setError(e.message))}
            />
            {selected && <AttributePanel attributes={selected.attributes} title="選択中の部下" />}
          </div>
        }
        center={
          selected ? (
            waitingForEval1 ? (
              <p className="hint">
                第1評価者の提出後に入力できます。右ペインで自己評価を参照してください。
              </p>
            ) : (
              <EvaluationForm
                template={selected.template}
                formData={formData}
                editable={selected.submission.can_edit}
                scoreKey="evaluator_score"
                onChange={setFormData}
              />
            )
          ) : (
            <p className="hint">左の一覧から担当者を選択してください。</p>
          )
        }
        right={
          <div className="right-stack">
            <ReferencePanel reference={workspace.reference} template={selected?.template} />
            {selected && (
              <SubmissionPanel
                submission={selected.submission}
                onSave={selected.submission.can_edit ? handleSave : undefined}
                onSubmit={selected.submission.can_submit ? handleSubmit : undefined}
                onValidate={() =>
                  validateFormData(selected.template, formData, userRole)
                }
                formData={formData}
                saving={saving}
              />
            )}
          </div>
        }
      />
    </div>
  );
}
