import { FormEvent, useState } from "react";

type Item = {
  id: number; name?: string; code?: string | null; country_id?: number | null;
  league_id?: number; season_id?: number; country_code?: string | null; external_id?: string | null;
  start_date?: string | null; end_date?: string | null; home_team_id?: number; away_team_id?: number;
  kickoff_at?: string; status?: string; home_goals?: number | null; away_goals?: number | null;
};
type Catalog = { countries: Item[]; leagues: Item[]; seasons: Item[]; teams: Item[]; fixtures: Item[] };
type Kind = "country" | "league" | "season" | "team" | "fixture";
type Props = {
  editing: { kind: Kind; item: Item } | null;
  data: Catalog;
  request: (path: string, init?: RequestInit) => Promise<any>;
  refresh: () => Promise<void>;
  close: () => void;
  notify: (message: string, failed?: boolean) => void;
};
const asLocalDateTime = (value?: string) => value ? value.slice(0, 16) : "";

export default function ManualEditor({ editing, data, request, refresh, close, notify }: Props) {
  const [busy, setBusy] = useState(false);
  if (!editing) return null;
  const { kind, item } = editing;
  const endpoint = kind === "fixture" ? "fixtures" : kind === "country" ? "countries" : kind === "league" ? "leagues" : kind === "season" ? "seasons" : "teams";

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const val = (key: string) => String(form.get(key) || "").trim();
    const opt = (key: string) => val(key) || null;
    let payload: Record<string, unknown>;
    if (kind === "country") payload = { name: val("name"), code: opt("code") };
    else if (kind === "league") payload = { name: val("name"), country_id: val("country_id") ? Number(val("country_id")) : null, external_id: opt("external_id") };
    else if (kind === "season") payload = { league_id: Number(val("league_id")), name: val("name"), start_date: opt("start_date"), end_date: opt("end_date") };
    else if (kind === "team") payload = { name: val("name"), country_code: opt("country_code"), external_id: opt("external_id") };
    else payload = {
      season_id: Number(val("season_id")), home_team_id: Number(val("home_team_id")), away_team_id: Number(val("away_team_id")),
      kickoff_at: new Date(val("kickoff_at")).toISOString(), status: val("status"),
      home_goals: val("home_goals") === "" ? null : Number(val("home_goals")),
      away_goals: val("away_goals") === "" ? null : Number(val("away_goals")),
    };
    setBusy(true);
    try {
      await request("/" + endpoint + "/" + item.id, { method: "PUT", body: JSON.stringify(payload) });
      notify("Perubahan berhasil disimpan.");
      close();
      await refresh();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Gagal memperbarui data.", true);
    } finally { setBusy(false); }
  }

  const field = (label: string, name: string, value?: string | number | null, type = "text", required = true) => (
    <label>{label}<input name={name} type={type} defaultValue={value ?? ""} required={required} /></label>
  );
  return (
    <article className="manual-card manual-editor">
      <div className="editor-heading"><h3>Edit {kind === "country" ? "negara" : kind === "league" ? "liga" : kind === "season" ? "musim" : kind === "team" ? "tim" : "pertandingan"} · #{item.id}</h3><button type="button" className="browse" onClick={close}>Batal</button></div>
      <form onSubmit={(event) => void save(event)}>
        {kind === "country" && <>{field("Nama negara", "name", item.name)}{field("Kode negara", "code", item.code, "text", false)}</>}
        {kind === "league" && <>{field("Nama liga", "name", item.name)}<label>Negara<select name="country_id" defaultValue={item.country_id ?? ""}><option value="">Tanpa negara</option>{data.countries.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>{field("ID eksternal", "external_id", item.external_id, "text", false)}</>}
        {kind === "season" && <><label>Liga<select name="league_id" defaultValue={item.league_id} required>{data.leagues.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>{field("Nama musim", "name", item.name)}{field("Tanggal mulai", "start_date", item.start_date, "date", false)}{field("Tanggal selesai", "end_date", item.end_date, "date", false)}</>}
        {kind === "team" && <>{field("Nama tim", "name", item.name)}{field("Kode negara", "country_code", item.country_code, "text", false)}{field("ID eksternal", "external_id", item.external_id, "text", false)}</>}
        {kind === "fixture" && <>
          <label>Musim<select name="season_id" defaultValue={item.season_id} required>{data.seasons.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
          <div className="form-pair"><label>Tim kandang<select name="home_team_id" defaultValue={item.home_team_id} required>{data.teams.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label><label>Tim tandang<select name="away_team_id" defaultValue={item.away_team_id} required>{data.teams.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label></div>
          {field("Kick-off", "kickoff_at", asLocalDateTime(item.kickoff_at), "datetime-local")}
          <label>Status<select name="status" defaultValue={item.status || "scheduled"}><option value="scheduled">Terjadwal</option><option value="live">Live</option><option value="finished">Selesai</option><option value="postponed">Ditunda</option><option value="cancelled">Dibatalkan</option></select></label>
          <div className="form-pair">{field("Gol kandang", "home_goals", item.home_goals, "number", false)}{field("Gol tandang", "away_goals", item.away_goals, "number", false)}</div>
        </>}
        <button className="browse" disabled={busy}>{busy ? "Menyimpan…" : "Simpan perubahan"}</button>
      </form>
    </article>
  );
}
