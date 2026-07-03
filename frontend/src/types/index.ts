export interface Criteria {
  score: number;
  text: string;
}

export interface EvaluationItem {
  id: string;
  label: string;
  name: string;
  element: string;
  criteria: Criteria[];
}

export interface TextField {
  id: string;
  label: string;
  instruction?: string;
  multiline?: boolean;
  readonly?: boolean;
  role?: string;
}

export interface FormTemplate {
  id: string;
  version: string;
  title: string;
  type: "self_evaluation" | "assessment";
  instructions?: string;
  items: EvaluationItem[];
  text_fields?: TextField[];
  scoring?: Record<string, unknown>;
}

export interface EmployeeAttributes {
  employee_id: string;
  name: string;
  assignment: string;
  job_type: string;
  job_title?: string | null;
  years_of_service: number;
}

export interface SubmissionPanel {
  status: string;
  deadline: string | null;
  submitted_at: string | null;
  can_edit: boolean;
  can_submit: boolean;
}

export interface WorkspaceResponse {
  period_name: string | null;
  attributes: EmployeeAttributes;
  template: FormTemplate;
  form_data: Record<string, unknown>;
  submission: SubmissionPanel;
}

export interface AssignmentSummary {
  evaluation_id: string;
  employee: EmployeeAttributes;
  self_eval_status: string;
  eval1_status: string;
  eval2_status: string;
  my_status: string;
  uses_facility_director_form?: boolean;
  skips_eval1?: boolean;
  hq_review_only?: boolean;
}

export interface EvaluatorWorkspaceResponse {
  period_name: string | null;
  assignments: AssignmentSummary[];
  selected?: WorkspaceResponse;
  reference?: Record<string, unknown>;
}
export interface AdminEvaluationItem {
  evaluation_id: string;
  employee: EmployeeAttributes;
  self_eval_status: string;
  eval1_status: string;
  eval2_status: string;
}

export interface AdminPeriod {
  id: string;
  name: string;
  season: "summer" | "winter";
  fiscal_year: number;
  status: "draft" | "active" | "closed";
  self_eval_deadline: string | null;
  eval1_deadline: string | null;
  eval2_deadline: string | null;
}

export interface RetiredArchiveItem {
  archive_id: string;
  employee_id: string | null;
  employee_name: string | null;
  retired_at: string | null;
  json_filename: string;
  xlsx_filename: string | null;
}

export interface EmployeeListItem {
  id: string;
  employee_id: string;
  name: string;
  assignment: string;
  job_type: string;
  job_title: string | null;
  years_of_service: number;
  employment_status: "active" | "retired";
  evaluator1_employee_id: string | null;
  evaluator1_name: string | null;
  evaluator2_employee_id: string | null;
  evaluator2_name: string | null;
}

export interface EmployeeActionResponse {
  ok: boolean;
  message: string;
  employee_id: string;
  name: string;
  archive_id?: string | null;
  warnings: string[];
}

export interface ImportResult {
  created: number;
  updated: number;
  users_created: number;
  evaluations_created: number;
  roles_updated: number;
  skipped?: number;
  errors: string[];
}

export interface BonusReflectResult {
  facility: string;
  updated_rows: number;
  matched_employees: string[];
  unmatched_employees: string[];
  unmatched_excel_names: string[];
  warnings: string[];
}

export interface BonusWorkbookRow {
  row_number: number;
  employee_id?: string | null;
  name: string;
  job_title: string;
  facility_label?: string | null;
  bonus_facility_key?: string | null;
  self_score?: number | null;
  eval1_score?: number | null;
  eval2_score?: number | null;
  final_score?: number | null;
  low_self_count?: number | null;
  low_other_count?: number | null;
  cut_self_items?: string | null;
  cut_other_items?: string | null;
  promotion_reference?: string | null;
  is_role_holder?: boolean;
  salary_raise?: string | null;
  rank_order?: number | null;
  rank_grade?: string | null;
  proposed_bonus_amount?: number | null;
  bonus_amount?: number | null;
  prior_summer_amount?: number | null;
  prior_winter_amount?: number | null;
  note: string;
}

export interface BonusWorkbookSummary {
  total_proposed: number;
  total_bonus: number;
  total_with_social_insurance: number;
  provision_monthly: number;
  provision_months: number;
  provision_total: number;
  difference: number;
  social_insurance_rate: number;
}

export interface BonusWorkbookResponse {
  facility: string;
  facility_key: string;
  period_name: string | null;
  template_configured: boolean;
  bonus_sheet_available?: boolean;
  fiscal_year: number;
  current_fiscal_year: number;
  available_fiscal_years: number[];
  read_only: boolean;
  provision_monthly: number;
  provision_months: number;
  summary: BonusWorkbookSummary;
  rows: BonusWorkbookRow[];
}

export interface BonusAmountsSaveResponse {
  ok: boolean;
  provision_monthly: number;
  provision_months: number;
  summary: BonusWorkbookSummary;
}

export interface AdminUserItem {
  user_id: string;
  employee_id: string;
  name: string | null;
  role: "employee" | "evaluator1" | "evaluator2" | "admin";
  is_active: boolean;
}

export interface FacilityItem {
  key: string;
  label: string;
  assignment_match: string;
  enabled: boolean;
  bonus_enabled: boolean;
}

export interface FacilitiesListResponse {
  facilities: FacilityItem[];
}

export interface EmployeeOptions {
  job_types: string[];
  job_titles: string[];
}

export interface UserInfo {
  id: string;
  employee_id: string;
  role: "employee" | "evaluator1" | "evaluator2" | "admin";
  name: string | null;
  must_change_password?: boolean;
  is_admin?: boolean;
  is_hq_evaluator?: boolean;
  has_facility_director_self_eval?: boolean;
  has_own_self_eval?: boolean;
  can_access_bonus_workbook?: boolean;
  can_reset_user_passwords?: boolean;
  facility_key?: string | null;
  facility_label?: string | null;
}

export interface DemoPersona {
  employee_id: string;
  label: string;
  name: string | null;
}

export interface DemoPersonasResponse {
  personas: DemoPersona[];
  default_employee_id: string;
}
