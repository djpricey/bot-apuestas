"""Descarga y normaliza resultados y próximos partidos."""
import io
import time
import pandas as pd
import requests

from .config import BASE, LIGAS_PRINCIPALES, LIGAS_EXTRA, TEMPORADAS

ALIAS = {
    "home": ["HomeTeam", "Home", "HT"],
    "away": ["AwayTeam", "Away", "AT"],
    "hg": ["FTHG", "HG"],
    "ag": ["FTAG", "AG"],
    # cuotas de cierre (preferidas) y de apertura
    "c1": ["PSCH", "AvgCH", "B365CH", "PSH", "AvgH", "B365H"],
    "cx": ["PSCD", "AvgCD", "B365CD", "PSD", "AvgD", "B365D"],
    "c2": ["PSCA", "AvgCA", "B365CA", "PSA", "AvgA", "B365A"],
    "o25": ["AvgC>2.5", "Avg>2.5", "B365>2.5", "P>2.5"],
    "u25": ["AvgC<2.5", "Avg<2.5", "B365<2.5", "P<2.5"],
}


def _get(url, intentos=3):
    for i in range(intentos):
        try:
            r = requests.get(url, timeout=40, headers={"User-Agent": "bot-apuestas/1.0"})
            if r.status_code == 200 and len(r.content) > 50:
                return r.content
            print(f"  aviso: {url} respondió {r.status_code}")
            return None
        except requests.RequestException as e:
            print(f"  aviso: {url} falló ({e}); intento {i + 1}")
            time.sleep(3)
    return None


def _leer_csv(contenido):
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(contenido), encoding=enc, on_bad_lines="skip")
        except Exception:
            continue
    return pd.DataFrame()


def normalizar(df, liga):
    """Convierte cualquier CSV de football-data al formato interno."""
    if df.empty:
        return pd.DataFrame()
    out = pd.DataFrame()
    for col, opciones in ALIAS.items():
        for o in opciones:
            if o in df.columns:
                out[col] = df[o]
                break
        else:
            out[col] = pd.NA
    out["fecha"] = pd.to_datetime(df.get("Date"), dayfirst=True, errors="coerce")
    out["hora"] = df["Time"] if "Time" in df.columns else ""
    out["liga"] = liga
    out = out.dropna(subset=["home", "away", "fecha"])
    for c in ["hg", "ag", "c1", "cx", "c2", "o25", "u25"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out["home"] = out["home"].astype(str).str.strip()
    out["away"] = out["away"].astype(str).str.strip()
    return out.reset_index(drop=True)


def descargar_resultados():
    partes = []
    for cod, nombre in LIGAS_PRINCIPALES.items():
        for t in TEMPORADAS:
            c = _get(f"{BASE}/mmz4281/{t}/{cod}.csv")
            if c:
                partes.append(normalizar(_leer_csv(c), nombre))
    for cod, nombre in LIGAS_EXTRA.items():
        c = _get(f"{BASE}/new/{cod}.csv")
        if c:
            partes.append(normalizar(_leer_csv(c), nombre))
    if not partes:
        return pd.DataFrame()
    df = pd.concat(partes, ignore_index=True)
    jugados = df.dropna(subset=["hg", "ag"])
    return jugados.drop_duplicates(subset=["liga", "fecha", "home", "away"]).sort_values("fecha").reset_index(drop=True)


def descargar_proximos():
    """Próximos partidos con cuotas (archivos de fixtures de football-data)."""
    partes = []
    c = _get(f"{BASE}/fixtures.csv")
    if c:
        raw = _leer_csv(c)
        print(f"  fixtures.csv: {len(raw)} filas; columnas: {list(raw.columns)[:12]}")
        if "Date" in raw.columns:
            print(f"  fechas: {raw['Date'].head(3).tolist()} ... {raw['Date'].tail(2).tolist()}")
        if "Div" in raw.columns:
            for cod, nombre in LIGAS_PRINCIPALES.items():
                partes.append(normalizar(raw[raw["Div"] == cod], nombre))
    c = _get(f"{BASE}/new_league_fixtures.csv")
    if c:
        raw = _leer_csv(c)
        print(f"  new_league_fixtures.csv: {len(raw)} filas; columnas: {list(raw.columns)[:12]}")
        if "Country" in raw.columns:
            print(f"  países: {raw['Country'].value_counts().head(8).to_dict()}")
        if "Country" in raw.columns:
            mapa = {"Argentina": "Argentina", "Brazil": "Brasil", "Mexico": "México", "USA": "MLS"}
            for pais, nombre in mapa.items():
                partes.append(normalizar(raw[raw["Country"] == pais], nombre))
    if not partes:
        return pd.DataFrame()
    return pd.concat(partes, ignore_index=True).sort_values("fecha").reset_index(drop=True)


URL_SELECCIONES = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
PESO_TORNEO = {"Friendly": 0.6}


def descargar_selecciones():
    """Resultados y partidos programados de selecciones (datos de martj42, se actualizan cada mes)."""
    c = _get(URL_SELECCIONES)
    if not c:
        return pd.DataFrame(), pd.DataFrame()
    raw = _leer_csv(c)
    out = pd.DataFrame({
        "fecha": pd.to_datetime(raw["date"], errors="coerce"),
        "home": raw["home_team"].astype(str).str.strip(),
        "away": raw["away_team"].astype(str).str.strip(),
        "hg": pd.to_numeric(raw["home_score"], errors="coerce"),
        "ag": pd.to_numeric(raw["away_score"], errors="coerce"),
        "neutral": raw["neutral"].astype(str).str.upper().eq("TRUE"),
        "torneo": raw["tournament"].astype(str),
    })
    out["peso"] = out["torneo"].map(PESO_TORNEO).fillna(1.0)
    out["liga"] = "Selecciones"
    out["hora"] = ""
    for col in ["c1", "cx", "c2", "o25", "u25"]:
        out[col] = pd.NA
    out = out.dropna(subset=["fecha"])
    jugados = out.dropna(subset=["hg", "ag"]).reset_index(drop=True)
    programados = out[out["hg"].isna()].reset_index(drop=True)
    print(f"  selecciones: {len(jugados)} resultados (último {jugados['fecha'].max().date() if len(jugados) else '-'}), {len(programados)} programados")
    return jugados, programados


def leer_manual(ruta):
    """Partidos de selecciones agregados a mano (fecha,local,visita,neutral,torneo,hg,ag)."""
    try:
        m = pd.read_csv(ruta)
    except FileNotFoundError:
        return pd.DataFrame(), pd.DataFrame()
    out = pd.DataFrame({
        "fecha": pd.to_datetime(m["fecha"], errors="coerce"), "home": m["local"].astype(str).str.strip(),
        "away": m["visita"].astype(str).str.strip(), "hg": pd.to_numeric(m.get("hg"), errors="coerce"),
        "ag": pd.to_numeric(m.get("ag"), errors="coerce"),
        "neutral": m["neutral"].astype(str).str.upper().isin(["TRUE", "1", "SI", "SÍ"]),
        "torneo": m.get("torneo", "").astype(str), "hora": m.get("hora", "").astype(str)})
    out["peso"] = out["torneo"].map(PESO_TORNEO).fillna(1.0)
    out["liga"] = "Selecciones"
    for col in ["c1", "cx", "c2", "o25", "u25"]:
        out[col] = pd.NA
    return out.dropna(subset=["hg", "ag"]).reset_index(drop=True), out[out["hg"].isna()].reset_index(drop=True)
