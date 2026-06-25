from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./safir_hyouka.db"
    secret_key: str = "dev-secret-key"
    access_token_expire_minutes: int = 480
    templates_dir: str = "templates"
    dev_allow_unsubmit: bool = True
    default_employee_password: str = "changeme123"
    auto_seed_demo: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
