import { useEffect, useMemo, useState } from "react";

type Option = { id: number; name: string };
type MarketPair = { home: number; draw: number; away: number };
type ValueResult = { bookmaker_margin_percent: number; selections: Array<{ name: string; no_vig_probability: number; model_fair_odds: number; ev: number; edge: number; recommended_stake_fraction: number; decision: "VALUE" | "NO_BET" }> };
type BacktestResult = { fixtures_considered: number; predictions_evaluated: number; fixtures_skipped_insufficient_history: number; period: { from: string | null; to: string | null }; metrics: { accuracy_1x2: number | null; brier_score_1x2: number | null; log_loss_1x2: number | null; top_correct_score_hit_rate: number | null }; calibration: { method: string; predictions_evaluated: number; bins: number; expected_calibration_error: number | null; maximum_calibration_error: number | null; classwise_brier_score: Record<"home" | "draw" | "away", number | null>; reliability: Array<{ outcome: string; bin: string; count: number; mean_probability: number; observed_frequency: number; absolute_gap: number }>; top_outcome_confidence: Array<{ bin: string; count: number; mean_confidence: number; accuracy: number }>; warning: string }; financial_metrics: { strategy: string; minimum_ev: number; bets_placed: number; fixtures_without_qualifying_odds: number; closing_odds_coverage: number; total_staked_units: number; profit_units: number; roi: number | null; yield: number | null; max_drawdown_units: number; max_drawdown_percent_of_peak_bankroll: number; clv_probability_points: number | null; unavailable_reason: string | null; warning: string; strategies: { flat_stake: { total_staked_units: number; profit_units: number; roi: number | null; ending_bankroll_units: number; max_drawdown_percent_of_peak_bankroll: number; equity_curve: Array<{ fixture_id: number | null; bankroll_units: number }> }; quarter_kelly: { total_staked_units: number; profit_units: number; roi: number | null; ending_bankroll_units: number; max_drawdown_percent_of_peak_bankroll: number; fraction: number; max_bankroll_fraction_per_bet: number; equity_curve: Array<{ fixture_id: number | null; bankroll_units: number }> } }; breakdowns: { league: Array<{ key: string; bets: number; profit_units: number; roi: number | null }>; bookmaker: Array<{ key: string; bets: number; profit_units: number; roi: number | null }>; month: Array<{ key: string; bets: number; profit_units: number; roi: number | null }>; expected_value: Array<{ key: string; bets: number; profit_units: number; roi: number | null }> }; risk_diagnostics: { longest_losing_streak: number; longest_drawdown_bets: number; initial_bankroll_units: number }; calibration: { top_outcome_confidence: Array<{ band: string; count: number; mean_confidence: number; accuracy: number }> } } };
type Analysis = {
  model: string;
  status: string;
  parameters: { home_lambda: number; away_lambda: number; rho: number; max_goals: number; rho_note: string };
  data: { matches_used: number; home_team_matches: number; away_team_matches: number; training_cutoff: string | null; lambda_method: string };
  markets: {
    "1x2": MarketPair;
    double_chance: { "1x": number; x2: number; "12": number };
    totals_2_5: { over: number; under: number };
    btts: { yes: number; no: number };
    top_correct_scores: Array<{ score: string; probability: number }>;
  };
};

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const pct = (value: number) => `${(value * 100).toFixed(1)}%`;

export default function Analytics() {
  const [leagues, setLeagues] = useState<Option[]>([]);
  const [teams, setTeams] = useState<Option[]>([]);
  const [leagueId, setLeagueId] = useState("");
  const [homeId, setHomeId] = useState("");
  const [awayId, setAwayId] = useState("");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState("");
  const [failed, setFailed] = useState(false);
  const [odds, setOdds] = useState({ home: "", draw: "", away: "" });
  const [valueResult, setValueResult] = useState<ValueResult | null>(null);
  const [valueBusy, setValueBusy] = useState(false);
  const [valueNotice, setValueNotice] = useState("");
  const [backtest, setBacktest] = useState<BacktestResult | null>(null);
  const [backtestBusy, setBacktestBusy] = useState(false);
  const [backtestNotice, setBacktestNotice] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      fetch(`${API_BASE}/api/v1/catalog/leagues?limit=200`),
      fetch(`${API_BASE}/api/v1/catalog/teams?limit=200`),
    ]).then(async ([leagueResponse, teamResponse]) => {
      if (!leagueResponse.ok || !teamResponse.ok) throw new Error("Katalog liga/tim tidak dapat dimuat. Periksa koneksi API.");
      const [leagueData, teamData] = await Promise.all([leagueResponse.json(), teamResponse.json()]);
      if (active) { setLeagues(leagueData); setTeams(teamData); }
    }).catch((error: unknown) => {
      if (active) { setNotice(error instanceof Error ? error.message : "Gagal memuat katalog."); setFailed(true); }
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const selectedLeague = leagues.find((item) => String(item.id) === leagueId);
  const canAnalyze = Boolean(leagueId && homeId && awayId && homeId !== awayId);
  const homeName = useMemo(() => teams.find((item) => String(item.id) === homeId)?.name || "Kandang", [teams, homeId]);
  const awayName = useMemo(() => teams.find((item) => String(item.id) === awayId)?.name || "Tandang", [teams, awayId]);

  async function runBacktest() {
    if (!leagueId || backtestBusy) return;
    setBacktestBusy(true); setBacktest(null); setBacktestNotice("");
    try {
      const response = await fetch(`${API_BASE}/api/v1/analytics/backtest?league_id=${encodeURIComponent(leagueId)}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "Backtesting gagal dijalankan.");
      setBacktest(payload as BacktestResult);
    } catch (error) {
      setBacktestNotice(error instanceof Error ? error.message : "Tidak dapat menjalankan backtesting.");
    } finally { setBacktestBusy(false); }
  }

  async function evaluateValue() {
    if (!analysis || valueBusy) return;
    const prices = [Number(odds.home), Number(odds.draw), Number(odds.away)];
    if (prices.some((price) => !Number.isFinite(price) || price <= 1)) {
      setValueNotice("Isi odds desimal valid (> 1.00) untuk Home, Draw, dan Away.");
      setValueResult(null);
      return;
    }
    setValueBusy(true); setValueNotice(""); setValueResult(null);
    const probabilities = analysis.markets["1x2"];
    const body = {
      selections: [
        { name: homeName, model_probability: probabilities.home, decimal_odds: prices[0] },
        { name: "Draw", model_probability: probabilities.draw, decimal_odds: prices[1] },
        { name: awayName, model_probability: probabilities.away, decimal_odds: prices[2] },
      ],
      fractional_kelly: 0.25,
      min_ev: 0.02,
    };
    try {
      const response = await fetch(`${API_BASE}/api/v1/analytics/value`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "Evaluasi odds gagal.");
      setValueResult(payload as ValueResult);
    } catch (error) {
      setValueNotice(error instanceof Error ? error.message : "Tidak dapat mengevaluasi odds.");
    } finally { setValueBusy(false); }
  }

  async function runAnalysis() {
    if (!canAnalyze || busy) return;
    setBusy(true); setAnalysis(null); setNotice(""); setFailed(false);
    const query = new URLSearchParams({ league_id: leagueId, home_team_id: homeId, away_team_id: awayId });
    try {
      const response = await fetch(`${API_BASE}/api/v1/analytics/pre-match?${query.toString()}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "Analisis gagal dijalankan.");
      setAnalysis(payload as Analysis);
      setNotice("Analisis selesai. Estimasi masih provisional dan belum melalui backtesting.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Tidak dapat menjalankan analisis.");
      setFailed(true);
    } finally { setBusy(false); }
  }

  return (
    <section className="panel analytics-panel" id="analysis">
      <div className="panel-heading">
        <div><p className="eyebrow">03 / MODEL ENGINE</p><h2>Analisis pre-match</h2></div>
        <span className="limit">POISSON + DIXON–COLES</span>
      </div>
      <p className="manual-lead">Pilih liga dan dua tim. Lambda dihitung otomatis dari pertandingan selesai yang tersedia di database.</p>
      <div className="analysis-selectors">
        <label>Liga<select value={leagueId} onChange={(event) => { setLeagueId(event.target.value); setAnalysis(null); }} disabled={loading}><option value="">Pilih liga</option>{leagues.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Tim kandang<select value={homeId} onChange={(event) => { setHomeId(event.target.value); setAnalysis(null); }} disabled={loading}><option value="">Pilih tim kandang</option>{teams.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Tim tandang<select value={awayId} onChange={(event) => { setAwayId(event.target.value); setAnalysis(null); }} disabled={loading}><option value="">Pilih tim tandang</option>{teams.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      </div>
      {selectedLeague && <p className="analysis-context">Liga dipilih: <b>{selectedLeague.name}</b> · {teams.length} tim tersedia</p>}
      <div className="backtest-launch">
        <div><b>Backtesting historis liga</b><span>Uji prediksi secara kronologis menggunakan data sebelum kickoff.</span></div>
        <button className="secondary" type="button" onClick={() => void runBacktest()} disabled={!leagueId || backtestBusy}>{backtestBusy ? "Menguji data…" : "Jalankan backtest"}</button>
      </div>
      {backtestNotice && <div className="notice warning" role="status">{backtestNotice}</div>}
      {backtest && <div className="backtest-results">
        <div className="backtest-heading"><b>Hasil walk-forward · {selectedLeague?.name}</b><span>{backtest.predictions_evaluated} prediksi · {backtest.fixtures_skipped_insufficient_history} dilewati karena histori kurang</span></div>
        <div className="backtest-metrics">
          <div><span>Akurasi 1X2</span><strong>{backtest.metrics.accuracy_1x2 === null ? "—" : pct(backtest.metrics.accuracy_1x2)}</strong></div>
          <div><span>Brier score ↓</span><strong>{backtest.metrics.brier_score_1x2?.toFixed(4) ?? "—"}</strong></div>
          <div><span>Log loss ↓</span><strong>{backtest.metrics.log_loss_1x2?.toFixed(4) ?? "—"}</strong></div>
          <div><span>Top correct score</span><strong>{backtest.metrics.top_correct_score_hit_rate === null ? "—" : pct(backtest.metrics.top_correct_score_hit_rate)}</strong></div>
        </div>
        <h3>Model Calibration · 1X2</h3>
        <div className="backtest-metrics financial-metrics">
          <div><span>Expected calibration error ↓</span><strong>{backtest.calibration.expected_calibration_error === null ? "—" : pct(backtest.calibration.expected_calibration_error)}</strong></div>
          <div><span>Maximum calibration error ↓</span><strong>{backtest.calibration.maximum_calibration_error === null ? "—" : pct(backtest.calibration.maximum_calibration_error)}</strong></div>
          <div><span>Sampel evaluasi</span><strong>{backtest.calibration.predictions_evaluated}</strong></div>
        </div>
        <div className="financial-breakdown">{backtest.calibration.reliability.length ? backtest.calibration.reliability.map((item, index) => <div key={`${item.outcome}-${item.bin}-${index}`}><span>{item.outcome.toUpperCase()} · {item.bin} · n={item.count}</span><b>Prediksi {pct(item.mean_probability)} · Aktual {pct(item.observed_frequency)}</b></div>) : <small>Belum ada prediksi out-of-sample untuk kalibrasi.</small>}</div>
        <small>{backtest.calibration.warning}</small>
        <h3>Financial backtest · 1X2</h3>
        <div className="backtest-metrics financial-metrics">
          <div><span>Bet terpilih</span><strong>{backtest.financial_metrics.bets_placed}</strong></div>
          <div><span>ROI / Yield</span><strong>{backtest.financial_metrics.roi === null ? "—" : pct(backtest.financial_metrics.roi)}</strong></div>
          <div><span>Profit / Loss</span><strong>{backtest.financial_metrics.profit_units.toFixed(2)} u</strong></div>
          <div><span>Max drawdown</span><strong>{pct(backtest.financial_metrics.max_drawdown_percent_of_peak_bankroll)}</strong></div>
          <div><span>CLV rata-rata</span><strong>{backtest.financial_metrics.clv_probability_points === null ? "—" : `${(backtest.financial_metrics.clv_probability_points * 100).toFixed(2)} pp`}</strong></div>
          <div><span>Closing coverage</span><strong>{backtest.financial_metrics.closing_odds_coverage}/{backtest.financial_metrics.bets_placed}</strong></div>
        </div>
        <small>{backtest.financial_metrics.unavailable_reason || `Flat stake 1 unit · EV minimum ${(backtest.financial_metrics.minimum_ev * 100).toFixed(1)}% · ${backtest.financial_metrics.fixtures_without_qualifying_odds} fixture tanpa odds value.`}</small>
        <small>{backtest.financial_metrics.warning}</small>
        <h3>Perbandingan strategi · bankroll awal 100u</h3>
        <div className="backtest-metrics financial-metrics">
          <div><span>Flat stake · ROI</span><strong>{backtest.financial_metrics.strategies.flat_stake.roi === null ? "—" : pct(backtest.financial_metrics.strategies.flat_stake.roi)}</strong></div>
          <div><span>Flat stake · akhir</span><strong>{backtest.financial_metrics.strategies.flat_stake.ending_bankroll_units.toFixed(2)}u</strong></div>
          <div><span>¼ Kelly · ROI</span><strong>{backtest.financial_metrics.strategies.quarter_kelly.roi === null ? "—" : pct(backtest.financial_metrics.strategies.quarter_kelly.roi)}</strong></div>
          <div><span>¼ Kelly · akhir</span><strong>{backtest.financial_metrics.strategies.quarter_kelly.ending_bankroll_units.toFixed(2)}u</strong></div>
        </div>
        <h3>Equity curve · quarter-Kelly</h3>
        <div className="equity-list">{backtest.financial_metrics.strategies.quarter_kelly.equity_curve.map((point, index) => <div className="equity-point" key={index}><span>{point.fixture_id === null ? "Mulai" : `#${point.fixture_id}`}</span><div><i style={{ width: `${Math.max(0, Math.min(100, point.bankroll_units / Math.max(100, ...backtest.financial_metrics.strategies.quarter_kelly.equity_curve.map((item) => item.bankroll_units)) * 100))}%` }} /></div><b>{point.bankroll_units.toFixed(2)}u</b></div>)}</div>
        <h3>Performa per bookmaker</h3>
        <div className="financial-breakdown">{backtest.financial_metrics.breakdowns.bookmaker.length ? backtest.financial_metrics.breakdowns.bookmaker.map((item) => <div key={item.key}><span>Bookmaker #{item.key} · {item.bets} bet</span><b>{item.profit_units.toFixed(2)}u · {item.roi === null ? "—" : pct(item.roi)} ROI</b></div>) : <small>Belum ada taruhan yang memenuhi kriteria.</small>}</div>
        <h3>Performa bulanan</h3>
        <div className="financial-breakdown">{backtest.financial_metrics.breakdowns.month.length ? backtest.financial_metrics.breakdowns.month.map((item) => <div key={item.key}><span>{item.key} · {item.bets} bet</span><b>{item.profit_units.toFixed(2)}u · {item.roi === null ? "—" : pct(item.roi)} ROI</b></div>) : <small>Belum ada data bulanan.</small>}</div>
        <h3>Performa berdasarkan EV</h3>
        <div className="financial-breakdown">{backtest.financial_metrics.breakdowns.expected_value.length ? backtest.financial_metrics.breakdowns.expected_value.map((item) => <div key={item.key}><span>EV {item.key} · {item.bets} bet</span><b>{item.profit_units.toFixed(2)}u · {item.roi === null ? "—" : pct(item.roi)} ROI</b></div>) : <small>Belum ada data EV.</small>}</div>
        <h3>Kalibrasi confidence model</h3>
        <div className="financial-breakdown">{backtest.financial_metrics.calibration.top_outcome_confidence.length ? backtest.financial_metrics.calibration.top_outcome_confidence.map((item) => <div key={item.band}><span>{item.band} · {item.count} prediksi · confidence {pct(item.mean_confidence)}</span><b>Akurasi {pct(item.accuracy)}</b></div>) : <small>Belum ada sampel untuk kalibrasi.</small>}</div>
        <div className="analysis-audit"><b>Diagnostik risiko</b><span>Rentetan kekalahan terpanjang: {backtest.financial_metrics.risk_diagnostics.longest_losing_streak}</span><span>Rentang drawdown terpanjang: {backtest.financial_metrics.risk_diagnostics.longest_drawdown_bets} taruhan</span><span>Modal awal simulasi: {backtest.financial_metrics.risk_diagnostics.initial_bankroll_units.toFixed(2)} unit</span></div>
      </div>}
      <button className="primary" type="button" onClick={() => void runAnalysis()} disabled={!canAnalyze || busy || loading}>
        {busy ? "Menghitung probabilitas…" : "Analisis pertandingan"} <span>→</span>
      </button>
      {notice && <div className={`notice ${failed ? "warning" : "success"}`} role="status">{notice}</div>}
      {analysis && (
        <div className="analysis-results">
          <div className="lambda-grid">
            <div><span>λ {homeName}</span><strong>{analysis.parameters.home_lambda.toFixed(3)}</strong><small>Expected goals</small></div>
            <div><span>λ {awayName}</span><strong>{analysis.parameters.away_lambda.toFixed(3)}</strong><small>Expected goals</small></div>
            <div><span>Data historis</span><strong>{analysis.data.matches_used}</strong><small>Fixture selesai</small></div>
          </div>
          <h3>Probabilitas 1X2</h3>
          <div className="market-grid">
            <div><span>1 · {homeName}</span><strong>{pct(analysis.markets["1x2"].home)}</strong></div>
            <div><span>X · Seri</span><strong>{pct(analysis.markets["1x2"].draw)}</strong></div>
            <div><span>2 · {awayName}</span><strong>{pct(analysis.markets["1x2"].away)}</strong></div>
          </div>
          <h3>Pasar lainnya</h3>
          <div className="market-grid market-grid-two">
            <div><span>Double chance 1X</span><strong>{pct(analysis.markets.double_chance["1x"])}</strong></div>
            <div><span>Double chance X2</span><strong>{pct(analysis.markets.double_chance.x2)}</strong></div>
            <div><span>Over 2.5 gol</span><strong>{pct(analysis.markets.totals_2_5.over)}</strong></div>
            <div><span>Under 2.5 gol</span><strong>{pct(analysis.markets.totals_2_5.under)}</strong></div>
            <div><span>BTTS · Ya</span><strong>{pct(analysis.markets.btts.yes)}</strong></div>
            <div><span>BTTS · Tidak</span><strong>{pct(analysis.markets.btts.no)}</strong></div>
          </div>
          <h3>Top correct score</h3>
          <div className="score-grid">{analysis.markets.top_correct_scores.slice(0, 6).map((item) => <div key={item.score}><b>{item.score}</b><span>{pct(item.probability)}</span></div>)}</div>
          <div className="odds-value-panel">
            <h3>Odds &amp; Value Engine</h3>
            <p>Masukkan odds desimal bookmaker untuk pasar 1X2. Probabilitas model otomatis diambil dari hasil analisis di atas.</p>
            <div className="odds-input-grid">
              <label>Odds {homeName}<input inputMode="decimal" type="number" min="1.01" step="0.01" placeholder="2.10" value={odds.home} onChange={(event) => setOdds({ ...odds, home: event.target.value })} /></label>
              <label>Odds Draw<input inputMode="decimal" type="number" min="1.01" step="0.01" placeholder="3.30" value={odds.draw} onChange={(event) => setOdds({ ...odds, draw: event.target.value })} /></label>
              <label>Odds {awayName}<input inputMode="decimal" type="number" min="1.01" step="0.01" placeholder="3.50" value={odds.away} onChange={(event) => setOdds({ ...odds, away: event.target.value })} /></label>
            </div>
            <button className="primary" type="button" onClick={() => void evaluateValue()} disabled={valueBusy}>{valueBusy ? "Menghitung EV…" : "Hitung value & Kelly"} <span>→</span></button>
            {valueNotice && <div className="notice warning" role="status">{valueNotice}</div>}
            {valueResult && <>
              <div className="value-summary"><span>Bookmaker margin</span><strong>{valueResult.bookmaker_margin_percent.toFixed(2)}%</strong><small>Margin dihapus dengan metode proporsional.</small></div>
              <div className="value-results">{valueResult.selections.map((item) => <div className="value-row" key={item.name}>
                <div><b>{item.name}</b><span>Fair odds model {item.model_fair_odds.toFixed(2)} · No-vig {pct(item.no_vig_probability)}</span></div>
                <div className="value-metrics"><strong className={item.decision === "VALUE" ? "value-positive" : ""}>{item.decision === "VALUE" ? "VALUE" : "NO BET"}</strong><span>EV {pct(item.ev)} · Edge {pct(item.edge)}</span><span>¼ Kelly {pct(item.recommended_stake_fraction)}</span></div>
              </div>)}</div>
              <p className="value-disclaimer">VALUE hanya jika EV ≥ 2% dan edge positif. Kelly adalah fraksi estimasi bankroll, bukan jaminan hasil.</p>
            </>}
          </div>
          <div className="analysis-audit">
            <b>Status model: provisional / belum backtested</b>
            <span>Home sample: {analysis.data.home_team_matches} pertandingan · Away sample: {analysis.data.away_team_matches} pertandingan</span>
            <span>Metode: {analysis.data.lambda_method}</span>
            <span>ρ = {analysis.parameters.rho.toFixed(2)} (default netral; fitting liga belum tersedia)</span>
          </div>
        </div>
      )}
    </section>
  );
}
