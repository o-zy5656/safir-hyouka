import { useEffect, useState } from "react";
import type { SubmissionPanel as SubmissionPanelType } from "../types";
import { ConfirmDialog } from "./ConfirmDialog";

interface Props {
  submission: SubmissionPanelType;
  onSave?: () => void;
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
  const [showConfirm, setShowConfirm] = useState(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  useEffect(() => {
    setValidationErrors([]);
  }, [formData]);

  const handleSubmitClick = () => {
    const errors = onValidate?.() ?? [];
    if (errors.length > 0) {
      setValidationErrors(errors);
      return;
    }
    setValidationErrors([]);
    setShowConfirm(true);
  };

  const handleConfirmSubmit = () => {
    setShowConfirm(false);
    onSubmit?.();
  };

  return (
    <section>
      <h2>提出・期限</h2>
      <p className="status-badge" data-status={submission.status}>
        {statusLabel[submission.status] ?? submission.status}
      </p>
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
      {validationErrors.length > 0 && (
        <div className="validation-errors" role="alert">
          <strong>未入力のため提出できません</strong>
          <ul>
            {validationErrors.map((msg) => (
              <li key={msg}>{msg}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="button-row">
        {onSave && submission.can_edit && (
          <button type="button" onClick={onSave} disabled={saving}>
            下書き保存
          </button>
        )}
        {onSubmit && submission.can_submit && (
          <button type="button" className="primary" onClick={handleSubmitClick} disabled={saving}>
            提出する
          </button>
        )}
      </div>
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

      <ConfirmDialog
        open={showConfirm}
        title="提出の確認"
        message="提出すると内容の編集ができなくなります。本当に提出してよろしいですか？"
        confirmLabel="提出する"
        cancelLabel="キャンセル"
        onConfirm={handleConfirmSubmit}
        onCancel={() => setShowConfirm(false)}
      />
    </section>
  );
}
