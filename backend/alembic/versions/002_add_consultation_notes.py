"""Add consultation_notes table for clinical EHR

Revision ID: 002_add_consultation_notes
Revises: 001_initial_schema
Create Date: 2026-10-19 21:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002_add_consultation_notes"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "consultation_notes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("appointment_id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("chief_complaint", sa.Text(), nullable=False),
        sa.Column("diagnosis", sa.String(length=255), nullable=False),
        sa.Column("clinical_notes", sa.Text(), nullable=True),
        sa.Column("prescriptions", sa.JSON(), nullable=True),
        sa.Column("follow_up_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("appointment_id"),
    )
    op.create_index("ix_consultation_notes_id", "consultation_notes", ["id"])
    op.create_index("ix_consultation_notes_appointment_id", "consultation_notes", ["appointment_id"])
    op.create_index("ix_consultation_notes_doctor_id", "consultation_notes", ["doctor_id"])
    op.create_index("ix_consultation_notes_patient_id", "consultation_notes", ["patient_id"])
    op.create_index("ix_consultation_notes_diagnosis", "consultation_notes", ["diagnosis"])


def downgrade() -> None:
    op.drop_index("ix_consultation_notes_diagnosis", table_name="consultation_notes")
    op.drop_index("ix_consultation_notes_patient_id", table_name="consultation_notes")
    op.drop_index("ix_consultation_notes_doctor_id", table_name="consultation_notes")
    op.drop_index("ix_consultation_notes_appointment_id", table_name="consultation_notes")
    op.drop_index("ix_consultation_notes_id", table_name="consultation_notes")
    op.drop_table("consultation_notes")
