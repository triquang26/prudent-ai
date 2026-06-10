"""SQLAlchemy 2.0 ORM models for the APT substrate schema."""
from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass

class Component(Base):
    __tablename__ = "component"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)

class Config(Base):
    __tablename__ = "config"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tau: Mapped[str] = mapped_column(String, nullable=False)

class ConfigComponent(Base):
    __tablename__ = "config_component"
    config_id: Mapped[str] = mapped_column(String, ForeignKey("config.id"), primary_key=True)
    component_id: Mapped[str] = mapped_column(String, ForeignKey("component.id"), primary_key=True)

class Source(Base):
    __tablename__ = "source"
    evidence_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    citation: Mapped[str | None] = mapped_column(String)
    snapshot_version: Mapped[str | None] = mapped_column(String)

class Observation(Base):
    __tablename__ = "observation"
    __table_args__ = (CheckConstraint("confidence IN ('H','M','L')", name="ck_confidence"),)
    obs_id: Mapped[str] = mapped_column(String, primary_key=True)
    config_id: Mapped[str] = mapped_column(String, ForeignKey("config.id"), nullable=False)
    axis: Mapped[str] = mapped_column(String, nullable=False)
    value_num: Mapped[float | None] = mapped_column(Float)
    value_cat: Mapped[str | None] = mapped_column(String)
    confidence: Mapped[str] = mapped_column(String, nullable=False)
    evidence_id: Mapped[str] = mapped_column(
        String, ForeignKey("source.evidence_id"), nullable=False
    )
    hardware_tier: Mapped[str | None] = mapped_column(String)
    dataset: Mapped[str | None] = mapped_column(String)
    split: Mapped[str | None] = mapped_column(String)
    decoding_cfg: Mapped[str | None] = mapped_column(String)
    obs_date: Mapped[str | None] = mapped_column(String)
