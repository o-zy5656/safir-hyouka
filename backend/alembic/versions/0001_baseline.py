"""Baseline schema marker for existing databases.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-26

既存環境は app.main.migrate_schema() で列追加済みのため、
このリビジョンは Alembic 履歴の起点（スタンプ用）です。
新規 DB は create_all() 後に `alembic stamp head` してください。
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
