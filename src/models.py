from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
import json


@dataclass
class PortfolioAllocation:
    asset_class: str
    value: float
    percentage: float


@dataclass
class TargetAllocation:
    asset_class: str
    percentage: float


@dataclass
class FixedIncomeAsset:
    indexer: str
    avg_rate: str
    value: float
    percentage: float


@dataclass
class Stock:
    ticker: str
    quantity: int
    value: float
    percentage: float


@dataclass
class FII:
    ticker: str
    quantity: int
    value: float
    percentage: float


@dataclass
class SectorDistribution:
    sector: str
    value: float
    percentage: float


@dataclass
class FIISegment:
    segment: str
    value: float
    percentage: float


@dataclass
class Proventos:
    acoes: float
    fiis: float
    cupons_rf: float
    total: float


@dataclass
class Movement:
    asset_class: str
    value: float


@dataclass
class MonthlyReport:
    date: str  # YYYY-MM-DD
    patrimony: float
    monthly_return_pct: float
    monthly_gains: float
    applications: float
    movements: float
    portfolio: list[PortfolioAllocation] = field(default_factory=list)
    target_allocation: list[TargetAllocation] = field(default_factory=list)
    fixed_income: list[FixedIncomeAsset] = field(default_factory=list)
    stocks: list[Stock] = field(default_factory=list)
    fiis: list[FII] = field(default_factory=list)
    sector_distribution: list[SectorDistribution] = field(default_factory=list)
    fii_segments: list[FIISegment] = field(default_factory=list)
    proventos: Proventos | None = None
    acquired_assets: list[Movement] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> MonthlyReport:
        return cls(
            date=d["date"],
            patrimony=d["patrimony"],
            monthly_return_pct=d["monthly_return_pct"],
            monthly_gains=d["monthly_gains"],
            applications=d["applications"],
            movements=d["movements"],
            portfolio=[PortfolioAllocation(**x) for x in d.get("portfolio", [])],
            target_allocation=[TargetAllocation(**x) for x in d.get("target_allocation", [])],
            fixed_income=[FixedIncomeAsset(**x) for x in d.get("fixed_income", [])],
            stocks=[Stock(**x) for x in d.get("stocks", [])],
            fiis=[FII(**x) for x in d.get("fiis", [])],
            sector_distribution=[SectorDistribution(**x) for x in d.get("sector_distribution", [])],
            fii_segments=[FIISegment(**x) for x in d.get("fii_segments", [])],
            proventos=Proventos(**d["proventos"]) if d.get("proventos") else None,
            acquired_assets=[Movement(**x) for x in d.get("acquired_assets", [])],
        )
