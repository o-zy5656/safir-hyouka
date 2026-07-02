import type {
  AdminEvaluationItem,
  AdminPeriod,
  AdminUserItem,
  BonusReflectResult,
  BonusAmountsSaveResponse,
  BonusWorkbookResponse,
  BonusWorkbookRow,
  EmployeeActionResponse,
  EmployeeListItem,
  EmployeeOptions,
  EvaluatorWorkspaceResponse,
  FacilitiesListResponse,
  ImportResult,
  RetiredArchiveItem,
  UserInfo,
  WorkspaceResponse,
} from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";
export const IS_DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";

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

export async function demoLogin() {
  const res = await fetch(`${API_BASE}/api/auth/demo-login`, { method: "POST" });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(formatApiError(detail.detail) || "デモログインに失敗しました");
  }
  const data = await res.json();
  localStorage.setItem("token", data.access_token);
  return data;
}

export async function login(employeeId: string, password: string) {
  const body = new URLSearchParams({ username: employeeId, password });
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(formatApiError(detail.detail) || "ログインに失敗しました");
  }
  const data = await res.json();
  localStorage.setItem("token", data.access_token);
  return data;
}

export function logout() {
  localStorage.removeItem("token");
}

export const api = {
  me: () => request<UserInfo>("/api/auth/me"),
  facilities: () => request<FacilitiesListResponse>("/api/facilities"),
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
  adminImportRoster: async (
    file: File,
    options: { facilityKey?: string; facilityLabel?: string } = {},
  ): Promise<ImportResult> => {
    const token = getToken();
    const formData = new FormData();
    formData.append("file", file);
    const params = new URLSearchParams();
    if (options.facilityKey) params.set("facility_key", options.facilityKey);
    if (options.facilityLabel) params.set("facility", options.facilityLabel);
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(
      `${API_BASE}/api/admin/employees/import-roster?${params.toString()}`,
      { method: "POST", headers, body: formData },
    );
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(formatApiError(detail.detail));
    }
    return res.json() as Promise<ImportResult>;
  },
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
  adminPreviewBonusReflect: (periodId: string, facility = "inaha") =>
    request<BonusReflectResult>(
      `/api/admin/periods/${periodId}/export-bonus/preview?facility=${encodeURIComponent(facility)}`,
    ),
  adminExportBonusReflect: async (periodId: string, filename: string, facility = "inaha") => {
    const token = getToken();
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(
      `${API_BASE}/api/admin/periods/${periodId}/export-bonus?facility=${encodeURIComponent(facility)}`,
      { headers },
    );
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
  bonusWorkbook: (facility = "inaha", fiscalYear?: number) => {
    const params = new URLSearchParams({ facility });
    if (fiscalYear != null) params.set("fiscal_year", String(fiscalYear));
    return request<BonusWorkbookResponse>(`/api/bonus-workbook?${params.toString()}`);
  },
  saveBonusWorkbook: (
    rows: BonusWorkbookRow[],
    facility = "inaha",
    options?: { provision_monthly?: number; provision_months?: number; fiscal_year?: number },
  ) => {
    const params = new URLSearchParams({ facility });
    if (options?.fiscal_year != null) params.set("fiscal_year", String(options.fiscal_year));
    return request<{ ok: boolean }>(`/api/bonus-workbook?${params.toString()}`, {
      method: "PUT",
      body: JSON.stringify({
        rows,
        provision_monthly: options?.provision_monthly,
        provision_months: options?.provision_months,
      }),
    });
  },
  saveBonusAmounts: (
    rows: BonusWorkbookRow[],
    facility = "inaha",
    options?: { provision_monthly?: number; provision_months?: number; fiscal_year?: number },
  ) => {
    const params = new URLSearchParams({ facility });
    if (options?.fiscal_year != null) params.set("fiscal_year", String(options.fiscal_year));
    return request<BonusAmountsSaveResponse>(
      `/api/bonus-workbook/amounts?${params.toString()}`,
      {
        method: "PUT",
        body: JSON.stringify({
          rows: rows
            .filter((row) => row.employee_id)
            .map((row) => ({
              employee_id: row.employee_id,
              bonus_facility_key: row.bonus_facility_key,
              proposed_bonus_amount: row.proposed_bonus_amount,
              bonus_amount: row.bonus_amount,
              prior_summer_amount: row.prior_summer_amount,
              prior_winter_amount: row.prior_winter_amount,
            })),
          provision_monthly: options?.provision_monthly,
          provision_months: options?.provision_months,
        }),
      },
    );
  },
  syncBonusWorkbook: (facility = "inaha") =>
    request<BonusReflectResult>(`/api/bonus-workbook/sync?facility=${encodeURIComponent(facility)}`, {
      method: "POST",
    }),
  syncBonusRoster: (facility = "inaha") =>
    request<BonusReflectResult>(`/api/bonus-workbook/sync-roster?facility=${encodeURIComponent(facility)}`, {
      method: "POST",
    }),
  exportBonusWorkbook: async (filename: string, facility = "inaha") => {
    const token = getToken();
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(
      `${API_BASE}/api/bonus-workbook/export?facility=${encodeURIComponent(facility)}`,
      { headers },
    );
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
  adminResetUserPassword: (userId: string) =>
    request<{ ok: boolean; message: string; employee_id: string; temporary_password: string }>(
      `/api/admin/users/${userId}/reset-password`,
      { method: "POST" },
    ),
  adminEmployees: (status: "active" | "retired" = "active") =>
    request<EmployeeListItem[]>(`/api/admin/employees?status=${status}`),
  adminEmployeeOptions: () => request<EmployeeOptions>("/api/admin/employee-options"),
  adminCreateEmployee: (body: {
    employee_id: string;
    name: string;
    assignment: string;
    job_type: string;
    job_title?: string;
    years_of_service?: number;
    evaluator1_employee_id?: string;
    evaluator2_employee_id?: string;
  }) =>
    request<EmployeeActionResponse>("/api/admin/employees", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  adminRetireEmployee: (employeeId: string, reason?: string) =>
    request<EmployeeActionResponse>(`/api/admin/employees/${employeeId}/retire`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  adminRetiredArchives: () => request<RetiredArchiveItem[]>("/api/admin/employees/retired-archives"),
  adminDownloadRetiredArchive: async (archiveId: string, fileType: "json" | "xlsx", filename: string) => {
    const token = getToken();
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(
      `${API_BASE}/api/admin/employees/retired-archives/${encodeURIComponent(archiveId)}/download?file_type=${fileType}`,
      { headers },
    );
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
  adminUpdateUserRole: (userId: string, role: AdminUserItem["role"]) =>
    request<AdminUserItem>(`/api/admin/users/${userId}/role`, {
      method: "PUT",
      body: JSON.stringify({ role }),
    }),
};
