import { ChangeEvent, DragEvent, useEffect, useRef, useState } from "react";

type ImportResult = {
  status?: string;
  rows_received?: number;
  imported?: number;
  duplicates_skipped?: number;
  invalid_rows?: number;
  message?: string;
};

type ImportBatch = { id: number; filename: string; format: string; status: string; rows_received: number; imported: number; duplicates_skipped: number; invalid_rows: number; message: string; created_at: string; };\n\ntype ApiError = {
  detail?: {
    message?: string;
    invalid_rows?: Array<{ row: number; errors: string[] }>;
  } | string;
};

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const MAX_BYTES = 10 * 1024 * 1024;

export default function App() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [errors, setErrors] = useState<Array<{ row: number; errors: string[] }>>([]);
  const [notice, setNotice] = useState("");\n  const [history, setHistory] = useState<ImportBatch[]>([]);\n  const [historyBusy, setHistoryBusy] = useState(false);\n\n  async function loadHistory() {\n    setHistoryBusy(true);\n    try { const response = await fetch(`${API_BASE}/api/v1/imports/history?limit=50`); if (!response.ok) throw new Error("history"); const data = await response.json(); setHistory(data.items || []); }\n    catch { setNotice("Riwayat impor belum dapat dimuat. Periksa koneksi API."); }\n    finally { setHistoryBusy(false); }\n  }\n\n  useEffect(() => { void loadHistory(); }, []);

  function chooseFile(candidate?: File) {
    setResult(null);
    setErrors([]);
    setNotice("");
    if (!candidate) return;
    const ext = candidate.name.toLowerCase().split(".").pop();
    if (ext !== "csv" && ext !== "xlsx") {
      setFile(null);
      setNotice("Pilih file berformat .csv atau .xlsx.");
      return;
    }
    if (candidate.size > MAX_BYTES) {
      setFile(null);
      setNotice("Ukuran file maksimal 10 MB.");
      return;
    }
    setFile(candidate);
  }

  function onInputChange(event: ChangeEvent<HTMLInputElement>) {
    chooseFile(event.target.files?.[0]);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    chooseFile(event.dataTransfer.files?.[0]);
  }

  async function upload() {
    if (!file || busy) return;
    setBusy(true);
    setResult(null);
    setErrors([]);
    setNotice("");
    const format = file.name.toLowerCase().endsWith(".csv") ? "csv" : "excel";
    const body = new FormData();
    body.append("file", file);
    try {
      const response = await fetch(`${API_BASE}/api/v1/imports/fixtures/${format}`, {
        method: "POST",
        body,
      });
      const payload = await response.json();
      if (!response.ok) {
        const detail = (payload as ApiError).detail;
        if (detail && typeof detail === "object") {
          setNotice(detail.message || "Validasi file gagal.");
          setErrors(detail.invalid_rows || []);
        } else {
          setNotice(typeof detail === "string" ? detail : "Import gagal. Periksa koneksi API.");
        }
        return;
      }
      setResult(payload as ImportResult);
      setNotice("Import berhasil diproses.");
    } catch {
      setNotice("Tidak dapat terhubung ke server. Periksa alamat API dan koneksi.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Betting Intelligence home">
          <span className="brand-mark">BI</span>
          <span>BETTING <b>INTELLIGENCE</b></span>
        </a>
        <nav className="nav-links"><a href="#upload">IMPORT</a><a href="#history">RIWAYAT</a></nav>\n        <span className="status"><i /> DATA FOUNDATION</span>
      </header>

      <section className="intro">
        <p className="eyebrow">DATA MANAGEMENT / IMPORT ENGINE V1.0</p>
        <h1>Bangun fondasi data.<br /><em>Temukan value.</em></h1>
        <p className="lead">Impor hasil pertandingan dari CSV atau Excel. Data akan divalidasi dan diperiksa duplikasinya sebelum disimpan.</p>
      </section>

      <section className="panel" id="upload">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">01 / UPLOAD DATA</p>
            <h2>Import pertandingan</h2>
          </div>
          <span className="limit">MAKS. 10 MB</span>
        </div>

        <div
          className={`dropzone ${dragging ? "dragging" : ""}`}
          onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") inputRef.current?.click(); }}
        >
          <input ref={inputRef} type="file" accept=".csv,.xlsx" onChange={onInputChange} hidden />
          <span className="upload-icon">↑</span>
          <strong>{file ? file.name : "Pilih file atau tarik ke area ini"}</strong>
          <span>{file ? `${(file.size / 1024).toFixed(1)} KB · siap diimpor` : "Format yang didukung: CSV dan Excel (.xlsx)"}</span>
          <button className="browse" type="button" onClick={(event) => { event.stopPropagation(); inputRef.current?.click(); }}>Pilih file</button>
        </div>

        <div className="template">
          <div>
            <strong>Format kolom wajib</strong>
            <p>Pastikan nama kolom sesuai dengan template.</p>
          </div>
          <code>date, league, season, home_team, away_team, home_goals, away_goals</code>
        </div>

        <button className="primary" disabled={!file || busy} onClick={upload}>
          {busy ? "Memproses data…" : "Mulai import"} <span>→</span>
        </button>

        {notice && <div className={`notice ${errors.length ? "warning" : result ? "success" : ""}`} role="status">{notice}</div>}

        {result && (
          <div className="result-grid">
            <div><span>Baris dibaca</span><strong>{result.rows_received ?? 0}</strong></div>
            <div><span>Berhasil diimpor</span><strong>{result.imported ?? 0}</strong></div>
            <div><span>Duplikat dilewati</span><strong>{result.duplicates_skipped ?? 0}</strong></div>
          </div>
        )}

        {errors.length > 0 && (
          <div className="errors">
            <h3>Detail validasi ({errors.length} baris)</h3>
            {errors.slice(0, 30).map((item) => (
              <div className="error-row" key={item.row}>
                <b>Baris {item.row}</b>
                <span>{item.errors.join(" · ")}</span>
              </div>
            ))}
            {errors.length > 30 && <p className="muted">Menampilkan 30 dari {errors.length} baris bermasalah.</p>}
          </div>
        )}
      </section>

      <section className="panel history-panel" id="history">\n        <div className="panel-heading"><div><p className="eyebrow">02 / AUDIT TRAIL</p><h2>Riwayat impor</h2></div><button className="browse" type="button" onClick={() => void loadHistory()}>{historyBusy ? "Memuat…" : "↻ Segarkan"}</button></div>\n        {history.length === 0 ? <p className="empty-history">{historyBusy ? "Memuat riwayat…" : "Belum ada aktivitas impor."}</p> : <div className="history-list">{history.map((item) => <article className="history-item" key={item.id}><div className="history-main"><strong>{item.filename}</strong><span>{new Date(item.created_at).toLocaleString("id-ID")} · {item.format.toUpperCase()}</span></div><span className={`history-status ${item.status}`}>{item.status === "completed" ? "BERHASIL" : "GAGAL"}</span><div className="history-stats"><span>{item.rows_received} baris</span><span>{item.imported} baru</span><span>{item.duplicates_skipped} duplikat</span><span>{item.invalid_rows} invalid</span></div><p>{item.message}</p></article>)}</div>}\n      </section>\n\n      <section className="rules">
        <h2>Validasi otomatis</h2>
        <div className="rule-list">
          <div><span>01</span><p><b>Format tanggal</b><br />YYYY-MM-DD atau sel tanggal Excel.</p></div>
          <div><span>02</span><p><b>Skor valid</b><br />Bilangan bulat, tidak boleh negatif.</p></div>
          <div><span>03</span><p><b>Deteksi duplikasi</b><br />Fixture yang sama tidak dimasukkan ulang.</p></div>
          <div><span>04</span><p><b>Transaksi aman</b><br />Baris invalid membatalkan seluruh proses.</p></div>
        </div>
      </section>

      <footer>BETTING INTELLIGENCE <span>FIND THE VALUE, NOT JUST THE WINNER.</span></footer>
    </main>
  );
}
