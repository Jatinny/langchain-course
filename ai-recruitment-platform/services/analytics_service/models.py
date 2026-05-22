"""SQLAlchemy models for analytics service."""
from datetime import datetime
from typing import Any, Optional
from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from common.database import Base


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    metric_name: Mapped[str] = mapped_column(String(200), index=True)
    metric_value: Mapped[float] = mapped_column(Float)
    dimensions: Mapped[Optional[Any]] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class OutreachAnalytics(Base):
    __tablename__ = "outreach_analytics"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    date: Mapped[datetime] = mapped_column(DateTime, index=True)
    sent: Mapped[int] = mapped_column(Integer, default=0)
    delivered: Mapped[int] = mapped_column(Integer, default=0)
    opened: Mapped[int] = mapped_column(Integer, default=0)
    replied: Mapped[int] = mapped_column(Integer, default=0)
    converted: Mapped[int] = mapped_column(Integer, default=0)
    bounced: Mapped[int] = mapped_column(Integer, default=0)


class RevenueAnalytics(Base):
    __tablename__ = "revenue_analytics"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    month: Mapped[int] = mapped_column(Integer)
    year: Mapped[int] = mapped_column(Integer)
    gross_revenue: Mapped[float] = mapped_column(Float, default=0)
    commissions_earned: Mapped[float] = mapped_column(Float, default=0)
    pending_payments: Mapped[float] = mapped_column(Float, default=0)
    placements_count: Mapped[int] = mapped_column(Integer, default=0)
    top_employers: Mapped[Optional[Any]] = mapped_column(JSON)
    top_roles: Mapped[Optional[Any]] = mapped_column(JSON)


class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    data: Mapped[Optional[Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    acted_upon: Mapped[bool] = mapped_column(default=False)
