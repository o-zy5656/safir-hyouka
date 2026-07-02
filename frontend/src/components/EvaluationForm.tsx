import type { FormTemplate, TextField } from "../types";

interface Props {
  template: FormTemplate;
  formData: Record<string, unknown>;
  editable: boolean;
  scoreKey?: string;
  role?: string;
  onChange: (data: Record<string, unknown>) => void;
  referenceScores?: {
    self?: Record<string, number | null>;
    evaluator1?: Record<string, number | null>;
  };
  referenceTextFields?: {
    evaluator1?: Record<string, string>;
  };
  footer?: React.ReactNode;
}

export function EvaluationForm({
  template,
  formData,
  editable,
  scoreKey = "self_score",
  role,
  onChange,
  referenceScores,
  referenceTextFields,
  footer,
}: Props) {
  const scores = (formData.scores as Record<string, number | null>) ?? {};
  const textFields = (formData.text_fields as Record<string, string>) ?? {};

  const setScore = (itemId: string, score: number) => {
    onChange({
      ...formData,
      scores: { ...scores, [itemId]: score },
    });
  };

  const setText = (fieldId: string, value: string) => {
    onChange({
      ...formData,
      text_fields: { ...textFields, [fieldId]: value },
    });
  };

  const total = Object.values(scores).reduce<number>((sum, v) => sum + (v ?? 0), 0);
  const scoring = template.scoring as { min?: number; max?: number; max_total?: number } | undefined;
  const scoreUnit = scoring?.max === 3 && scoring?.min === 1 ? "" : "点";

  const isAssessment = template.type === "assessment";
  const allTextFields = template.text_fields ?? [];
  const referenceFields = isAssessment ? allTextFields.filter((field) => field.readonly) : [];
  const selfInputFields = !isAssessment
    ? allTextFields.filter((field) => !field.readonly)
    : [];
  const editableFields = isAssessment
    ? allTextFields.filter((field) => {
        if (field.readonly) return false;
        if (!field.role) return true;
        if (!role) return false;
        return field.role === role;
      })
    : [];

  const philosophyIntro =
    referenceFields.find((f) => f.id === "philosophy")?.instruction ??
    "サフィールの理念及び今年度のスローガンを記入してください（一語一句間違えず、正確に記入してください）";

  const eval1NoteField = allTextFields.find((f) => f.id === "evaluator1_note");
  const eval1NoteValue = referenceTextFields?.evaluator1?.evaluator1_note ?? "";
  const showEval1Note =
    role === "evaluator2" && eval1NoteField && referenceTextFields?.evaluator1 != null;

  const renderTextArea = (field: TextField, value: string, readOnly?: boolean) => (
    <div
      key={field.id}
      className={[
        "text-field-block",
        readOnly || field.readonly ? "readonly-block" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <label htmlFor={field.id}>
        <strong>{field.label}</strong>
      </label>
      {field.instruction && <p className="field-instruction">{field.instruction}</p>}
      <textarea
        id={field.id}
        rows={field.multiline ? 4 : 2}
        value={value}
        readOnly={readOnly ?? (!editable || Boolean(field.readonly))}
        onChange={(e) => setText(field.id, e.target.value)}
      />
    </div>
  );

  return (
    <section className="evaluation-form">
      <h2>{template.title}</h2>
      {template.instructions && <p className="instructions">{template.instructions}</p>}

      <div className="form-table">
        {template.items.map((item) => (
          <article key={item.id} className="eval-item">
            <header>
              <span className="item-label">{item.label}</span>
              <strong>{item.name}</strong>
              {referenceScores && (
                <div className="ref-score-inline">
                  {referenceScores.self?.[item.id] != null && (
                    <span className="ref-score-chip ref-score-self">
                      本人 {referenceScores.self[item.id]}点
                    </span>
                  )}
                  {referenceScores.evaluator1?.[item.id] != null && (
                    <span className="ref-score-chip ref-score-ev1">
                      評1 {referenceScores.evaluator1[item.id]}点
                    </span>
                  )}
                </div>
              )}
            </header>
            <p className="item-element">{item.element}</p>
            <ul className="criteria-list">
              {item.criteria.map((c) => (
                <li key={c.score}>
                  <label>
                    <input
                      type="radio"
                      name={`${item.id}-${scoreKey}`}
                      checked={scores[item.id] === c.score}
                      disabled={!editable}
                      onChange={() => setScore(item.id, c.score)}
                    />
                    <span className="score">{c.score}{scoreUnit}</span> {c.text}
                  </label>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>

      <p className="total-line">
        <strong>合計:</strong> {total}
        {scoring?.max_total ? ` / ${scoring.max_total}` : " 点"}
      </p>

      {referenceScores && (referenceScores.self || referenceScores.evaluator1) && (
        <p className="ref-total-inline">
          参照合計:
          {referenceScores.self && (
            <span>
              {" "}
              本人{" "}
              {Object.values(referenceScores.self).reduce<number>(
                (s, v) => s + (v ?? 0),
                0,
              )}
              点
            </span>
          )}
          {referenceScores.evaluator1 && (
            <span>
              {" "}
              / 評1{" "}
              {Object.values(referenceScores.evaluator1).reduce<number>(
                (s, v) => s + (v ?? 0),
                0,
              )}
              点
            </span>
          )}
        </p>
      )}

      {referenceFields.length > 0 && (
        <div className="readonly-fields-section">
          <h3 className="subsection-title">理念・スローガン・実践（本人の記入）</h3>
          <p className="field-instruction section-instruction">{philosophyIntro}</p>
          {referenceFields.map((field) =>
            renderTextArea(
              field.id === "philosophy" ? { ...field, instruction: undefined } : field,
              textFields[field.id] ?? "",
              true,
            ),
          )}
        </div>
      )}

      {selfInputFields.length > 0 && (
        <div className="self-text-section">
          <h3 className="subsection-title">記述欄</h3>
          {selfInputFields.map((field) =>
            renderTextArea(field, textFields[field.id] ?? ""),
          )}
          {footer}
        </div>
      )}

      {isAssessment && (editableFields.length > 0 || showEval1Note) && (
        <div className="evaluator-text-section">
          <h3 className="subsection-title">評価者の記入</h3>
          {showEval1Note && eval1NoteField && (
            <div className="text-field-block readonly-block">
              <label htmlFor="ref_evaluator1_note">
                <strong>{eval1NoteField.label}</strong>
              </label>
              <textarea
                id="ref_evaluator1_note"
                rows={4}
                value={eval1NoteValue}
                readOnly
              />
            </div>
          )}
          {editableFields.map((field) =>
            renderTextArea(field, textFields[field.id] ?? ""),
          )}
          {footer}
        </div>
      )}

      {isAssessment &&
        editableFields.length === 0 &&
        !showEval1Note &&
        footer}
      {!isAssessment && selfInputFields.length === 0 && footer}
    </section>
  );
}
