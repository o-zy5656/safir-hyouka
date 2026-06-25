import type { FormTemplate } from "../types";

interface Props {
  template: FormTemplate;
  formData: Record<string, unknown>;
  editable: boolean;
  scoreKey?: string;
  onChange: (data: Record<string, unknown>) => void;
}

export function EvaluationForm({
  template,
  formData,
  editable,
  scoreKey = "self_score",
  onChange,
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

  return (
    <section>
      <h2>{template.title}</h2>
      {template.instructions && <p className="instructions">{template.instructions}</p>}

      <div className="form-table">
        {template.items.map((item) => (
          <article key={item.id} className="eval-item">
            <header>
              <span className="item-label">{item.label}</span>
              <strong>{item.name}</strong>
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
                    <span className="score">{c.score}点</span> {c.text}
                  </label>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>

      <p className="total-line">
        <strong>合計点数:</strong> {total} 点
      </p>

      {template.text_fields?.map((field) => (
        <div key={field.id} className="text-field-block">
          <label htmlFor={field.id}>
            <strong>{field.label}</strong>
          </label>
          {field.instruction && <p className="field-instruction">{field.instruction}</p>}
          <textarea
            id={field.id}
            rows={field.multiline ? 4 : 2}
            value={textFields[field.id] ?? ""}
            readOnly={!editable || field.readonly}
            onChange={(e) => setText(field.id, e.target.value)}
          />
        </div>
      ))}
    </section>
  );
}
