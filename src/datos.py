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
