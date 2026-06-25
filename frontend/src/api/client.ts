import type {
  AdminEvaluationItem,
  AdminPeriod,
  AdminUserItem,
  EvaluatorWorkspaceResponse,
  ImportResult,
  UserInfo,
  WorkspaceResponse,
} from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

function getToken(): string | null {
  return localStorage.getItem("token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(formatApiError(detail.detail));
  }
  return res.json() as Promise<T>;
}

function formatApiError(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const d = detail as { message?: string; errors?: string[] };
    if (d.errors?.length) {
      return [d.message ?? "エラーが発生しました", ...d.errors.map((e) => `・${e}`)].join("\n");
    }
    if (d.message) return d.message;
  }
  return "APIエラーが発生しました";
}

export async function login(employeeId: string, password: string) {
  const body = new URLSearchParams({ username: employeeId, password });
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) throw new Error("ログインに失敗しました");
  const data = await res.json();
  localStorage.setItem("token", data.access_token);
  return data;
}

export function logout() {
  localStorage.removeItem("token");
}

export const api = {
  me: () => request<UserInfo>("/api/auth/me"),
  changePassword: (currentPassword: string, newPassword: string) =>
    request<{ ok: boolean; message: string }>("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),
  employeeWorkspace: () => request<WorkspaceResponse>("/api/me/workspace"),
  saveSelfEvaluation: (data: Record<string, unknown>) =>
    request("/api/me/self-evaluation", { method: "PUT", body: JSON.stringify({ data }) }),
  submitSelfEvaluation: () => request("/api/me/self-evaluation/submit", { method: "POST" }),
  unsubmitSelfEvaluation: () =>
    request<{ ok: boolean; message: string }>("/api/me/self-evaluation/unsubmit", { method: "POST" }),
  evaluatorWorkspace: () => request<EvaluatorWorkspaceResponse>("/api/evaluator/workspace"),
  evaluatorAssignment: (id: string) =>
    request<EvaluatorWorkspaceResponse>(`/api/evaluator/assignments/${id}`),
  saveEvaluatorAssignment: (id: string, data: Record<string, unknown>) =>
    request(`/api/evaluator/assignments/${id}`, {
      method: "PUT",
      body: JSON.stringify({ data }),
    }),
  submitEvaluatorAssignment: (id: string) =>
    request(`/api/evaluator/assignments/${id}/submit`, { method: "POST" }),
  adminEvaluations: () => request<AdminEvaluationItem[]>("/api/admin/evaluations"),
  adminReturn: (evaluationId: string, target: string, reason?: string) =>
    request<{ ok: boolean; message: string }>(`/api/admin/evaluations/${evaluationId}/return`, {
      method: "POST",
      body: JSON.stringify({ target, reason }),
    }),
  adminPeriods: () => request<AdminPeriod[]>("/api/admin/periods"),
  adminCreatePeriod: (body: {
    name: string;
    season: "summer" | "winter";
    fiscal_year: number;
    self_eval_deadline?: string;
    eval1_deadline?: string;
    eval2_deadline?: string;
  }) =>
    request<AdminPeriod>("/api/admin/periods", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  adminActivatePeriod: (periodId: string) =>
    request<AdminPeriod>(`/api/admin/periods/${periodId}/activate`, { method: "POST" }),
  adminImportEmployees: async (file: File): Promise<ImportResult> => {
    const token = getToken();
    const formData = new FormData();
    formData.append("file", file);
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(`${API_BASE}/api/admin/employees/import`, {
      method: "POST",
      headers,
      body: formData,
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(formatApiError(detail.detail));
    }
    return res.json() as Promise<ImportResult>;
  },
  adminExportPeriod: async (periodId: string, filename: string) => {
    const token = getToken();
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(`${API_BASE}/api/admin/periods/${periodId}/export`, { headers });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(formatApiError(detail.detail));
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  },
  adminUsers: () => request<AdminUserItem[]>("/api/admin/users"),
  adminUpdateUserRole: (userId: string, role: AdminUserItem["role"]) =>
    request<AdminUserItem>(`/api/admin/users/${userId}/role`, {
      method: "PUT",
      body: JSON.stringify({ role }),
    }),
};
