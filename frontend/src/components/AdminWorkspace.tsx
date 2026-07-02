import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type {
  AdminEvaluationItem,
  AdminPeriod,
  AdminUserItem,
  EmployeeListItem,
  EmployeeOptions,
  FacilityItem,
  ImportResult,
  RetiredArchiveItem,
} from "../types";
import { ConfirmDialog } from "./ConfirmDialog";

const statusLabel: Record<string, string> = {
  pending: "未着手",
  draft: "下書き",
  submitted: "提出済み",
  returned: "差し戻し",
};

const periodStatusLabel: Record<string, string> = {
  draft: "下書き",
  active: "実施中",
  closed: "終了",
};

const seasonLabel: Record<string, string> = {
  summer: "夏季",
  winter: "冬季",
};

const roleLabel: Record<string, string> = {
  employee: "本人",
  evaluator1: "評価者1",
  evaluator2: "評価者2",
  admin: "管理者",
};

type AdminTab = "progress" | "periods" | "import" | "staff" | "users";

type ProgressFilter = "all" | "incomplete" | "submitted" | "returned";

export function AdminWorkspace() {
  const [tab, setTab] = useState<AdminTab>("progress");
  const [items, setItems] = useState<AdminEvaluationItem[]>([]);
  const [periods, setPeriods] = useState<AdminPeriod[]>([]);
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [employees, setEmployees] = useState<EmployeeListItem[]>([]);
  const [archives, setArchives] = useState<RetiredArchiveItem[]>([]);
  const [facilities, setFacilities] = useState<FacilityItem[]>([]);
  const [employeeOptions, setEmployeeOptions] = useState<EmployeeOptions>({
    job_types: [],
    job_titles: [],
  });
  const [rosterFacilityKey, setRosterFacilityKey] = useState("all");
  const [bonusFacilityKey, setBonusFacilityKey] = useState("inaha");
  const [employeeForm, setEmployeeForm] = useState({
    employee_id: "",
    name: "",
    assignment: "サフィールいなは",
    job_type: "介護",
    job_title: "一般",
    years_of_service: 0,
    evaluator1_employee_id: "",
    evaluator2_employee_id: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [rosterFile, setRosterFile] = useState<File | null>(null);
  const [genericFile, setGenericFile] = useState<File | null>(null);
  const [retireTarget, setRetireTarget] = useState<EmployeeListItem | null>(null);
  const [retireReason, setRetireReason] = useState("");
  const [roleChangeTarget, setRoleChangeTarget] = useState<{
    userId: string;
    employeeId: string;
    name: string;
    role: AdminUserItem["role"];
  } | null>(null);
  const [periodForm, setPeriodForm] = useState({
    name: "令和8年度 冬季考課",
    season: "winter" as "summer" | "winter",
    fiscal_year: 8,
  });
  const [progressQuery, setProgressQuery] = useState("");
  const [progressFilter, setProgressFilter] = useState<ProgressFilter>("all");

  const jobTypeOptions = useMemo(() => {
    const values = new Set(employeeOptions.job_types);
    if (employeeForm.job_type) values.add(employeeForm.job_type);
    for (const employee of employees) {
      if (employee.job_type) values.add(employee.job_type);
    }
    return [...values];
  }, [employeeOptions.job_types, employeeForm.job_type, employees]);

  const jobTitleOptions = useMemo(() => {
    const values = new Set(employeeOptions.job_titles);
    if (employeeForm.job_title) values.add(employeeForm.job_title);
    for (const employee of employees) {
      if (employee.job_title) values.add(employee.job_title);
    }
    return [...values];
  }, [employeeOptions.job_titles, employeeForm.job_title, employees]);

  const filteredProgressItems = useMemo(() => {
    const query = progressQuery.trim().toLowerCase();
    return items.filter((item) => {
      if (query) {
        const haystack = [
          item.employee.employee_id,
          item.employee.name,
          item.employee.assignment,
        ]
          .join(" ")
          .toLowerCase();
        if (!haystack.includes(query)) return false;
      }

      if (progressFilter === "incomplete") {
        return (
          item.self_eval_status !== "submitted" ||
          item.eval1_status !== "submitted" ||
          item.eval2_status !== "submitted"
        );
      }
      if (progressFilter === "submitted") {
        return (
          item.self_eval_status === "submitted" &&
          item.eval1_status === "submitted" &&
          item.eval2_status === "submitted"
        );
      }
      if (progressFilter === "returned") {
        return (
          item.self_eval_status === "returned" ||
          item.eval1_status === "returned" ||
          item.eval2_status === "returned"
        );
      }
      return true;
    });
  }, [items, progressQuery, progressFilter]);

  const loadProgress = async () => {
    const data = await api.adminEvaluations();
    setItems(data);
  };

  const loadPeriods = async () => {
    const data = await api.adminPeriods();
    setPeriods(data);
  };

  const loadUsers = async () => {
    const data = await api.adminUsers();
    setUsers(data);
  };

  const loadEmployees = async () => {
    const data = await api.adminEmployees("active");
    setEmployees(data);
  };

  const loadArchives = async () => {
    const data = await api.adminRetiredArchives();
    setArchives(data);
  };

  useEffect(() => {
    loadProgress().catch((e: Error) => setError(e.message));
    loadPeriods().catch(() => undefined);
    api
      .facilities()
      .then((response) => {
        setFacilities(response.facilities);
        const bonusReady = response.facilities.filter((facility) => facility.bonus_enabled);
        if (bonusReady.some((facility) => facility.key === "inaha")) {
          setBonusFacilityKey("inaha");
        } else if (bonusReady.length > 0) {
          setBonusFacilityKey(bonusReady[0].key);
        }
        if (response.facilities.length > 0) {
          setEmployeeForm((prev) => ({
            ...prev,
            assignment: response.facilities[0].assignment_match,
          }));
        }
      })
      .catch(() => undefined);
    api.adminEmployeeOptions().then(setEmployeeOptions).catch(() => undefined);
  }, []);

  const handleReturn = async (evaluationId: string, target: string, label: string) => {
    if (!confirm(`${label}を差し戻しますか？\n本人・評価者が再度編集できるようになります。`)) return;
    setError(null);
    setMessage(null);
    try {
      const res = await api.adminReturn(evaluationId, target);
      setMessage(res.message ?? "差し戻ししました");
      await loadProgress();
    } catch (e) {
      setError(e instanceof Error ? e.message : "差し戻しに失敗しました");
    }
  };

  const handleCreatePeriod = async () => {
    setError(null);
    setMessage(null);
    try {
      await api.adminCreatePeriod(periodForm);
      setMessage("考課期間を作成しました");
      await loadPeriods();
    } catch (e) {
      setError(e instanceof Error ? e.message : "期間作成に失敗しました");
    }
  };

  const handleActivatePeriod = async (periodId: string, name: string) => {
    if (!confirm(`「${name}」を開始しますか？\n現在の実施中期間は終了し、全社員の考課データが作成されます。`)) return;
    setError(null);
    setMessage(null);
    try {
      await api.adminActivatePeriod(periodId);
      setMessage("考課期間を開始しました");
      await loadPeriods();
      await loadProgress();
    } catch (e) {
      setError(e instanceof Error ? e.message : "期間開始に失敗しました");
    }
  };

  const handleExport = async (period: AdminPeriod) => {
    setError(null);
    try {
      const filename = `hyouka_${period.name.replace(/\s+/g, "_")}.xlsx`;
      await api.adminExportPeriod(period.id, filename);
      setMessage(`${period.name} の Excel をダウンロードしました`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Excel出力に失敗しました");
    }
  };

  const handleExportBonus = async (period: AdminPeriod) => {
    setError(null);
    setMessage(null);
    try {
      const preview = await api.adminPreviewBonusReflect(period.id, bonusFacilityKey);
      const unmatchedNote =
        preview.unmatched_employees.length > 0
          ? `\n未照合 ${preview.unmatched_employees.length}名（名簿・Excel の氏名差異など）`
          : "";
      if (
        !confirm(
          `「${preview.facility}」の賞与資料シートへ考課結果を反映します。\n` +
            `反映対象: ${preview.updated_rows}名${unmatchedNote}\n\n` +
            "ダウンロードした Excel を確認してください。",
        )
      ) {
        return;
      }
      const filename = `R7夏季賞与_考課反映_${period.name.replace(/\s+/g, "_")}.xlsx`;
      await api.adminExportBonusReflect(period.id, filename, bonusFacilityKey);
      setMessage(
        `${preview.facility} の賞与 Excel を出力しました（${preview.updated_rows}名反映）`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "賞与表への反映に失敗しました");
    }
  };

  const handleImportRoster = async () => {
    if (!rosterFile) {
      setError("Excelファイルを選択してください");
      return;
    }
    setError(null);
    setMessage(null);
    setImportResult(null);
    try {
      const importOptions =
        rosterFacilityKey === "all"
          ? { facilityKey: "all" }
          : { facilityKey: rosterFacilityKey };
      const result = await api.adminImportRoster(rosterFile, importOptions);
      setImportResult(result);
      setMessage(
        `名簿取込完了: 新規 ${result.created}件 / 更新 ${result.updated}件 / ロール ${result.roles_updated}件`,
      );
      await loadProgress();
      await loadUsers();
      setRosterFile(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "名簿取込に失敗しました");
    }
  };

  const handleImport = async () => {
    if (!genericFile) {
      setError("Excelファイルを選択してください");
      return;
    }
    setError(null);
    setMessage(null);
    setImportResult(null);
    try {
      const result = await api.adminImportEmployees(genericFile);
      setImportResult(result);
      setMessage(
        `取込完了: 新規 ${result.created}件 / 更新 ${result.updated}件 / ユーザー作成 ${result.users_created}件 / ロール更新 ${result.roles_updated}件 / 考課データ ${result.evaluations_created}件`,
      );
      await loadProgress();
      await loadUsers();
      setGenericFile(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "取込に失敗しました");
    }
  };

  const handleRoleChange = async (userId: string, role: AdminUserItem["role"]) => {
    setError(null);
    setMessage(null);
    try {
      await api.adminUpdateUserRole(userId, role);
      setMessage("ロールを更新しました");
      await loadUsers();
    } catch (e) {
      setError(e instanceof Error ? e.message : "ロール更新に失敗しました");
    }
  };

  const confirmRoleChange = async () => {
    if (!roleChangeTarget) return;
    const { userId, role } = roleChangeTarget;
    setRoleChangeTarget(null);
    await handleRoleChange(userId, role);
  };

  useEffect(() => {
    if (tab === "users") {
      loadUsers().catch((e: Error) => setError(e.message));
    }
    if (tab === "staff") {
      loadEmployees().catch((e: Error) => setError(e.message));
      loadArchives().catch((e: Error) => setError(e.message));
    }
  }, [tab]);

  const handleCreateEmployee = async () => {
    if (!employeeForm.employee_id.trim() || !employeeForm.name.trim()) {
      setError("社員IDと氏名は必須です");
      return;
    }
    if (!employeeForm.job_type.trim()) {
      setError("職種を選択してください");
      return;
    }
    setError(null);
    setMessage(null);
    try {
      const res = await api.adminCreateEmployee({
        ...employeeForm,
        years_of_service: Number(employeeForm.years_of_service) || 0,
        evaluator1_employee_id: employeeForm.evaluator1_employee_id || undefined,
        evaluator2_employee_id: employeeForm.evaluator2_employee_id || undefined,
      });
      setMessage(
        [res.message, ...(res.warnings ?? []).map((w) => `※ ${w}`)].join("\n"),
      );
      setEmployeeForm({
        employee_id: "",
        name: "",
        assignment: "サフィールいなは",
        job_type: "介護",
        job_title: "一般",
        years_of_service: 0,
        evaluator1_employee_id: "",
        evaluator2_employee_id: "",
      });
      await loadEmployees();
      await loadProgress();
    } catch (e) {
      setError(e instanceof Error ? e.message : "入職登録に失敗しました");
    }
  };

  const handleRetireEmployee = async () => {
    if (!retireTarget) return;
    setError(null);
    setMessage(null);
    try {
      const res = await api.adminRetireEmployee(retireTarget.id, retireReason.trim() || undefined);
      setMessage(
        [res.message, ...(res.warnings ?? []).map((w) => `※ ${w}`)].join("\n"),
      );
      setRetireTarget(null);
      setRetireReason("");
      await loadEmployees();
      await loadArchives();
      await loadProgress();
    } catch (e) {
      setError(e instanceof Error ? e.message : "退職処理に失敗しました");
    }
  };

  return (
    <div className="admin-page">
      <header className="topbar">
        <h1>管理画面</h1>
        <span className="period">人事・経営層向け</span>
      </header>

      <nav className="admin-tabs">
        <button type="button" className={tab === "progress" ? "active" : ""} onClick={() => setTab("progress")}>
          進捗・差し戻し
        </button>
        <button type="button" className={tab === "periods" ? "active" : ""} onClick={() => setTab("periods")}>
          考課期間
        </button>
        <button type="button" className={tab === "import" ? "active" : ""} onClick={() => setTab("import")}>
          社員取込
        </button>
        <button type="button" className={tab === "staff" ? "active" : ""} onClick={() => setTab("staff")}>
          職員管理
        </button>
        <button type="button" className={tab === "users" ? "active" : ""} onClick={() => setTab("users")}>
          ユーザー
        </button>
      </nav>

      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}

      {tab === "progress" && (
        <div className="admin-table-wrap">
          <div className="admin-filter-bar">
            <label className="admin-filter-search">
              検索
              <input
                type="search"
                placeholder="社員ID・氏名・配属"
                value={progressQuery}
                onChange={(e) => setProgressQuery(e.target.value)}
              />
            </label>
            <label>
              状態
              <select
                value={progressFilter}
                onChange={(e) => setProgressFilter(e.target.value as ProgressFilter)}
              >
                <option value="all">すべて</option>
                <option value="incomplete">未完了あり</option>
                <option value="submitted">全工程提出済み</option>
                <option value="returned">差し戻しあり</option>
              </select>
            </label>
            <span className="admin-filter-count">
              {filteredProgressItems.length} / {items.length} 件
            </span>
          </div>
          <table className="admin-table">
            <thead>
              <tr>
                <th>社員ID</th>
                <th>氏名</th>
                <th>配属</th>
                <th>自己評価</th>
                <th>評価者1</th>
                <th>評価者2</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredProgressItems.map((item) => (
                <tr key={item.evaluation_id}>
                  <td>{item.employee.employee_id}</td>
                  <td>{item.employee.name}</td>
                  <td>{item.employee.assignment}</td>
                  <td>{statusLabel[item.self_eval_status] ?? item.self_eval_status}</td>
                  <td>{statusLabel[item.eval1_status] ?? item.eval1_status}</td>
                  <td>{statusLabel[item.eval2_status] ?? item.eval2_status}</td>
                  <td className="admin-actions">
                    {item.self_eval_status === "submitted" && (
                      <button
                        type="button"
                        onClick={() => handleReturn(item.evaluation_id, "self_eval", "自己評価")}
                      >
                        自己評価を差戻
                      </button>
                    )}
                    {item.eval1_status === "submitted" && (
                      <button
                        type="button"
                        onClick={() => handleReturn(item.evaluation_id, "eval1", "評価者1の考課")}
                      >
                        評1を差戻
                      </button>
                    )}
                    {item.eval2_status === "submitted" && (
                      <button
                        type="button"
                        onClick={() => handleReturn(item.evaluation_id, "eval2", "評価者2の考課")}
                      >
                        評2を差戻
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {items.length === 0 && <p className="hint">考課データがありません。</p>}
          {items.length > 0 && filteredProgressItems.length === 0 && (
            <p className="hint">条件に一致する考課データがありません。</p>
          )}
        </div>
      )}

      {tab === "periods" && (
        <div className="admin-section">
          <section className="admin-card">
            <h2>考課期間を作成</h2>
            <div className="admin-form-grid">
              <label>
                名称
                <input
                  value={periodForm.name}
                  onChange={(e) => setPeriodForm({ ...periodForm, name: e.target.value })}
                />
              </label>
              <label>
                季節
                <select
                  value={periodForm.season}
                  onChange={(e) =>
                    setPeriodForm({ ...periodForm, season: e.target.value as "summer" | "winter" })
                  }
                >
                  <option value="summer">夏季</option>
                  <option value="winter">冬季</option>
                </select>
              </label>
              <label>
                年度（令和）
                <input
                  type="number"
                  min={1}
                  value={periodForm.fiscal_year}
                  onChange={(e) =>
                    setPeriodForm({ ...periodForm, fiscal_year: Number(e.target.value) || 1 })
                  }
                />
              </label>
            </div>
            <button type="button" onClick={handleCreatePeriod}>
              期間を作成
            </button>
          </section>

          <section className="admin-card">
            <h2>考課期間一覧</h2>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>名称</th>
                  <th>季節</th>
                  <th>状態</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {periods.map((period) => (
                  <tr key={period.id}>
                    <td>{period.name}</td>
                    <td>{seasonLabel[period.season] ?? period.season}</td>
                    <td>{periodStatusLabel[period.status] ?? period.status}</td>
                    <td className="admin-actions admin-actions-row">
                      {period.status !== "active" && (
                        <button type="button" onClick={() => handleActivatePeriod(period.id, period.name)}>
                          開始
                        </button>
                      )}
                      <button type="button" onClick={() => handleExport(period)}>
                        Excel出力
                      </button>
                      <label className="bonus-facility-select admin-inline-select">
                        賞与施設
                        <select
                          value={bonusFacilityKey}
                          onChange={(e) => setBonusFacilityKey(e.target.value)}
                        >
                          {facilities.map((facility) => (
                            <option key={facility.key} value={facility.key}>
                              {facility.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <button type="button" onClick={() => handleExportBonus(period)}>
                        賞与表へ反映
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {periods.length === 0 && <p className="hint">考課期間がありません。</p>}
            <p className="hint">
              「賞与表へ反映」は .env の BONUS_WORKBOOK_TEMPLATE_PATH
              に指定した秀成会賞与 Excel へ、施設ごとの資料シートに考課結果を書き込みます。
              施設の追加・シート名は backend/data/facilities.json で設定します。
            </p>
          </section>
        </div>
      )}

      {tab === "import" && (
        <div className="admin-section">
          <section className="admin-card">
            <h2>名簿 Excel 取込</h2>
            <p className="hint">
              Dropbox の「名簿.xlsx」形式。在職者のみ。施設を選ぶか「全施設」で一括取込できます。
              取込後は考課・賞与表の対象施設が利用可能になります（Excel 資料シートがなくても名簿から賞与表を表示）。
              第1・第2評価者は名簿の社員IDから紐づけ、別施設の評価者は警告します。
            </p>
            <p className="hint">
              <strong>管理者</strong>: 施設長（例: i9213）は評価者2としてログインし、画面上部の「管理画面へ」から管理者機能に切り替えられます。
              <br />
              <strong>評価者1</strong>: リーダー・サブリーダー等のリーダークラス（名簿の一次評価者からも自動設定）。
              <br />
              <strong>評価者2</strong>: 施設長（名簿の二次評価者）。施設長本人は1次評価者がおらず、自己評価提出後に本部（例: hq001）が考課します。
              <br />
              <strong>本部確認</strong>: 施設長が一般職・リーダーの二次評価を提出すると、本部アカウントで結果を確認できます。
              <br />
              <strong>施設長の自己評価</strong>: 施設長用の別シート。ログイン後「自分の自己評価（施設長用）」から入力します。
            </p>
            <p className="hint">初期パスワード: changeme123（全員共通・初回変更推奨）</p>
            <label className="bonus-facility-select admin-inline-select">
              取込施設
              <select
                value={rosterFacilityKey}
                onChange={(e) => setRosterFacilityKey(e.target.value)}
              >
                <option value="all">全施設（名簿の全行）</option>
                {facilities.map((facility) => (
                  <option key={facility.key} value={facility.key}>
                    {facility.label}
                  </option>
                ))}
              </select>
            </label>
            <div className="admin-import-row">
              <input
                type="file"
                accept=".xlsx,.xlsm"
                onChange={(e) => setRosterFile(e.target.files?.[0] ?? null)}
              />
              <button type="button" onClick={handleImportRoster} disabled={!rosterFile}>
                名簿を取込
              </button>
            </div>
          </section>

          <section className="admin-card">
            <h2>汎用 Excel 取込</h2>
            <p className="hint">
              列: 社員ID / 氏名 / 配属 / 職種 / 勤続年数 / 評価者1社員ID / 評価者2社員ID / ロール（任意）
            </p>
            <div className="admin-import-row">
              <input
                type="file"
                accept=".xlsx,.xlsm"
                onChange={(e) => setGenericFile(e.target.files?.[0] ?? null)}
              />
              <button type="button" onClick={handleImport} disabled={!genericFile}>
                汎用フォーマットで取込
              </button>
            </div>
            {importResult && importResult.errors.length > 0 && (
              <div className="validation-errors">
                <strong>取込時の警告 ({importResult.errors.length}件)</strong>
                <ul>
                  {importResult.errors.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        </div>
      )}

      {tab === "staff" && (
        <div className="admin-section">
          <section className="admin-card">
            <h2>入職登録</h2>
            <p className="hint">
              新規入職者を個別に登録します。初期パスワードは changeme123 です。施設長の二次評価者は自動で本部になります。
            </p>
            <div className="admin-form-grid">
              <label>
                社員ID
                <input
                  value={employeeForm.employee_id}
                  onChange={(e) => setEmployeeForm({ ...employeeForm, employee_id: e.target.value })}
                />
              </label>
              <label>
                氏名
                <input
                  value={employeeForm.name}
                  onChange={(e) => setEmployeeForm({ ...employeeForm, name: e.target.value })}
                />
              </label>
                <label>
                  配属（施設）
                  <select
                    value={employeeForm.assignment}
                    onChange={(e) => setEmployeeForm({ ...employeeForm, assignment: e.target.value })}
                  >
                    {facilities.map((facility) => (
                      <option key={facility.key} value={facility.assignment_match}>
                        {facility.label}
                      </option>
                    ))}
                  </select>
                </label>
              <label>
                職種
                <select
                  value={employeeForm.job_type}
                  onChange={(e) => setEmployeeForm({ ...employeeForm, job_type: e.target.value })}
                >
                  {jobTypeOptions.map((jobType) => (
                    <option key={jobType} value={jobType}>
                      {jobType}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                役職
                <select
                  value={employeeForm.job_title}
                  onChange={(e) => setEmployeeForm({ ...employeeForm, job_title: e.target.value })}
                >
                  {jobTitleOptions.map((jobTitle) => (
                    <option key={jobTitle} value={jobTitle}>
                      {jobTitle}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                勤続年数
                <input
                  type="number"
                  min={0}
                  value={employeeForm.years_of_service}
                  onChange={(e) =>
                    setEmployeeForm({ ...employeeForm, years_of_service: Number(e.target.value) })
                  }
                />
              </label>
              <label>
                評価者1 社員ID
                <input
                  value={employeeForm.evaluator1_employee_id}
                  onChange={(e) =>
                    setEmployeeForm({ ...employeeForm, evaluator1_employee_id: e.target.value })
                  }
                />
              </label>
              <label>
                評価者2 社員ID
                <input
                  value={employeeForm.evaluator2_employee_id}
                  onChange={(e) =>
                    setEmployeeForm({ ...employeeForm, evaluator2_employee_id: e.target.value })
                  }
                />
              </label>
            </div>
            <button type="button" onClick={handleCreateEmployee}>
              入職登録
            </button>
          </section>

          <section className="admin-card">
            <h2>在籍職員</h2>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>社員ID</th>
                  <th>氏名</th>
                  <th>役職</th>
                  <th>評価者1</th>
                  <th>評価者2</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {employees.map((emp) => (
                  <tr key={emp.id}>
                    <td>{emp.employee_id}</td>
                    <td>{emp.name}</td>
                    <td>{emp.job_title ?? "—"}</td>
                    <td>
                      {emp.evaluator1_name ?? "—"}
                      {emp.evaluator1_employee_id ? ` (${emp.evaluator1_employee_id})` : ""}
                    </td>
                    <td>
                      {emp.evaluator2_name ?? "—"}
                      {emp.evaluator2_employee_id ? ` (${emp.evaluator2_employee_id})` : ""}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="danger-btn"
                        onClick={() => {
                          setRetireReason("");
                          setRetireTarget(emp);
                        }}
                      >
                        退職処理
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {employees.length === 0 && <p className="hint">在籍職員がいません。</p>}
          </section>

          <section className="admin-card">
            <h2>退職者アーカイブ</h2>
            <p className="hint">
              退職処理時に考課データを JSON（完全データ）と Excel（一覧）で保存します。
            </p>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>社員ID</th>
                  <th>氏名</th>
                  <th>退職日時</th>
                  <th>ダウンロード</th>
                </tr>
              </thead>
              <tbody>
                {archives.map((arc) => (
                  <tr key={arc.archive_id}>
                    <td>{arc.employee_id ?? "—"}</td>
                    <td>{arc.employee_name ?? "—"}</td>
                    <td>{arc.retired_at ? new Date(arc.retired_at).toLocaleString("ja-JP") : "—"}</td>
                    <td className="admin-actions-row">
                      <button
                        type="button"
                        onClick={async () => {
                          try {
                            await api.adminDownloadRetiredArchive(
                              arc.archive_id,
                              "json",
                              arc.json_filename,
                            );
                          } catch (e) {
                            setError(e instanceof Error ? e.message : "ダウンロードに失敗しました");
                          }
                        }}
                      >
                        JSON
                      </button>
                      {arc.xlsx_filename && (
                        <button
                          type="button"
                          onClick={async () => {
                            try {
                              await api.adminDownloadRetiredArchive(
                                arc.archive_id,
                                "xlsx",
                                arc.xlsx_filename!,
                              );
                            } catch (e) {
                              setError(e instanceof Error ? e.message : "ダウンロードに失敗しました");
                            }
                          }}
                        >
                          Excel
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {archives.length === 0 && <p className="hint">退職者アーカイブはまだありません。</p>}
          </section>
        </div>
      )}

      {tab === "users" && (
        <div className="admin-staff-stack">
          <div className="admin-card">
            <h2>ロール変更</h2>
            <p className="hint">
              評価者ロール（本人 / 評価者1 / 評価者2）を変更します。職員パスワードのリセットは画面上部の「パスワード管理」から行えます。
            </p>
            <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>社員ID</th>
                <th>氏名</th>
                <th>ロール</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.user_id}>
                  <td>{user.employee_id}</td>
                  <td>{user.name ?? "—"}</td>
                  <td>{roleLabel[user.role] ?? user.role}</td>
                  <td>
                    {user.role !== "admin" ? (
                      <select
                        value={user.role}
                        onChange={(e) => {
                          const nextRole = e.target.value as AdminUserItem["role"];
                          if (nextRole === user.role) return;
                          setRoleChangeTarget({
                            userId: user.user_id,
                            employeeId: user.employee_id,
                            name: user.name ?? user.employee_id,
                            role: nextRole,
                          });
                        }}
                      >
                        <option value="employee">本人</option>
                        <option value="evaluator1">評価者1</option>
                        <option value="evaluator2">評価者2</option>
                      </select>
                    ) : (
                      <span className="hint">管理者</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {users.length === 0 && <p className="hint">ユーザーがありません。</p>}
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={roleChangeTarget !== null}
        title="ロール変更の確認"
        message={
          roleChangeTarget
            ? `${roleChangeTarget.name}（${roleChangeTarget.employeeId}）のロールを「${roleLabel[roleChangeTarget.role] ?? roleChangeTarget.role}」に変更します。`
            : ""
        }
        confirmLabel="変更する"
        cancelLabel="キャンセル"
        onConfirm={confirmRoleChange}
        onCancel={() => setRoleChangeTarget(null)}
      />

      <ConfirmDialog
        open={retireTarget !== null}
        title="退職処理の確認"
        message={
          retireTarget
            ? `${retireTarget.name}（${retireTarget.employee_id}）を退職処理します。考課データはアーカイブに保存され、ログインできなくなります。`
            : ""
        }
        confirmLabel="退職処理する"
        cancelLabel="キャンセル"
        reason={retireReason}
        onReasonChange={setRetireReason}
        reasonLabel="退職理由（任意）"
        reasonPlaceholder="例: 2026年3月31日付退職"
        onConfirm={handleRetireEmployee}
        onCancel={() => {
          setRetireTarget(null);
          setRetireReason("");
        }}
      />
    </div>
  );
}
