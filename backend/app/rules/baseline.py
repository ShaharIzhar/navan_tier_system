"""Navan's official baseline tier rules, implemented deterministically.

The LLM never touches these thresholds.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from .. import config


@dataclass
class BaselineResult:
    tier: Optional[int]
    provisional: bool = False
    basis: str = ""  # human-readable explanation of which rule applied
    unresolved: list[str] = field(default_factory=list)
    data_quality_issues: list[str] = field(default_factory=list)
    inputs: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _fmt_usd(v: float) -> str:
    return f"${v:,.0f}"


def calculate_baseline(gbv: Optional[float], employees: Optional[int]) -> BaselineResult:
    inputs = {"gbv_usd": gbv, "employees": employees}

    if gbv is None:
        return BaselineResult(
            tier=None,
            basis="Annual GBV is missing or invalid, so the GBV rules cannot be applied.",
            unresolved=["annual_gbv"],
            data_quality_issues=["Missing or invalid annual GBV (not treated as $0)."],
            inputs=inputs,
        )
    if gbv < 0:
        return BaselineResult(
            tier=None,
            basis="Annual GBV is negative, which is not a valid value.",
            unresolved=["annual_gbv"],
            data_quality_issues=[f"Negative annual GBV ({gbv:,.0f}) is invalid."],
            inputs=inputs,
        )
    issues: list[str] = []
    if employees is not None and employees < 0:
        issues.append(f"Negative employee estimate ({employees}) ignored.")
        employees = None

    if gbv >= config.TIER1_GBV_MIN:
        return BaselineResult(
            tier=1,
            basis=f"Reported GBV {_fmt_usd(gbv)} is at or above {_fmt_usd(config.TIER1_GBV_MIN)}.",
            data_quality_issues=issues,
            inputs=inputs,
        )
    if gbv >= config.TIER2_GBV_MIN:
        return BaselineResult(
            tier=2,
            basis=(
                f"Reported GBV {_fmt_usd(gbv)} is between {_fmt_usd(config.TIER2_GBV_MIN)} "
                f"and {_fmt_usd(config.TIER1_GBV_MIN)}."
            ),
            data_quality_issues=issues,
            inputs=inputs,
        )
    if employees is not None and employees >= config.TIER2_EMPLOYEES_MIN:
        return BaselineResult(
            tier=2,
            basis=(
                f"Reported GBV {_fmt_usd(gbv)} is below {_fmt_usd(config.TIER2_GBV_MIN)}, but "
                f"{employees:,} employees meets the {config.TIER2_EMPLOYEES_MIN}+ employee rule."
            ),
            data_quality_issues=issues,
            inputs=inputs,
        )
    if employees is None:
        return BaselineResult(
            tier=3,
            provisional=True,
            basis=(
                f"Reported GBV {_fmt_usd(gbv)} is below {_fmt_usd(config.TIER2_GBV_MIN)} and no "
                "employee estimate is available, so Tier 2 eligibility by headcount cannot be ruled out."
            ),
            unresolved=["employee_count"],
            data_quality_issues=issues,
            inputs=inputs,
        )
    return BaselineResult(
        tier=3,
        basis=(
            f"Reported GBV {_fmt_usd(gbv)} is below {_fmt_usd(config.TIER2_GBV_MIN)} and "
            f"{employees:,} employees is below {config.TIER2_EMPLOYEES_MIN}."
        ),
        data_quality_issues=issues,
        inputs=inputs,
    )
