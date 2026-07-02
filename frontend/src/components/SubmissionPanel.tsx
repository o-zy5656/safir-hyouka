import { useEffect, useState } from "react";
import type { SubmissionPanel as SubmissionPanelType } from "../types";
import { SubmitActionBar } from "./SubmitActionBar";

interface Props {
  submission: SubmissionPanelType;
  onSave?: () => void | Promise<void>;
  onSubmit?: () => void;
  onDevUnsubmit?: () => void;
  onValidate?: () => string[];
  formData?: Record<string, unknown>;
  saving?: boolean;
}

const statusLabel: Record<string, string> = {
  pending: "未着手",
  draft: "下書き",
  submitted: "提出済み",
  returned: "差し戻し",
};

export function SubmissionPanel({
  submission,
  onSave,
  onSubmit,
  onDevUnsubmit,
  onValidate,
  formData,
  saving,
}: Props) {
  const [saveNotice, setSaveNotice] = useState<string | null>(null);

  useEffect(() => {
    // reset notice when form changes
    setSaveNotice(null);
  }, [formData]);

  const handleSaveClick = async () => {
    if (!onSave) return;
    try {
      await onSave();
      const now = new Date().toLocaleString("ja-JP");
      setSaveNotice(`下書きを保存しました（${now}）`);
      window.setTimeout(() => setSaveNotice(null), 4000);
    } catch {
      setSaveNotice(null);
    }
  };

  return (
    <section>
      <h2>提出・期限</h2>
      <p className="status-badge" data-status={submission.status}>
        {statusLabel[submission.status] ?? submission.status}
      </p>
      {saveNotice && (
        <p className="success save-notice" role="status" aria-live="polite">
          {saveNotice}
        </p>
      )}
      {submission.deadline && (
        <p>
          <strong>期限:</strong> {new Date(submission.deadline).toLocaleString("ja-JP")}
        </p>
      )}
      {submission.submitted_at && (
        <p>
          <strong>提出日時:</strong> {new Date(submission.submitted_at).toLocaleString("ja-JP")}
        </p>
      )}
      <SubmitActionBar
        canEdit={submission.can_edit}
        canSubmit={submission.can_submit}
        onSave={onSave ? handleSaveClick : undefined}
        onSubmit={onSubmit}
        onValidate={onValidate}
        saving={saving}
      />
      {submission.status === "submitted" && (
        <>
          <p className="hint">提出後は編集できません。修正が必要な場合は人事に差し戻しを依頼してください。</p>
          {onDevUnsubmit && (
            <button type="button" className="dev-unsubmit" onClick={onDevUnsubmit} disabled={saving}>
              提出を取り消す（開発用）
            </button>
          )}
        </>
      )}
      {submission.status === "returned" && (
        <p className="hint">差し戻されました。内容を修正して再度提出してください。</p>
      )}
    </section>
  );
}
