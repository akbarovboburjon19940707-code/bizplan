"""Remove product_id foreign key from payments

Revision ID: a3f1c8d9b4e2
Revises: 7efb330a2a1a
Create Date: 2026-05-04 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3f1c8d9b4e2'
down_revision = '7efb330a2a1a'
branch_labels = None
depends_on = None


def upgrade():
    """
    payments.product_id ustunidan business_plans jadvaliga foreign key ni olib tashlash.
    Sabab: katalog mahsulotlari JSON faylda (catalog_products.json) saqlanadi,
    business_plans jadvalida emas. FK shart emas va xatolik keltiradi.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # FK bor-yo'qligini tekshirish
    fks = inspector.get_foreign_keys('payments')
    fk_exists = False
    fk_name = 'payments_product_id_fkey'
    
    for fk in fks:
        if fk['name'] == fk_name or ('product_id' in fk.get('constrained_columns', [])):
            fk_exists = True
            if fk['name']:
                fk_name = fk['name']
            break
            
    if fk_exists:
        with op.batch_alter_table('payments', schema=None) as batch_op:
            batch_op.drop_constraint(fk_name, type_='foreignkey')


def downgrade():
    """FK ni qayta tiklash (agar kerak bo'lsa)."""
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'payments_product_id_fkey',
            'business_plans',
            ['product_id'],
            ['id'],
            ondelete='SET NULL'
        )
