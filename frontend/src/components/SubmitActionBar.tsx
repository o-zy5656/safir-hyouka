import { useEffect, useState } from "react";
import { ConfirmDialog } from "./ConfirmDialog";

interface Props {
  canEdit?: boolean;
  canSubmit?: boolean;
  onSave?: () => void | Promise<void>;
  onSubmit?: () => void;
  onValidate?: () => string[];
  saving?: boolean;
  className?: string;
}

export function SubmitActionBar({
  canEdit,
  canSubmit,
  onSave,
  onSubmit,
  onValidate,
  saving,
  className,
}: Props) {
  const [showConfirm, setShowConfirm] = useState(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  useEffect(() => {
    setValidationErrors([]);
  }, [onValidate]);

  if (!onSave && !onSubmit) return null;

  const handleSubmitClick = () => {
    const errors = onValidate?.() ?? [];
    if (errors.length > 0) {
      setValidationErrors(errors);
      return;
    }
    setValidationErrors([]);
    setShowConfirm(true);
  };

  return (
    <div className={["form-bottom-actions", className].filter(Boolean).join(" ")}>
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
        {onSave && canEdit && (
          <button type="button" onClick={onSave} disabled={saving}>
            下書き保存
          </button>
        )}
        {onSubmit && canSubmit && (
          <button type="button" className="primary" onClick={handleSubmitClick} disabled={saving}>
            提出する
          </button>
        )}
      </div>
      <ConfirmDialog
        open={showConfirm}
        title="提出の確認"
        message="提出すると内容の編集ができなくなります。本当に提出してよろしいですか？"
        confirmLabel="提出する"
        cancelLabel="キャンセル"
        onConfirm={() => {
          setShowConfirm(false);
          onSubmit?.();
        }}
        onCancel={() => setShowConfirm(false)}
      />
    </div>
  );
}
