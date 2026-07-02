import { useEffect, useState } from "react";
import { api, demoLogin, IS_DEMO_MODE, logout } from "./api/client";
import { AdminWorkspace } from "./components/AdminWorkspace";
import { BonusWorkbookWorkspace } from "./components/BonusWorkbookWorkspace";
import { ChangePasswordPage } from "./components/ChangePasswordPage";
import { DemoBanner } from "./components/DemoBanner";
import { EvaluateeWorkspace } from "./components/EvaluateeWorkspace";
import { EvaluatorWorkspace } from "./components/EvaluatorWorkspace";
import { LoginPage } from "./components/LoginPage";
import { PasswordResetWorkspace } from "./components/PasswordResetWorkspace";
import type { UserInfo } from "./types";
import "./App.css";

const ROLE_LABELS: Record<UserInfo["role"], string> = {
  employee: "本人",
  evaluator1: "評価者1",
  evaluator2: "評価者2",
  admin: "管理者",
};

async function bootstrapSession(): Promise<UserInfo> {
  if (IS_DEMO_MODE && !localStorage.getItem("token")) {
    await demoLogin();
  }
  return api.me();
}

function App() {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [viewAdmin, setViewAdmin] = useState(false);
  const [viewSelfEval, setViewSelfEval] = useState(false);
  const [viewBonus, setViewBonus] = useState(IS_DEMO_MODE);
  const [viewPasswordReset, setViewPasswordReset] = useState(false);

  const refreshUser = async () => {
    const me = await bootstrapSession();
    setUser(me);
    setSessionError(null);
  };

  useEffect(() => {
    bootstrapSession()
      .then((me) => {
        setUser(me);
        if (IS_DEMO_MODE && me.can_access_bonus_workbook) {
          setViewBonus(true);
        }
      })
      .catch((error: unknown) => {
        setUser(null);
        setSessionError(error instanceof Error ? error.message : "セッションの開始に失敗しました");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    setViewAdmin(false);
    setViewSelfEval(false);
    if (!IS_DEMO_MODE) {
      setViewBonus(false);
    }
    setViewPasswordReset(false);
  }, [user?.id]);

  if (loading) {
    return (
      <>
        <DemoBanner />
        <p className="loading">{sessionError ?? "読み込み中..."}</p>
      </>
    );
  }

  if (!user) {
    return (
      <>
        <DemoBanner />
        {IS_DEMO_MODE ? (
          <div className="login-page">
            <div className="login-card">
              <h1>デモ環境</h1>
              <p className="error">{sessionError ?? "デモ用 API に接続できません。"}</p>
              <p className="hint">
                Railway の API が起動しているか、`VITE_API_BASE` が正しいか確認してください。
              </p>
            </div>
          </div>
        ) : (
          <LoginPage onSuccess={refreshUser} />
        )}
      </>
    );
  }

  if (user.must_change_password && !IS_DEMO_MODE) {
    return (
      <>
        <DemoBanner />
        <ChangePasswordPage onSuccess={refreshUser} />
      </>
    );
  }

  const canAccessAdmin = Boolean(user.is_admin || user.role === "admin");
  const hasDirectorSelfEval = Boolean(user.has_facility_director_self_eval);
  const hasOwnSelfEval = Boolean(user.has_own_self_eval);
  const canAccessBonus = Boolean(
    user.can_access_bonus_workbook || user.is_admin || user.role === "admin",
  );
  const canResetPasswords = Boolean(user.can_reset_user_passwords) && !IS_DEMO_MODE;
  const showPasswordResetWorkspace = viewPasswordReset && canResetPasswords;
  const showAdminWorkspace =
    !viewBonus &&
    !showPasswordResetWorkspace &&
    (user.role === "admin" || (canAccessAdmin && viewAdmin));
  const showBonusWorkspace = viewBonus && canAccessBonus;
  const showSelfEvalWorkspace =
    !showAdminWorkspace &&
    !showBonusWorkspace &&
    !showPasswordResetWorkspace &&
    (user.role === "employee" || (viewSelfEval && hasOwnSelfEval));
  const showEvaluatorWorkspace =
    !showAdminWorkspace &&
    !showBonusWorkspace &&
    !showPasswordResetWorkspace &&
    !showSelfEvalWorkspace &&
    (user.role === "evaluator1" || user.role === "evaluator2");

  const selfEvalToggleLabel = hasDirectorSelfEval
    ? viewSelfEval
      ? "部下の考課へ"
      : "自分の自己評価（施設長用）"
    : viewSelfEval
      ? "部下の考課へ"
      : "自分の自己評価へ";

  const currentModeLabel = showPasswordResetWorkspace
    ? "パスワード管理"
    : showBonusWorkspace
    ? "賞与表"
    : showAdminWorkspace
    ? "管理画面"
    : showSelfEvalWorkspace
      ? hasDirectorSelfEval
        ? "自己評価（施設長用）"
        : "自己評価"
      : user.role === "employee"
        ? "自己評価"
        : user.is_hq_evaluator
          ? "本部考課"
          : "部下の考課";

  const passwordResetReturnLabel = user.is_hq_evaluator
    ? "本部考課へ"
    : user.role === "admin"
      ? "管理画面へ"
      : viewAdmin && canAccessAdmin
        ? "管理画面へ"
        : user.role === "evaluator1" || user.role === "evaluator2"
          ? "考課画面へ"
          : "元の画面へ";

  return (
    <div className="app-shell">
      <DemoBanner />
      <div className="user-bar">
        <div className="user-bar-identity">
          <span className="user-bar-name">
            {IS_DEMO_MODE ? "デモ閲覧（管理者）" : user.name ?? user.employee_id}（
            {ROLE_LABELS[user.role]}
            {user.is_hq_evaluator ? "・本部" : ""}）
          </span>
          <span className="current-mode-badge">{currentModeLabel}</span>
        </div>
        <div className="user-bar-actions">
          {hasOwnSelfEval &&
            user.role !== "employee" &&
            !showAdminWorkspace &&
            !showBonusWorkspace &&
            !showPasswordResetWorkspace && (
            <button type="button" onClick={() => setViewSelfEval((v) => !v)}>
              {selfEvalToggleLabel}
            </button>
          )}
          {canResetPasswords && (
            <button
              type="button"
              onClick={() => {
                setViewPasswordReset((v) => !v);
                if (!viewPasswordReset) {
                  setViewBonus(false);
                  setViewSelfEval(false);
                }
              }}
            >
              {viewPasswordReset ? passwordResetReturnLabel : "パスワード管理"}
            </button>
          )}
          {canAccessBonus && !showPasswordResetWorkspace && (
            <button
              type="button"
              onClick={() => {
                setViewBonus((v) => !v);
                if (!viewBonus) {
                  setViewAdmin(false);
                  setViewSelfEval(false);
                  setViewPasswordReset(false);
                }
              }}
            >
              {viewBonus ? "考課画面へ" : "賞与表"}
            </button>
          )}
          {canAccessAdmin && user.role !== "admin" && !showBonusWorkspace && !showPasswordResetWorkspace && (
            <button type="button" onClick={() => setViewAdmin((v) => !v)}>
              {viewAdmin ? "評価画面へ" : "管理画面へ"}
            </button>
          )}
          {!IS_DEMO_MODE && (
            <button
              type="button"
              onClick={() => {
                logout();
                setUser(null);
              }}
            >
              ログアウト
            </button>
          )}
        </div>
      </div>
      {showPasswordResetWorkspace && <PasswordResetWorkspace />}
      {showBonusWorkspace && (
        <BonusWorkbookWorkspace
          canManageAllFacilities={Boolean(user.is_hq_evaluator || user.role === "admin")}
          userFacilityKey={user.facility_key ?? undefined}
          userFacilityLabel={user.facility_label ?? undefined}
        />
      )}
      {showAdminWorkspace && <AdminWorkspace />}
      {!showBonusWorkspace &&
        !showAdminWorkspace &&
        !showPasswordResetWorkspace &&
        showSelfEvalWorkspace && <EvaluateeWorkspace />}
      {!showBonusWorkspace &&
        !showAdminWorkspace &&
        !showPasswordResetWorkspace &&
        showEvaluatorWorkspace && <EvaluatorWorkspace />}
    </div>
  );
}

export default App;
