from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Fixture, OddsQuote


OUTCOMES = ("home", "draw", "away")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _complete_snapshots(quotes: list[OddsQuote], *, allowed_types: set[str], kickoff: datetime, strict_before: bool):
    grouped = defaultdict(dict)
    for quote in quotes:
        if quote.quote_type not in allowed_types:
            continue
        captured = _utc(quote.captured_at)
        if (captured >= kickoff if strict_before else captured > kickoff):
            continue
        if quote.selection not in OUTCOMES:
            continue
        grouped[(quote.bookmaker_id, captured)][quote.selection] = float(quote.decimal_odds)
    return [
        {"bookmaker_id": bookmaker_id, "captured_at": captured, **prices}
        for (bookmaker_id, captured), prices in grouped.items()
        if all(key in prices for key in OUTCOMES)
    ]


def _latest_per_bookmaker(snapshots: list[dict]) -> list[dict]:
    latest = {}
    for snapshot in snapshots:
        bookmaker_id = snapshot["bookmaker_id"]
        if bookmaker_id not in latest or snapshot["captured_at"] > latest[bookmaker_id]["captured_at"]:
            latest[bookmaker_id] = snapshot
    return list(latest.values())


def calculate_financial_backtest(
    db: Session,
    predictions: list[dict],
    fixtures_by_id: dict[int, Fixture],
    *,
    min_ev: float = 0.02,
) -> dict:
    """Evaluate only complete, pre-kickoff 1X2 snapshots; closing quotes are CLV-only."""
    bets = []
    skipped_no_odds = 0
    clv_values = []
    total_staked = 0.0
    total_profit = 0.0
    equity = 100.0
    peak = equity
    max_drawdown = 0.0
    max_drawdown_ratio = 0.0

    for prediction in predictions:
        fixture = fixtures_by_id[prediction["fixture_id"]]
        kickoff = _utc(fixture.kickoff_at)
        quotes = list(db.scalars(
            select(OddsQuote).where(
                OddsQuote.fixture_id == fixture.id,
                OddsQuote.market == "1x2",
                OddsQuote.quote_type.in_(("opening", "current", "closing")),
            )
        ))
        decision_snapshots = _latest_per_bookmaker(_complete_snapshots(
            quotes, allowed_types={"opening", "current"}, kickoff=kickoff, strict_before=True
        ))
        probabilities = prediction["probabilities"]
        candidates = []
        for snapshot in decision_snapshots:
            implied = {outcome: 1.0 / snapshot[outcome] for outcome in OUTCOMES}
            overround = sum(implied.values())
            if overround <= 0:
                continue
            for outcome in OUTCOMES:
                model_probability = probabilities[outcome]
                no_vig = implied[outcome] / overround
                odds = snapshot[outcome]
                ev = model_probability * odds - 1.0
                edge = model_probability - no_vig
                if ev >= min_ev and edge > 0:
                    candidates.append({
                        "outcome": outcome, "odds": odds, "ev": ev, "edge": edge,
                        "bookmaker_id": snapshot["bookmaker_id"],
                        "captured_at": snapshot["captured_at"],
                    })
        if not candidates:
            skipped_no_odds += 1
            continue

        # One bet maximum per fixture: highest EV, deterministic tie-break.
        chosen = max(candidates, key=lambda item: (item["ev"], item["edge"], -item["bookmaker_id"]))
        closing_snapshots = _complete_snapshots(
            quotes, allowed_types={"closing"}, kickoff=kickoff, strict_before=False
        )
        matching_closes = [
            item for item in closing_snapshots
            if item["bookmaker_id"] == chosen["bookmaker_id"]
        ]
        clv = None
        if matching_closes:
            close = max(matching_closes, key=lambda item: item["captured_at"])
            close_implied = {outcome: 1.0 / close[outcome] for outcome in OUTCOMES}
            close_total = sum(close_implied.values())
            if close_total > 0:
                clv = close_implied[chosen["outcome"]] / close_total - 1.0 / chosen["odds"]
                clv_values.append(clv)

        won = prediction["actual"] == chosen["outcome"]
        profit = chosen["odds"] - 1.0 if won else -1.0
        total_staked += 1.0
        total_profit += profit
        equity += profit
        peak = max(peak, equity)
        drawdown = peak - equity
        max_drawdown = max(max_drawdown, drawdown)
        max_drawdown_ratio = max(max_drawdown_ratio, drawdown / peak if peak else 0.0)
        bets.append({
            "fixture_id": fixture.id,
            "kickoff_at": fixture.kickoff_at.isoformat(),
            "bookmaker_id": chosen["bookmaker_id"],
            "decision_odds_at": chosen["captured_at"].isoformat(),
            "selection": chosen["outcome"],
            "decimal_odds": chosen["odds"],
            "model_probability": probabilities[chosen["outcome"]],
            "ev": chosen["ev"],
            "edge": chosen["edge"],
            "result": "won" if won else "lost",
            "stake_units": 1.0,
            "profit_units": profit,
            "clv_probability_points": clv,
        })

    count = len(bets)
    roi = total_profit / total_staked if total_staked else None
    average_clv = sum(clv_values) / len(clv_values) if clv_values else None
    return {
        "strategy": "best_1x2_value_per_fixture_flat_1u",
        "minimum_ev": min_ev,
        "bets_placed": count,
        "fixtures_without_qualifying_odds": skipped_no_odds,
        "closing_odds_coverage": len(clv_values),
        "total_staked_units": total_staked,
        "profit_units": total_profit,
        "roi": roi,
        "yield": roi,
        "max_drawdown_units": max_drawdown,
        "max_drawdown": max_drawdown_ratio,
        "max_drawdown_percent_of_peak_bankroll": max_drawdown_ratio,
        "clv": average_clv,
        "clv_probability_points": average_clv,
        "clv_definition": "closing no-vig implied probability minus taken implied probability; positive is favorable",
        "bets": bets,
        "unavailable_reason": None if count else "Tidak ada snapshot odds 1X2 lengkap sebelum kickoff yang memenuhi EV minimum dan edge positif.",
        "warning": "Simulasi flat stake 1 unit per bet, bankroll awal 100 unit. Hasil historis bukan jaminan profit masa depan.",
    }
