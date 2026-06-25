import { useState } from "react";
import type { FormEvent } from "react";
import { api } from "../api/client";

interface Props {
  onSuccess: () => void;
}

export function ChangePasswordPage({ onSuccess }: Props) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (newPassword.length < 8) {
      setError("新しいパスワードは8文字以上にしてください");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("新しいパスワード（確認）が一致しません");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await api.changePassword(currentPassword, newPassword);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "パスワード変更に失敗しました");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <h1>パスワード変更</h1>
        <p>初回ログインのため、パスワードを変更してください。</p>
        <label>
          現在のパスワード
          <input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
          />
        </label>
        <label>
          新しいパスワード（8文字以上）
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            minLength={8}
          />
        </label>
        <label>
          新しいパスワード（確認）
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            minLength={8}
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" className="primary" disabled={loading}>
          {loading ? "変更中..." : "パスワードを変更"}
        </button>
      </form>
    </div>
  );
}
