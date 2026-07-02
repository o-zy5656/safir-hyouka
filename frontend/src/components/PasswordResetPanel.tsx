import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { AdminUserItem } from "../types";
import { ConfirmDialog } from "./ConfirmDialog";

const roleLabel: Record<string, string> = {
  employee: "本人",
  evaluator1: "評価者1",
  evaluator2: "評価者2",
  admin: "管理者",
};

export function PasswordResetPanel() {
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [resetTarget, setResetTarget] = useState<AdminUserItem | null>(null);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const data = await api.adminUsers();
      setUsers(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "ユーザー一覧の取得に失敗しました");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers().catch(() => undefined);
  }, []);

  const filteredUsers = useMemo(() => {
    const text = query.trim().toLowerCase();
    if (!text) return users;
    return users.filter((user) => {
      const haystack = [user.employee_id, user.name ?? ""].join(" ").toLowerCase();
      return haystack.includes(text);
    });
  }, [users, query]);

  const handleReset = async () => {
    if (!resetTarget) return;
    setError(null);
    setMessage(null);
    try {
      const result = await api.adminResetUserPassword(resetTarget.user_id);
      setMessage(`${result.message}\n仮パスワード: ${result.temporary_password}`);
      setResetTarget(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "パスワードリセットに失敗しました");
      setResetTarget(null);
    }
  };

  return (
    <section className="admin-card password-reset-panel">
      <p className="hint">
        パスワードを忘れた職員のパスワードを初期値に戻します。リセット後、本人は次回ログイン時に新しいパスワードを設定します。
      </p>
      {error && <p className="error">{error}</p>}
      {message && <p className="success save-notice">{message}</p>}
      <label className="password-reset-search">
        社員ID・氏名で検索
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="例: i1005"
        />
      </label>
      {loading ? (
        <p className="hint">読み込み中...</p>
      ) : (
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
              {filteredUsers.map((user) => (
                <tr key={user.user_id}>
                  <td>{user.employee_id}</td>
                  <td>{user.name ?? "—"}</td>
                  <td>{roleLabel[user.role] ?? user.role}</td>
                  <td>
                    {user.role === "admin" ? (
                      <span className="hint">—</span>
                    ) : (
                      <button type="button" onClick={() => setResetTarget(user)}>
                        リセット
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filteredUsers.length === 0 && <p className="hint">該当するユーザーがありません。</p>}
        </div>
      )}

      <ConfirmDialog
        open={resetTarget !== null}
        title="パスワードリセットの確認"
        message={
          resetTarget
            ? `${resetTarget.name ?? resetTarget.employee_id}（${resetTarget.employee_id}）のパスワードを初期値にリセットします。`
            : ""
        }
        confirmLabel="リセットする"
        cancelLabel="キャンセル"
        onConfirm={handleReset}
        onCancel={() => setResetTarget(null)}
      />
    </section>
  );
}
