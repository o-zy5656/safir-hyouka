"""職員マスタで使う職種・役職の選択肢（名簿・賞与表ロジックと整合）。"""

JOB_TYPES: tuple[str, ...] = (
    "介護",
    "介護職",
    "介護P",
    "ケアアシスト",
    "看護師",
    "准看護師",
    "介護支援専門員",
    "管理栄養士",
    "事務",
    "管理職",
)

JOB_TITLES: tuple[str, ...] = (
    "一般",
    "リーダー",
    "サブリーダー",
    "施設長",
    "特養管理者",
)


def employee_options_dict() -> dict[str, list[str]]:
    return {
        "job_types": list(JOB_TYPES),
        "job_titles": list(JOB_TITLES),
    }
