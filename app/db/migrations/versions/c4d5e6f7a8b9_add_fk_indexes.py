"""add indexes on FK columns missing from query paths

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7
Branch Labels: None
Depends On: None

"""
from alembic import op
import sqlalchemy as sa


revision = 'c4d5e6f7a8b9'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None

# (index_name, table, column)
INDEXES = [
    ('ix_users_admin_id',                    'users',                  'admin_id'),
    ('ix_proxies_user_id',                   'proxies',                'user_id'),
    ('ix_node_user_usages_user_id',          'node_user_usages',       'user_id'),
    ('ix_node_user_usages_node_id',          'node_user_usages',       'node_id'),
    ('ix_node_usages_node_id',               'node_usages',            'node_id'),
    ('ix_user_usage_logs_user_id',           'user_usage_logs',        'user_id'),
    ('ix_notification_reminders_user_id',    'notification_reminders', 'user_id'),
    ('ix_next_plans_user_id',                'next_plans',             'user_id'),
    ('ix_admin_usage_logs_admin_id',         'admin_usage_logs',       'admin_id'),
]


def upgrade() -> None:
    bind = op.get_bind()
    for index_name, table, column in INDEXES:
        bind.execute(sa.text(
            f"CREATE INDEX IF NOT EXISTS `{index_name}` ON `{table}` (`{column}`)"
        ))


def downgrade() -> None:
    bind = op.get_bind()
    for index_name, table, _ in INDEXES:
        bind.execute(sa.text(
            f"DROP INDEX IF EXISTS `{index_name}` ON `{table}`"
        ))
