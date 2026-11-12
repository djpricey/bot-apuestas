"""Datos de API-Football (plan gratis, 100 consultas/día): partidos, cuotas, bajas y Liga BetPlay."""
import os
import time
import requests
import pandas as pd

BASE = "https://v3.football.api-sports.io"
LIMITE = 90  # deja margen sobre las 100 diarias
LIGA_COLOMBIA = 239
_usadas = 0

# Nombres de la API -> nombres de la base de selecciones (martj42)
ALIAS = {
    "USA": "United States", "Korea Republic": "South Korea", "Türkiye": "Turkey", "Turkiye": "Turkey",
    "Czechia": "Czech Republic", "Bosnia & Herzegovina": "Bosnia and Herzegovina", "Cape Verde Islands": "Cape Verde",
    "Congo DR": "DR Congo", "Curacao": "Curaçao", "China PR": "China", "Ireland": "Republic of Ireland",
    "Côte d'Ivoire": "Ivory Coast", "Cote D'Ivoire": "Ivory Coast", "Macedonia": "North Macedonia",
    "Kyrgyz Republic": "Kyrgyzstan", "FYR Macedonia": "North Macedonia", "St. Lucia": "Saint Lucia",
    "St. Kitts and Nevis": "Saint Kitts and Nevis", "St. Vincent / Grenadines": "Saint Vincent and the Grenadines", "Swaziland": "Eswatini", "Chinese Taipei": "Taiwan", "IR Iran": "Iran",
}
TORNEOS_SEL = ("Nations League", "World Cup", "Friendlies", "Euro", "Africa Cup", "Copa America", "Gold Cup",
               "Asian Cup", "CONCACAF", "CONMEBOL", "UEFA", "CAF", "AFC")


def _key():
    return os.environ.get("API_FOOTBALL_KEY", "")


_ultima = 0.0


def _get(path, _reintento=True, **params):
    """Respeta el límite de 10 consultas por minuto del plan gratis."""
    global _usadas, _ultima
    if not _key() or _usadas >= LIMITE:
        return []
    espera = 6.5 - (time.time() - _ultima)
    if espera > 0:
        time.sleep(espera)
    try:
        r = requests.get(BASE + path, headers={"x-apisports-key": _key()}, params=params, timeout=40)
        _ultima = time.time()
        _usadas += 1
        j = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"  api: {path} falló ({e})")
        return []
    if isinstance(j.get("errors"), dict) and "rateLimit" in j["errors"] and _reintento:
        time.sleep(61)
        return _get(path, _reintento=False, **params)
    if j.get("errors"):
        print(f"  api: {path} {params} -> {j['errors']}")
    return j.get("response") or []


def _nombre(n):
    return ALIAS.get(n, n)


def _es_sub(n):
    t = n.upper()
    return any(x in t for x in (" U2", " U1", " W", "OLYMPIC")) or t.endswith(" W")


def _cuotas(fid):
    """1X2 y más/menos 2.5 promediando las casas que trae la API."""
    resp = _get("/odds", fixture=fid)
    if not resp:
        return {}
    v = {"1": [], "x": [], "2": [], "o": [], "u": []}
    for bk in resp[0].get("bookmakers", []):
        for bet in bk.get("bets", []):
            if bet.get("name") == "Match Winner":
                for x in bet["values"]:
                    k = {"Home": "1", "Draw": "x", "Away": "2"}.get(x["value"])
                    if k:
                        v[k].append(float(x["odd"]))
            if bet.get("name") == "Goals Over/Under":
                for x in bet["values"]:
                    if x["value"] == "Over 2.5":
                        v["o"].append(float(x["odd"]))
                    if x["value"] == "Under 2.5":
                        v["u"].append(float(x["odd"]))
    m = lambda L: round(sum(L) / len(L), 3) if L else None  # noqa: E731
    return {"c1": m(v["1"]), "cx": m(v["x"]), "c2": m(v["2"]), "o25": m(v["o"]), "u25": m(v["u"])}


def _bajas(fid):
    out = {}
    for x in _get("/injuries", fixture=fid):
        out.setdefault(x["team"]["name"], []).append(f"{x['player']['name']} ({x['player'].get('reason') or x['player'].get('type')})")
    return out


def datos(fechas, equipos_sel, max_partidos=30):
    """Devuelve (resultados_colombia, proximos, bajas). Gasta como máximo ~LIMITE consultas."""
    if not _key():
        print("  api: sin clave, se omite")
        return pd.DataFrame(), pd.DataFrame(), {}
    global LIMITE
    st = _get("/status")
    try:
        usadas_hoy = st["requests"]["current"] if isinstance(st, dict) else 0
    except (KeyError, TypeError):
        usadas_hoy = 0
    LIMITE = max(0, min(LIMITE, 95 - usadas_hoy))
    print(f"  api: {usadas_hoy} consultas ya usadas hoy; esta corrida puede usar {LIMITE}")
    filas, bajas = [], {}
    elegidos = []
    for f in fechas:
        for fx in _get("/fixtures", date=f):
            lg, t = fx["league"], fx["teams"]
            if fx["fixture"]["status"]["short"] not in ("NS", "TBD"):
                continue
            h, a = t["home"]["name"], t["away"]["name"]
            if lg["id"] == LIGA_COLOMBIA:
                elegidos.append(("Liga BetPlay", h, a, fx))
            elif lg["country"] == "World" and any(s in lg["name"] for s in TORNEOS_SEL) and not (_es_sub(h) or _es_sub(a)) and "Clubs" not in lg["name"]:
                hn, an = _nombre(h), _nombre(a)
                if hn in equipos_sel and an in equipos_sel:
                    elegidos.append(("Selecciones", hn, an, fx))
                else:
                    print(f"  api: selección sin historial: {h} / {a}")
    def prioridad(e):
        nombre = e[3]["league"]["name"]
        return (0 if ("Nations League" in nombre or "Qualification" in nombre) else 1 if e[0] == "Liga BetPlay" else 2, e[3]["fixture"]["date"])
    elegidos.sort(key=prioridad)
    # Colombia (2 consultas) antes que las cuotas de partidos menores
    res = []
    for temporada in (pd.Timestamp.now().year - 1, pd.Timestamp.now().year):
        for fx in _get("/fixtures", league=LIGA_COLOMBIA, season=temporada):
            if fx["fixture"]["status"]["short"] in ("FT", "AET", "PEN") and fx["goals"]["home"] is not None:
                res.append({"liga": "Liga BetPlay", "home": fx["teams"]["home"]["name"], "away": fx["teams"]["away"]["name"],
                            "fecha": pd.Timestamp(pd.Timestamp(fx["fixture"]["date"]).date()), "hora": "",
                            "hg": float(fx["goals"]["home"]), "ag": float(fx["goals"]["away"]), "neutral": False, "peso": 1.0,
                            "c1": None, "cx": None, "c2": None, "o25": None, "u25": None})
    for liga, h, a, fx in elegidos[:max_partidos]:
        if _usadas >= LIMITE - 1:
            break
        fid = fx["fixture"]["id"]
        inicio = pd.Timestamp(fx["fixture"]["date"]).tz_convert("America/Bogota")
        c = _cuotas(fid)
        b = _bajas(fid)
        bajas[(liga, h, a)] = {"local": b.get(fx["teams"]["home"]["name"], []), "visita": b.get(fx["teams"]["away"]["name"], [])}
        filas.append({"liga": liga, "home": h, "away": a, "fecha": pd.Timestamp(inicio.date()), "hora": inicio.strftime("%H:%M"),
                      "hg": float("nan"), "ag": float("nan"), "neutral": False, "peso": 1.0, "fuente": "api", **{k: c.get(k) for k in ("c1", "cx", "c2", "o25", "u25")}})
    print(f"  api: {len(filas)} partidos con cuotas/bajas, {len(res)} resultados de Liga BetPlay, {_usadas} consultas usadas")
    return pd.DataFrame(res), pd.DataFrame(filas), bajas
