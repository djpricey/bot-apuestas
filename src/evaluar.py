"""Evaluación: compara al modelo contra el mercado, partido por partido.

Esto es lo que hace que el bot 'aprenda': cada día mide qué tan bien predijo,
elige solo el parámetro de olvido que mejor funcionó y guarda su récord.
"""
import numpy as np
import pandas as pd

from .modelo import ajustar, goles_esperados, probabilidades, implicitas, logloss, resultado
from .config import EDGE_MIN


def walk_forward(liga_df, xi, desde, paso_dias=7):
    """Predice cada partido desde 'desde' usando solo datos anteriores."""
    filas = []
    fechas = pd.date_range(desde, liga_df["fecha"].max() + pd.Timedelta(days=1), freq=f"{paso_dias}D")
    for f0 in fechas:
        f1 = f0 + pd.Timedelta(days=paso_dias)
        bloque = liga_df[(liga_df["fecha"] >= f0) & (liga_df["fecha"] < f1)]
        if bloque.empty:
            continue
        p = ajustar(liga_df, f0, xi)
        if p is None:
            continue
        for r in bloque.itertuples():
            lam, mu, ok = goles_esperados(p, r.home, r.away)
            if not ok:
                continue
            pr = probabilidades(lam, mu)
            filas.append({"fecha": r.fecha, "liga": r.liga, "home": r.home, "away": r.away,
                          "p1": pr["p1"], "px": pr["px"], "p2": pr["p2"], "over25": pr["over25"],
                          "c1": r.c1, "cx": r.cx, "c2": r.c2, "hg": r.hg, "ag": r.ag})
    return pd.DataFrame(filas)


def mejor_peso(pred):
    """Aprende cuánto confiar en el modelo frente al mercado (0 = solo mercado, 1 = solo modelo)."""
    filas = [(np.array([r.p1, r.px, r.p2]), implicitas(r.c1, r.cx, r.c2), resultado(r.hg, r.ag)) for r in pred.itertuples()]
    filas = [f for f in filas if f[1] is not None]
    if len(filas) < 80:
        return 0.0
    mejor, mejor_ll = 0.0, None
    for w in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0):
        ll = np.mean([logloss(w * pm + (1 - w) * mk, res) for pm, mk, res in filas])
        if mejor_ll is None or ll < mejor_ll - 1e-6:
            mejor, mejor_ll = w, ll
    return mejor


def metricas(pred, w=1.0):
    """Log-loss del modelo vs mercado, calibración y apuestas simuladas de valor."""
    if pred.empty:
        return {"n": 0}
    ll_m, ll_k, ll_ms, ll_c, n_k = [], [], [], [], 0
    apuestas, ganancia = 0, 0.0
    calib = np.zeros((10, 2))
    for r in pred.itertuples():
        res = resultado(r.hg, r.ag)
        pm = [r.p1, r.px, r.p2]
        ll_m.append(logloss(pm, res))
        k = {"H": 0, "D": 1, "A": 2}[res]
        for j, pj in enumerate(pm):
            b = min(int(pj * 10), 9)
            calib[b, 0] += pj
            calib[b, 1] += 1.0 if j == k else 0.0
        mk = implicitas(r.c1, r.cx, r.c2)
        if mk is not None:
            ll_k.append(logloss(mk, res))
            ll_ms.append(logloss(pm, res))
            n_k += 1
            cuotas = [r.c1, r.cx, r.c2]
            pc = w * np.array(pm) + (1 - w) * mk
            ll_c.append(logloss(pc, res))
            for j in range(3):
                ev = pc[j] * cuotas[j] - 1
                if ev >= EDGE_MIN and pc[j] >= 0.2:
                    apuestas += 1
                    ganancia += (cuotas[j] - 1) if j == k else -1
    cuenta = np.bincount(np.minimum((np.concatenate([pred[["p1", "px", "p2"]].to_numpy().ravel()]) * 10).astype(int), 9), minlength=10)
    calibracion = [{"rango": f"{i*10}-{i*10+10}%", "esperado": round(calib[i, 0] / cuenta[i], 3) if cuenta[i] else None,
                    "real": round(calib[i, 1] / cuenta[i], 3) if cuenta[i] else None, "n": int(cuenta[i])} for i in range(10)]
    return {
        "n": int(len(pred)),
        "logloss_modelo": round(float(np.mean(ll_m)), 4),
        "logloss_mercado": round(float(np.mean(ll_k)), 4) if ll_k else None,
        "logloss_modelo_mismos": round(float(np.mean(ll_ms)), 4) if ll_ms else None,
        "logloss_combinado": round(float(np.mean(ll_c)), 4) if ll_c else None,
        "peso_modelo": w,
        "n_con_cuotas": n_k,
        "apuestas_valor": apuestas,
        "roi_valor": round(ganancia / apuestas, 4) if apuestas else None,
        "calibracion": calibracion,
    }
