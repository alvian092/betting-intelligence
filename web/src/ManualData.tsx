import { FormEvent, useCallback, useEffect, useState } from "react";
import ManualEditor from "./ManualEditor";

type Item = { id: number; name?: string; code?: string | null; country_id?: number | null; league_id?: number; season_id?: number; country_code?: string | null; external_id?: string | null; start_date?: string | null; end_date?: string | null; home_team_id?: number; away_team_id?: number; kickoff_at?: string; status?: string; home_goals?: number | null; away_goals?: number | null };
type Catalog = { countries: Item[]; leagues: Item[]; seasons: Item[]; teams: Item[]; fixtures: Item[] };

const emptyCatalog: Catalog = { countries: [], leagues: [], seasons: [], teams: [], fixtures: [] };

export default function ManualData() {
  const [data, setData] = useState<Catalog>(emptyCatalog);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState(false);
  const [search, setSearch] = useState("");
  const [fixtureSeason, setFixtureSeason] = useState("");
  const [fixtureTeam, setFixtureTeam] = useState("");
  const [fixtureStatus, setFixtureStatus] = useState("");
  const [editing, setEditing] = useState<{ kind: "country" | "league" | "season" | "team" | "fixture"; item: Item } | null>(null);
  const api = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

  const request = useCallback(async (path: string, init?: RequestInit) => {
    const response = await fetch(`${api}/api/v1/catalog${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = body.detail;
      throw new Error(typeof detail === "string" ? detail : "Permintaan gagal. Periksa data dan koneksi API.");
    }
    return body;
  }, [api]);

  const refresh = useCallback(async () => {
    setBusy(true);
    try {
      const [countries, leagues, seasons, teams, fixtures] = await Promise.all([
        request("/countries"), request("/leagues"), request("/seasons"),
        request("/teams?limit=200"), request("/fixtures?limit=100"),
      ]);
      setData({ countries, leagues, seasons, teams, fixtures });
      setNotice("");
      setError(false);
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Data master belum dapat dimuat. Pastikan backend aktif.");
      setError(true);
    } finally { setBusy(false); }
  }, [request]);

  useEffect(() => { void refresh(); }, [refresh]);

  async function submit(event: FormEvent<HTMLFormElement>, path: string, build: (form: FormData) => Record<string, unknown>) {
    event.preventDefault();
    const form = event.currentTarget;
    setBusy(true); setNotice("");
    try {
      await request(path, { method: "POST", body: JSON.stringify(build(new FormData(form))) });
      form.reset();
      setNotice("Data berhasil disimpan.");
      setError(false);
      await refresh();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Gagal menyimpan data.");
      setError(true);
    } finally { setBusy(false); }
  }

  const text = (form: FormData, key: string) => String(form.get(key) || "").trim();
  const number = (form: FormData, key: string) => Number(form.get(key));
  const optional = (value: string) => value || null;
  const label = (items: Item[], id?: number | null) => items.find((item) => item.id === id)?.name || `#${id ?? "?"}`;
  const matches = (...values: (string | number | null | undefined)[]) => values.join(" ").toLowerCase().includes(search.trim().toLowerCase());

  async function remove(kind: "countries" | "leagues" | "seasons" | "teams" | "fixtures", item: Item) {
    const title = item.name || (kind === "fixtures" ? `${label(data.teams,item.home_team_id)} vs ${label(data.teams,item.away_team_id)}` : `#${item.id}`);
    if (!window.confirm(`Hapus ${title}?\n\nData yang masih dipakai oleh relasi lain akan ditolak oleh sistem.`)) return;
    setBusy(true); setNotice("");
    try {
      await request(`/${kind}/${item.id}`, { method: "DELETE" });
      setNotice("Data berhasil dihapus."); setError(false);
      if (editing?.kind === kind.slice(0, -1) && editing.item.id === item.id) setEditing(null);
      await refresh();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Gagal menghapus data."); setError(true);
    } finally { setBusy(false); }
  }

  return (
    <section className="panel manual-panel" id="manual">
      <div className="panel-heading">
        <div><p className="eyebrow">02 / MASTER DATA</p><h2>Input data manual</h2></div>
        <button className="browse" type="button" onClick={() => void refresh()} disabled={busy}>{busy ? "Memuat…" : "↻ Segarkan"}</button>
      </div>
      <p className="manual-lead">Tambahkan atau perbarui negara, liga, musim, tim, dan jadwal pertandingan. Gunakan pencarian untuk menyaring daftar.</p>
      <label className="manual-search">Cari data master<input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cari negara, liga, musim, tim, atau pertandingan…" /></label>
      {notice && <div className={`notice ${error ? "warning" : "success"}`} role="status">{notice}</div>}

      <div className="manual-grid">
        <article className="manual-card">
          <h3>01 · Negara</h3>
          <form onSubmit={(e) => void submit(e, "/countries", (f) => ({ name: text(f,"name"), code: optional(text(f,"code")) }))}>
            <label>Nama negara<input name="name" placeholder="Indonesia" minLength={2} required /></label>
            <label>Kode negara<input name="code" placeholder="ID" maxLength={3} /></label>
            <button className="browse" disabled={busy}>Simpan negara</button>
          </form>
          <ul className="mini-list">{data.countries.filter((x) => matches(x.name, x.code)).slice(0,8).map((x) => <li key={x.id}><span>{x.name}<small>{x.code || "—"}</small></span><span className="row-actions"><button type="button" className="edit-link" onClick={() => setEditing({kind:"country",item:x})}>Edit</button><button type="button" className="delete-link" disabled={busy} onClick={() => void remove("countries",x)}>Hapus</button></span></li>)}</ul>
        </article>

        <article className="manual-card">
          <h3>02 · Liga</h3>
          <form onSubmit={(e) => void submit(e, "/leagues", (f) => ({ name: text(f,"name"), country_id: text(f,"country_id") ? number(f,"country_id") : null, external_id: optional(text(f,"external_id")) }))}>
            <label>Nama liga<input name="name" placeholder="Premier League" required minLength={2} /></label>
            <label>Negara<select name="country_id" defaultValue=""><option value="">Pilih negara (opsional)</option>{data.countries.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
            <label>ID eksternal<input name="external_id" placeholder="Opsional" /></label>
            <button className="browse" disabled={busy}>Simpan liga</button>
          </form>
          <ul className="mini-list">{data.leagues.filter((x) => matches(x.name, label(data.countries,x.country_id))).slice(0,8).map((x) => <li key={x.id}><span>{x.name}<small>{label(data.countries,x.country_id)}</small></span><span className="row-actions"><button type="button" className="edit-link" onClick={() => setEditing({kind:"league",item:x})}>Edit</button><button type="button" className="delete-link" disabled={busy} onClick={() => void remove("leagues",x)}>Hapus</button></span></li>)}</ul>
        </article>

        <article className="manual-card">
          <h3>03 · Musim</h3>
          <form onSubmit={(e) => void submit(e, "/seasons", (f) => ({ league_id: number(f,"league_id"), name: text(f,"name"), start_date: optional(text(f,"start_date")), end_date: optional(text(f,"end_date")) }))}>
            <label>Liga<select name="league_id" required defaultValue=""><option value="" disabled>Pilih liga</option>{data.leagues.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
            <label>Nama musim<input name="name" placeholder="2026-2027" required /></label>
            <div className="form-pair"><label>Mulai<input name="start_date" type="date" /></label><label>Selesai<input name="end_date" type="date" /></label></div>
            <button className="browse" disabled={busy || data.leagues.length === 0}>Simpan musim</button>
          </form>
          <ul className="mini-list">{data.seasons.filter((x) => matches(x.name, label(data.leagues,x.league_id))).slice(0,8).map((x) => <li key={x.id}><span>{x.name}<small>{label(data.leagues,x.league_id)}</small></span><span className="row-actions"><button type="button" className="edit-link" onClick={() => setEditing({kind:"season",item:x})}>Edit</button><button type="button" className="delete-link" disabled={busy} onClick={() => void remove("seasons",x)}>Hapus</button></span></li>)}</ul>
        </article>

        <article className="manual-card">
          <h3>04 · Tim</h3>
          <form onSubmit={(e) => void submit(e, "/teams", (f) => ({ name: text(f,"name"), country_code: optional(text(f,"country_code")), external_id: optional(text(f,"external_id")) }))}>
            <label>Nama tim<input name="name" placeholder="Liverpool" required minLength={2} /></label>
            <label>Kode negara<input name="country_code" placeholder="GB" maxLength={3} /></label>
            <label>ID eksternal<input name="external_id" placeholder="Opsional" /></label>
            <button className="browse" disabled={busy}>Simpan tim</button>
          </form>
          <ul className="mini-list">{data.teams.filter((x) => matches(x.name, x.country_code)).slice(0,8).map((x) => <li key={x.id}><span>{x.name}<small>{x.country_code || "—"}</small></span><span className="row-actions"><button type="button" className="edit-link" onClick={() => setEditing({kind:"team",item:x})}>Edit</button><button type="button" className="delete-link" disabled={busy} onClick={() => void remove("teams",x)}>Hapus</button></span></li>)}</ul>
        </article>

        <article className="manual-card fixture-card">
          <h3>05 · Pertandingan</h3>
          <form onSubmit={(e) => void submit(e, "/fixtures", (f) => {
            const home = text(f,"home_goals"), away = text(f,"away_goals");
            return { season_id: number(f,"season_id"), home_team_id: number(f,"home_team_id"), away_team_id: number(f,"away_team_id"), kickoff_at: text(f,"kickoff_at"), status: text(f,"status"), home_goals: home === "" ? null : Number(home), away_goals: away === "" ? null : Number(away) };
          })}>
            <label>Musim<select name="season_id" required defaultValue=""><option value="" disabled>Pilih musim</option>{data.seasons.map((x) => <option key={x.id} value={x.id}>{label(data.leagues,x.league_id)} · {x.name}</option>)}</select></label>
            <div className="form-pair"><label>Tim kandang<select name="home_team_id" required defaultValue=""><option value="" disabled>Pilih tim</option>{data.teams.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label><label>Tim tandang<select name="away_team_id" required defaultValue=""><option value="" disabled>Pilih tim</option>{data.teams.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label></div>
            <label>Waktu kick-off<input name="kickoff_at" type="datetime-local" required /></label>
            <div className="form-pair"><label>Status<select name="status" defaultValue="scheduled"><option value="scheduled">Terjadwal</option><option value="live">Live</option><option value="finished">Selesai</option><option value="postponed">Ditunda</option><option value="cancelled">Dibatalkan</option></select></label><label>Skor kandang / tandang<div className="score-inputs"><input name="home_goals" type="number" min="0" placeholder="0" /><input name="away_goals" type="number" min="0" placeholder="0" /></div></label></div>
            <button className="browse" disabled={busy || !data.seasons.length || data.teams.length < 2}>Simpan pertandingan</button>
          </form>
          <div className="fixture-filters"><label>Musim<select value={fixtureSeason} onChange={(e) => setFixtureSeason(e.target.value)}><option value="">Semua musim</option>{data.seasons.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label><label>Tim<select value={fixtureTeam} onChange={(e) => setFixtureTeam(e.target.value)}><option value="">Semua tim</option>{data.teams.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label><label>Status<select value={fixtureStatus} onChange={(e) => setFixtureStatus(e.target.value)}><option value="">Semua status</option><option value="scheduled">Terjadwal</option><option value="live">Live</option><option value="finished">Selesai</option><option value="postponed">Ditunda</option><option value="cancelled">Dibatalkan</option></select></label></div>
          <div className="fixture-list">{data.fixtures.filter((x) => matches(label(data.teams,x.home_team_id), label(data.teams,x.away_team_id), x.status, x.kickoff_at) && (!fixtureSeason || String(x.season_id) === fixtureSeason) && (!fixtureTeam || String(x.home_team_id) === fixtureTeam || String(x.away_team_id) === fixtureTeam) && (!fixtureStatus || x.status === fixtureStatus)).slice(0,8).map((x) => <div key={x.id}><strong>{label(data.teams,x.home_team_id)} vs {label(data.teams,x.away_team_id)}</strong><small>{x.kickoff_at ? new Date(x.kickoff_at).toLocaleString("id-ID") : ""} · {x.status} {x.home_goals !== null && x.home_goals !== undefined ? `· ${x.home_goals}-${x.away_goals}` : ""}</small><span className="row-actions"><button type="button" className="edit-link" onClick={() => setEditing({kind:"fixture",item:x})}>Edit</button><button type="button" className="delete-link" disabled={busy} onClick={() => void remove("fixtures",x)}>Hapus</button></span></div>)}</div>
        </article>
      </div>
      <ManualEditor editing={editing} data={data} request={request} refresh={refresh} close={() => setEditing(null)} notify={(message, failed = false) => { setNotice(message); setError(failed); }} />
      <p className="manual-footnote">Daftar menampilkan hingga 8 hasil per kategori. Data yang masih memiliki relasi tidak dapat dihapus; hapus data turunannya terlebih dahulu.</p>
    </section>
  );
}
