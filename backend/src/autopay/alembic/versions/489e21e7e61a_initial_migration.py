"""Initial migration

Revision ID: 489e21e7e61a
Revises:
Create Date: 2026-07-09 16:08:09.352059

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '489e21e7e61a'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables from scratch."""
    op.create_table(
        'merchants',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('api_key_hash', sa.String(), nullable=False),
        sa.Column('phone_number', sa.String(), nullable=True),
        sa.Column('encrypted_session', sa.String(), nullable=True),
        sa.Column('is_connected', sa.Boolean(), nullable=True),
        sa.Column('webhook_url', sa.String(), nullable=True),
        sa.Column('webhook_secret', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_merchants_api_key_hash'), 'merchants', ['api_key_hash'], unique=True)

    op.create_table(
        'processed_payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('merchant_id', sa.String(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('chat_username', sa.String(), nullable=False),
        sa.Column('card_type', sa.String(), nullable=False),
        sa.Column('amount_tiyins', sa.BigInteger(), nullable=False),
        sa.Column('currency', sa.String(), nullable=True),
        sa.Column('receiver_card_info', sa.String(), nullable=True),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('transaction_date', sa.DateTime(), nullable=True),
        sa.Column('date_received', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_processed_payments_id'), 'processed_payments', ['id'], unique=False)
    op.create_index(op.f('ix_processed_payments_message_id'), 'processed_payments', ['message_id'], unique=False)
    op.create_index(op.f('ix_processed_payments_chat_username'), 'processed_payments', ['chat_username'], unique=False)

    op.create_table(
        'payment_intents',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('merchant_id', sa.String(), nullable=False),
        sa.Column('base_amount_tiyins', sa.BigInteger(), nullable=False),
        sa.Column('expected_amount_tiyins', sa.BigInteger(), nullable=False),
        sa.Column('currency', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('matched_payment_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['matched_payment_id'], ['processed_payments.id']),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'unparsed_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('merchant_id', sa.String(), nullable=True),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('chat_username', sa.String(), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('error_reason', sa.String(), nullable=False),
        sa.Column('date_received', sa.DateTime(), nullable=True),
        sa.Column('is_resolved', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_unparsed_messages_id'), 'unparsed_messages', ['id'], unique=False)
    op.create_index(op.f('ix_unparsed_messages_message_id'), 'unparsed_messages', ['message_id'], unique=False)
    op.create_index(op.f('ix_unparsed_messages_chat_username'), 'unparsed_messages', ['chat_username'], unique=False)


def downgrade() -> None:
    """Drop all tables."""
    op.drop_index(op.f('ix_unparsed_messages_chat_username'), table_name='unparsed_messages')
    op.drop_index(op.f('ix_unparsed_messages_message_id'), table_name='unparsed_messages')
    op.drop_index(op.f('ix_unparsed_messages_id'), table_name='unparsed_messages')
    op.drop_table('unparsed_messages')
    op.drop_table('payment_intents')
    op.drop_index(op.f('ix_processed_payments_chat_username'), table_name='processed_payments')
    op.drop_index(op.f('ix_processed_payments_message_id'), table_name='processed_payments')
    op.drop_index(op.f('ix_processed_payments_id'), table_name='processed_payments')
    op.drop_table('processed_payments')
    op.drop_index(op.f('ix_merchants_api_key_hash'), table_name='merchants')
    op.drop_table('merchants')
