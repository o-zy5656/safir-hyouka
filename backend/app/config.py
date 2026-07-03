from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./safir_hyouka.db"
    secret_key: str = "dev-secret-key"
    access_token_expire_minutes: int = 480
    templates_dir: str = "templates"
    dev_allow_unsubmit: bool = True
    default_employee_password: str = "changeme123"
    auto_seed_demo: bool = False
    demo_mode: bool = False
    demo_guest_employee_id: str = "ADMIN001"
    demo_switchable_employee_ids: str = "ADMIN001,hq001,DIR001,E010,E101"
    production_mode: bool = False
    admin_job_titles: str = "施設長"
    eval1_leader_titles: str = "リーダー,サブリーダー"
    admin_employee_ids: str = ""
    hq_evaluator_employee_id: str = "hq001"
    hq_evaluator_display_name: str = "本部"
    default_facility_filter: str = "サフィールいなは"
    retired_archives_dir: str = "data/retired_employees"
    facilities_config_path: str = "data/facilities.json"
    bonus_workbook_template_path: str = ""
    bonus_workbook_password: str = "7770"
    bonus_name_aliases: str = (
        '{"i3016":"渡邊　昌代","i3026":"ニン　イ　イ","i3025":"キン　ダンダリー"}'
    )
    bonus_auto_rank_order: bool = True
    bonus_auto_rank_grade: bool = True
    # 令和7年度 評価基準.xlsx の人数割合（A10% B20% C40% D20% E10%）
    bonus_rank_grade_rules: str = "A:0.10,B:0.20,C:0.40,D:0.20,E:0.10"
    bonus_social_insurance_rate: float = 0.15
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def admin_job_title_set(self) -> set[str]:
        return {t.strip() for t in self.admin_job_titles.split(",") if t.strip()}

    @property
    def eval1_leader_title_set(self) -> set[str]:
        return {t.strip() for t in self.eval1_leader_titles.split(",") if t.strip()}

    @property
    def admin_employee_id_set(self) -> set[str]:
        return {i.strip() for i in self.admin_employee_ids.split(",") if i.strip()}

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def bonus_rank_grade_percentages(self) -> list[tuple[str, float]]:
        rules: list[tuple[str, float]] = []
        for part in self.bonus_rank_grade_rules.split(","):
            piece = part.strip()
            if not piece or ":" not in piece:
                continue
            grade, ratio = piece.split(":", 1)
            rules.append((grade.strip().upper(), float(ratio.strip())))
        return rules

    def validate_runtime(self) -> None:
        if self.production_mode and self.demo_mode:
            raise RuntimeError("本番モードでは DEMO_MODE=true にできません")
        if not self.production_mode:
            return
        weak_secrets = {"dev-secret-key", "change-me-in-production", "change-me"}
        if self.secret_key.strip() in weak_secrets:
            raise RuntimeError("本番モードでは SECRET_KEY を変更してください")
        if self.default_employee_password.strip() in {"changeme123", "password", "12345678"}:
            raise RuntimeError("本番モードでは DEFAULT_EMPLOYEE_PASSWORD を変更してください")
        if self.dev_allow_unsubmit:
            raise RuntimeError("本番モードでは DEV_ALLOW_UNSUBMIT=false にしてください")


settings = Settings()
