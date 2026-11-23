import { useEffect, useMemo, useState } from "react";

type Option = { id: number; name: string };
type MarketPair = { home: number; draw: number; away: number };
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
