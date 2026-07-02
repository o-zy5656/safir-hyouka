import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { WorkspaceResponse } from "../types";
import { AttributePanel } from "./AttributePanel";
import { EvaluationForm } from "./EvaluationForm";
import { SubmissionPanel } from "./SubmissionPanel";
import { SubmitActionBar } from "./SubmitActionBar";
import { ThreePaneLayout } from "./ThreePaneLayout";
import { validateFormData } from "../utils/formValidation";

export function EvaluateeWorkspace() {
  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null);
  const [formData, setFormData] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    const data = await api.employeeWorkspace();
    setWorkspace(data);
    setFormData(data.form_data ?? {});
  };

  useEffect(() => {
    load().catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    const refresh = () => {
      load().catch(() => {});
    };
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.saveSelfEvaluation(formData);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  const handleSubmit = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.saveSelfEvaluation(formData);
      await api.submitSelfEvaluation();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "提出に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  const handleDevUnsubmit = async () => {
    if (!confirm("提出を取り消して編集可能に戻しますか？（開発用）")) return;
    setSaving(true);
    setError(null);
    try {
      await api.unsubmitSelfEvaluation();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "取り消しに失敗しました");
    } finally {
      setSaving(false);
    }
  };

  if (!workspace) return <p className="loading">{error ?? "読み込み中..."}</p>;

  return (
    <div className="workspace-page">
      <header className="topbar">
        <h1>自己評価ワークスペース</h1>
        {workspace.period_name && <span className="period">{workspace.period_name}</span>}
      </header>
      {error && <p className="error">{error}</p>}
      <ThreePaneLayout
        left={<AttributePanel attributes={workspace.attributes} />}
        center={
          <EvaluationForm
            template={workspace.template}
            formData={formData}
            editable={workspace.submission.can_edit}
            onChange={setFormData}
            footer={
              <SubmitActionBar
                canEdit={workspace.submission.can_edit}
                canSubmit={workspace.submission.can_submit}
                onSave={workspace.submission.can_edit ? handleSave : undefined}
                onSubmit={workspace.submission.can_submit ? handleSubmit : undefined}
                onValidate={() => validateFormData(workspace.template, formData)}
                saving={saving}
              />
            }
          />
        }
        right={
          <SubmissionPanel
            submission={workspace.submission}
            onSave={handleSave}
            onSubmit={handleSubmit}
            onDevUnsubmit={import.meta.env.DEV ? handleDevUnsubmit : undefined}
            onValidate={() => validateFormData(workspace.template, formData)}
            formData={formData}
            saving={saving}
          />
        }
      />
    </div>
  );
}
