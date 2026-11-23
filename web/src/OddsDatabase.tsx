import { FormEvent, useEffect, useState } from "react";

type FixtureOption = { id: number; season_id: number; home_team_id: number; away_team_id: number; kickoff_at: string; status: string };
type Bookmaker = { id: number; name: string; provider_key: string | null; enabled: boolean };
type ImportResult = { rows_received: number; imported: number; duplicates_skipped: number; invalid_rows: number; message: string };
type Quote = { id: number; bookmaker_id: number; bookmaker_name: string; market: string; selection: string; line: string | null; decimal_odds: string; captured_at: string; quote_type: string; source: string };

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const marketOptions = ["1x2", "totals", "asian_handicap", "btts", "correct_score", "team_total", "other"];
const quoteTypes = ["opening", "current", "closing", "live"];

export default function OddsDatabase() {
  const [fixtures, setFixtures] = useState<FixtureOption[]>([]);
  const [bookmakers, setBookmakers] = useState<Bookmaker[]>([]);
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [fixtureId, setFixtureId] = useState("");
  const [bookmakerId, setBookmakerId] = useState("");
  const [market, setMarket] = useState("1x2");
  const [selection, setSelection] = useState("home");
  const [line, setLine] = useState("");
  const [decimalOdds, setDecimalOdds] = useState("");
  const [capturedAt, setCapturedAt] = useState("");
  const [quoteType, setQuoteType] = useState("opening");
  const [newBookmaker, setNewBookmaker] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importFormat, setImportFormat] = useState("csv");
  const [importResult, setImportResult] = useState<ImportResult | null>(null);

  async function loadBase() {
    setLoading(true);
    try {
      const [fixtureResponse, bookmakerResponse] = await Promise.all([
        fetch(`${API_BASE}/api/v1/catalog/fixtures?limit=200`),
        fetch(`${API_BASE}/api/v1/odds/bookmakers`),
      ]);
      if (!fixtureResponse.ok || !bookmakerResponse.ok) throw new Error("Katalog pertandingan atau bookmaker gagal dimuat.");
      const [fixtureData, bookmakerData] = await Promise.all([fixtureResponse.json(), bookmakerResponse.json()]);
      setFixtures(fixtureData);
      setBookmakers(bookmakerData);
      if (!fixtureId && fixtureData.length) setFixtureId(String(fixtureData[0].id));
      if (!bookmakerId && bookmakerData.length) setBookmakerId(String(bookmakerData[0].id));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Gagal memuat database odds.");
    } finally { setLoading(false); }
  }

  async function loadQuotes(id = fixtureId) {
    if (!id) { setQuotes([]); return; }
    try {
      const response = await fetch(`${API_BASE}/api/v1/odds/fixtures/${id}/quotes?limit=100`);
      if (!response.ok) throw new Error("Riwayat odds gagal dimuat.");
      setQuotes(await response.json());
    } catch (error) { setNotice(error instanceof Error ? error.message : "Riwayat odds gagal dimuat."); }
  }

  useEffect(() => { void loadBase(); }, []);
  useEffect(() => { void loadQuotes(); }, [fixtureId]);

  async function addBookmaker(event: FormEvent) {
    event.preventDefault();
    if (!newBookmaker.trim() || busy) return;
    setBusy(true); setNotice("");
    try {
      const response = await fetch(`${API_BASE}/api/v1/odds/bookmakers`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newBookmaker.trim() }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Bookmaker gagal disimpan.");
      setNewBookmaker("");
      await loadBase();
      setBookmakerId(String(payload.id));
      setNotice("Bookmaker berhasil ditambahkan.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Gagal menambahkan bookmaker."); }
    finally { setBusy(false); }
  }

  async function saveQuote(event: FormEvent) {
    event.preventDefault();
    if (!fixtureId || !bookmakerId || !capturedAt || busy) return;
    setBusy(true); setNotice("");
    try {
      const response = await fetch(`${API_BASE}/api/v1/odds/quotes`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fixture_id: Number(fixtureId), bookmaker_id: Number(bookmakerId), market, selection,
          line: line.trim() ? line : null, decimal_odds: decimalOdds,
          captured_at: new Date(capturedAt).toISOString(), quote_type: quoteType, source: "manual",
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Odds gagal disimpan.");
      setDecimalOdds("");
      await loadQuotes();
      setNotice("Snapshot odds berhasil disimpan.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Gagal menyimpan odds."); }
    finally { setBusy(false); }
  }

  async function importOdds(event: FormEvent) {
    event.preventDefault();
    if (!importFile || busy) return;
    setBusy(true); setNotice(""); setImportResult(null);
    try {
      const response = await fetch(`${API_BASE}/api/v1/odds/import/${importFormat}`, { method: "POST", body: (() => { const data = new FormData(); data.append("file", importFile); return data; })() });
      const payload = await response.json();
      if (!response.ok) {
        const details = payload.detail;
        const rows = details?.invalid_rows?.slice(0, 5).map((item: { row: number; errors: string[] }) => `Baris ${item.row}: ${item.errors.join(", ")}`).join(" | ");
        throw new Error(rows || details?.message || details || "Impor odds gagal.");
      }
      setImportResult(payload); setImportFile(null);
      const picker = document.getElementById("odds-import-file") as HTMLInputElement | null; if (picker) picker.value = "";
      await loadQuotes();
      setNotice("Impor odds selesai.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Impor odds gagal."); }
    finally { setBusy(false); }
  }

  const needsLine = ["totals", "asian_handicap", "team_total"].includes(market);
  return (
    <section className="panel odds-database-panel" id="odds-database">
      <div className="panel-heading">
        <div><p className="eyebrow">04 / HISTORICAL ODDS</p><h2>Database odds historis</h2></div>
        <span className="limit">SNAPSHOT LOG</span>
      </div>
      <p className="manual-lead">Catat odds opening, current, closing, atau live dari bookmaker. Waktu pencatatan wajib akurat agar evaluasi tidak memakai data masa depan.</p>
      <div className="odds-db-grid">
        <div className="manual-card">
          <h3>Bookmaker</h3>
          <form onSubmit={addBookmaker}>
            <label>Tambah bookmaker<input value={newBookmaker} onChange={(event) => setNewBookmaker(event.target.value)} placeholder="Contoh: Pinnacle" maxLength={120} /></label>
            <button className="browse" type="submit" disabled={busy || !newBookmaker.trim()}>{busy ? "Menyimpan…" : "Tambah bookmaker"}</button>
          </form>
          <label className="odds-db-select">Bookmaker aktif<select value={bookmakerId} onChange={(event) => setBookmakerId(event.target.value)}><option value="">Pilih bookmaker</option>{bookmakers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        </div>
        <div className="manual-card odds-db-form-card">
          <h3>Rekam snapshot odds</h3>
          <form onSubmit={saveQuote}>
            <label>Pertandingan<select value={fixtureId} onChange={(event) => setFixtureId(event.target.value)}><option value="">Pilih fixture</option>{fixtures.map((item) => <option key={item.id} value={item.id}>Fixture #{item.id} · {new Date(item.kickoff_at).toLocaleString("id-ID")}</option>)}</select></label>
            <div className="form-pair">
              <label>Market<select value={market} onChange={(event) => { setMarket(event.target.value); setLine(""); }}>{marketOptions.map((item) => <option key={item} value={item}>{item.toUpperCase()}</option>)}</select></label>
              <label>Tipe snapshot<select value={quoteType} onChange={(event) => setQuoteType(event.target.value)}>{quoteTypes.map((item) => <option key={item} value={item}>{item.toUpperCase()}</option>)}</select></label>
            </div>
            <div className="form-pair">
              <label>Selection<input value={selection} onChange={(event) => setSelection(event.target.value)} placeholder="home / draw / away / over" required maxLength={80} /></label>
              {needsLine && <label>Line<input value={line} onChange={(event) => setLine(event.target.value)} placeholder="2.5 / -0.5" required /></label>}
            </div>
            <div className="form-pair">
              <label>Odds desimal<input type="number" min="1.0001" max="1000" step="0.0001" value={decimalOdds} onChange={(event) => setDecimalOdds(event.target.value)} placeholder="2.1500" required /></label>
              <label>Waktu dicatat<input type="datetime-local" value={capturedAt} onChange={(event) => setCapturedAt(event.target.value)} required /></label>
            </div>
            <button className="primary" type="submit" disabled={busy || !fixtureId || !bookmakerId}>{busy ? "Menyimpan…" : "Simpan snapshot odds"} <span>→</span></button>
          </form>
        </div>
      </div>
      <div className="manual-card odds-import-card">
        <h3>Impor odds massal · CSV / Excel</h3>
        <p className="manual-footnote">Gunakan fixture_id dan nama bookmaker yang sudah terdaftar. Timestamp wajib menyertakan zona waktu, misalnya +07:00.</p>
        <div className="download-links">
          <a href={`${API_BASE}/api/v1/odds/templates/csv`}>↓ Template CSV</a>
          <a href={`${API_BASE}/api/v1/odds/templates/excel`}>↓ Template Excel</a>
        </div>
        <form className="odds-import-form" onSubmit={importOdds}>
          <label>Format<select value={importFormat} onChange={(event) => setImportFormat(event.target.value)}><option value="csv">CSV</option><option value="excel">Excel (.xlsx)</option></select></label>
          <label>File odds<input id="odds-import-file" type="file" accept={importFormat === "csv" ? ".csv,text/csv" : ".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"} onChange={(event) => setImportFile(event.target.files?.[0] || null)} /></label>
          <button className="browse" type="submit" disabled={busy || !importFile}>{busy ? "Mengimpor…" : "Impor file odds"}</button>
        </form>
        {importResult && <div className="result-grid odds-import-result"><div><span>Baris diterima</span><strong>{importResult.rows_received}</strong></div><div><span>Berhasil masuk</span><strong>{importResult.imported}</strong></div><div><span>Duplikat dilewati</span><strong>{importResult.duplicates_skipped}</strong></div></div>}
      </div>
      {notice && <div className="notice" role="status">{notice}</div>}
      <div className="odds-db-history">
        <div className="odds-db-history-heading"><b>Riwayat fixture terpilih</b><button className="browse" type="button" onClick={() => void loadQuotes()} disabled={!fixtureId}>↻ Segarkan</button></div>
        {!fixtureId ? <p className="empty-history">Pilih pertandingan untuk melihat riwayat odds.</p> : quotes.length === 0 ? <p className="empty-history">{loading ? "Memuat…" : "Belum ada snapshot odds untuk fixture ini."}</p> : <div className="odds-quote-list">{quotes.map((quote) => <article key={quote.id}>
          <div><b>{quote.bookmaker_name}</b><span>{quote.market.toUpperCase()} · {quote.selection}{quote.line ? ` ${quote.line}` : ""}</span></div>
          <strong>{Number(quote.decimal_odds).toFixed(4)}</strong>
          <small>{quote.quote_type.toUpperCase()} · {new Date(quote.captured_at).toLocaleString("id-ID")}</small>
        </article>)}</div>}
      </div>
      <p className="manual-footnote">Catatan: data manual tidak otomatis terisi dari bookmaker. Integrasi provider/API akan ditambahkan setelah sumber dan ketentuan aksesnya ditetapkan.</p>
    </section>
  );
}
