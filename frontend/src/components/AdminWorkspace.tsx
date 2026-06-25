import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { AdminEvaluationItem, AdminPeriod, AdminUserItem, ImportResult } from "../types";

const statusLabel: Record<string, string> = {
  pending: "未着手",
  draft: "下書き",
  submitted: "提出済",
  returned: "差戻",
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

type AdminTab = "progress" | "periods" | "import" | "users";

export function AdminWorkspace() {
  const [tab, setTab] = useState<AdminTab>("progress");
  const [items, setItems] = useState<AdminEvaluationItem[]>([]);
  const [periods, setPeriods] = useState<AdminPeriod[]>([]);
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [periodForm, setPeriodForm] = useState({
    name: "令和8年度 冬季考課",
    season: "winter" as "summer" | "winter",
    fiscal_year: 8,
  });

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

  useEffect(() => {
    loadProgress().catch((e: Error) => setError(e.message));
    loadPeriods().catch(() => undefined);
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

  const handleImport = async () => {
    if (!importFile) {
      setError("Excelファイルを選択してください");
      return;
    }
    setError(null);
    setMessage(null);
    setImportResult(null);
    try {
      const result = await api.adminImportEmployees(importFile);
      setImportResult(result);
      setMessage(
        `取込完了: 新規 ${result.created}件 / 更新 ${result.updated}件 / ユーザー作成 ${result.users_created}件 / ロール更新 ${result.roles_updated}件 / 考課データ ${result.evaluations_created}件`,
      );
      await loadProgress();
      await loadUsers();
      setImportFile(null);
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

  useEffect(() => {
    if (tab === "users") {
      loadUsers().catch((e: Error) => setError(e.message));
    }
  }, [tab]);

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
        <button type="button" className={tab === "users" ? "active" : ""} onClick={() => setTab("users")}>
          ユーザー
        </button>
      </nav>

      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}

      {tab === "progress" && (
        <div className="admin-table-wrap">
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
              {items.map((item) => (
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
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {periods.length === 0 && <p className="hint">考課期間がありません。</p>}
          </section>
        </div>
      )}

      {tab === "import" && (
        <div className="admin-section">
          <section className="admin-card">
            <h2>社員Excel一括取込</h2>
            <p className="hint">
              列: 社員ID / 氏名 / 配属 / 職種 / 勤続年数 / 評価者1社員ID / 評価者2社員ID / ロール（任意）
            </p>
            <p className="hint">
              ロール列がない場合、他行の「評価者1/2社員ID」から自動判定します。値の例: 本人 / 評価者1 / 評価者2
            </p>
            <p className="hint">新規社員の初期パスワードは changeme123 です（初回変更を推奨）。</p>
            <div className="admin-import-row">
              <input
                type="file"
                accept=".xlsx,.xlsm"
                onChange={(e) => setImportFile(e.target.files?.[0] ?? null)}
              />
              <button type="button" onClick={handleImport} disabled={!importFile}>
                取込実行
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

      {tab === "users" && (
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
                        onChange={(e) =>
                          handleRoleChange(user.user_id, e.target.value as AdminUserItem["role"])
                        }
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
      )}
    </div>
  );
}
