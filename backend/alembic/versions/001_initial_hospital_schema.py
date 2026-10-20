"""Initial hospital schema for MediVoice

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-19 19:22:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Departments table
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=100), nullable=False),
        sa.Column("floor", sa.String(length=50), nullable=False),
        sa.Column("extension", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_departments_code", "departments", ["code"])
    op.create_index("ix_departments_id", "departments", ["id"])
    op.create_index("ix_departments_name", "departments", ["name"])

    # 2. Doctors table
    op.create_table(
        "doctors",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("specialty", sa.String(length=150), nullable=False),
        sa.Column("qualifications", sa.String(length=255), nullable=False),
        sa.Column("experience", sa.String(length=50), nullable=False),
        sa.Column("consultation_fee", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("room_number", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_doctors_id", "doctors", ["id"])
    op.create_index("ix_doctors_name", "doctors", ["name"])
    op.create_index("ix_doctors_department_id", "doctors", ["department_id"])
    op.create_index("ix_doctors_specialty", "doctors", ["specialty"])

    # 3. Doctor Schedules table
    op.create_table(
        "doctor_schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("working_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("slot_duration_minutes", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doctor_id", "working_date", name="uq_doctor_working_date"),
    )
    op.create_index("ix_doctor_schedules_id", "doctor_schedules", ["id"])
    op.create_index("ix_doctor_schedules_doctor_id", "doctor_schedules", ["doctor_id"])
    op.create_index("ix_doctor_schedules_working_date", "doctor_schedules", ["working_date"])

    # 4. Patients table
    op.create_table(
        "patients",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("display_name", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patients_id", "patients", ["id"])
    op.create_index("ix_patients_display_name", "patients", ["display_name"])
    op.create_index("ix_patients_phone", "patients", ["phone"])

    # 5. Appointments table
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("booking_reference", sa.String(length=50), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("appointment_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="booked"),
        sa.Column("appointment_type", sa.String(length=50), nullable=False, server_default="Consultation"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("booking_reference"),
    )
    op.create_index("ix_appointments_id", "appointments", ["id"])
    op.create_index("ix_appointments_booking_reference", "appointments", ["booking_reference"])
    op.create_index("ix_appointments_department_id", "appointments", ["department_id"])
    op.create_index("ix_appointments_doctor_id", "appointments", ["doctor_id"])
    op.create_index("ix_appointments_patient_id", "appointments", ["patient_id"])
    op.create_index("ix_appointments_appointment_date", "appointments", ["appointment_date"])
    op.create_index("ix_appointments_status", "appointments", ["status"])
    op.create_index("ix_appointment_doctor_date", "appointments", ["doctor_id", "appointment_date"])
    op.create_index("ix_appointment_patient_date", "appointments", ["patient_id", "appointment_date"])

    # 6. Queue Entries table
    op.create_table(
        "queue_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("appointment_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="waiting"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="normal"),
        sa.Column("check_in_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("called_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_time", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("appointment_id"),
    )
    op.create_index("ix_queue_entries_id", "queue_entries", ["id"])
    op.create_index("ix_queue_entries_appointment_id", "queue_entries", ["appointment_id"])
    op.create_index("ix_queue_entries_token", "queue_entries", ["token"])
    op.create_index("ix_queue_entries_status", "queue_entries", ["status"])

    # 7. Triage Alerts table
    op.create_table(
        "triage_alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("alert_type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("patient_id", sa.Integer(), nullable=True),
        sa.Column("appointment_id", sa.Integer(), nullable=True),
        sa.Column("location", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_triage_alerts_id", "triage_alerts", ["id"])
    op.create_index("ix_triage_alerts_priority", "triage_alerts", ["priority"])
    op.create_index("ix_triage_alerts_alert_type", "triage_alerts", ["alert_type"])
    op.create_index("ix_triage_alerts_status", "triage_alerts", ["status"])
    op.create_index("ix_triage_alerts_department_id", "triage_alerts", ["department_id"])
    op.create_index("ix_triage_alerts_patient_id", "triage_alerts", ["patient_id"])
    op.create_index("ix_triage_alerts_appointment_id", "triage_alerts", ["appointment_id"])


def downgrade() -> None:
    op.drop_table("triage_alerts")
    op.drop_table("queue_entries")
    op.drop_table("appointments")
    op.drop_table("patients")
    op.drop_table("doctor_schedules")
    op.drop_table("doctors")
    op.drop_table("departments")
