import type { FormTemplate } from "../types";

export function validateFormData(
  template: FormTemplate,
  formData: Record<string, unknown>,
  role?: string,
): string[] {
  const errors: string[] = [];
  const scores = (formData.scores as Record<string, number | null | undefined>) ?? {};
  const textFields = (formData.text_fields as Record<string, string | undefined>) ?? {};

  for (const item of template.items) {
    const display = `${item.label} ${item.name}`.trim();
    const score = scores[item.id];
    if (score === undefined || score === null) {
      errors.push(`「${display}」の採点が未入力です`);
    }
  }

  for (const field of template.text_fields ?? []) {
    if (field.readonly) continue;
    if (field.role && role && field.role !== role) continue;
    if (field.role && !role) continue;
    const value = textFields[field.id] ?? "";
    if (!value.trim()) {
      errors.push(`「${field.label}」が未入力です`);
    }
  }

  return errors;
}

export function formatValidationErrors(errors: string[]): string {
  if (errors.length === 0) return "";
  return ["未入力の項目があります:", ...errors.map((e) => `・${e}`)].join("\n");
}
