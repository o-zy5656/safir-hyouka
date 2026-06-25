import { useState } from "react";
import type { FormEvent } from "react";
import { login } from "../api/client";

interface Props {
  onSuccess: () => void;
}

export function LoginPage({ onSuccess }: Props) {
  const [employeeId, setEmployeeId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(employeeId, password);
      onSuccess();
    } catch {
      setError("社員IDまたはパスワードが正しくありません");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <h1>サフィール人事考課</h1>
        <p>社員IDとパスワードでログインしてください。</p>
        <label>
          社員ID
          <input value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} required />
        </label>
        <label>
          パスワード
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" className="primary" disabled={loading}>
          {loading ? "ログイン中..." : "ログイン"}
        </button>
      </form>
    </div>
  );
}
