import { PasswordResetPanel } from "./PasswordResetPanel";

export function PasswordResetWorkspace() {
  return (
    <div className="workspace-page password-reset-workspace">
      <header className="topbar">
        <h1>職員パスワードリセット</h1>
        <span className="role-badge">パスワード管理</span>
      </header>
      <div className="password-reset-workspace-body">
        <PasswordResetPanel />
      </div>
    </div>
  );
}
