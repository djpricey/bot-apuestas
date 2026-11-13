"""Análisis por datos: forma reciente de cada equipo + modelo -> "lo mejor para apostar" en cada partido.

La cuota de la casa NO decide nada aquí: solo se usa al final para decir si paga lo suficiente.
"""
import pandas as pd

N = 10            # últimos N partidos de cada equipo
MIN_PARTIDOS = 6  # con menos, no se recomienda
UMBRAL = 0.62     # el modelo y los datos deben estar ambos por encima


def forma(d, equipo, antes):
    """Resumen de los últimos N partidos de un equipo (cualquier condición)."""
    m = d[((d["home"] == equipo) | (d["away"] == equipo)) & (d["fecha"] < antes)].sort_values("fecha").tail(N)
    if m.empty:
        return None
    gf = m.apply(lambda r: r["hg"] if r["home"] == equipo else r["ag"], axis=1)
    gc = m.apply(lambda r: r["ag"] if r["home"] == equipo else r["hg"], axis=1)
    tot = gf + gc
    rival = m.apply(lambda r: r["away"] if r["home"] == equipo else r["home"], axis=1)
    return {
        "n": int(len(m)), "desde": m["fecha"].min().strftime("%Y-%m-%d"),
        "g": int((gf > gc).sum()), "e": int((gf == gc).sum()), "p": int((gf < gc).sum()),
        "gf": round(float(gf.mean()), 2), "gc": round(float(gc.mean()), 2),
        "o15": round(float((tot >= 2).mean()), 2), "o25": round(float((tot >= 3).mean()), 2),
        "u35": round(float((tot <= 3).mean()), 2),
        "btts": round(float(((gf > 0) & (gc > 0)).mean()), 2),
        "marco": round(float((gf > 0).mean()), 2), "cero": round(float((gc == 0).mean()), 2),
        # marcador tal como se publica: fecha, local, goles, visitante (sin voltear)
        "ultimos": [f"{r.fecha.strftime('%d/%m/%y')} {r.home} {int(r.hg)}-{int(r.ag)} {r.away}" for r in m.itertuples()][::-1],
    }


def h2h(d, a, b, antes, n=5):
    m = d[(((d["home"] == a) & (d["away"] == b)) | ((d["home"] == b) & (d["away"] == a))) & (d["fecha"] < antes)]
    m = m.sort_values("fecha").tail(n)
    return [f"{r.fecha.strftime('%Y')} {r.home} {int(r.hg)}-{int(r.ag)} {r.away}" for r in m.itertuples()][::-1]


def recomendar(local, visita, fl, fv, pr):
    """Cruza modelo (pr) con datos de forma (fl, fv). Devuelve las mejores opciones y su respaldo."""
    if not fl or not fv or min(fl["n"], fv["n"]) < MIN_PARTIDOS:
        return [], "Pocos partidos recientes de algún equipo: sin recomendación."
    nl, nv = fl["n"], fv["n"]
    pct = lambda x: f"{round(x * 100)} %"
    c = []

    def add(sel, p_mod, p_dat, por):
        c.append({"seleccion": sel, "prob_modelo": round(p_mod, 3), "prob_datos": round(p_dat, 3),
                  "prob": round(min(p_mod, p_dat), 3), "cuota_minima": round(1.04 / min(p_mod, p_dat), 2), "por": por})

    p1, px, p2 = pr["p1"], pr["px"], pr["p2"]
    add(f"Gana {local}", p1, (fl["g"] / nl + fv["p"] / nv) / 2,
        f"{local} ganó {fl['g']} de {nl}; {visita} perdió {fv['p']} de {nv}")
    add(f"Gana {visita}", p2, (fv["g"] / nv + fl["p"] / nl) / 2,
        f"{visita} ganó {fv['g']} de {nv}; {local} perdió {fl['p']} de {nl}")
    add(f"{local} o empate", p1 + px, (1 - fl["p"] / nl + 1 - fv["g"] / nv) / 2,
        f"{local} perdió solo {fl['p']} de {nl}; {visita} ganó {fv['g']} de {nv}")
    add(f"{visita} o empate", p2 + px, (1 - fv["p"] / nv + 1 - fl["g"] / nl) / 2,
        f"{visita} perdió solo {fv['p']} de {nv}; {local} ganó {fl['g']} de {nl}")
    add("Más de 1.5 goles", pr["over15"], (fl["o15"] + fv["o15"]) / 2,
        f"Más de 1.5 en {pct(fl['o15'])} de los de {local} y {pct(fv['o15'])} de los de {visita}")
    add("Más de 2.5 goles", pr["over25"], (fl["o25"] + fv["o25"]) / 2,
        f"Más de 2.5 en {pct(fl['o25'])} de los de {local} y {pct(fv['o25'])} de los de {visita}")
    add("Menos de 2.5 goles", 1 - pr["over25"], (1 - fl["o25"] + 1 - fv["o25"]) / 2,
        f"Menos de 2.5 en {pct(1 - fl['o25'])} de los de {local} y {pct(1 - fv['o25'])} de los de {visita}")
    add("Menos de 3.5 goles", pr["under35"], (fl["u35"] + fv["u35"]) / 2,
        f"Menos de 3.5 en {pct(fl['u35'])} de los de {local} y {pct(fv['u35'])} de los de {visita}")
    add("Ambos marcan: sí", pr["btts"], (fl["btts"] + fv["btts"]) / 2,
        f"Ambos marcaron en {pct(fl['btts'])} de los de {local} y {pct(fv['btts'])} de los de {visita}")
    add("Ambos marcan: no", 1 - pr["btts"], (1 - fl["btts"] + 1 - fv["btts"]) / 2,
        f"{visita} no marcó en {pct(1 - fv['marco'])} de sus partidos; {local} no recibió gol en {pct(fl['cero'])}")
    buenas = [x for x in c if x["prob_modelo"] >= UMBRAL and x["prob_datos"] >= UMBRAL]
    # de las respaldadas, primero las que más dicen (menos obvias): cuota mínima más alta
    buenas.sort(key=lambda x: -x["cuota_minima"])
    # no repetir la misma idea (p. ej. "Gana X" y "X o empate"): una por familia
    fam, out = set(), []
    for x in buenas:
        f = "1x2" if ("Gana" in x["seleccion"] or "empate" in x["seleccion"]) else x["seleccion"].split(" ")[0] + ("btts" if "Ambos" in x["seleccion"] else "")
        f = "goles" if "goles" in x["seleccion"] else f
        if f in fam:
            continue
        fam.add(f)
        out.append(x)
    nota = "" if out else "Los datos y el modelo no coinciden en nada con suficiente fuerza: no apostar."
    return out[:3], nota
