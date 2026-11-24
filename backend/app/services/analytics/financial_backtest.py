from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Fixture, OddsQuote


OUTCOMES = ("home", "draw", "away")
INITIAL_BANKROLL = 100.0
FRACTIONAL_KELLY = 0.25
MAX_KELLY_STAKE_FRACTION = 0.05


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


def _drawdown(equity_curve: list[dict], initial: float) -> tuple[float, float]:
    peak = initial
    max_units = 0.0
    max_ratio = 0.0
    for point in equity_curve:
        equity = point["bankroll_units"]
        peak = max(peak, equity)
        decline = peak - equity
        max_units = max(max_units, decline)
        max_ratio = max(max_ratio, decline / peak if peak else 0.0)
    return max_units, max_ratio


def _summary(stakes: list[float], profits: list[float], initial: float) -> dict:
    staked = sum(stakes)
    profit = sum(profits)
    curve = []
    bankroll = initial
    for stake, pnl in zip(stakes, profits):
        bankroll += pnl
        curve.append({"bankroll_units": bankroll})
    drawdown_units, drawdown_ratio = _drawdown(curve, initial)
    return {
        "bets_placed": len(stakes),
        "total_staked_units": staked,
        "profit_units": profit,
        "roi": profit / staked if staked else None,
        "yield": profit / staked if staked else None,
        "ending_bankroll_units": initial + profit,
        "max_drawdown_units": drawdown_units,
        "max_drawdown_percent_of_peak_bankroll": drawdown_ratio,
    }


def calculate_financial_backtest(
    db: Session,
    predictions: list[dict],
    fixtures_by_id: dict[int, Fixture],
    *,
    min_ev: float = 0.02,
    league_id: int | None = None,
) -> dict:
    """Evaluate pre-kickoff 1X2 odds with flat-stake and capped quarter-Kelly simulations."""
    bets = []
    skipped_no_odds = 0
    clv_values = []
    flat_stakes, flat_profits = [], []
    kelly_stakes, kelly_profits = [], []
    flat_equity = INITIAL_BANKROLL
    kelly_bankroll = INITIAL_BANKROLL
    flat_curve = [{"fixture_id": None, "bankroll_units": INITIAL_BANKROLL}]
    kelly_curve = [{"fixture_id": None, "bankroll_units": INITIAL_BANKROLL}]
    bookmaker_groups = defaultdict(lambda: {"bets": 0, "stake": 0.0, "profit": 0.0})
    period_groups = defaultdict(lambda: {"bets": 0, "stake": 0.0, "profit": 0.0})
    ev_groups = defaultdict(lambda: {"bets": 0, "stake": 0.0, "profit": 0.0})
    confidence_groups = defaultdict(lambda: {"count": 0, "confidence": 0.0, "correct": 0})
    current_losing_streak = 0
    longest_losing_streak = 0
    current_drawdown_bets = 0
    longest_drawdown_bets = 0
    flat_peak = INITIAL_BANKROLL

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

        chosen = max(candidates, key=lambda item: (item["ev"], item["edge"], -item["bookmaker_id"]))
        closing_snapshots = _complete_snapshots(
            quotes, allowed_types={"closing"}, kickoff=kickoff, strict_before=False
        )
        matching_closes = [item for item in closing_snapshots if item["bookmaker_id"] == chosen["bookmaker_id"]]
        clv = None
        if matching_closes:
            close = max(matching_closes, key=lambda item: item["captured_at"])
            close_implied = {outcome: 1.0 / close[outcome] for outcome in OUTCOMES}
            close_total = sum(close_implied.values())
            if close_total > 0:
                clv = close_implied[chosen["outcome"]] / close_total - 1.0 / chosen["odds"]
                clv_values.append(clv)

        won = prediction["actual"] == chosen["outcome"]
        flat_profit = chosen["odds"] - 1.0 if won else -1.0
        probability = probabilities[chosen["outcome"]]
        full_kelly = max(0.0, (probability * chosen["odds"] - 1.0) / (chosen["odds"] - 1.0))
        kelly_fraction = min(FRACTIONAL_KELLY * full_kelly, MAX_KELLY_STAKE_FRACTION)
        kelly_stake = min(kelly_bankroll * kelly_fraction, kelly_bankroll)
        kelly_profit = kelly_stake * (chosen["odds"] - 1.0) if won else -kelly_stake

        flat_stakes.append(1.0)
        flat_profits.append(flat_profit)
        flat_equity += flat_profit
        flat_curve.append({"fixture_id": fixture.id, "bankroll_units": flat_equity})
        if kelly_stake > 0 and kelly_bankroll > 0:
            kelly_stakes.append(kelly_stake)
            kelly_profits.append(kelly_profit)
            kelly_bankroll += kelly_profit
        kelly_curve.append({"fixture_id": fixture.id, "bankroll_units": kelly_bankroll})

        bookmaker_key = str(chosen["bookmaker_id"])
        group = bookmaker_groups[bookmaker_key]
        group["bets"] += 1
        group["stake"] += 1.0
        group["profit"] += flat_profit
        month_key = kickoff.strftime("%Y-%m")
        period = period_groups[month_key]
        period["bets"] += 1
        period["stake"] += 1.0
        period["profit"] += flat_profit
        bets.append({
            "fixture_id": fixture.id,
            "kickoff_at": fixture.kickoff_at.isoformat(),
            "bookmaker_id": chosen["bookmaker_id"],
            "decision_odds_at": chosen["captured_at"].isoformat(),
            "selection": chosen["outcome"],
            "decimal_odds": chosen["odds"],
            "model_probability": probability,
            "ev": chosen["ev"],
            "edge": chosen["edge"],
            "result": "won" if won else "lost",
            "stake_units": 1.0,
            "profit_units": flat_profit,
            "full_kelly_fraction": full_kelly,
            "quarter_kelly_stake_units": kelly_stake,
            "quarter_kelly_profit_units": kelly_profit,
            "clv_probability_points": clv,
        })

    flat_summary = _summary(flat_stakes, flat_profits, INITIAL_BANKROLL)
    kelly_summary = _summary(kelly_stakes, kelly_profits, INITIAL_BANKROLL)

    def grouped_rows(groups):
        rows = []
        for key, values in sorted(groups.items()):
            stake, profit = values["stake"], values["profit"]
            rows.append({
                "key": key, "bets": values["bets"], "stake_units": stake,
                "profit_units": profit, "roi": profit / stake if stake else None,
            })
        return rows

    count = len(bets)
    average_clv = sum(clv_values) / len(clv_values) if clv_values else None
    return {
        "strategy": "best_1x2_value_per_fixture",
        "minimum_ev": min_ev,
        "bets_placed": count,
        "fixtures_without_qualifying_odds": skipped_no_odds,
        "closing_odds_coverage": len(clv_values),
        "total_staked_units": flat_summary["total_staked_units"],
        "profit_units": flat_summary["profit_units"],
        "roi": flat_summary["roi"],
        "yield": flat_summary["yield"],
        "max_drawdown_units": flat_summary["max_drawdown_units"],
        "max_drawdown": flat_summary["max_drawdown_percent_of_peak_bankroll"],
        "max_drawdown_percent_of_peak_bankroll": flat_summary["max_drawdown_percent_of_peak_bankroll"],
        "clv": average_clv,
        "clv_probability_points": average_clv,
        "clv_definition": "closing no-vig implied probability minus taken implied probability; positive is favorable",
        "bets": bets,
        "strategies": {
            "flat_stake": {**flat_summary, "stake_per_bet_units": 1.0, "equity_curve": flat_curve},
            "quarter_kelly": {
                **kelly_summary, "fraction": FRACTIONAL_KELLY,
                "max_bankroll_fraction_per_bet": MAX_KELLY_STAKE_FRACTION,
                "equity_curve": kelly_curve,
            },
        },
        "breakdowns": {
            "league": [{"key": str(league_id) if league_id is not None else "current", "bets": count,
                        "stake_units": flat_summary["total_staked_units"], "profit_units": flat_summary["profit_units"],
                        "roi": flat_summary["roi"]}],
            "bookmaker": grouped_rows(bookmaker_groups),
            "month": grouped_rows(period_groups),
        },
        "unavailable_reason": None if count else "Tidak ada snapshot odds 1X2 lengkap sebelum kickoff yang memenuhi EV minimum dan edge positif.",
        "warning": "Simulasi flat stake 1 unit dibandingkan quarter-Kelly dengan batas 5% bankroll per bet. Bankroll awal 100 unit. Hasil historis bukan jaminan profit masa depan.",
    }
