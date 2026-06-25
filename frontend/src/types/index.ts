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

export interface ImportResult {
  created: number;
  updated: number;
  users_created: number;
  evaluations_created: number;
  roles_updated: number;
  errors: string[];
}

export interface AdminUserItem {
  user_id: string;
  employee_id: string;
  name: string | null;
  role: "employee" | "evaluator1" | "evaluator2" | "admin";
  is_active: boolean;
}

export interface UserInfo {
  id: string;
  employee_id: string;
  role: "employee" | "evaluator1" | "evaluator2" | "admin";
  name: string | null;
  must_change_password?: boolean;
}
