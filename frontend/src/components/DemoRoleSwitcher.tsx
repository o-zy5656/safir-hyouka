import { useEffect, useState } from "react";
import { api, demoLogin, fetchDemoPersonas } from "../api/client";
import type { DemoPersona, UserInfo } from "../types";

type Props = {
  currentEmployeeId: string;
  onSwitch: (user: UserInfo) => void;
};

export function DemoRoleSwitcher({ currentEmployeeId, onSwitch }: Props) {
  const [personas, setPersonas] = useState<DemoPersona[]>([]);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDemoPersonas()
      .then(setPersonas)
      .catch(() => setPersonas([]));
  }, []);

  const handleChange = async (event: React.ChangeEvent<HTMLSelectElement>) => {
    const employeeId = event.target.value;
    if (!employeeId || employeeId === currentEmployeeId) return;

    setSwitching(true);
    setError(null);
    try {
      await demoLogin(employeeId);
      onSwitch(await api.me());
    } catch (err) {
      setError(err instanceof Error ? err.message : "切り替えに失敗しました");
      event.target.value = currentEmployeeId;
    } finally {
      setSwitching(false);
    }
  };

  if (personas.length === 0) return null;

  return (
    <label className="demo-role-switcher">
      <span className="demo-role-switcher-label">デモ役割</span>
      <select
        className="demo-role-switcher-select"
        value={currentEmployeeId}
        onChange={handleChange}
        disabled={switching}
        aria-label="デモ役割の切り替え"
      >
        {personas.map((persona) => (
          <option key={persona.employee_id} value={persona.employee_id}>
            {persona.label}
            {persona.name ? ` — ${persona.name}` : ""}
          </option>
        ))}
      </select>
      {switching && <span className="demo-role-switcher-status">切替中…</span>}
      {error && <span className="demo-role-switcher-error">{error}</span>}
    </label>
  );
}
