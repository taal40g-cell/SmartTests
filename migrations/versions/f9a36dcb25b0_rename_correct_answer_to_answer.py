"""rename correct_answer to answer

Revision ID: f9a36dcb25b0
Revises:
Create Date: 2025-10-02 10:21:25.592312
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'f9a36dcb25b0'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema: rename correct_answer -> answer"""
    op.alter_column(
        "questions",
        "correct_answer",
        new_column_name="answer",
        existing_type=sa.String(length=255)
    )

def downgrade() -> None:
    """Downgrade schema: rename answer -> correct_answer"""
    op.alter_column(
        "questions",
        "answer",
        new_column_name="correct_answer",
        existing_type=sa.String(length=255)
    )
