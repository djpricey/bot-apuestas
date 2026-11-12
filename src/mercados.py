"""Córners y tarjetas con datos reales (football-data.co.uk trae córners, tarjetas y árbitro por partido).

Cada equipo tiene una tasa "a favor" y una "en contra" (con más peso a lo reciente).
Se usa una binomial negativa (los córners varían más que una Poisson).
Antes de publicar, el modelo se pone a prueba contra el último año: solo se marca
como "respaldado" el mercado cuyo acierto real coincide con lo que prometía.
"""
import math
import numpy as np
import pandas as pd

XI = 0.002          # olvido por día
PSEUDO = 5.0        # partidos de promedio de liga para equipos con pocos datos
MIN_PARTIDOS = 8    # mínimo de partidos con estadística por equipo para publicar
LINEAS = {
    "corners_total": [8.5, 9.5, 10.5, 11.5],
    "corners_local": [3.5, 4.5, 5.5, 6.5],
    "corners_visita": [2.5, 3.5, 4.5, 5.5],
    "tarjetas_total": [2.5, 3.5, 4.5, 5.5],
}
NOMBRES = {"corners_total": "Córners totales", "corners_local": "Córners del local",
           "corners_visita": "Córners de la visita", "tarjetas_total": "Tarjetas totales"}
BINS = [0.5, 0.6, 0.7, 0.8, 1.01]


def _tasas(d, col_h, col_a, fecha_ref):
    """Tasas a favor y en contra por equipo, relativas al promedio de la liga (ajuste iterativo)."""
    d = d[(d["fecha"] < fecha_ref)].dropna(subset=[col_h, col_a])
    if len(d) < 60:
        return None
    w = np.exp(-XI * (fecha_ref - d["fecha"]).dt.days.to_numpy(float))
    eq = sorted(set(d["home"]) | set(d["away"]))
    ix = {e: i for i, e in enumerate(eq)}
    h, a = d["home"].map(ix).to_numpy(), d["away"].map(ix).to_numpy()
    xh, xa = d[col_h].to_numpy(float), d[col_a].to_numpy(float)
    bh, ba = np.sum(w * xh) / np.sum(w), np.sum(w * xa) / np.sum(w)
    n = len(eq)
    f, c = np.ones(n), np.ones(n)
    for _ in range(30):
        num = np.bincount(h, w * xh, n) + np.bincount(a, w * xa, n) + PSEUDO
        den = np.bincount(h, w * bh * c[a], n) + np.bincount(a, w * ba * c[h], n) + PSEUDO
        f = num / den
        num = np.bincount(a, w * xh, n) + np.bincount(h, w * xa, n) + PSEUDO
        den = np.bincount(a, w * bh * f[h], n) + np.bincount(h, w * ba * f[a], n) + PSEUDO
        c = num / den
    pj = np.bincount(h, minlength=n) + np.bincount(a, minlength=n)
    # dispersión: varianza/media del total (>1 = más variable que Poisson)
    lam_tot = bh * f[h] * c[a] + ba * f[a] * c[h]
    tot = xh + xa
    disp = max(1.0, float(np.sum(w * (tot - lam_tot) ** 2) / np.sum(w * lam_tot)))
    return {"ix": ix, "f": f, "c": c, "bh": bh, "ba": ba, "pj": pj, "disp": disp,
            "prom_favor": {e: (float(np.sum(xh[h == i]) + np.sum(xa[a == i])) / max(pj[i], 1)) for e, i in ix.items()},
            "prom_contra": {e: (float(np.sum(xa[h == i]) + np.sum(xh[a == i])) / max(pj[i], 1)) for e, i in ix.items()}}


def _arbitros(d, fecha_ref, t):
    """Factor de cada árbitro: tarjetas reales / tarjetas esperadas en sus partidos (con encogimiento)."""
    if "arbitro" not in d.columns or t is None:
        return {}
    d = d[(d["fecha"] < fecha_ref)].dropna(subset=["arbitro", "tj_l", "tj_v"])
    out = {}
    for ref, g in d.groupby("arbitro"):
        esp = sum(_esperado(t, r.home, r.away)[2] for r in g.itertuples())
        real = float((g["tj_l"] + g["tj_v"]).sum())
        media = esp / max(len(g), 1)
        out[ref] = {"factor": (real + 10 * media) / (esp + 10 * media) if esp else 1.0,
                    "partidos": int(len(g)), "promedio": round(real / len(g), 2)}
    return out


def _esperado(t, local, visita):
    i, j = t["ix"].get(local), t["ix"].get(visita)
    if i is None or j is None:
        return None, None, None
    l = t["bh"] * t["f"][i] * t["c"][j]
    v = t["ba"] * t["f"][j] * t["c"][i]
    return l, v, l + v


def p_mas(lam, linea, disp):
    """P(X > linea) con binomial negativa de media lam y varianza disp*lam."""
    k = int(math.floor(linea))
    if disp <= 1.0001:
        cdf = sum(math.exp(-lam) * lam ** x / math.factorial(x) for x in range(k + 1))
        return 1 - cdf
    r = lam / (disp - 1)
    p = r / (r + lam)
    cdf, term = 0.0, p ** r
    for x in range(k + 1):
        if x > 0:
            term *= (x - 1 + r) / x * (1 - p)
        cdf += term
    return 1 - cdf


def ajustar_liga(d, fecha_ref):
    tc = _tasas(d, "co_l", "co_v", fecha_ref) if "co_l" in d.columns else None
    tt = _tasas(d, "tj_l", "tj_v", fecha_ref) if "tj_l" in d.columns else None
    return {"corners": tc, "tarjetas": tt, "arbitros": _arbitros(d, fecha_ref, tt)}


def predecir(m, local, visita, arbitro=None):
    """Probabilidades de cada línea + los datos que las respaldan."""
    out = []
    tc, tt = m["corners"], m["tarjetas"]
    if tc:
        l, v, tot = _esperado(tc, local, visita)
        if l is not None and min(tc["pj"][tc["ix"][local]], tc["pj"][tc["ix"][visita]]) >= MIN_PARTIDOS:
            base = {"local_favor": round(tc["prom_favor"][local], 2), "local_contra": round(tc["prom_contra"][local], 2),
                    "visita_favor": round(tc["prom_favor"][visita], 2), "visita_contra": round(tc["prom_contra"][visita], 2),
                    "partidos_local": int(tc["pj"][tc["ix"][local]]), "partidos_visita": int(tc["pj"][tc["ix"][visita]])}
            for mk, lam, disp in (("corners_total", tot, tc["disp"]), ("corners_local", l, tc["disp"]), ("corners_visita", v, tc["disp"])):
                for ln in LINEAS[mk]:
                    out.append({"mercado": mk, "linea": ln, "esperado": round(lam, 2), "p_mas": round(p_mas(lam, ln, disp), 3), "datos": base})
    if tt:
        l, v, tot = _esperado(tt, local, visita)
        if l is not None and min(tt["pj"][tt["ix"][local]], tt["pj"][tt["ix"][visita]]) >= MIN_PARTIDOS:
            ref = m["arbitros"].get(arbitro) if arbitro else None
            fac = ref["factor"] if ref and ref["partidos"] >= 5 else 1.0
            base = {"local_tarjetas": round(tt["prom_favor"][local], 2), "visita_tarjetas": round(tt["prom_favor"][visita], 2),
                    "arbitro": arbitro, "arbitro_promedio": ref["promedio"] if ref else None,
                    "arbitro_partidos": ref["partidos"] if ref else 0}
            for ln in LINEAS["tarjetas_total"]:
                out.append({"mercado": "tarjetas_total", "linea": ln, "esperado": round(tot * fac, 2),
                            "p_mas": round(p_mas(tot * fac, ln, tt["disp"]), 3), "datos": base})
    return out


def _real(mk, r):
    return {"corners_total": r.co_l + r.co_v, "corners_local": r.co_l, "corners_visita": r.co_v,
            "tarjetas_total": r.tj_l + r.tj_v}[mk]


def backtest(d, desde, paso_dias=14):
    """Predice cada partido del último año usando solo datos anteriores. Devuelve una fila por línea."""
    filas = []
    fechas = pd.date_range(desde, d["fecha"].max() + pd.Timedelta(days=1), freq=f"{paso_dias}D")
    for ini, fin in zip(fechas[:-1], fechas[1:]):
        bloque = d[(d["fecha"] >= ini) & (d["fecha"] < fin)]
        if bloque.empty:
            continue
        m = ajustar_liga(d, ini)
        for r in bloque.itertuples():
            for p in predecir(m, r.home, r.away, getattr(r, "arbitro", None)):
                real = _real(p["mercado"], r)
                if pd.isna(real):
                    continue
                filas.append({"mercado": p["mercado"], "linea": p["linea"], "p_mas": p["p_mas"], "salio_mas": int(real > p["linea"])})
    return pd.DataFrame(filas)


def calibracion(bt):
    """Por mercado: lo que el modelo prometía frente a lo que pasó, por tramos de probabilidad del lado elegido."""
    res = {}
    if bt.empty:
        return res
    for mk, g in bt.groupby("mercado"):
        lado = np.where(g["p_mas"] >= 0.5, g["p_mas"], 1 - g["p_mas"])
        acierto = np.where(g["p_mas"] >= 0.5, g["salio_mas"], 1 - g["salio_mas"])
        tramos = []
        for lo, hi in zip(BINS[:-1], BINS[1:]):
            s = (lado >= lo) & (lado < hi)
            if s.sum() >= 30:
                tramos.append({"desde": lo, "hasta": min(hi, 1.0), "n": int(s.sum()),
                               "prometido": round(float(lado[s].mean()), 3), "real": round(float(acierto[s].mean()), 3)})
        brier = float(np.mean((g["p_mas"] - g["salio_mas"]) ** 2))
        base = g.groupby("linea")["salio_mas"].transform("mean")
        brier_base = float(np.mean((base - g["salio_mas"]) ** 2))
        altos = [t for t in tramos if t["desde"] >= 0.6]
        ok = (len(g) >= 300 and brier < brier_base and altos and
              all(t["real"] >= t["prometido"] - max(0.03, 2 * math.sqrt(t["prometido"] * (1 - t["prometido"]) / t["n"])) for t in altos))
        res[mk] = {"n": int(len(g)), "brier": round(brier, 4), "brier_sin_modelo": round(brier_base, 4),
                   "tramos": tramos, "respaldado": bool(ok)}
    return res


def ajuste_por_tramo(cal, mk, p):
    """Si el modelo exageraba en ese tramo, usa el acierto real del backtest en vez de lo prometido."""
    c = cal.get(mk)
    if not c:
        return p
    lado = max(p, 1 - p)
    for t in c["tramos"]:
        if t["desde"] <= lado < t["hasta"]:
            real = min(lado, t["real"])  # nunca sube la probabilidad, solo la baja
            return real if p >= 0.5 else 1 - real
    return p
