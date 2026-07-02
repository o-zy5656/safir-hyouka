import type { FormTemplate } from "../../types";

interface ScoreData {
  scores?: Record<string, number>;
  text_fields?: Record<string, string>;
}

interface Props {
  reference?: Record<string, unknown>;
  template?: FormTemplate;
  userRole: string;
  showEval2?: boolean;
}

export function EvaluatorReferencePanel({ reference, template, userRole, showEval2 }: Props) {
  if (!reference || Object.keys(reference).length === 0) {
    return (
      <section className="reference-panel">
        <h2>参照</h2>
        <p className="hint">本人の自己評価提出後、採点・記述内容がここに表示されます。</p>
      </section>
    );
  }

  const selfEval = reference.self_evaluation as ScoreData;
  const eval1 = reference.evaluator1 as ScoreData | undefined;
  const eval2 = reference.evaluator2 as ScoreData | undefined;
  const includeEval2 = showEval2 ?? Boolean(eval2);

  const labelFor = (itemId: string) => {
    const item = template?.items.find((i) => i.id === itemId);
    return item ? `${item.label} ${item.name}` : itemId;
  };

  const selfScores = selfEval?.scores ?? {};
  const eval1Scores = eval1?.scores ?? {};
  const eval2Scores = eval2?.scores ?? {};
  const itemIds = template?.items.map((i) => i.id) ?? Object.keys(selfScores);

  const selfTotal = Object.values(selfScores).reduce((s, v) => s + (v ?? 0), 0);
  const eval1Total = eval1
    ? Object.values(eval1Scores).reduce((s, v) => s + (v ?? 0), 0)
    : null;
  const eval2Total = eval2
    ? Object.values(eval2Scores).reduce((s, v) => s + (v ?? 0), 0)
    : null;

  const textFields = selfEval?.text_fields ?? {};
  const readonlyLabels: Record<string, string> = {};
  for (const field of template?.text_fields ?? []) {
    if (field.readonly) readonlyLabels[field.id] = field.label;
  }

  const showEval1Col = !includeEval2 && userRole === "evaluator2" && eval1;
  const showEval2Col = includeEval2 && eval2;

  return (
    <section className="reference-panel">
      <h2>{includeEval2 ? "考課結果（確認）" : "参照"}</h2>

      <h3 className="ref-section-title">採点比較</h3>
      <div className="ref-table-wrap">
        <table className="ref-table">
          <thead>
            <tr>
              <th>項目</th>
              <th>本人</th>
              {(showEval1Col || (includeEval2 && eval1)) && <th>評価者1</th>}
              {showEval2Col && <th>施設長</th>}
            </tr>
          </thead>
          <tbody>
            {itemIds.map((id) => {
              const selfScore = selfScores[id];
              const ev1Score = eval1Scores[id];
              const ev2Score = eval2Scores[id];
              const hasDiff =
                showEval1Col &&
                eval1 &&
                selfScore != null &&
                ev1Score != null &&
                selfScore !== ev1Score;
              return (
                <tr key={id} className={hasDiff ? "score-diff-row" : ""}>
                  <td>{labelFor(id)}</td>
                  <td className="score-cell">{selfScore ?? "—"}</td>
                  {(showEval1Col || (includeEval2 && eval1)) && (
                    <td className={`score-cell ${hasDiff ? "score-diff" : ""}`}>
                      {ev1Score ?? "—"}
                    </td>
                  )}
                  {showEval2Col && (
                    <td className="score-cell">{ev2Score ?? "—"}</td>
                  )}
                </tr>
              );
            })}
            <tr className="total-row">
              <td>合計</td>
              <td className="score-cell">{selfTotal || "—"}</td>
              {(showEval1Col || (includeEval2 && eval1)) && (
                <td className="score-cell">{eval1Total ?? "—"}</td>
              )}
              {showEval2Col && (
                <td className="score-cell">{eval2Total ?? "—"}</td>
              )}
            </tr>
          </tbody>
        </table>
      </div>

      {showEval1Col && eval1 && (
        <p className="ref-legend">
          <span className="score-diff-sample" /> 本人と評価者1で採点が異なる項目
        </p>
      )}

      {Object.entries(textFields).some(([, v]) => v?.trim()) && (
        <>
          <h3 className="ref-section-title">本人の記述</h3>
          {Object.entries(textFields).map(([id, value]) => {
            if (!value?.trim()) return null;
            return (
              <div key={id} className="ref-text-block">
                <strong>{readonlyLabels[id] ?? id}</strong>
                <p>{value}</p>
              </div>
            );
          })}
        </>
      )}

      {eval1?.text_fields?.evaluator1_note?.trim() && (
        <>
          <h3 className="ref-section-title">第1評価者の特記事項</h3>
          <div className="ref-text-block">
            <p>{eval1.text_fields.evaluator1_note}</p>
          </div>
        </>
      )}

      {eval2?.text_fields?.evaluator2_note?.trim() && (
        <>
          <h3 className="ref-section-title">施設長の特記事項</h3>
          <div className="ref-text-block">
            <p>{eval2.text_fields.evaluator2_note}</p>
          </div>
        </>
      )}
    </section>
  );
}
