"""fix duplicate rows in exclude_inbounds_association

Revision ID: a1b2c3d4e5f6
Revises: 2b231de97dc3
Create Date: 2026-05-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '2b231de97dc3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.engine.name == 'mysql':
        bind.execute(sa.text(
            "CREATE TABLE _tmp_excl_inbounds LIKE exclude_inbounds_association"
        ))
        bind.execute(sa.text(
            "INSERT INTO _tmp_excl_inbounds "
            "SELECT DISTINCT proxy_id, inbound_tag FROM exclude_inbounds_association "
            "WHERE proxy_id IN (SELECT id FROM proxies) "
            "AND inbound_tag IN (SELECT tag FROM inbounds)"
        ))
        bind.execute(sa.text("DELETE FROM exclude_inbounds_association"))
        bind.execute(sa.text(
            "INSERT INTO exclude_inbounds_association SELECT * FROM _tmp_excl_inbounds"
        ))
        bind.execute(sa.text("DROP TABLE _tmp_excl_inbounds"))
    else:
        bind.execute(sa.text(
            "DELETE FROM exclude_inbounds_association "
            "WHERE rowid NOT IN ("
            "  SELECT MIN(rowid) FROM exclude_inbounds_association "
            "  GROUP BY proxy_id, inbound_tag"
            ")"
        ))

    op.create_index(
        'uq_exclude_inbounds_association',
        'exclude_inbounds_association',
        ['proxy_id', 'inbound_tag'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('uq_exclude_inbounds_association', table_name='exclude_inbounds_association')
