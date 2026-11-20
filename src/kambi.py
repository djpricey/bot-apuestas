"""Cuotas de BetPlay (plataforma Kambi), leídas de los mismos datos públicos que carga la página.

Sin claves ni sesión. Guarda una muestra en docs/data/kambi_probe.json para revisar qué mercados trae.
"""
import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
BASE = "https://us.offering-api.kambicdn.com/offering/v2018/betplay"
PARAMS = "lang=es_CO&market=CO&client_id=200&channel_id=1&useCombined=true"


def _get(path):
    sep = "&" if "?" in path else "?"
    url = f"{BASE}{path}{sep}{PARAMS}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json",
                                               "Origin": "https://betplay.com.co", "Referer": "https://betplay.com.co/"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def partidos_futbol():
    """Lista de partidos de fútbol próximos con su id de Kambi."""
    d = _get("/listView/football/all/all/all/matches.json")
    out = []
    for ev in d.get("events", []):
        e = ev.get("event", {})
        out.append({"id": e.get("id"), "nombre": e.get("name"), "local": e.get("homeName"), "visita": e.get("awayName"),
                    "inicio": e.get("start"), "grupo": e.get("group"), "ruta": [p.get("name") for p in e.get("path", [])]})
    return out


def mercados(event_id):
    """Todos los mercados de un partido: [{mercado, tipo, opciones:[(nombre, cuota, linea)]}]."""
    d = _get(f"/betoffer/event/{event_id}.json")
    res = []
    for bo in d.get("betOffers", []):
        crit = bo.get("criterion", {})
        ops = []
        for o in bo.get("outcomes", []):
            if o.get("odds"):
                ops.append((o.get("label") or o.get("participant"), o["odds"] / 1000, (o.get("line") or 0) / 1000 or None))
        if ops:
            res.append({"mercado": crit.get("label"), "tipo": (bo.get("betOfferType") or {}).get("name"), "opciones": ops})
    return res


def probar():
    out = {"ok": False}
    try:
        lista = partidos_futbol()
        out["partidos"] = len(lista)
        out["muestra"] = lista[:15]
        ejemplo = next((p for p in lista if p["grupo"] and ("Premier" in p["grupo"] or "Sudamericana" in p["grupo"])),
                       lista[0] if lista else None)
        if ejemplo:
            time.sleep(1)
            m = mercados(ejemplo["id"])
            out["ejemplo"] = {"partido": ejemplo["nombre"], "grupo": ejemplo["grupo"], "n_mercados": len(m),
                              "nombres_mercados": sorted({str(x["mercado"]) for x in m})[:80], "primeros": m[:8]}
        out["ok"] = bool(lista)
    except Exception as e:  # noqa: BLE001 - prueba: se registra el error
        out["error"] = repr(e)[:300]
    with open("docs/data/kambi_probe.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: out.get(k) for k in ("ok", "partidos", "error")}, ensure_ascii=False))
    if out.get("ejemplo"):
        print(out["ejemplo"]["partido"], out["ejemplo"]["n_mercados"], "mercados")


if __name__ == "__main__":
    probar()


# ------------------------------------------------------------------ detector de errores de cuota

EDGE_ERROR = 0.02  # BetPlay paga al menos 2 % más que la cuota justa de Pinnacle


def _parse(bo_list):
    """Mercados de un partido en forma estable (usa las etiquetas en inglés y los tipos de Kambi)."""
    res = []
    for bo in bo_list:
        crit = bo.get("criterion", {})
        en = (crit.get("englishLabel") or crit.get("label") or "").strip()
        for o in bo.get("outcomes", []):
            if not o.get("odds") or o.get("status", "OPEN") != "OPEN":
                continue
            res.append({"mercado": crit.get("label"), "en": en, "tipo": o.get("type"),
                        "op": o.get("label") or o.get("participant"),
                        "linea": (o["line"] / 1000) if o.get("line") is not None else None,
                        "cuota": round(o["odds"] / 1000, 2)})
    return res


def _justas(pin):
    """Probabilidades sin margen de Pinnacle para cada (mercado, tipo, línea)."""
    j = {}
    p = (pin or {}).get("p1x2")
    if p:
        j[("1x2", "OT_ONE", None)], j[("1x2", "OT_CROSS", None)], j[("1x2", "OT_TWO", None)] = p
        j[("dc", "OT_ONE_OR_CROSS", None)] = p[0] + p[1]
        j[("dc", "OT_CROSS_OR_TWO", None)] = p[1] + p[2]
        j[("dc", "OT_ONE_OR_TWO", None)] = p[0] + p[2]
    for linea, v in ((pin or {}).get("totales") or {}).items():
        if v.get("p_mas") is None or float(linea) % 1 != 0.5:
            continue  # solo líneas .5: las asiáticas (2.25, 3...) no se comparan con las de BetPlay
        j[("goles", "OT_OVER", float(linea))] = v["p_mas"]
        j[("goles", "OT_UNDER", float(linea))] = 1 - v["p_mas"]
    b = (pin or {}).get("btts")
    if b and b.get("p_si") is not None:
        j[("btts", "OT_YES", None)], j[("btts", "OT_NO", None)] = b["p_si"], 1 - b["p_si"]
    return j


def _clave(m):
    en = m["en"].lower()
    if en in ("full time", "match odds", "1x2"):
        return ("1x2", m["tipo"], None)
    if en == "double chance":
        return ("dc", m["tipo"], None)
    if en == "total goals":
        return ("goles", m["tipo"], m["linea"])
    if en == "both teams to score":
        return ("btts", m["tipo"], None)
    return None


def detectar(partidos, ahora, max_eventos=120):
    """Agrega a cada partido sus cuotas de BetPlay y devuelve la lista de errores de cuota contra Pinnacle."""
    from . import oddspapi as op  # usa el mismo emparejador de nombres
    try:
        lista = partidos_futbol()
    except Exception as e:  # noqa: BLE001
        print("  betplay: no se pudo leer la lista:", repr(e)[:150])
        return []
    limite = (ahora + timedelta(days=2)).isoformat()
    cand = [p for p in partidos if (p.get("inicio") or "") > ahora.isoformat(timespec="minutes")
            and (p.get("inicio") or "") < limite]
    errores, n = [], 0
    for p in cand:
        if n >= max_eventos:
            break
        mejor, puntaje = None, 0
        for e in lista:
            if not e.get("local") or not e.get("inicio"):
                continue
            ini = datetime.fromisoformat(e["inicio"].replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=-5)))
            if abs((ini.date() - datetime.fromisoformat(p["inicio"]).date()).days) > 1:
                continue
            s = min(op.parecido(p["local"], e["local"]), op.parecido(p["visita"], e["visita"]))
            if s > puntaje:
                mejor, puntaje = e, s
        if not mejor or puntaje < 0.72:
            continue
        try:
            time.sleep(0.4)
            crudo = _get(f"/betoffer/event/{mejor['id']}.json")
        except Exception as e:  # noqa: BLE001
            print("  betplay: falló", mejor["nombre"], repr(e)[:80])
            continue
        n += 1
        ms = _parse(crudo.get("betOffers", []))
        p["betplay"] = {"id": mejor["id"], "nombre": mejor["nombre"], "n_mercados": len({m["mercado"] for m in ms}),
                        "mercados": ms}
        just = _justas(p.get("pinnacle"))
        for m in ms:
            k = _clave(m)
            if not k or k not in just:
                continue
            pj = just[k]
            ev = pj * m["cuota"] - 1
            if ev >= EDGE_ERROR and pj >= 0.15:
                errores.append({"inicio": p["inicio"], "liga": p["liga"], "partido": f"{p['local']} vs {p['visita']}",
                                "mercado": m["mercado"], "seleccion": m["op"] + (f" {m['linea']}" if m["linea"] else ""),
                                "cuota_betplay": m["cuota"], "prob_pinnacle": round(pj, 3),
                                "cuota_justa": round(1 / pj, 2), "ventaja": round(ev, 3)})
    errores.sort(key=lambda x: -x["ventaja"])
    print(f"  betplay: {len(lista)} partidos en BetPlay, {n} unidos y revisados, {len(errores)} errores de cuota")
    return errores
