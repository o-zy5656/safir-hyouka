import { useEffect, useRef, useState } from "react";

export function BonusNoteCell({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(value);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!open) setDraft(value);
  }, [open, value]);

  useEffect(() => {
    if (open) textareaRef.current?.focus();
  }, [open]);

  const close = (save: boolean) => {
    if (save && draft !== value) onChange(draft);
    setOpen(false);
  };

  const preview = value.trim() || "—";

  return (
    <>
      <button
        type="button"
        className={`bonus-note-preview${value.trim() ? " has-text" : ""}`}
        onClick={() => setOpen(true)}
        title={value.trim() ? "クリックで全文表示・編集" : "クリックで備考を入力"}
      >
        <span className="bonus-note-preview-text">{preview}</span>
      </button>
      {open && (
        <div
          className="bonus-note-modal-backdrop"
          onClick={() => close(true)}
          role="presentation"
        >
          <div
            className="bonus-note-modal"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="備考"
          >
            <div className="bonus-note-modal-header">
              <h3>備考</h3>
              <button type="button" className="bonus-note-modal-close" onClick={() => close(true)}>
                閉じる
              </button>
            </div>
            <textarea
              ref={textareaRef}
              className="bonus-note-modal-textarea"
              rows={8}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
            />
            <div className="bonus-note-modal-actions">
              <button type="button" onClick={() => close(true)}>
                反映して閉じる
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
