from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Sport(Base):
    __tablename__ = "sports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)

    competitions = relationship("Competition", back_populates="sport")
    teams = relationship("Team", back_populates="sport")


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sports.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(50))
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    season: Mapped[str] = mapped_column(String(20), nullable=False)
    region: Mapped[str | None] = mapped_column(String(100))
    start_date: Mapped[str | None] = mapped_column(String(20))
    end_date: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    sport = relationship("Sport", back_populates="competitions")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sports.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(50))
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    confederation: Mapped[str | None] = mapped_column(String(50))
    fifa_ranking: Mapped[int | None] = mapped_column(Integer)
    elo_rating: Mapped[float | None] = mapped_column(Float)
    founded_year: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[str | None] = mapped_column(String(30), server_default=func.datetime("now"))

    sport = relationship("Sport", back_populates="teams")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), nullable=False)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    match_date: Mapped[str] = mapped_column(String(30), nullable=False)
    venue: Mapped[str | None] = mapped_column(String(150))
    city: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    stage: Mapped[str | None] = mapped_column(String(100))
    group_name: Mapped[str | None] = mapped_column(String(50))
    score_home_ht: Mapped[int | None] = mapped_column(Integer)
    score_away_ht: Mapped[int | None] = mapped_column(Integer)
    score_home_ft: Mapped[int | None] = mapped_column(Integer)
    score_away_ft: Mapped[int | None] = mapped_column(Integer)
    score_home_et: Mapped[int | None] = mapped_column(Integer)
    score_away_et: Mapped[int | None] = mapped_column(Integer)
    score_home_pen: Mapped[int | None] = mapped_column(Integer)
    score_away_pen: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="scheduled", nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    scraped_at: Mapped[str | None] = mapped_column(String(30), server_default=func.datetime("now"))

    competition = relationship("Competition")
    home_team = relationship("Team", foreign_keys=[home_team_id])
    away_team = relationship("Team", foreign_keys=[away_team_id])

    __table_args__ = (
        UniqueConstraint("competition_id", "home_team_id", "away_team_id", "match_date", name="uq_match_identity"),
    )


class MatchStat(Base):
    __tablename__ = "match_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    is_home: Mapped[bool] = mapped_column(Boolean, nullable=False)
    xg: Mapped[float | None] = mapped_column(Float)
    xga: Mapped[float | None] = mapped_column(Float)
    shots_total: Mapped[int | None] = mapped_column(Integer)
    shots_on_target: Mapped[int | None] = mapped_column(Integer)
    possession_pct: Mapped[float | None] = mapped_column(Float)
    corners: Mapped[int | None] = mapped_column(Integer)
    yellow_cards: Mapped[int | None] = mapped_column(Integer)
    red_cards: Mapped[int | None] = mapped_column(Integer)
    source_url: Mapped[str | None] = mapped_column(Text)
    scraped_at: Mapped[str | None] = mapped_column(String(30), server_default=func.datetime("now"))

    __table_args__ = (
        UniqueConstraint("match_id", "team_id", name="uq_match_team_stats"),
    )


class Bookmaker(Base):
    __tablename__ = "bookmakers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    country: Mapped[str | None] = mapped_column(String(100))
    url: Mapped[str | None] = mapped_column(Text)
    scraping_method: Mapped[str] = mapped_column(String(50), nullable=False)
    api_key_env: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class Odd(Base):
    __tablename__ = "odds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    bookmaker_id: Mapped[int] = mapped_column(ForeignKey("bookmakers.id"), nullable=False)
    market_level: Mapped[int] = mapped_column(Integer, nullable=False)
    market_type: Mapped[str] = mapped_column(String(50), nullable=False)
    market_category: Mapped[str] = mapped_column(String(50), nullable=False)
    selection: Mapped[str] = mapped_column(String(50), nullable=False)
    odd_value: Mapped[float] = mapped_column(Float, nullable=False)
    implied_prob: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp_scraped: Mapped[str | None] = mapped_column(String(30), server_default=func.datetime("now"))
    is_opening: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_live: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    model_version: Mapped[str] = mapped_column(String(20), default="1.0", nullable=False)
    model_type: Mapped[str] = mapped_column(String(50), nullable=False)
    market_level: Mapped[int] = mapped_column(Integer, nullable=False)
    market_type: Mapped[str] = mapped_column(String(50), nullable=False)
    market_category: Mapped[str] = mapped_column(String(50), nullable=False)
    selection: Mapped[str] = mapped_column(String(50), nullable=False)
    estimated_prob: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_odd: Mapped[float] = mapped_column(Float, nullable=False)
    bookmaker_prob: Mapped[float | None] = mapped_column(Float)
    bookmaker_odd: Mapped[float | None] = mapped_column(Float)
    bookmaker_id: Mapped[int | None] = mapped_column(ForeignKey("bookmakers.id"))
    edge_pct: Mapped[float | None] = mapped_column(Float)
    expected_value: Mapped[float | None] = mapped_column(Float)
    kelly_fraction_raw: Mapped[float | None] = mapped_column(Float)
    kelly_fraction: Mapped[float | None] = mapped_column(Float)
    kelly_fraction_capped: Mapped[float | None] = mapped_column(Float)
    profile_tag: Mapped[str] = mapped_column(String(50), nullable=False)
    recommendation_score: Mapped[int | None] = mapped_column(Integer)
    confidence_level: Mapped[str | None] = mapped_column(String(20))
    reasoning: Mapped[str | None] = mapped_column(Text)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    actual_result: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[str | None] = mapped_column(String(30), server_default=func.datetime("now"))

    __table_args__ = (
        UniqueConstraint("match_id", "model_version", "market_type", "selection", name="uq_prediction_identity"),
    )


class ScrapingLog(Base):
    __tablename__ = "scraping_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    timestamp_start: Mapped[str | None] = mapped_column(String(30), server_default=func.datetime("now"))
    timestamp_end: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    rows_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[float | None] = mapped_column(Float)


class ApiCache(Base):
    __tablename__ = "api_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    cache_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    cached_at: Mapped[str | None] = mapped_column(String(30), server_default=func.datetime("now"))
    expires_at: Mapped[str] = mapped_column(String(30), nullable=False)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)