"""Prueba sin internet de OddsPapi (cuotas Pinnacle) y de la liquidación del libro."""
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import src.oddspapi as op  # noqa: E402
from src import libro  # noqa: E402

TZ = timezone(timedelta(hours=-5))
tmp = tempfile.mkdtemp()
op.RUTA_CACHE = os.path.join(tmp, "cache.json")
op.RUTA_USO = os.path.join(tmp, "uso.json")
op.RUTA_EQUIPOS = os.path.join(tmp, "equipos.json")
op.COOLDOWN = 0

MERCADOS = [
    {"marketId": 101, "sportId": 10, "period": "fulltime", "marketType": "1x2", "marketName": "Full Time Result",
     "playerProp": False, "handicap": 0, "outcomes": [{"outcomeId": 101, "outcomeName": "1"}, {"outcomeId": 102, "outcomeName": "X"}, {"outcomeId": 103, "outcomeName": "2"}]},
    {"marketId": 1010, "sportId": 10, "period": "fulltime", "marketType": "totals", "marketName": "Over Under Full Time",
     "playerProp": False, "handicap": 2.5, "outcomes": [{"outcomeId": 1010, "outcomeName": "Over"}, {"outcomeId": 1011, "outcomeName": "Under"}]},
    {"marketId": 1012, "sportId": 10, "period": "fulltime", "marketType": "totals", "marketName": "Over Under Full Time",
     "playerProp": False, "handicap": 3.5, "outcomes": [{"outcomeId": 1012, "outcomeName": "Over"}, {"outcomeId": 1013, "outcomeName": "Under"}]},
    {"marketId": 2010, "sportId": 10, "period": "firsthalf", "marketType": "totals", "marketName": "Over Under First Half",
     "playerProp": False, "handicap": 0.5, "outcomes": [{"outcomeId": 2010, "outcomeName": "Over"}, {"outcomeId": 2011, "outcomeName": "Under"}]},
    {"marketId": 104, "sportId": 10, "period": "fulltime", "marketType": "bothteamstoscore", "marketName": "Both Teams To Score",
     "playerProp": False, "handicap": 0, "outcomes": [{"outcomeId": 104, "outcomeName": "Yes"}, {"outcomeId": 105, "outcomeName": "No"}]},
    {"marketId": 11101, "sportId": 11, "period": "fulltime", "marketType": "moneyline", "marketName": "Winner",
     "playerProp": False, "handicap": 0, "outcomes": [{"outcomeId": 111, "outcomeName": "1"}]},
]
TORNEOS = [
    {"tournamentId": 325, "tournamentSlug": "brasileiro-serie-a", "categorySlug": "brazil", "futureFixtures": 40, "upcomingFixtures": 10},
    {"tournamentId": 390, "tournamentSlug": "brasileiro-serie-b", "categorySlug": "brazil", "futureFixtures": 50},
    {"tournamentId": 999, "tournamentSlug": "brasileiro-serie-a-women", "categorySlug": "brazil", "futureFixtures": 90},
    {"tournamentId": 240, "tournamentSlug": "primera-a-clausura", "categorySlug": "colombia", "futureFixtures": 12},
    {"tournamentId": 17, "tournamentSlug": "premier-league", "categorySlug": "england", "futureFixtures": 200},
    {"tournamentId": 679, "tournamentSlug": "uefa-europa-league", "categorySlug": "international-clubs", "futureFixtures": 30},
    {"tournamentId": 852, "tournamentSlug": "int-friendly-games-w", "categorySlug": "international", "futureFixtures": 30},
    {"tournamentId": 27420, "tournamentSlug": "concacaf-nations-league", "categorySlug": "international", "futureFixtures": 8},
    {"tournamentId": 27070, "tournamentSlug": "primera-a-apertura", "categorySlug": "colombia", "futureFixtures": 0},
]


def jug(p):
    return {"players": {"0": {"active": True, "price": p}}}


FIXTURE = {
    "fixtureId": "id1", "participant1Id": 1, "participant2Id": 2,
    "startTime": "2026-11-18T23:30:00.000Z",
    "bookmakerOdds": {"pinnacle": {"suspended": False, "markets": {
        "101": {"outcomes": {"101": jug(1.62), "102": jug(4.0), "103": jug(5.6)}},
        "1010": {"outcomes": {"1010": jug(1.85), "1011": jug(2.02)}},
        "1012": {"outcomes": {"1012": jug(3.1), "1013": jug(1.37)}},
        "2010": {"outcomes": {"2010": jug(1.3), "2011": jug(3.5)}},
        "104": {"outcomes": {"104": jug(1.95), "105": jug(1.85)}},
    }}},
}
OTRO = {"fixtureId": "id2", "participant1Id": 3, "participant2Id": 4, "startTime": "2026-11-19T00:30:00.000Z",
        "bookmakerOdds": {"pinnacle": {"markets": {"101": {"outcomes": {"101": jug(2.1), "102": jug(3.3), "103": jug(3.6)}}}}}}

llamadas = []


def falso_get(path, pres, **params):
    if not pres.puede():
        return None
    pres.anotar()
    llamadas.append((path, params))
    if path == "/markets":
        return MERCADOS
    if path == "/tournaments":
        return TORNEOS
    if path == "/odds-by-tournaments":
        return [FIXTURE, OTRO]
    if path == "/participants":
        return {"1": "Flamengo RJ", "2": "Athletico Paranaense", "3": "Gremio", "4": "Bahia"}
    return None


op._get = falso_get
os.environ["ODDSPAPI_KEY"] = "prueba"

# 1) catálogo: mercados y torneos correctos
ahora = datetime(2026, 11, 18, 7, 0, tzinfo=TZ)
pres = op.Presupuesto(ahora)
cat = op._catalogo(pres, ahora)
assert set(cat["mercados"]) == {"101", "1010", "1012", "104"}, cat["mercados"]
assert cat["torneos"]["Brasil"][0]["id"] == 325, cat["torneos"]
assert [t["id"] for t in cat["torneos"]["Liga BetPlay"]] == [240, 27070]
assert [t["id"] for t in cat["torneos"]["Selecciones"]] == [27420], cat["torneos"]["Selecciones"]
# 2) leer fixture y quitar margen
d = op.leer_fixture(FIXTURE, cat["mercados"])
assert (d["c1"], d["cx"], d["c2"]) == (1.62, 4.0, 5.6)
assert d["totales"] == {"2.5": [1.85, 2.02], "3.5": [3.1, 1.37]}, d["totales"]
assert d["btts"] == [1.95, 1.85]
r = op.resumen_pinnacle(d)
assert abs(sum(r["p1x2"]) - 1) < 0.01 and r["p1x2"][0] > 0.58
assert 0.5 < r["totales"]["2.5"]["p_mas"] < 0.54
# 3) nombres parecidos
assert op.parecido("Flamengo", "Flamengo RJ") >= 0.9
assert op.parecido("Athletico-PR", "Athletico Paranaense") >= 0.72
assert op.parecido("Gremio", "Grêmio") == 1.0
assert op.parecido("Flamengo", "Fluminense") < 0.72
# 4) flujo completo con un DataFrame como el del bot
prox = pd.DataFrame([
    {"liga": "Brasil", "fecha": pd.Timestamp("2026-11-18"), "home": "Flamengo RJ", "away": "Athletico-PR", "c1": None, "cx": None, "c2": None, "o25": None, "u25": None},
    {"liga": "Brasil", "fecha": pd.Timestamp("2026-11-18"), "home": "Gremio", "away": "Bahia", "c1": None, "cx": None, "c2": None, "o25": None, "u25": None},
    {"liga": "Brasil", "fecha": pd.Timestamp("2026-11-18"), "home": "Cruzeiro", "away": "Palmeiras", "c1": None, "cx": None, "c2": None, "o25": None, "u25": None},
    {"liga": "Premier League", "fecha": pd.Timestamp("2026-11-28"), "home": "Arsenal", "away": "Chelsea", "c1": None, "cx": None, "c2": None, "o25": None, "u25": None},
])
llamadas.clear()
pin = op.cuotas_pinnacle(prox, ahora)
assert set(pin) == {0, 1}, pin.keys()               # Cruzeiro no viene en la respuesta: no se inventa
assert [c[0] for c in llamadas] == ["/odds-by-tournaments", "/participants"], llamadas  # catálogo en caché; Premier fuera de rango
assert llamadas[0][1]["tournamentIds"] == "325"
# 5) presupuesto: no pasa del límite diario ni mensual
p2 = op.Presupuesto(ahora)
usadas = p2.u["usadas_mes"]
assert usadas == 4, usadas
p2.u["usadas_mes"] = op.PRESUPUESTO_MES
assert not p2.puede()
llamadas.clear()
assert set(op.cuotas_pinnacle(prox, ahora)) == {0, 1}
assert [c[0] for c in llamadas] == ["/odds-by-tournaments"], llamadas
# 6) sin clave no hace nada
os.environ["ODDSPAPI_KEY"] = ""
assert op.cuotas_pinnacle(prox, ahora) == {}

# 7) libro: liquida con resultados de selecciones, aunque la fuente invierta local y visita
lib = {"bankroll_inicial": 100, "apuestas": [
    {"id": "a", "fecha": "2026-11-12", "liga": "Selecciones", "local": "Benin", "visita": "Central African Republic",
     "seleccion": "Más de 2.5", "cuota": 2.11, "stake": 3.0, "estado": "pendiente", "resultado": "", "ganancia": 0.0},
    {"id": "b", "fecha": "2026-11-13", "liga": "Selecciones", "local": "Moldova", "visita": "Kazakhstan",
     "seleccion": "Visita", "cuota": 2.86, "stake": 1.0, "estado": "pendiente", "resultado": "", "ganancia": 0.0},
    {"id": "c", "fecha": "2026-11-13", "liga": "Selecciones", "local": "Mali", "visita": "Rwanda",
     "seleccion": "Menos de 2.5", "cuota": 1.66, "stake": 2.5, "estado": "pendiente", "resultado": "", "ganancia": 0.0},
]}
res = pd.DataFrame([
    {"liga": "Selecciones", "fecha": pd.Timestamp("2026-11-12"), "home": "Benin", "away": "Central African Republic", "hg": 2.0, "ag": 1.0},
    {"liga": "Selecciones", "fecha": pd.Timestamp("2026-11-13"), "home": "Kazakhstan", "away": "Moldova", "hg": 2.0, "ag": 0.0},
])
libro.liquidar(lib, res)
a, b, c = lib["apuestas"]
assert a["estado"] == "ganada" and a["resultado"] == "2-1" and a["ganancia"] == round(3 * 1.11, 2)
assert b["estado"] == "ganada" and b["resultado"] == "0-2", b   # invertido: Kazakhstan (visita) ganó
assert c["estado"] == "pendiente"                                 # sin resultado: sigue pendiente
print("Todas las pruebas de OddsPapi y del libro pasaron.")
