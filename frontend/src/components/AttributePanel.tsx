import type { EmployeeAttributes } from "../types";

interface Props {
  attributes: EmployeeAttributes;
  title?: string;
}

export function AttributePanel({ attributes, title = "属性" }: Props) {
  return (
    <section>
      <h2>{title}</h2>
      <dl className="attr-list">
        <dt>社員ID</dt>
        <dd>{attributes.employee_id}</dd>
        <dt>氏名</dt>
        <dd>{attributes.name}</dd>
        <dt>配属</dt>
        <dd>{attributes.assignment}</dd>
        <dt>職種</dt>
        <dd>{attributes.job_type}</dd>
        <dt>勤続年数</dt>
        <dd>{attributes.years_of_service} 年</dd>
      </dl>
    </section>
  );
}
