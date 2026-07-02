import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { EvaluatorWorkspaceResponse } from "../types";
import { AttributePanel } from "./AttributePanel";
import { EvaluationForm } from "./EvaluationForm";
import { SubmissionPanel } from "./SubmissionPanel";
import { ThreePaneLayout } from "./ThreePaneLayout";
import { validateFormData } from "../utils/formValidation";
import { AssignmentList, EvaluatorSummary } from "./evaluator/AssignmentList";
import { EvaluatorReferencePanel } from "./evaluator/EvaluatorReferencePanel";
import { SubmitActionBar } from "./SubmitActionBar";

const roleTitle: Record<string, string> = {
  evaluator1: "第1評価者",
  evaluator2: "第2評価者",
};

export function EvaluatorWorkspace() {
  const [workspace, setWorkspace] = useState<EvaluatorWorkspaceResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [formData, setFormData] = useState<Record<string, unknown>>({});
  const [savedFormData, setSavedFormData] = useState<Record<string, unknown>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [userRole, setUserRole] = useState<string>("evaluator1");
  const [isHqEvaluator, setIsHqEvaluator] = useState(false);

  const loadList = async () => {
    const data = await api.evaluatorWorkspace();
    setWorkspace(data);
    return data;
  };

  const loadDetail = async (id: string) => {
    const data = await api.evaluatorAssignment(id);
    setWorkspace((prev) => ({ ...data, assignments: prev?.assignments ?? data.assignments }));
    setSelectedId(id);
    const loaded = data.selected?.form_data ?? {};
    setFormData(loaded);
    setSavedFormData(loaded);
    setError(null);
  };

  const isFormDirty =
    JSON.stringify(formData) !== JSON.stringify(savedFormData);

  const handleSelectAssignment = (id: string) => {
    if (selectedId && id !== selectedId && isFormDirty) {
      if (!confirm("未保存の変更があります。担当者を切り替えますか？")) return;
    }
    loadDetail(id).catch((e: Error) => setError(e.message));
  };

  useEffect(() => {
    api.me().then((u) => {
      setUserRole(u.role);
      setIsHqEvaluator(Boolean(u.is_hq_evaluator));
    }).catch(() => {});
    loadList()
      .then((data) => {
        const first = data.assignments.find(
          (a) => a.evaluation_id !== "00000000-0000-0000-0000-000000000000",
        );
        if (first) loadDetail(first.evaluation_id).catch(() => undefined);
      })
      .catch((e: Error) => setError(e.message));
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
  const selectedAssignment = workspace.assignments.find((a) => a.evaluation_id === selectedId);
  const waitingSelf = selectedAssignment?.self_eval_status !== "submitted";
  const hqReviewOnly = Boolean(selectedAssignment?.hq_review_only);
  const skipsEval1 = Boolean(selectedAssignment?.skips_eval1);
  const waitingEval1 =
    userRole === "evaluator2" &&
    !skipsEval1 &&
    !hqReviewOnly &&
    selectedAssignment?.eval1_status !== "submitted" &&
    !waitingSelf;

  const reference = workspace.reference as
    | {
        self_evaluation?: { scores?: Record<string, number> };
        evaluator1?: {
          scores?: Record<string, number>;
          text_fields?: Record<string, string>;
        };
        evaluator2?: { scores?: Record<string, number> };
      }
    | undefined;
  const referenceScores = {
    self: reference?.self_evaluation?.scores,
    evaluator1:
      userRole === "evaluator2" && !hqReviewOnly ? reference?.evaluator1?.scores : undefined,
  };

  const centerContent = () => {
    if (!selected) {
      return <p className="hint">左の一覧から担当者を選択してください。</p>;
    }
    if (waitingSelf) {
      return (
        <div className="waiting-panel">
          <h2>自己評価の提出待ち</h2>
          <p>
            <strong>{selected.attributes.name}</strong> さんの自己評価がまだ提出されていません。
          </p>
          <p className="hint">提出後に自己評価の参照と考課入力が可能になります。</p>
        </div>
      );
    }
    if (waitingEval1) {
      return (
        <div className="waiting-panel">
          <h2>第1評価者の提出待ち</h2>
          <p>
            自己評価は参照できます。考課の入力は第1評価者の提出後に行えます。
          </p>
          <EvaluatorReferencePanel
            reference={workspace.reference}
            template={selected?.template}
            userRole={userRole}
          />
        </div>
      );
    }
    if (hqReviewOnly) {
      return (
        <div className="waiting-panel">
          <h2>考課結果の確認</h2>
          <p>
            施設長による二次評価が提出済みです。内容は右の参照パネルおよび下記で確認できます（編集不可）。
          </p>
          <EvaluatorReferencePanel
            reference={workspace.reference}
            template={selected?.template}
            userRole={userRole}
            showEval2
          />
        </div>
      );
    }
    return (
      <EvaluationForm
        template={selected.template}
        formData={formData}
        editable={selected.submission.can_edit}
        scoreKey="evaluator_score"
        role={userRole}
        onChange={setFormData}
        referenceScores={referenceScores}
        referenceTextFields={{
          evaluator1: reference?.evaluator1?.text_fields,
        }}
        footer={
          <SubmitActionBar
            canEdit={selected.submission.can_edit}
            canSubmit={selected.submission.can_submit}
            onSave={selected.submission.can_edit ? handleSave : undefined}
            onSubmit={selected.submission.can_submit ? handleSubmit : undefined}
            onValidate={() => validateFormData(selected.template, formData, userRole)}
            saving={saving}
          />
        }
      />
    );
  };

  return (
    <div className="workspace-page">
      <header className="topbar">
        <h1>
          {isHqEvaluator
            ? "本部考課ワークスペース"
            : userRole === "evaluator2" &&
                workspace.assignments.some((a) => a.uses_facility_director_form)
              ? "本部考課ワークスペース"
              : "考課ワークスペース"}
        </h1>
        <span className="role-badge">{roleTitle[userRole] ?? userRole}</span>
        {workspace.period_name && <span className="period">{workspace.period_name}</span>}
      </header>
      {error && <p className="error">{error}</p>}
      <ThreePaneLayout
        left={
          <div className="left-stack">
            <EvaluatorSummary
              assignments={workspace.assignments}
              userRole={userRole}
              isHqEvaluator={isHqEvaluator}
            />
            <AssignmentList
              assignments={workspace.assignments}
              selectedId={selectedId ?? undefined}
              userRole={userRole}
              onSelect={handleSelectAssignment}
            />
            {selected && <AttributePanel attributes={selected.attributes} title="選択中の部下" />}
          </div>
        }
        center={centerContent()}
        right={
          <div className="right-stack">
            <EvaluatorReferencePanel
              reference={workspace.reference}
              template={selected?.template}
              userRole={userRole}
              showEval2={hqReviewOnly}
            />
            {selected && !waitingSelf && !hqReviewOnly && (
              <SubmissionPanel
                submission={selected.submission}
                onSave={selected.submission.can_edit ? handleSave : undefined}
                onSubmit={selected.submission.can_submit ? handleSubmit : undefined}
                onValidate={() => validateFormData(selected.template, formData, userRole)}
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
