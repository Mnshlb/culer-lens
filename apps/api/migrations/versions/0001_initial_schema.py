"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-09-25 11:26:30.737167
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('competitions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('model_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('description', sa.String(length=300), nullable=False),
    sa.Column('trained_at', sa.DateTime(), nullable=True),
    sa.Column('card', sa.JSON(), nullable=False),
    sa.Column('evaluation', sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('players',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('display_name', sa.String(length=80), nullable=False),
    sa.Column('country', sa.String(length=60), nullable=True),
    sa.Column('position_family', sa.String(length=2), nullable=True),
    sa.Column('position_group', sa.String(length=2), nullable=True),
    sa.Column('barca_minutes', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('players', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_players_display_name'), ['display_name'], unique=False)

    op.create_table('seasons',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('label', sa.String(length=9), nullable=False),
    sa.Column('start_year', sa.SmallInteger(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('label')
    )
    with op.batch_alter_table('seasons', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_seasons_start_year'), ['start_year'], unique=False)

    op.create_table('teams',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('statsbomb_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('short_name', sa.String(length=40), nullable=False),
    sa.Column('code', sa.String(length=3), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name'),
    sa.UniqueConstraint('statsbomb_id')
    )
    op.create_table('matches',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('statsbomb_id', sa.Integer(), nullable=True),
    sa.Column('fixture_id', sa.Integer(), nullable=True),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('kickoff', sa.DateTime(), nullable=True),
    sa.Column('season_id', sa.Integer(), nullable=False),
    sa.Column('competition_id', sa.Integer(), nullable=False),
    sa.Column('home_team_id', sa.Integer(), nullable=False),
    sa.Column('away_team_id', sa.Integer(), nullable=False),
    sa.Column('home_score', sa.SmallInteger(), nullable=False),
    sa.Column('away_score', sa.SmallInteger(), nullable=False),
    sa.Column('barca_home', sa.Boolean(), nullable=False),
    sa.Column('barca_result', sa.String(length=1), nullable=False),
    sa.Column('era', sa.String(length=40), nullable=True),
    sa.Column('match_week', sa.SmallInteger(), nullable=True),
    sa.Column('stadium', sa.String(length=120), nullable=True),
    sa.Column('referee', sa.String(length=120), nullable=True),
    sa.Column('has_events', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['away_team_id'], ['teams.id'], ),
    sa.ForeignKeyConstraint(['competition_id'], ['competitions.id'], ),
    sa.ForeignKeyConstraint(['home_team_id'], ['teams.id'], ),
    sa.ForeignKeyConstraint(['season_id'], ['seasons.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('fixture_id'),
    sa.UniqueConstraint('statsbomb_id')
    )
    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_matches_date'), ['date'], unique=False)
        batch_op.create_index(batch_op.f('ix_matches_season_id'), ['season_id'], unique=False)

    op.create_table('player_season_ratings',
    sa.Column('player_id', sa.Integer(), nullable=False),
    sa.Column('season_id', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('position_family', sa.String(length=2), nullable=True),
    sa.Column('appearances', sa.SmallInteger(), nullable=False),
    sa.Column('starts', sa.SmallInteger(), nullable=False),
    sa.Column('minutes', sa.Float(), nullable=False),
    sa.Column('overall', sa.Float(), nullable=True),
    sa.Column('overall_pct', sa.Float(), nullable=True),
    sa.Column('pillars', sa.JSON(), nullable=True),
    sa.Column('per90', sa.JSON(), nullable=True),
    sa.Column('reliable', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['player_id'], ['players.id'], ),
    sa.ForeignKeyConstraint(['season_id'], ['seasons.id'], ),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ),
    sa.PrimaryKeyConstraint('player_id', 'season_id', 'team_id')
    )
    op.create_table('team_features',
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('season_id', sa.Integer(), nullable=False),
    sa.Column('opponent_id', sa.Integer(), nullable=False),
    sa.Column('is_home', sa.Boolean(), nullable=False),
    sa.Column('goals', sa.SmallInteger(), nullable=False),
    sa.Column('goals_against', sa.SmallInteger(), nullable=False),
    sa.Column('result', sa.String(length=1), nullable=False),
    sa.Column('elo', sa.Float(), nullable=False),
    sa.Column('elo_post', sa.Float(), nullable=False),
    sa.Column('points_5', sa.Float(), nullable=True),
    sa.Column('goals_10', sa.Float(), nullable=True),
    sa.Column('goals_against_10', sa.Float(), nullable=True),
    sa.Column('sot_10', sa.Float(), nullable=True),
    sa.Column('sot_against_10', sa.Float(), nullable=True),
    sa.Column('points_std', sa.Float(), nullable=True),
    sa.Column('matches_played', sa.SmallInteger(), nullable=False),
    sa.Column('days_rest', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['opponent_id'], ['teams.id'], ),
    sa.ForeignKeyConstraint(['season_id'], ['seasons.id'], ),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ),
    sa.PrimaryKeyConstraint('team_id', 'date')
    )
    op.create_table('events',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('match_id', sa.Integer(), nullable=False),
    sa.Column('index', sa.Integer(), nullable=False),
    sa.Column('period', sa.SmallInteger(), nullable=False),
    sa.Column('minute', sa.SmallInteger(), nullable=False),
    sa.Column('second', sa.SmallInteger(), nullable=False),
    sa.Column('type', sa.String(length=24), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('player_id', sa.Integer(), nullable=True),
    sa.Column('x', sa.Float(), nullable=True),
    sa.Column('y', sa.Float(), nullable=True),
    sa.Column('end_x', sa.Float(), nullable=True),
    sa.Column('end_y', sa.Float(), nullable=True),
    sa.Column('outcome', sa.String(length=32), nullable=True),
    sa.Column('subtype', sa.String(length=32), nullable=True),
    sa.Column('recipient_id', sa.Integer(), nullable=True),
    sa.Column('xg', sa.Float(), nullable=True),
    sa.Column('xt', sa.Float(), nullable=True),
    sa.Column('body_part', sa.String(length=20), nullable=True),
    sa.Column('play_pattern', sa.String(length=24), nullable=True),
    sa.Column('is_touch', sa.Boolean(), nullable=False),
    sa.Column('is_pass', sa.Boolean(), nullable=False),
    sa.Column('is_complete_pass', sa.Boolean(), nullable=False),
    sa.Column('is_carry', sa.Boolean(), nullable=False),
    sa.Column('is_attacking', sa.Boolean(), nullable=False),
    sa.Column('is_defending', sa.Boolean(), nullable=False),
    sa.Column('is_shot', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ),
    sa.ForeignKeyConstraint(['player_id'], ['players.id'], ),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.create_index('ix_events_match_type', ['match_id', 'type'], unique=False)
        batch_op.create_index('ix_events_player_match', ['player_id', 'match_id'], unique=False)

    op.create_table('lineups',
    sa.Column('match_id', sa.Integer(), nullable=False),
    sa.Column('player_id', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('jersey_number', sa.SmallInteger(), nullable=True),
    sa.Column('started', sa.Boolean(), nullable=False),
    sa.Column('played', sa.Boolean(), nullable=False),
    sa.Column('minutes', sa.Float(), nullable=False),
    sa.Column('position', sa.String(length=40), nullable=True),
    sa.Column('position_group', sa.String(length=2), nullable=True),
    sa.Column('on_minute', sa.Float(), nullable=True),
    sa.Column('off_minute', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ),
    sa.ForeignKeyConstraint(['player_id'], ['players.id'], ),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ),
    sa.PrimaryKeyConstraint('match_id', 'player_id')
    )
    op.create_table('player_fixtures',
    sa.Column('match_id', sa.Integer(), nullable=False),
    sa.Column('player_id', sa.Integer(), nullable=False),
    sa.Column('position_family', sa.String(length=2), nullable=True),
    sa.Column('minutes_7d', sa.Float(), nullable=False),
    sa.Column('minutes_14d', sa.Float(), nullable=False),
    sa.Column('minutes_30d', sa.Float(), nullable=False),
    sa.Column('consecutive_starts', sa.SmallInteger(), nullable=False),
    sa.Column('days_since_last_app', sa.SmallInteger(), nullable=True),
    sa.Column('starts_last5', sa.Float(), nullable=False),
    sa.Column('minutes_last5', sa.Float(), nullable=False),
    sa.Column('form_rating', sa.Float(), nullable=True),
    sa.Column('workload_index', sa.Float(), nullable=False),
    sa.Column('workload_band', sa.String(length=10), nullable=False),
    sa.Column('p_start', sa.Float(), nullable=True),
    sa.Column('in_xi', sa.Boolean(), nullable=False),
    sa.Column('slot', sa.String(length=40), nullable=True),
    sa.Column('slot_x', sa.Float(), nullable=True),
    sa.Column('slot_y', sa.Float(), nullable=True),
    sa.Column('reasons', sa.JSON(), nullable=True),
    sa.Column('started', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ),
    sa.ForeignKeyConstraint(['player_id'], ['players.id'], ),
    sa.PrimaryKeyConstraint('match_id', 'player_id')
    )
    op.create_table('player_match_stats',
    sa.Column('match_id', sa.Integer(), nullable=False),
    sa.Column('player_id', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('started', sa.Boolean(), nullable=False),
    sa.Column('minutes', sa.Float(), nullable=False),
    sa.Column('position', sa.String(length=40), nullable=True),
    sa.Column('position_family', sa.String(length=2), nullable=True),
    sa.Column('goals', sa.SmallInteger(), nullable=False),
    sa.Column('assists', sa.SmallInteger(), nullable=False),
    sa.Column('xg', sa.Float(), nullable=False),
    sa.Column('npxg', sa.Float(), nullable=False),
    sa.Column('xa', sa.Float(), nullable=False),
    sa.Column('xt', sa.Float(), nullable=False),
    sa.Column('shots', sa.SmallInteger(), nullable=False),
    sa.Column('key_passes', sa.SmallInteger(), nullable=False),
    sa.Column('touches', sa.SmallInteger(), nullable=False),
    sa.Column('touches_in_box', sa.SmallInteger(), nullable=False),
    sa.Column('passes', sa.SmallInteger(), nullable=False),
    sa.Column('passes_completed', sa.SmallInteger(), nullable=False),
    sa.Column('progressive_passes', sa.SmallInteger(), nullable=False),
    sa.Column('progressive_carries', sa.SmallInteger(), nullable=False),
    sa.Column('dribbles_completed', sa.SmallInteger(), nullable=False),
    sa.Column('pressures', sa.SmallInteger(), nullable=False),
    sa.Column('tackles_won', sa.SmallInteger(), nullable=False),
    sa.Column('interceptions', sa.SmallInteger(), nullable=False),
    sa.Column('recoveries', sa.SmallInteger(), nullable=False),
    sa.Column('match_rating', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ),
    sa.ForeignKeyConstraint(['player_id'], ['players.id'], ),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ),
    sa.PrimaryKeyConstraint('match_id', 'player_id')
    )
    op.create_table('predictions',
    sa.Column('match_id', sa.Integer(), nullable=False),
    sa.Column('model_version_id', sa.Integer(), nullable=False),
    sa.Column('p_win', sa.Float(), nullable=False),
    sa.Column('p_draw', sa.Float(), nullable=False),
    sa.Column('p_loss', sa.Float(), nullable=False),
    sa.Column('exp_goals_barca', sa.Float(), nullable=True),
    sa.Column('exp_goals_opp', sa.Float(), nullable=True),
    sa.Column('top_scores', sa.JSON(), nullable=True),
    sa.Column('market', sa.JSON(), nullable=True),
    sa.Column('formation', sa.String(length=8), nullable=True),
    sa.Column('explanation', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ),
    sa.ForeignKeyConstraint(['model_version_id'], ['model_versions.id'], ),
    sa.PrimaryKeyConstraint('match_id', 'model_version_id'),
    sa.UniqueConstraint('match_id', 'model_version_id')
    )
    op.create_table('team_match_stats',
    sa.Column('match_id', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('goals', sa.SmallInteger(), nullable=False),
    sa.Column('xg', sa.Float(), nullable=False),
    sa.Column('npxg', sa.Float(), nullable=False),
    sa.Column('shots', sa.SmallInteger(), nullable=False),
    sa.Column('shots_on_target', sa.SmallInteger(), nullable=False),
    sa.Column('big_chances', sa.SmallInteger(), nullable=False),
    sa.Column('possession', sa.Float(), nullable=False),
    sa.Column('passes', sa.Integer(), nullable=False),
    sa.Column('pass_completion', sa.Float(), nullable=False),
    sa.Column('progressive_passes', sa.SmallInteger(), nullable=False),
    sa.Column('progressive_carries', sa.SmallInteger(), nullable=False),
    sa.Column('box_entries', sa.SmallInteger(), nullable=False),
    sa.Column('final_third_entries', sa.SmallInteger(), nullable=False),
    sa.Column('pressures', sa.SmallInteger(), nullable=False),
    sa.Column('counterpresses', sa.SmallInteger(), nullable=False),
    sa.Column('high_recoveries', sa.SmallInteger(), nullable=False),
    sa.Column('ppda', sa.Float(), nullable=False),
    sa.Column('field_tilt', sa.Float(), nullable=False),
    sa.Column('defensive_action_height', sa.Float(), nullable=True),
    sa.Column('xt', sa.Float(), nullable=True),
    sa.Column('yellow_cards', sa.SmallInteger(), nullable=False),
    sa.Column('red_cards', sa.SmallInteger(), nullable=False),
    sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ),
    sa.PrimaryKeyConstraint('match_id', 'team_id')
    )


def downgrade() -> None:
    op.drop_table('team_match_stats')
    op.drop_table('predictions')
    op.drop_table('player_match_stats')
    op.drop_table('player_fixtures')
    op.drop_table('lineups')
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_index('ix_events_player_match')
        batch_op.drop_index('ix_events_match_type')

    op.drop_table('events')
    op.drop_table('team_features')
    op.drop_table('player_season_ratings')
    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_matches_season_id'))
        batch_op.drop_index(batch_op.f('ix_matches_date'))

    op.drop_table('matches')
    op.drop_table('teams')
    with op.batch_alter_table('seasons', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_seasons_start_year'))

    op.drop_table('seasons')
    with op.batch_alter_table('players', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_players_display_name'))

    op.drop_table('players')
    op.drop_table('model_versions')
    op.drop_table('competitions')
