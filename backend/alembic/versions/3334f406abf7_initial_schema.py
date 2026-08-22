"""基线 schema：创建全部表（可独立从空库初始化）

Revision ID: 3334f406abf7
Revises:
Create Date: 2026-08-22 00:26:47

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3334f406abf7'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_tables() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('username', sa.String(length=50), nullable=False, index=True),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='doctor'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_table(
        'patients',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('gender', sa.String(length=10), nullable=False),
        sa.Column('age', sa.Integer(), nullable=False),
        sa.Column('medical_record_no', sa.String(length=50), nullable=True),
        sa.Column('clinical_symptoms', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_table(
        'system_settings',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('key', sa.String(length=100), nullable=False, index=True),
        sa.Column('value', sa.Text(), nullable=False),
    )
    op.create_table(
        'images',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('patient_id', sa.Integer(), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('filepath', sa.String(length=500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('uploaded_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_table(
        'detection_results',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('image_id', sa.Integer(), sa.ForeignKey('images.id'), nullable=False, unique=True),
        sa.Column('classification', sa.String(length=50), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=True),
        sa.Column('treatment_success_rate', sa.Float(), nullable=True),
        sa.Column('treatment_advice', sa.Text(), nullable=True),
        sa.Column('detected_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=True),
        sa.Column('model_version', sa.String(length=50), nullable=True),
        sa.Column('inference_ms', sa.Float(), nullable=True),
        sa.Column('class_probabilities', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('username', sa.String(length=50), nullable=False, index=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('resource', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), index=True),
    )


def upgrade() -> None:
    _create_tables()


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('detection_results')
    op.drop_table('images')
    op.drop_table('system_settings')
    op.drop_table('patients')
    op.drop_table('users')
