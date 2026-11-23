import { useEffect, useMemo, useState } from "react";

type Option = { id: number; name: string };
type MarketPair = { home: number; draw: number; away: number };
type ValueResult = { bookmaker_margin_percent: number; selections: Array<{ name: string; no_vig_probability: number; model_fair_odds: number; ev: number; edge: number; recommended_stake_fraction: number; decision: "VALUE" | "NO_BET" }> };
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
