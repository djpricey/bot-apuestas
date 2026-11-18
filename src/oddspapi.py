"""Cuotas de Pinnacle vía OddsPapi (plan gratis: ~250 consultas al mes).

Pinnacle es la casa "afilada": sus cuotas, sin margen, son la mejor estimación pública
de la probabilidad real. El bot las usa como referencia para comparar con BetPlay.

Cuidado con la cuota mensual:
- El catálogo de mercados y de torneos se guarda en docs/data/oddspapi_cache.json y se
  renueva solo cada 30 días (2 consultas).
- Cada consulta de cuotas trae TODOS los partidos de hasta 3 torneos.
- El uso se anota en docs/data/oddspapi_uso.json y nunca se pasa de PRESUPUESTO_MES.
"""
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

import requests

BASE = "https://api.oddspapi.io/v4"
PRESUPUESTO_MES = 230      # deja margen sobre las 250 del plan gratis
MAX_POR_DIA = 7
COOLDOWN = 1.2             # segundos entre consultas (la API pide 1 s)
SOCCER = 10

SALIDA = os.path.join(os.path.dirname(__file__), "..", "docs", "data")
RUTA_CACHE = os.path.join(SALIDA, "oddspapi_cache.json")
RUTA_USO = os.path.join(SALIDA, "oddspapi_uso.json")
RUTA_EQUIPOS = os.path.join(SALIDA, "oddspapi_equipos.json")
VERSION_CACHE = 3

# liga interna -> (país/categoría, palabras del torneo). Se busca en el catálogo de OddsPapi.
TORNEOS = {
    "Liga BetPlay": [("colombia", ("primera-a", "liga-betplay", "primera-division"))],
    "Brasil": [("brazil", ("brasileiro-serie-a", "serie-a", "brasileirao"))],
    "Argentina": [("argentina", ("liga-profesional", "primera-division"))],
    "México": [("mexico", ("liga-mx",))],
    "MLS": [("usa", ("mls", "major-league-soccer"))],
    "Premier League": [("england", ("premier-league",))],
    "Championship": [("england", ("championship",))],
    "LaLiga": [("spain", ("laliga", "la-liga"))],
    "Serie A": [("italy", ("serie-a",))],
    "Bundesliga": [("germany", ("bundesliga",))],
    "Ligue 1": [("france", ("ligue-1",))],
    "Eredivisie": [("netherlands", ("eredivisie",))],
    "Portugal": [("portugal", ("liga-portugal", "primeira-liga"))],
    "Bélgica": [("belgium", ("pro-league", "first-division-a", "jupiler"))],
    "Turquía": [("turkey", ("super-lig",)), ("turkiye", ("super-lig",))],
    "Escocia": [("scotland", ("premiership",))],
    "Selecciones": [("international", ("nations-league", "world-cup-qualification", "friendl",
                                       "copa-america", "uefa-euro", "european-championship", "africa-cup", "gold-cup", "asian-cup"))],
}
# Orden de prioridad cuando no alcanza la cuota del día
PRIORIDAD = ["Liga BetPlay", "Selecciones", "Brasil", "Argentina", "México", "Premier League", "LaLiga",
             "Serie A", "Bundesliga", "Ligue 1", "MLS", "Portugal", "Eredivisie", "Championship",
             "Bélgica", "Turquía", "Escocia"]
EXCLUIR = ("women", "femen", "u17", "u18", "u19", "u20", "u21", "u23", "youth", "reserve", "serie-b", "primera-b",
           "segunda", "-2", "2-", "cup",
           "copa-", "promotion", "playoff", "play-off", "amateur", "regional", "state", "estadual", "paulista", "carioca")

_ultima = 0.0


def _key():
    return os.environ.get("ODDSPAPI_KEY", "").strip()


def _leer(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return defecto


def _escribir(ruta, datos):
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=1)


class Presupuesto:
    """Lleva la cuenta de consultas del mes y del día (en el repo, para que sobreviva entre corridas)."""

    def __init__(self, ahora):
        self.mes = ahora.strftime("%Y-%m")
        self.dia = ahora.strftime("%Y-%m-%d")
        u = _leer(RUTA_USO, {})
        if u.get("mes") != self.mes:
            u = {"mes": self.mes, "usadas_mes": 0, "por_dia": {}}
        self.u = u
        quedan_dias = (datetime(ahora.year + ahora.month // 12, ahora.month % 12 + 1, 1, tzinfo=ahora.tzinfo) - ahora).days + 1
        restante = max(0, PRESUPUESTO_MES - u["usadas_mes"])
        self.hoy_max = min(MAX_POR_DIA, max(1, restante // max(1, quedan_dias))) if restante else 0

    def usadas_hoy(self):
        return self.u["por_dia"].get(self.dia, 0)

    def puede(self, extra=1):
        return self.u["usadas_mes"] + extra <= PRESUPUESTO_MES and self.usadas_hoy() + extra <= self.hoy_max

    def anotar(self):
        self.u["usadas_mes"] += 1
        self.u["por_dia"][self.dia] = self.usadas_hoy() + 1
        # solo se guardan los últimos 40 días
        self.u["por_dia"] = dict(sorted(self.u["por_dia"].items())[-40:])
        _escribir(RUTA_USO, self.u)


def _get(path, pres, **params):
    global _ultima
    if not _key() or not pres.puede():
        return None
    espera = COOLDOWN - (time.time() - _ultima)
    if espera > 0:
        time.sleep(espera)
    try:
        r = requests.get(f"{BASE}{path}", params={**params, "apiKey": _key()}, timeout=40)
        _ultima = time.time()
        pres.anotar()
        if r.status_code != 200:
            print(f"  oddspapi: {path} respondió {r.status_code}: {r.text[:200]}")
            return None
        return r.json()
    except Exception as e:  # noqa: BLE001
        print(f"  oddspapi: {path} falló ({e})")
        return None


# ---------------------------------------------------------------- catálogo (mercados y torneos)

def _catalogo(pres, ahora):
    cache = _leer(RUTA_CACHE, {})
    vence = cache.get("actualizado", "")
    fresco = vence and datetime.fromisoformat(vence) > ahora - timedelta(days=30)
    if fresco and cache.get("mercados") and cache.get("torneos") and cache.get("version") == VERSION_CACHE:
        return cache
    mercados = _get("/markets", pres)
    torneos = _get("/tournaments", pres, sportId=SOCCER)
    if not mercados or not torneos:
        return cache if cache.get("mercados") else None
    cache = {
        "version": VERSION_CACHE,
        "actualizado": ahora.isoformat(timespec="minutes"),
        "mercados": _resumir_mercados(mercados),
        "torneos": _elegir_torneos(torneos),
    }
    _escribir(RUTA_CACHE, cache)
    print(f"  oddspapi: catálogo renovado ({len(cache['torneos'])} ligas con torneo)")
    return cache


def _participantes(pres, ids_faltantes):
    """Nombres de los equipos (la API de cuotas solo trae el id). Se guardan en el repo y se renuevan
    solo si aparece un equipo que no conocemos."""
    nombres = _leer(RUTA_EQUIPOS, {})
    if ids_faltantes and not all(str(i) in nombres for i in ids_faltantes):
        resp = _get("/participants", pres, sportId=SOCCER)
        if isinstance(resp, dict) and resp:
            nombres = {str(k): v for k, v in resp.items() if isinstance(v, str)}
            _escribir(RUTA_EQUIPOS, nombres)
            print(f"  oddspapi: {len(nombres)} nombres de equipos guardados")
        elif isinstance(resp, list):
            nombres = {str(x.get("participantId") or x.get("id")): x.get("participantName") or x.get("name")
                       for x in resp if isinstance(x, dict)}
            _escribir(RUTA_EQUIPOS, nombres)
    return nombres


def _resumir_mercados(mercados):
    """Solo fútbol, tiempo completo: 1X2, más/menos y ambos marcan. Guarda qué outcome es cada lado."""
    out = {}
    for m in mercados if isinstance(mercados, list) else []:
        if m.get("sportId") != SOCCER or m.get("playerProp"):
            continue
        per = str(m.get("period", "")).lower()
        if per not in ("fulltime", "regulartime", "full time", ""):
            continue
        tipo = str(m.get("marketType", "")).lower()
        nombre = str(m.get("marketName", "")).lower()
        lados = {str(o["outcomeId"]): str(o.get("outcomeName", "")).strip().lower() for o in m.get("outcomes", [])}
        if tipo == "1x2" and "half" not in nombre and set(lados.values()) >= {"1", "x", "2"}:
            out[str(m["marketId"])] = {"tipo": "1x2", "lados": lados}
        elif tipo == "totals" and "half" not in nombre and "team" not in nombre and ("corner" in nombre):
            out[str(m["marketId"])] = {"tipo": "corners", "linea": float(m.get("handicap") or 0), "lados": lados, "nombre": nombre}
        elif tipo == "totals" and "half" not in nombre and "team" not in nombre and any(x in nombre for x in ("card", "booking")):
            out[str(m["marketId"])] = {"tipo": "tarjetas", "linea": float(m.get("handicap") or 0), "lados": lados, "nombre": nombre}
        elif tipo == "totals" and "half" not in nombre and "team" not in nombre and not any(x in nombre for x in ("corner", "card", "booking", "shot", "foul", "offside", "throw")):
            out[str(m["marketId"])] = {"tipo": "totales", "linea": float(m.get("handicap") or 0), "lados": lados}
        elif ("both" in nombre and "score" in nombre or tipo in ("btts", "bothteamstoscore")) and "half" not in nombre:
            out[str(m["marketId"])] = {"tipo": "btts", "lados": lados}
    return out


def _elegir_torneos(torneos):
    """Para cada liga interna, el torneo de OddsPapi que mejor coincide (el de más partidos futuros)."""
    elegidos = {}
    lista = torneos if isinstance(torneos, list) else []
    for liga, reglas in TORNEOS.items():
        cands = []
        for t in lista:
            cat = str(t.get("categorySlug", "")).lower()
            slug = str(t.get("tournamentSlug", "")).lower()
            for pais, palabras in reglas:
                if (cat != pais if liga == "Selecciones" else pais not in cat) or not any(p in slug for p in palabras):
                    continue
                if slug.endswith("-w") or "-w-" in slug:
                    continue
                if liga != "Selecciones" and any(x in slug for x in EXCLUIR):
                    continue
                if liga == "Selecciones" and any(x in slug for x in ("women", "u17", "u19", "u20", "u21", "u23")):
                    continue
                cands.append(t)
        if not cands:
            continue
        cands.sort(key=lambda t: -((t.get("futureFixtures") or 0) + (t.get("upcomingFixtures") or 0)))
        # Colombia y México tienen Apertura y Clausura como torneos distintos: se piden los dos
        tope = cands if liga == "Selecciones" else cands[:2] if liga in ("Liga BetPlay", "México", "Argentina") else cands[:1]
        elegidos[liga] = [{"id": t["tournamentId"], "slug": t.get("tournamentSlug"), "pais": t.get("categorySlug")}
                          for t in tope if (t.get("futureFixtures") or 0) + (t.get("upcomingFixtures") or 0) > 0 or liga != "Selecciones"]
    return elegidos


# ---------------------------------------------------------------- cuotas

def _precio(outcome):
    jugadores = (outcome or {}).get("players") or {}
    p = jugadores.get("0") or (next(iter(jugadores.values())) if jugadores else None)
    if not p or p.get("active") is False:
        return None
    try:
        v = float(p.get("price"))
        return v if v > 1.0 else None
    except (TypeError, ValueError):
        return None


def sin_margen(cuotas):
    """Probabilidades sin margen (normalización simple). None si falta algún lado."""
    if not cuotas or any(c is None or c <= 1 for c in cuotas):
        return None
    inv = [1 / c for c in cuotas]
    s = sum(inv)
    return [x / s for x in inv]


def leer_fixture(fx, mercados):
    """Extrae de un fixture de OddsPapi: 1X2, más/menos por línea y ambos marcan (Pinnacle)."""
    bk = (fx.get("bookmakerOdds") or {}).get("pinnacle") or {}
    if not bk or bk.get("suspended"):
        return None
    out = {"c1": None, "cx": None, "c2": None, "totales": {}, "btts": None, "corners": {}, "tarjetas": {}}
    for mid, m in (bk.get("markets") or {}).items():
        info = mercados.get(str(mid))
        if not info:
            continue
        precios = {info["lados"].get(str(oid)): _precio(o) for oid, o in (m.get("outcomes") or {}).items()}
        if info["tipo"] == "1x2":
            out["c1"], out["cx"], out["c2"] = precios.get("1"), precios.get("x"), precios.get("2")
        elif info["tipo"] in ("totales", "corners", "tarjetas"):
            o, u = precios.get("over"), precios.get("under")
            if o and u:
                out[info["tipo"]][f"{info['linea']:.2f}".rstrip("0").rstrip(".")] = [o, u]
        elif info["tipo"] == "btts" and (str(mid) == "104" or out["btts"] is None):
            si, no = precios.get("yes"), precios.get("no")
            if si and no and (str(mid) == "104" or out.get("_btts_id") != "104"):
                out["btts"] = [si, no]
                out["_btts_id"] = str(mid)
    out.pop("_btts_id", None)
    if not out["c1"] and not out["totales"]:
        return None
    return out


def _norm(nombre):
    s = unicodedata.normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    quitar = {"fc", "cf", "sc", "ac", "afc", "cd", "ca", "club", "de", "the", "sk", "fk", "cr", "ec", "se", "rj", "pr", "sp", "mg", "ba", "rs"}
    s = " ".join(w for w in s.split() if w not in quitar)
    return ALIAS_EQUIPOS.get(s, s)


# nombres que no se parecen entre fuentes (bot -> nombre normalizado de OddsPapi)
ALIAS_EQUIPOS = {"athletico": "paranaense", "athletico paranaense": "paranaense", "atletico paranaense": "paranaense",
                 "atletico": "atletico mineiro", "red bull bragantino": "bragantino",
                 "man city": "manchester city", "man united": "manchester united", "nott m forest": "nottingham forest",
                 "wolves": "wolverhampton", "spurs": "tottenham", "ath bilbao": "athletic bilbao", "ath madrid": "atletico madrid",
                 "sociedad": "real sociedad", "betis": "real betis", "psg": "paris saint germain", "paris sg": "paris saint germain"}


def parecido(a, b):
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.9
    return SequenceMatcher(None, na, nb).ratio()


def emparejar(prox_filas, fixtures_op, umbral=0.72):
    """Une partidos del bot con fixtures de OddsPapi por fecha (±1 día) y nombres parecidos."""
    pares = {}
    for i, f in prox_filas:
        mejor, mejor_s = None, 0.0
        for fx in fixtures_op:
            if abs((fx["_fecha"] - f["fecha"]).days) > 1:
                continue
            if fx.get("_liga") and f.get("liga") and fx["_liga"] != f["liga"]:
                continue
            s = min(parecido(f["home"], fx["_local"]), parecido(f["away"], fx["_visita"]))
            if s > mejor_s:
                mejor, mejor_s = fx, s
        if mejor is not None and mejor_s >= umbral:
            pares[i] = mejor
    return pares


def cuotas_pinnacle(prox, ahora, dias=2):
    """Agrega a `prox` (DataFrame del bot) las cuotas de Pinnacle de los próximos `dias` días.

    Devuelve un dict {índice de prox: datos Pinnacle}. Nunca rompe la corrida: si algo falla, devuelve {}.
    """
    if not _key():
        print("  oddspapi: sin clave (secreto ODDSPAPI_KEY), se omite")
        return {}
    if prox is None or prox.empty:
        return {}
    import pandas as pd  # import local: el módulo se puede probar sin pandas
    pres = Presupuesto(ahora)
    print(f"  oddspapi: {pres.u['usadas_mes']} consultas usadas este mes; hoy puede usar {pres.hoy_max - pres.usadas_hoy()}")
    cat = _catalogo(pres, ahora)
    if not cat:
        print("  oddspapi: sin catálogo, se omite")
        return {}
    hoy = pd.Timestamp(ahora.date())
    cerca = prox[(prox["fecha"] >= hoy) & (prox["fecha"] <= hoy + pd.Timedelta(days=dias))]
    cuenta = cerca["liga"].value_counts().to_dict()
    ligas = [l for l in PRIORIDAD if cuenta.get(l) and l in cat["torneos"]]
    ids = []
    for l in ligas:
        for t in cat["torneos"][l]:
            if t["id"] not in ids:
                ids.append(t["id"])
    liga_de = {t["id"]: l for l, ts in cat["torneos"].items() for t in ts}
    fixtures, crudos = [], []
    reserva = 1 if os.path.exists(RUTA_EQUIPOS) else 2  # deja una consulta para los nombres si aún no están
    for k in range(0, len(ids), 3):
        if not pres.puede(reserva):
            print("  oddspapi: se acabó la cuota de hoy")
            break
        lote = ",".join(str(x) for x in ids[k:k + 3])
        resp = _get("/odds-by-tournaments", pres, tournamentIds=lote, bookmaker="pinnacle", oddsFormat="decimal")
        if isinstance(resp, dict):
            resp = resp.get("data") or resp.get("fixtures") or [resp]
        crudos.extend(x for x in resp or [] if isinstance(x, dict))
    faltan = {fx.get(k) for fx in crudos for k in ("participant1Id", "participant2Id")
              if not fx.get("participant1Name") and fx.get(k) is not None}
    nombres = _participantes(pres, faltan) if faltan else {}
    for fx in crudos:
        ini = fx.get("startTime") or fx.get("trueStartTime")
        loc = fx.get("participant1Name") or nombres.get(str(fx.get("participant1Id")))
        vis = fx.get("participant2Name") or nombres.get(str(fx.get("participant2Id")))
        if not ini or not loc or not vis:
            continue
        fecha_col = pd.Timestamp(ini).tz_convert("America/Bogota")
        fx["_fecha"] = pd.Timestamp(fecha_col.date())
        fx["_local"], fx["_visita"] = loc, vis
        fx["_liga"] = liga_de.get(fx.get("tournamentId"))
        fixtures.append(fx)
    filas = [(i, {"fecha": r.fecha, "home": r.home, "away": r.away, "liga": r.liga}) for i, r in cerca.iterrows()]
    pares = emparejar(filas, fixtures)
    out = {}
    for i, fx in pares.items():
        d = leer_fixture(fx, cat["mercados"])
        if d:
            d["fixture"] = fx.get("fixtureId")
            d["nombres"] = [fx["_local"], fx["_visita"]]
            out[i] = d
    print(f"  oddspapi: {len(fixtures)} partidos de Pinnacle recibidos, {len(out)} unidos a partidos del bot")
    return out


def resumen_pinnacle(d):
    """Lo que se publica en hoy.json: cuotas y probabilidades sin margen."""
    if not d:
        return None
    r = {"c1": d.get("c1"), "cx": d.get("cx"), "c2": d.get("c2")}
    p = sin_margen([d.get("c1"), d.get("cx"), d.get("c2")])
    r["p1x2"] = [round(x, 3) for x in p] if p else None
    r["totales"] = {}
    for linea, (o, u) in sorted(d.get("totales", {}).items(), key=lambda kv: float(kv[0])):
        pm = sin_margen([o, u])
        r["totales"][linea] = {"mas": o, "menos": u, "p_mas": round(pm[0], 3) if pm else None}
    for clave in ("corners", "tarjetas"):
        lineas = {}
        for linea, (o, u) in sorted(d.get(clave, {}).items(), key=lambda kv: float(kv[0])):
            pm = sin_margen([o, u])
            lineas[linea] = {"mas": o, "menos": u, "p_mas": round(pm[0], 3) if pm else None}
        if lineas:
            r[clave] = lineas
    if d.get("btts"):
        pm = sin_margen(d["btts"])
        r["btts"] = {"si": d["btts"][0], "no": d["btts"][1], "p_si": round(pm[0], 3) if pm else None}
    r["fuente"] = "Pinnacle vía OddsPapi"
    return r


def probar():
    """Para el workflow 'Probar OddsPapi': muestra qué devuelve la API con 3 consultas."""
    ahora = datetime.now(timezone(timedelta(hours=-5)))
    pres = Presupuesto(ahora)
    pres.hoy_max = max(pres.hoy_max, pres.usadas_hoy() + 4)
    cat = _catalogo(pres, ahora)
    if not cat:
        raise SystemExit("No se pudo leer el catálogo: revisa el secreto ODDSPAPI_KEY.")
    print("Córners/tarjetas reconocidos:", {k: (v["tipo"], v.get("linea"), v.get("nombre")) for k, v in cat["mercados"].items() if v["tipo"] in ("corners", "tarjetas")})
    print("Mercados reconocidos:", {k: v["tipo"] + (f" {v.get('linea')}" if v.get("linea") is not None else "") for k, v in list(cat["mercados"].items())[:40]})
    print("Torneos elegidos:", json.dumps(cat["torneos"], ensure_ascii=False, indent=1))
    lig = cat["torneos"].get("Brasil") or next(iter(cat["torneos"].values()), None)
    if lig:
        resp = _get("/odds-by-tournaments", pres, tournamentIds=lig[0]["id"], bookmaker="pinnacle", oddsFormat="decimal")
        lista = resp if isinstance(resp, list) else [resp] if resp else []
        nombres = _participantes(pres, {fx.get("participant1Id") for fx in lista})
        print(f"{len(lista)} partidos; ejemplo:")
        for fx in lista[:9]:
            print(nombres.get(str(fx.get("participant1Id"))), "vs", nombres.get(str(fx.get("participant2Id"))), fx.get("startTime"),
                  json.dumps(resumen_pinnacle(leer_fixture(fx, cat["mercados"])), ensure_ascii=False))
        if lista:
            print("Llaves del fixture:", list(lista[0].keys()))
    print(f"Consultas usadas este mes: {pres.u['usadas_mes']}")


if __name__ == "__main__":
    probar()
