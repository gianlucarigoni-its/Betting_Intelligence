"""add historical and backtest tables

Revision ID: b7a2c9d4e501
Revises: 996644213396
Create Date: 2026-06-08

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b7a2c9d4e501"
down_revision = "996644213396"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add tables for historical data and backtesting."""
    op.create_table(
        "historical_data_imports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_name", sa.String(length=100), nullable=False),
        sa.Column("dataset_name", sa.String(length=150), nullable=False),
        sa.Column("imported_at", sa.String(length=30), server_default=sa.text("(datetime('now'))"), nullable=True),
        sa.Column("matches_imported", sa.Integer(), nullable=False),
        sa.Column("odds_imported", sa.Integer(), nullable=False),
        sa.Column("ratings_imported", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "team_rating_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=100), nullable=False),
        sa.Column("rating_type", sa.String(length=50), nullable=False),
        sa.Column("rating_value", sa.Float(), nullable=False),
        sa.Column("snapshot_date", sa.String(length=30), nullable=False),
        sa.Column("valid_from", sa.String(length=30), nullable=True),
        sa.Column("valid_to", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.String(length=30), server_default=sa.text("(datetime('now'))"), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "team_id",
            "source_name",
            "rating_type",
            "snapshot_date",
            name="uq_team_rating_snapshot_identity",
        ),
    )

    op.create_table(
        "historical_odd_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("bookmaker_id", sa.Integer(), nullable=True),
        sa.Column("source_name", sa.String(length=100), nullable=False),
        sa.Column("market_level", sa.Integer(), nullable=False),
        sa.Column("market_type", sa.String(length=50), nullable=False),
        sa.Column("market_category", sa.String(length=50), nullable=False),
        sa.Column("selection", sa.String(length=50), nullable=False),
        sa.Column("odd_value", sa.Float(), nullable=False),
        sa.Column("implied_prob", sa.Float(), nullable=False),
        sa.Column("overround_pct", sa.Float(), nullable=True),
        sa.Column("snapshot_time", sa.String(length=30), nullable=False),
        sa.Column("is_opening", sa.Boolean(), nullable=False),
        sa.Column("is_closing", sa.Boolean(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=30), server_default=sa.text("(datetime('now'))"), nullable=True),
        sa.ForeignKeyConstraint(["bookmaker_id"], ["bookmakers.id"]),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "match_id",
            "bookmaker_id",
            "market_type",
            "selection",
            "snapshot_time",
            name="uq_historical_odd_snapshot_identity",
        ),
    )

    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("model_version", sa.String(length=20), nullable=False),
        sa.Column("model_type", sa.String(length=50), nullable=False),
        sa.Column("strategy_name", sa.String(length=100), nullable=False),
        sa.Column("started_at", sa.String(length=30), server_default=sa.text("(datetime('now'))"), nullable=True),
        sa.Column("completed_at", sa.String(length=30), nullable=True),
        sa.Column("train_start_date", sa.String(length=30), nullable=True),
        sa.Column("train_end_date", sa.String(length=30), nullable=True),
        sa.Column("test_start_date", sa.String(length=30), nullable=False),
        sa.Column("test_end_date", sa.String(length=30), nullable=False),
        sa.Column("initial_bankroll", sa.Float(), nullable=False),
        sa.Column("final_bankroll", sa.Float(), nullable=True),
        sa.Column("total_bets", sa.Integer(), nullable=False),
        sa.Column("winning_bets", sa.Integer(), nullable=False),
        sa.Column("losing_bets", sa.Integer(), nullable=False),
        sa.Column("push_bets", sa.Integer(), nullable=False),
        sa.Column("total_staked", sa.Float(), nullable=False),
        sa.Column("profit_loss", sa.Float(), nullable=False),
        sa.Column("roi_pct", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "backtest_bets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("backtest_run_id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("prediction_id", sa.Integer(), nullable=True),
        sa.Column("bookmaker_id", sa.Integer(), nullable=True),
        sa.Column("market_level", sa.Integer(), nullable=False),
        sa.Column("market_type", sa.String(length=50), nullable=False),
        sa.Column("market_category", sa.String(length=50), nullable=False),
        sa.Column("selection", sa.String(length=50), nullable=False),
        sa.Column("model_probability", sa.Float(), nullable=False),
        sa.Column("bookmaker_probability", sa.Float(), nullable=False),
        sa.Column("bookmaker_odds", sa.Float(), nullable=False),
        sa.Column("edge_pct", sa.Float(), nullable=False),
        sa.Column("expected_value", sa.Float(), nullable=True),
        sa.Column("stake", sa.Float(), nullable=False),
        sa.Column("potential_profit", sa.Float(), nullable=False),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("profit_loss", sa.Float(), nullable=True),
        sa.Column("bankroll_before", sa.Float(), nullable=True),
        sa.Column("bankroll_after", sa.Float(), nullable=True),
        sa.Column("placed_at", sa.String(length=30), nullable=True),
        sa.Column("settled_at", sa.String(length=30), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["backtest_run_id"], ["backtest_runs.id"]),
        sa.ForeignKeyConstraint(["bookmaker_id"], ["bookmakers.id"]),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"]),
        sa.ForeignKeyConstraint(["prediction_id"], ["predictions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "backtest_run_id",
            "match_id",
            "market_type",
            "selection",
            name="uq_backtest_bet_identity",
        ),
    )


def downgrade() -> None:
    """Remove historical data and backtesting tables."""
    op.drop_table("backtest_bets")
    op.drop_table("backtest_runs")
    op.drop_table("historical_odd_snapshots")
    op.drop_table("team_rating_snapshots")
    op.drop_table("historical_data_imports")
