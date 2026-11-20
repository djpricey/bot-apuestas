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
                sen = senales(p, k)
                ver, favor, contra = veredicto(pj, sen)
                errores.append({"inicio": p["inicio"], "liga": p["liga"], "partido": f"{p['local']} vs {p['visita']}",
                                "mercado": m["mercado"], "seleccion": m["op"] + (f" {m['linea']}" if m["linea"] else ""),
                                "cuota_betplay": m["cuota"], "prob_pinnacle": round(pj, 3),
                                "cuota_justa": round(1 / pj, 2), "ventaja": round(ev, 3),
                                "kelly": round(ev / (m["cuota"] - 1), 3), "idea": idea(k),
                                "senales": dict(sen), "veredicto": ver, "en_contra": contra})
    errores.sort(key=lambda x: -x["ventaja"])
    # Picks: solo errores respaldados por el análisis; una sola selección por partido y por idea (la de mejor Kelly)
    picks, vistos = [], set()
    for e in sorted([x for x in errores if x["veredicto"] == "respaldado"], key=lambda x: -x["kelly"]):
        clave = (e["partido"], e["idea"])
        if clave in vistos:
            continue
        vistos.add(clave)
        e["misma_idea"] = [x["seleccion"] for x in errores if (x["partido"], x["idea"]) == clave and x is not e]
        picks.append(e)
    detectar.picks = picks
    print(f"  betplay: {len(lista)} partidos en BetPlay, {n} unidos y revisados, {len(errores)} errores de cuota, {len(picks)} respaldados por el análisis")
    return errores


# ------------------------------------------------------------------ análisis: ¿qué dice el partido?

import math
import re as _re


def _poisson_tot(lam, k):
    """P(total de goles <= k) con Poisson de media lam."""
    return sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(int(k) + 1))


def _res(s):
    m = _re.match(r"\S+ (.+?) (\d+)-(\d+) (.+)$", s or "")
    return (m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)) if m else None


def _prob_de(partidos_lista, k, local, visita):
    """Proporción de partidos (lista de (L, gl, gv, V)) donde se cumple la selección k, vista desde local/visita."""
    if not partidos_lista:
        return None
    ok = 0
    for L, gl, gv, V in partidos_lista:
        tot = gl + gv
        fam, tipo, linea = k
        if fam == "goles":
            ok += (tot > linea) if tipo == "OT_OVER" else (tot < linea)
        elif fam == "btts":
            ok += (gl > 0 and gv > 0) if tipo == "OT_YES" else not (gl > 0 and gv > 0)
        else:
            # resultado desde el punto de vista del equipo "local" del partido analizado
            if L == local or V == visita:
                g1, g2 = (gl, gv) if L == local else (gv, gl)
            elif V == local or L == visita:
                g1, g2 = (gv, gl) if V == local else (gl, gv)
            else:
                continue
            r = "1" if g1 > g2 else "X" if g1 == g2 else "2"
            quiere = {"OT_ONE": "1", "OT_CROSS": "X", "OT_TWO": "2", "OT_ONE_OR_CROSS": "1X",
                      "OT_CROSS_OR_TWO": "X2", "OT_ONE_OR_TWO": "12"}.get(tipo, "")
            ok += r in quiere
    return ok / len(partidos_lista)


def senales(p, k):
    """Tres miradas independientes del mercado k: modelo del bot, rachas local-en-casa/visita-fuera y cruces directos."""
    out = []
    fam, tipo, linea = k
    # 1) modelo del bot
    lam, mu = p.get("goles_local"), p.get("goles_visita")
    if fam == "goles" and lam and mu:
        pu = _poisson_tot(lam + mu, math.floor(linea))
        out.append(("modelo", round(1 - pu if tipo == "OT_OVER" else pu, 3)))
    elif fam == "btts" and p.get("btts") is not None:
        out.append(("modelo", p["btts"] if tipo == "OT_YES" else 1 - p["btts"]))
    elif fam in ("1x2", "dc") and p.get("p1") is not None:
        m = {"OT_ONE": p["p1"], "OT_CROSS": p["px"], "OT_TWO": p["p2"], "OT_ONE_OR_CROSS": p["p1"] + p["px"],
             "OT_CROSS_OR_TWO": p["px"] + p["p2"], "OT_ONE_OR_TWO": p["p1"] + p["p2"]}.get(tipo)
        if m is not None:
            out.append(("modelo", round(m, 3)))
    # 2) rachas: el local en casa y el visitante fuera
    f = p.get("forma") or {}
    casa = [r for r in map(_res, (f.get("local") or {}).get("ultimos", [])) if r and r[0] == p["local"]]
    fuera = [r for r in map(_res, (f.get("visita") or {}).get("ultimos", [])) if r and r[3] == p["visita"]]
    if len(casa) >= 3 and len(fuera) >= 3:
        a, b = _prob_de(casa, k, p["local"], p["visita"]), _prob_de(fuera, k, p["local"], p["visita"])
        if a is not None and b is not None:
            out.append(("rachas", round((a + b) / 2, 3)))
    # 3) cruces directos (últimos enfrentamientos)
    h = [r for r in map(_res, p.get("h2h") or []) if r]
    if len(h) >= 3:
        v = _prob_de(h, k, p["local"], p["visita"])
        if v is not None:
            out.append(("cruces", round(v, 3)))
    return out


def veredicto(pj, sen):
    """Respaldado solo si al menos 2 miradas apuntan al mismo lado que la apuesta y ninguna va claramente en contra."""
    favor = [n for n, v in sen if v >= pj - 0.02]
    contra = [n for n, v in sen if v <= pj - 0.08]
    if len(favor) >= 2 and not contra:
        return "respaldado", favor, contra
    if contra:
        return "en contra", favor, contra
    return "sin datos suficientes", favor, contra


def idea(k):
    """Agrupa selecciones que son la misma apuesta (p. ej. más de 2.5 y más de 3.5)."""
    fam, tipo, _ = k
    if fam in ("1x2", "dc"):
        return "local" if tipo in ("OT_ONE", "OT_ONE_OR_CROSS") else "visita" if tipo in ("OT_TWO", "OT_CROSS_OR_TWO") else "otro"
    return f"{fam}-{tipo}"


# ------------------------------------------------------------------ mercados de estadísticas (todos los partidos de BetPlay)

VAR_FACTOR = {"corners": 1.5, "tarjetas": 1.4, "tiros": 1.8, "tiros_puerta": 1.3, "atajadas": 1.2, "faltas": 1.4}


def _nb_cdf(k, mu, f):
    """P(X <= k) con binomial negativa de media mu y varianza f*mu (f<=1 → Poisson)."""
    k = int(math.floor(k))
    if mu <= 0:
        return 1.0
    if f <= 1.0001:
        return sum(math.exp(-mu) * mu ** i / math.factorial(i) for i in range(k + 1))
    p = 1 / f
    r = mu * p / (1 - p)
    tot, term = 0.0, p ** r
    for i in range(k + 1):
        if i > 0:
            term *= (r + i - 1) / i * (1 - p)
        tot += term
    return min(tot, 1.0)


def _buscar_equipo(nombre, est, liga=None):
    from . import oddspapi as op
    mejor, s_mejor = None, 0
    ligas = [liga] if liga in est else list(est)
    for lg in ligas:
        for eq in est[lg]:
            s = op.parecido(nombre, eq)
            if s > s_mejor:
                mejor, s_mejor = (lg, eq), s
    return mejor if s_mejor >= 0.8 else None


def _esperados(sl, sv):
    """Valores esperados por equipo combinando lo que hace cada uno y lo que concede el rival."""
    def m(a, b):
        xs = [x for x in (a, b) if x is not None]
        return sum(xs) / len(xs) if xs else None
    e = {}
    for c in ("corners", "tarjetas", "tiros", "tiros_puerta", "faltas", "goles"):
        e[c + "_l"] = m(sl.get(c), sv.get(c + "_contra"))
        e[c + "_v"] = m(sv.get(c), sl.get(c + "_contra"))
    if e["tiros_puerta_v"] is not None and e["goles_v"] is not None:
        e["atajadas_l"] = max(e["tiros_puerta_v"] - e["goles_v"], 0.3)  # paradas del portero local
    if e["tiros_puerta_l"] is not None and e["goles_l"] is not None:
        e["atajadas_v"] = max(e["tiros_puerta_l"] - e["goles_l"], 0.3)
    return e


def _tipo_stat(en, local_bp, visita_bp):
    """('corners', 'l'|'v'|'t') a partir de la etiqueta en inglés de Kambi; None si no es de estadísticas a tiempo completo."""
    from . import oddspapi as op
    en0 = en.replace(" (Settled using Opta data)", "").strip()
    if any(x in en0 for x in ("Half", "Interval", "0:00", "Most", "Next", "Handicap", "Player", "To ")):
        return None
    bases = [("Total Shots on Target", "tiros_puerta"), ("Total Shots", "tiros"), ("Total Corners", "corners"),
             ("Total Cards", "tarjetas"), ("Goalkeeper Saves", "atajadas"), ("Total Fouls conceded", "faltas")]
    for pref, clave in bases:
        if en0 == pref:
            return clave, "t"
        if en0.startswith(pref):
            resto = en0[len(pref):].replace(" by ", " ").replace(" By ", " ").strip(" -")
            if not resto:
                return clave, "t"
            sl, sv = op.parecido(resto, local_bp), op.parecido(resto, visita_bp)
            if max(sl, sv) < 0.6:
                return None
            return clave, "l" if sl >= sv else "v"
    return None


def escanear_estadisticas(ahora, est, horas=40, max_eventos=180, ev_min=0.05):
    """Recorre los partidos de BetPlay de las próximas `horas` con equipos en `est` y compara cada línea de
    córners, tarjetas, tiros, tiros a puerta, atajadas y faltas con lo esperado por las estadísticas."""
    try:
        lista = partidos_futbol()
    except Exception as e:  # noqa: BLE001
        print("  stats-betplay: no se pudo leer la lista:", repr(e)[:120])
        return [], 0
    fin = ahora + timedelta(hours=horas)
    out, n = [], 0
    for e in lista:
        if n >= max_eventos or not e.get("local") or not e.get("inicio"):
            continue
        ini = datetime.fromisoformat(e["inicio"].replace("Z", "+00:00"))
        if ini <= ahora or ini > fin:
            continue
        el, ev = _buscar_equipo(e["local"], est), _buscar_equipo(e["visita"], est)
        if not el or not ev or el[0] != ev[0]:
            continue
        sl, sv = est[el[0]][el[1]]["casa"], est[ev[0]][ev[1]]["fuera"]
        if sl.get("n", 0) < 4 or sv.get("n", 0) < 4:
            continue
        try:
            time.sleep(0.3)
            ms = _parse(_get(f"/betoffer/event/{e['id']}.json").get("betOffers", []))
        except Exception:  # noqa: BLE001
            continue
        n += 1
        esp = _esperados(sl, sv)
        hora = ini.astimezone(timezone(timedelta(hours=-5))).strftime("%Y-%m-%d %H:%M")
        for m in ms:
            t = _tipo_stat(m["en"], e["local"], e["visita"])
            if not t or m["linea"] is None or m["tipo"] not in ("OT_OVER", "OT_UNDER"):
                continue
            clave, lado = t
            mu = (esp.get(clave + "_l") or 0) + (esp.get(clave + "_v") or 0) if lado == "t" else esp.get(f"{clave}_{lado}")
            if not mu:
                continue
            pu = _nb_cdf(m["linea"], mu, VAR_FACTOR[clave])
            pj = 1 - pu if m["tipo"] == "OT_OVER" else pu
            evv = pj * m["cuota"] - 1
            if evv >= ev_min and pj >= 0.35:
                out.append({"inicio": hora, "liga": el[0], "partido": e["nombre"], "mercado": m["mercado"],
                            "seleccion": f"{m['op']} {m['linea']}", "cuota": m["cuota"], "esperado": round(mu, 2),
                            "prob": round(pj, 3), "cuota_minima": round(1.04 / pj, 2), "ventaja": round(evv, 3),
                            "kelly": round(evv / (m["cuota"] - 1), 3), "clave": clave, "lado": lado,
                            "datos": {"local_casa": {k: sl.get(k) for k in (clave, clave + "_contra", "n")},
                                      "visita_fuera": {k: sv.get(k) for k in (clave, clave + "_contra", "n")}}})
    # una sola línea por partido/mercado/lado/dirección: la de mejor Kelly
    mejores = {}
    for x in sorted(out, key=lambda x: -x["kelly"]):
        k = (x["partido"], x["clave"], x["lado"], x["seleccion"].split()[0])
        mejores.setdefault(k, x)
    res = sorted(mejores.values(), key=lambda x: -x["ventaja"])
    print(f"  stats-betplay: {n} partidos de BetPlay con estadísticas revisados, {len(res)} líneas con ventaja ≥ {ev_min:.0%}")
    return res, n
