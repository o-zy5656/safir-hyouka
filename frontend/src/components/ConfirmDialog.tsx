interface Props {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  reason?: string;
  onReasonChange?: (value: string) => void;
  reasonLabel?: string;
  reasonPlaceholder?: string;
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "提出する",
  cancelLabel = "キャンセル",
  onConfirm,
  onCancel,
  reason,
  onReasonChange,
  reasonLabel,
  reasonPlaceholder,
}: Props) {
  if (!open) return null;

  return (
    <div className="confirm-overlay" onClick={onCancel} role="presentation">
      <div
        className="confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id="confirm-dialog-title">{title}</h3>
        <p>{message}</p>
        {onReasonChange && (
          <label className="confirm-reason-field">
            {reasonLabel ?? "理由（任意）"}
            <textarea
              rows={3}
              value={reason ?? ""}
              placeholder={reasonPlaceholder}
              onChange={(e) => onReasonChange(e.target.value)}
            />
          </label>
        )}
        <div className="confirm-actions">
          <button type="button" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button type="button" className="primary danger-btn" onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
