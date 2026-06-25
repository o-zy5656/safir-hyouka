import { useEffect, useState } from "react";
import { api, logout } from "./api/client";
import { AdminWorkspace } from "./components/AdminWorkspace";
import { ChangePasswordPage } from "./components/ChangePasswordPage";
import { DemoBanner } from "./components/DemoBanner";
import { EvaluateeWorkspace } from "./components/EvaluateeWorkspace";
import { EvaluatorWorkspace } from "./components/EvaluatorWorkspace";
import { LoginPage } from "./components/LoginPage";
import type { UserInfo } from "./types";
import "./App.css";

function App() {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = async () => {
    try {
      const me = await api.me();
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshUser();
  }, []);

  if (loading) {
    return (
      <>
        <DemoBanner />
        <p className="loading">読み込み中...</p>
      </>
    );
  }

  if (!user) {
    return (
      <>
        <DemoBanner />
        <LoginPage onSuccess={refreshUser} />
      </>
    );
  }

  if (user.must_change_password) {
    return (
      <>
        <DemoBanner />
        <ChangePasswordPage onSuccess={refreshUser} />
      </>
    );
  }

  return (
    <div className="app-shell">
      <DemoBanner />
      <div className="user-bar">
        <span>
          {user.name ?? user.employee_id}（{user.role}）
        </span>
        <button
          type="button"
          onClick={() => {
            logout();
            setUser(null);
          }}
        >
          ログアウト
        </button>
      </div>
      {user.role === "employee" && <EvaluateeWorkspace />}
      {(user.role === "evaluator1" || user.role === "evaluator2") && <EvaluatorWorkspace />}
      {user.role === "admin" && <AdminWorkspace />}
    </div>
  );
}

export default App;
