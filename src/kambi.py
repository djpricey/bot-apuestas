"""Cuotas de BetPlay (plataforma Kambi), leídas de los mismos datos públicos que carga la página.

Sin claves ni sesión. Guarda una muestra en docs/data/kambi_probe.json para revisar qué mercados trae.
"""
import json
import time
import urllib.request

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
