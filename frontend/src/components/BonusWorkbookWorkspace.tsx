import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import { BonusNoteCell } from "./BonusNoteCell";
import type { BonusWorkbookResponse, BonusWorkbookRow, BonusWorkbookSummary, FacilityItem } from "../types";

const DEFAULT_BONUS_FACILITY_KEY = "inaha";
const FACILITY_DIRECTORS_BONUS_KEY = "facility_directors";
const PROVISION_MONTH_OPTIONS = [6, 12] as const;
const AMOUNTS_AUTOSAVE_MS = 700;
const COLUMN_PREF_KEY = "bonus-workbook-column-prefs";

type ColumnPrefs = {
  showCut: boolean;
  showPromotion: boolean;
};

function loadColumnPrefs(facilityKey: string): ColumnPrefs {
  try {
    const raw = localStorage.getItem(`${COLUMN_PREF_KEY}:${facilityKey}`);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<ColumnPrefs>;
      return {
        showCut: parsed.showCut !== false,
        showPromotion: parsed.showPromotion !== false,
      };
    }
  } catch {
    /* ignore */
  }
  return { showCut: true, showPromotion: true };
}

function saveColumnPrefs(facilityKey: string, prefs: ColumnPrefs) {
  localStorage.setItem(`${COLUMN_PREF_KEY}:${facilityKey}`, JSON.stringify(prefs));
}

function computeFinal(row: BonusWorkbookRow): number | null {
  const { self_score, eval1_score, eval2_score } = row;
  if (eval1_score != null && eval2_score != null) {
    return Math.round((eval1_score + eval2_score) / 2);
  }
  if (eval2_score != null) return eval2_score;
  if (eval1_score != null) return eval1_score;
  return self_score ?? null;
}

function facilityOptionLabel(facility: FacilityItem): string {
  return facility.label;
}

function parseBonusAmount(value: string): number | null {
  if (value.trim() === "") return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) return null;
  return Math.round(parsed);
}

function formatSenYen(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${Math.round(value).toLocaleString("ja-JP")}千円`;
}

function normalizeProvisionMonths(value: number): 6 | 12 {
  return value === 6 ? 6 : 12;
}

function buildAmountsSnapshot(
  facility: string,
  fiscalYear: number,
  rows: BonusWorkbookRow[],
  provisionMonthly: number,
  provisionMonths: number,
): string {
  return JSON.stringify({
    facility,
    fiscalYear,
    provisionMonthly,
    provisionMonths: normalizeProvisionMonths(provisionMonths),
    rows: rows.map((row) => ({
      employee_id: row.employee_id ?? "",
      bonus_facility_key: row.bonus_facility_key ?? null,
      proposed_bonus_amount: row.proposed_bonus_amount ?? null,
      bonus_amount: row.bonus_amount ?? null,
      prior_summer_amount: row.prior_summer_amount ?? null,
      prior_winter_amount: row.prior_winter_amount ?? null,
    })),
  });
}

function rowsWorkbookComparableState(source: BonusWorkbookRow[]): BonusWorkbookRow[] {
  return source.map((row) => {
    const {
      proposed_bonus_amount: _p,
      bonus_amount: _b,
      prior_summer_amount: _ps,
      prior_winter_amount: _pw,
      ...rest
    } = {
      ...row,
      final_score: computeFinal(row),
    };
    return rest as BonusWorkbookRow;
  });
}

function computeLocalSummary(
  rows: BonusWorkbookRow[],
  provisionMonthly: number,
  provisionMonths: number,
  socialInsuranceRate: number,
  serverSummary?: BonusWorkbookSummary | null,
  isDirectorsView = false,
): BonusWorkbookSummary {
  const totalProposed = rows.reduce((sum, row) => sum + (row.proposed_bonus_amount ?? 0), 0);
  const totalBonus = rows.reduce((sum, row) => sum + (row.bonus_amount ?? 0), 0);
  const totalWithSocial = Math.round(totalBonus * (1 + socialInsuranceRate));
  const provisionTotal = isDirectorsView
    ? (serverSummary?.provision_total ?? 0)
    : provisionMonthly * provisionMonths;
  const difference = provisionTotal - totalWithSocial;

  return {
    total_proposed: totalProposed,
    total_bonus: totalBonus,
    total_with_social_insurance: totalWithSocial,
    provision_monthly: provisionMonthly,
    provision_months: provisionMonths,
    provision_total: provisionTotal,
    difference,
    social_insurance_rate: socialInsuranceRate,
  };
}

export function BonusWorkbookWorkspace({
  canManageAllFacilities,
  userFacilityKey,
  userFacilityLabel,
}: {
  canManageAllFacilities: boolean;
  userFacilityKey?: string;
  userFacilityLabel?: string;
}) {
  const scopedFacilityKey = userFacilityKey || DEFAULT_BONUS_FACILITY_KEY;
  const [facilities, setFacilities] = useState<FacilityItem[]>([]);
  const [facilityKey, setFacilityKey] = useState(DEFAULT_BONUS_FACILITY_KEY);
  const [fiscalYear, setFiscalYear] = useState<number | undefined>(undefined);
  const [data, setData] = useState<BonusWorkbookResponse | null>(null);
  const [rows, setRows] = useState<BonusWorkbookRow[]>([]);
  const [provisionMonthly, setProvisionMonthly] = useState(0);
  const [provisionMonths, setProvisionMonths] = useState(12);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);
  const [amountsSaving, setAmountsSaving] = useState(false);
  const [showCutColumn, setShowCutColumn] = useState(true);
  const [showPromotionColumn, setShowPromotionColumn] = useState(true);
  const savedAmountsKeyRef = useRef("");
  const latestAmountsRef = useRef({
    facilityKey: DEFAULT_BONUS_FACILITY_KEY,
    fiscalYear: undefined as number | undefined,
    rows: [] as BonusWorkbookRow[],
    provisionMonthly: 0,
    provisionMonths: 12 as 6 | 12,
    canManageAllFacilities: false,
    isDirectorsView: false,
    bonusSheetAvailable: false,
    isReadOnly: false,
  });

  const selectedFacility = facilities.find((facility) => facility.key === facilityKey);
  const isDirectorsView =
    facilityKey === FACILITY_DIRECTORS_BONUS_KEY || data?.facility_key === FACILITY_DIRECTORS_BONUS_KEY;
  const bonusSheetAvailable = data?.bonus_sheet_available ?? rows.length > 0;

  useEffect(() => {
    api
      .facilities()
      .then((response) => {
        setFacilities(response.facilities);
        if (canManageAllFacilities) {
          setFacilityKey((current) =>
            response.facilities.some((facility) => facility.key === current)
              ? current
              : DEFAULT_BONUS_FACILITY_KEY,
          );
        } else {
          const ownFacility = response.facilities.find((facility) => facility.key === scopedFacilityKey);
          setFacilityKey(ownFacility?.key ?? scopedFacilityKey);
        }
      })
      .catch((e: Error) => setError(e.message));
  }, [canManageAllFacilities, scopedFacilityKey]);

  const load = async (facility = facilityKey, year = fiscalYear) => {
    setLoading(true);
    try {
      const response = await api.bonusWorkbook(facility, year ?? undefined);
      setData(response);
      setRows(response.rows);
      setProvisionMonthly(response.provision_monthly ?? 0);
      setProvisionMonths(normalizeProvisionMonths(response.provision_months ?? 12));
      savedAmountsKeyRef.current = buildAmountsSnapshot(
        facility,
        response.fiscal_year,
        response.rows,
        response.provision_monthly ?? 0,
        response.provision_months ?? 12,
      );
      setError(null);
    } catch (e) {
      setData(null);
      setRows([]);
      setError(e instanceof Error ? e.message : "読み込みに失敗しました");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!facilityKey) return;
    const prefs = loadColumnPrefs(facilityKey);
    setShowCutColumn(prefs.showCut);
    setShowPromotionColumn(prefs.showPromotion);
  }, [facilityKey]);

  useEffect(() => {
    if (!facilityKey) return;
    load(facilityKey, fiscalYear).catch(() => undefined);
  }, [facilityKey, fiscalYear]);

  const isReadOnly = data?.read_only ?? false;
  const canEditProposed = !canManageAllFacilities && !isReadOnly;
  const canEditBonus = canManageAllFacilities && !isReadOnly;
  const canEditProvision = !canManageAllFacilities && !isDirectorsView && !isReadOnly;
  const availableFiscalYears = data?.available_fiscal_years ?? [];
  const currentFiscalYear = data?.current_fiscal_year;

  latestAmountsRef.current = {
    facilityKey,
    fiscalYear: data?.fiscal_year,
    rows,
    provisionMonthly,
    provisionMonths: normalizeProvisionMonths(provisionMonths),
    canManageAllFacilities,
    isDirectorsView,
    bonusSheetAvailable,
    isReadOnly,
  };

  const amountsSnapshot = useMemo(
    () =>
      buildAmountsSnapshot(
        facilityKey,
        data?.fiscal_year ?? 0,
        rows,
        provisionMonthly,
        normalizeProvisionMonths(provisionMonths),
      ),
    [facilityKey, data?.fiscal_year, rows, provisionMonthly, provisionMonths],
  );

  const isAmountsDirty = amountsSnapshot !== savedAmountsKeyRef.current;

  const isWorkbookDirty = useMemo(
    () =>
      JSON.stringify(rowsWorkbookComparableState(rows)) !==
      JSON.stringify(rowsWorkbookComparableState(data?.rows ?? [])),
    [rows, data?.rows],
  );

  const persistAmounts = useCallback(async (silent = true) => {
    const snap = latestAmountsRef.current;
    if (!snap.bonusSheetAvailable || snap.isReadOnly || snap.fiscalYear == null) return;
    const snapshot = buildAmountsSnapshot(
      snap.facilityKey,
      snap.fiscalYear,
      snap.rows,
      snap.provisionMonthly,
      snap.provisionMonths,
    );
    if (snapshot === savedAmountsKeyRef.current) return;

    setAmountsSaving(true);
    try {
      const response = await api.saveBonusAmounts(
        snap.rows,
        snap.facilityKey,
        {
          fiscal_year: snap.fiscalYear,
          ...(!snap.canManageAllFacilities && !snap.isDirectorsView
            ? {
                provision_monthly: snap.provisionMonthly,
                provision_months: snap.provisionMonths,
              }
            : {}),
        },
      );
      savedAmountsKeyRef.current = snapshot;
      setData((prev) =>
        prev
          ? {
              ...prev,
              rows: snap.rows,
              provision_monthly: response.provision_monthly,
              provision_months: normalizeProvisionMonths(response.provision_months),
              summary: response.summary,
            }
          : prev,
      );
      setProvisionMonths(normalizeProvisionMonths(response.provision_months));
      if (!silent) {
        setMessage("賞与金額を保存しました");
      }
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "賞与金額の保存に失敗しました");
    } finally {
      setAmountsSaving(false);
    }
  }, []);

  useEffect(() => {
    if (!data || !bonusSheetAvailable || loading || isReadOnly) return;
    if (!isAmountsDirty) return;
    const timer = window.setTimeout(() => {
      persistAmounts(true).catch(() => undefined);
    }, AMOUNTS_AUTOSAVE_MS);
    return () => window.clearTimeout(timer);
  }, [amountsSnapshot, bonusSheetAvailable, data, isAmountsDirty, isReadOnly, loading, persistAmounts]);

  useEffect(() => {
    return () => {
      const snap = latestAmountsRef.current;
      if (!snap.bonusSheetAvailable || snap.isReadOnly || snap.fiscalYear == null) return;
      const snapshot = buildAmountsSnapshot(
        snap.facilityKey,
        snap.fiscalYear,
        snap.rows,
        snap.provisionMonthly,
        snap.provisionMonths,
      );
      if (snapshot === savedAmountsKeyRef.current) return;
      void api
        .saveBonusAmounts(
          snap.rows,
          snap.facilityKey,
          {
            fiscal_year: snap.fiscalYear,
            ...(!snap.canManageAllFacilities && !snap.isDirectorsView
              ? {
                  provision_monthly: snap.provisionMonthly,
                  provision_months: snap.provisionMonths,
                }
              : {}),
          },
        )
        .catch(() => undefined);
    };
  }, [facilityKey]);

  const summary = useMemo(
    () =>
      computeLocalSummary(
        rows,
        provisionMonthly,
        provisionMonths,
        data?.summary.social_insurance_rate ?? 0.15,
        data?.summary,
        isDirectorsView,
      ),
    [rows, provisionMonthly, provisionMonths, data?.summary, isDirectorsView],
  );

  const updateRow = (rowNumber: number, patch: Partial<BonusWorkbookRow>) => {
    if (isReadOnly) return;
    setRows((prev) =>
      prev.map((row) => {
        if (row.row_number !== rowNumber) return row;
        const next = { ...row, ...patch };
        return { ...next, final_score: computeFinal(next) };
      }),
    );
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const payload = rows.map((row) => ({ ...row, final_score: computeFinal(row) }));
      await api.saveBonusWorkbook(payload, facilityKey, {
        fiscal_year: data?.fiscal_year,
        ...(!canManageAllFacilities && !isDirectorsView
          ? {
              provision_monthly: provisionMonthly,
              provision_months: normalizeProvisionMonths(provisionMonths),
            }
          : {}),
      });
      await load(facilityKey, data?.fiscal_year);
      setMessage("賞与資料を保存しました");
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  const handleSyncRoster = async () => {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api.syncBonusRoster(facilityKey);
      await load(facilityKey, data?.fiscal_year);
      setMessage(`名簿から ${result.updated_rows} 名分の氏名・役職を反映しました`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "名簿反映に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  const handleSync = async () => {
    if (
      !confirm(
        "名簿の氏名・役職に加え、提出済み考課（採点・特記・8点/6点未満件数・昇給有）を反映します。\n" +
          "順位・ランク（A10% B20% C40% D20% E10%）も考課点順に自動設定されます。よろしいですか？",
      )
    ) {
      return;
    }
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api.syncBonusWorkbook(facilityKey);
      await load(facilityKey, data?.fiscal_year);
      setMessage(`考課データを ${result.updated_rows} 名分反映しました`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "反映に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  const handleExport = async () => {
    setError(null);
    try {
      await api.exportBonusWorkbook(
        `賞与表_${data?.facility ?? facilityKey}.xlsx`,
        facilityKey,
      );
      setMessage("Excel をダウンロードしました");
    } catch (e) {
      setError(e instanceof Error ? e.message : "ダウンロードに失敗しました");
    }
  };

  if (loading && !data) {
    return (
      <div className="workspace-page bonus-workbook-page">
        <p className="loading">{error ?? "読み込み中..."}</p>
      </div>
    );
  }

  const facilityLabel =
    data?.facility ?? selectedFacility?.label ?? "サフィールいなは";

  const hiddenInsightColumns =
    (!isDirectorsView && !showCutColumn ? 1 : 0) +
    (!isDirectorsView && !showPromotionColumn ? 1 : 0);
  const tableWrapClassName = [
    "bonus-table-wrap",
    !isDirectorsView && !showCutColumn ? "bonus-hide-cut" : "",
    !isDirectorsView && !showPromotionColumn ? "bonus-hide-promo" : "",
    hiddenInsightColumns === 1 ? "bonus-note-grow-1" : "",
    hiddenInsightColumns >= 2 ? "bonus-note-grow-2" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const updateColumnPref = (patch: Partial<ColumnPrefs>) => {
    const next = {
      showCut: patch.showCut ?? showCutColumn,
      showPromotion: patch.showPromotion ?? showPromotionColumn,
    };
    setShowCutColumn(next.showCut);
    setShowPromotionColumn(next.showPromotion);
    saveColumnPrefs(facilityKey, next);
  };

  return (
    <div className="workspace-page bonus-workbook-page">
      <header className="topbar">
        <h1>賞与表ワークスペース</h1>
        <span className="role-badge">{canManageAllFacilities ? "本部・管理者" : "施設長"}</span>
        {data?.period_name && <span className="period">{data.period_name}</span>}
      </header>

      {error && <p className="error">{error}</p>}
      {message && <p className="success save-notice">{message}</p>}

      <section className="bonus-toolbar">
        {canManageAllFacilities ? (
          <label className="bonus-facility-select">
            施設
            <select
              value={facilityKey}
              onChange={(e) => {
                if (isWorkbookDirty && !confirm("未保存の変更があります。施設を切り替えますか？")) return;
                if (isAmountsDirty) {
                  persistAmounts(true).finally(() => {
                    setFiscalYear(undefined);
                    setFacilityKey(e.target.value);
                  });
                  return;
                }
                setFiscalYear(undefined);
                setFacilityKey(e.target.value);
              }}
            >
              {facilities.map((option) => (
                <option key={option.key} value={option.key}>
                  {facilityOptionLabel(option)}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <span className="summary-chip">{userFacilityLabel ?? selectedFacility?.label ?? "所属施設"}</span>
        )}
        <label className="bonus-facility-select">
          年度
          <select
            value={data?.fiscal_year ?? ""}
            onChange={(e) => {
              const nextYear = Number(e.target.value);
              if (!Number.isFinite(nextYear)) return;
              if (isWorkbookDirty && !confirm("未保存の変更があります。年度を切り替えますか？")) return;
              if (isAmountsDirty && !isReadOnly) {
                persistAmounts(true).finally(() => setFiscalYear(nextYear));
                return;
              }
              setFiscalYear(nextYear);
            }}
            disabled={loading || availableFiscalYears.length === 0}
          >
            {availableFiscalYears.map((year) => (
              <option key={year} value={year}>
                {year}年度{year === currentFiscalYear ? "（現行）" : ""}
              </option>
            ))}
          </select>
        </label>
        {isReadOnly && (
          <span className="summary-chip bonus-readonly-badge">閲覧のみ（過去年度）</span>
        )}
        <div className="button-row">
          <button
            type="button"
            onClick={handleSyncRoster}
            disabled={saving || !bonusSheetAvailable || isReadOnly}
          >
            名簿を反映
          </button>
          <button type="button" onClick={handleSync} disabled={saving || !bonusSheetAvailable || isReadOnly}>
            考課から反映
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || !isWorkbookDirty || !bonusSheetAvailable || isReadOnly}
          >
            保存
          </button>
          {amountsSaving && <span className="bonus-autosave-status">金額を保存中...</span>}
          {!amountsSaving && isAmountsDirty && (
            <span className="bonus-autosave-status">金額は自動保存されます</span>
          )}
          <button
            type="button"
            className="primary"
            onClick={handleExport}
            disabled={saving || !bonusSheetAvailable || !data?.template_configured}
            title={data?.template_configured ? undefined : "デモ環境では Excel テンプレート未設定のため利用できません"}
          >
            Excelダウンロード
          </button>
        </div>
      </section>

      <div className="bonus-workbook-scroll">
      {!bonusSheetAvailable && (
        <p className="hint">
          「{facilityLabel}」の在籍職員が名簿にありません。管理画面から名簿を取込してください。
        </p>
      )}

      {bonusSheetAvailable && (
        <>
          <div className="bonus-rules-panel">
            <h2>自動反映ルール（令和7年度 評価基準.xlsx）</h2>
            <ul className="bonus-rules-list">
              <li>
                <strong>名簿を反映</strong>: 氏名（全角スペース）・役職を名簿／自己評価システムに合わせる
              </li>
              <li>
                <strong>考課から反映</strong>: 自己／評1／評2合計、特記事項、①〜⑤の低得点件数、昇給有、
                考課点順の<strong>順位</strong>と<strong>ランク</strong>を自動入力
              </li>
              <li>①〜⑤ 自己8点未満／他者6点以下 → <strong>カット対象</strong>列に項目番号と件数（金額は手入力）</li>
              <li>⑥〜⑩ 自己・他者8点未満 → <strong>昇格参考</strong>列（役職者の昇格可否の目安）</li>
              <li>①〜⑤ 他者評価合計40点以上 → 昇給欄に「○」</li>
              <li>ランク配分: A 10% / B 20% / C 40% / D 20% / E 10%（考課点順）</li>
              <li>
                <strong>賞与金額（案）</strong>は施設長、<strong>賞与金額</strong>・<strong>前年夏/冬</strong>は本部が入力（千円・自動保存）
              </li>
              <li>備考はセルをクリックすると全文表示・編集できます。カット対象・昇格参考は列表示を切替可能</li>
              <li>施設長（本部評価のみ）: 自己＋本部評2。評1・カット対象・昇格参考はなし</li>
              <li>評1なし（リーダー・相談員等）: 評2のみ。一般職: 評1と評2の平均</li>
            </ul>
          </div>

          <p className="hint">
            {isDirectorsView ? (
              <>
                <strong>施設長</strong>ビューでは、本部評価のみの施設長を一覧表示します。反映・保存は各施設の賞与シート上の行に書き込まれます。
              </>
            ) : canManageAllFacilities ? (
              <>本部・管理者は施設を切り替えできます。「施設長」で本部評価のみの施設長を確認できます。</>
            ) : (
              <>
                施設長は<strong>所属施設</strong>の賞与表のみ表示・編集できます。
              </>
            )}
          </p>

          <section className="bonus-summary-panel">
            <h2>賞与金額サマリー</h2>
            {!isDirectorsView && canEditProvision && (
              <div className="bonus-provision-controls">
                <label>
                  賞与引当金（月額・千円）
                  <input
                    type="number"
                    className="bonus-num-input"
                    min={0}
                    step={1}
                    value={provisionMonthly}
                    onChange={(e) =>
                      setProvisionMonthly(Math.max(0, Number(e.target.value) || 0))
                    }
                  />
                </label>
                <label>
                  月数
                  <select
                    className="bonus-provision-months-select"
                    value={normalizeProvisionMonths(provisionMonths)}
                    onChange={(e) =>
                      setProvisionMonths(normalizeProvisionMonths(Number(e.target.value)))
                    }
                  >
                    {PROVISION_MONTH_OPTIONS.map((months) => (
                      <option key={months} value={months}>
                        {months}ヶ月
                      </option>
                    ))}
                  </select>
                </label>
                <span className="bonus-provision-note">
                  年間引当: {formatSenYen(summary.provision_total)}
                </span>
              </div>
            )}
            {!isDirectorsView && !canEditProvision && (
              <p className="hint bonus-provision-hint">
                賞与引当金: 月額 {formatSenYen(provisionMonthly)} ×{" "}
                {normalizeProvisionMonths(provisionMonths)}ヶ月 = {formatSenYen(summary.provision_total)}
                {canManageAllFacilities && !isReadOnly && (
                  <span>（施設長が各施設で設定）</span>
                )}
              </p>
            )}
            {isDirectorsView && (
              <p className="hint bonus-provision-hint">
                引当金は各施設の設定を合算しています。月額の変更は各施設の賞与表で行ってください。
              </p>
            )}
            <dl className="bonus-summary-grid">
              <div>
                <dt>賞与金額（案）合計</dt>
                <dd>{formatSenYen(summary.total_proposed)}</dd>
              </div>
              <div>
                <dt>賞与金額合計</dt>
                <dd>{formatSenYen(summary.total_bonus)}</dd>
              </div>
              <div>
                <dt>社保込み合計</dt>
                <dd>
                  {formatSenYen(summary.total_with_social_insurance)}
                  <span className="bonus-summary-sub">
                    （社保 {Math.round(summary.social_insurance_rate * 100)}%）
                  </span>
                </dd>
              </div>
              <div>
                <dt>賞与引当金（合計）</dt>
                <dd>{formatSenYen(summary.provision_total)}</dd>
              </div>
              <div className={summary.difference >= 0 ? "bonus-diff-ok" : "bonus-diff-over"}>
                <dt>引当金との差額</dt>
                <dd>
                  {formatSenYen(summary.difference)}
                  <span className="bonus-summary-sub">
                    {summary.difference >= 0 ? "余剰" : "超過"}
                  </span>
                </dd>
              </div>
            </dl>
          </section>

          {!isDirectorsView && (
            <div className="bonus-column-toggles">
              <span className="bonus-column-toggles-label">列の表示:</span>
              <label className="bonus-column-toggle">
                <input
                  type="checkbox"
                  checked={showCutColumn}
                  onChange={(e) => updateColumnPref({ showCut: e.target.checked })}
                />
                カット対象
              </label>
              <label className="bonus-column-toggle">
                <input
                  type="checkbox"
                  checked={showPromotionColumn}
                  onChange={(e) => updateColumnPref({ showPromotion: e.target.checked })}
                />
                昇格参考
              </label>
            </div>
          )}

          <div className={tableWrapClassName}>
            <table className="bonus-table admin-table">
              <thead>
                <tr>
                  {isDirectorsView && <th className="bonus-col-facility">所属施設</th>}
                  <th className="bonus-col-name">氏名</th>
                  <th className="bonus-col-title">役職</th>
                  <th className="bonus-col-score">自己</th>
                  <th className="bonus-col-score">評1</th>
                  <th className="bonus-col-score">評2</th>
                  <th className="bonus-col-final">考課</th>
                  {!isDirectorsView && showCutColumn && (
                    <th className="bonus-col-cut">カット対象</th>
                  )}
                  {!isDirectorsView && showPromotionColumn && (
                    <th className="bonus-col-promo">昇格参考</th>
                  )}
                  <th className="bonus-col-rank">順位</th>
                  <th className="bonus-col-rank">ランク</th>
                  <th className="bonus-amount-col bonus-amount-col-prior">前年夏</th>
                  <th className="bonus-amount-col bonus-amount-col-prior">前年冬</th>
                  <th className="bonus-amount-col">賞与金額（案）</th>
                  <th className="bonus-amount-col">賞与金額</th>
                  <th className="bonus-note-col">備考</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={`${row.bonus_facility_key ?? "row"}-${row.row_number}`}>
                    {isDirectorsView && <td className="bonus-col-facility">{row.facility_label ?? "—"}</td>}
                    <td className="bonus-col-name">
                      <strong className="bonus-name-text">{row.name}</strong>
                      {row.employee_id && (
                        <span className="employee-id-tag">{row.employee_id}</span>
                      )}
                    </td>
                    <td className="bonus-col-title">{row.job_title}</td>
                    <td className="bonus-col-score">
                      <input
                        type="number"
                        className="bonus-num-input bonus-num-input-compact"
                        value={row.self_score ?? ""}
                        onChange={(e) =>
                          updateRow(row.row_number, {
                            self_score: e.target.value === "" ? null : Number(e.target.value),
                          })
                        }
                      />
                    </td>
                    <td className="bonus-col-score">
                      <input
                        type="number"
                        className="bonus-num-input bonus-num-input-compact"
                        value={row.eval1_score ?? ""}
                        onChange={(e) =>
                          updateRow(row.row_number, {
                            eval1_score: e.target.value === "" ? null : Number(e.target.value),
                          })
                        }
                      />
                    </td>
                    <td className="bonus-col-score">
                      <input
                        type="number"
                        className="bonus-num-input bonus-num-input-compact"
                        value={row.eval2_score ?? ""}
                        onChange={(e) =>
                          updateRow(row.row_number, {
                            eval2_score: e.target.value === "" ? null : Number(e.target.value),
                          })
                        }
                      />
                    </td>
                    <td className="bonus-col-final score-cell">{computeFinal(row) ?? "—"}</td>
                    {!isDirectorsView && showCutColumn && (
                      <td className="bonus-col-cut bonus-insight-cell">
                        <div className="bonus-cut-lines">
                          <span className={row.cut_self_items ? "bonus-cut-hit" : "bonus-cut-none"}>
                            自:{row.cut_self_items ?? "—"}
                          </span>
                          <span className={row.cut_other_items ? "bonus-cut-hit" : "bonus-cut-none"}>
                            他:{row.cut_other_items ?? "—"}
                          </span>
                        </div>
                      </td>
                    )}
                    {!isDirectorsView && showPromotionColumn && (
                      <td className="bonus-col-promo bonus-insight-cell">
                        {row.promotion_reference ? (
                          <span
                            className={
                              row.is_role_holder ? "bonus-promo-warn" : "bonus-promo-ref"
                            }
                            title={
                              row.is_role_holder
                                ? "役職者: ⑥〜⑩に8点未満があると昇格不可の参考"
                                : "⑥〜⑩の8点未満（参考）"
                            }
                          >
                            {row.promotion_reference}
                            {row.is_role_holder && (
                              <span className="bonus-promo-badge">役職</span>
                            )}
                          </span>
                        ) : (
                          <span className="bonus-cut-none">—</span>
                        )}
                      </td>
                    )}
                    <td className="bonus-col-rank">
                      <input
                        type="number"
                        className="bonus-num-input bonus-num-input-narrow"
                        value={row.rank_order ?? ""}
                        onChange={(e) =>
                          updateRow(row.row_number, {
                            rank_order: e.target.value === "" ? null : Number(e.target.value),
                          })
                        }
                      />
                    </td>
                    <td className="bonus-col-rank">
                      <input
                        type="text"
                        className="bonus-rank-input"
                        value={row.rank_grade ?? ""}
                        onChange={(e) =>
                          updateRow(row.row_number, {
                            rank_grade: e.target.value || null,
                          })
                        }
                      />
                    </td>
                    <td className="bonus-amount-col bonus-amount-col-prior">
                      {canEditBonus ? (
                        <input
                          type="number"
                          className="bonus-num-input bonus-amount-input"
                          min={0}
                          step={1}
                          placeholder="千円"
                          value={row.prior_summer_amount ?? ""}
                          onChange={(e) =>
                            updateRow(row.row_number, {
                              prior_summer_amount: parseBonusAmount(e.target.value),
                            })
                          }
                        />
                      ) : (
                        <span className="bonus-amount-readonly">
                          {formatSenYen(row.prior_summer_amount)}
                        </span>
                      )}
                    </td>
                    <td className="bonus-amount-col bonus-amount-col-prior">
                      {canEditBonus ? (
                        <input
                          type="number"
                          className="bonus-num-input bonus-amount-input"
                          min={0}
                          step={1}
                          placeholder="千円"
                          value={row.prior_winter_amount ?? ""}
                          onChange={(e) =>
                            updateRow(row.row_number, {
                              prior_winter_amount: parseBonusAmount(e.target.value),
                            })
                          }
                        />
                      ) : (
                        <span className="bonus-amount-readonly">
                          {formatSenYen(row.prior_winter_amount)}
                        </span>
                      )}
                    </td>
                    <td className="bonus-amount-col">
                      {canEditProposed ? (
                        <input
                          type="number"
                          className="bonus-num-input bonus-amount-input"
                          min={0}
                          step={1}
                          placeholder="千円"
                          value={row.proposed_bonus_amount ?? ""}
                          onChange={(e) =>
                            updateRow(row.row_number, {
                              proposed_bonus_amount: parseBonusAmount(e.target.value),
                            })
                          }
                        />
                      ) : (
                        <span className="bonus-amount-readonly">
                          {formatSenYen(row.proposed_bonus_amount)}
                        </span>
                      )}
                    </td>
                    <td className="bonus-amount-col">
                      {canEditBonus ? (
                        <input
                          type="number"
                          className="bonus-num-input bonus-amount-input"
                          min={0}
                          step={1}
                          placeholder="千円"
                          value={row.bonus_amount ?? ""}
                          onChange={(e) =>
                            updateRow(row.row_number, {
                              bonus_amount: parseBonusAmount(e.target.value),
                            })
                          }
                        />
                      ) : (
                        <span className="bonus-amount-readonly">
                          {formatSenYen(row.bonus_amount)}
                        </span>
                      )}
                    </td>
                    <td className="bonus-note-col">
                      <BonusNoteCell
                        value={row.note}
                        onChange={(note) => updateRow(row.row_number, { note })}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      </div>
    </div>
  );
}
