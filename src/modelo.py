"""Modelo de Poisson con decaimiento temporal (estilo Dixon-Coles).

Cada equipo tiene una fuerza de ataque y una de defensa; cada liga, una ventaja
de local. Se ajusta con TODOS los partidos jugados de la liga, dando más peso a
los recientes. Se re-ajusta cada día con los resultados nuevos.
"""
import math
import numpy as np
import pandas as pd

from .config import RHO

MAX_GOLES = 10
PSEUDO = 4.0  # partidos "imaginarios" de promedio para equipos con pocos datos


def ajustar(partidos, fecha_ref, xi, iteraciones=60):
    """Devuelve los parámetros de una liga usando partidos anteriores a fecha_ref."""
    d = partidos[partidos["fecha"] < fecha_ref]
    if len(d) < 30:
        return None
    dias = (fecha_ref - d["fecha"]).dt.days.to_numpy(dtype=float)
    w = np.exp(-xi * dias)
    equipos = sorted(set(d["home"]) | set(d["away"]))
    idx = {e: i for i, e in enumerate(equipos)}
    h = d["home"].map(idx).to_numpy()
    a = d["away"].map(idx).to_numpy()
    hg = d["hg"].to_numpy(dtype=float)
    ag = d["ag"].to_numpy(dtype=float)
    neu = d["neutral"].fillna(False).astype(bool).to_numpy() if "neutral" in d.columns else np.zeros(len(d), bool)
    if "peso" in d.columns:
        w = w * d["peso"].fillna(1.0).to_numpy(dtype=float)
    n = len(equipos)
    att = np.ones(n)
    de = np.ones(n)
    media = (np.sum(w * (hg + ag)) / (2 * np.sum(w))) or 1.3
    home, away = 1.15, 0.87
    for _ in range(iteraciones):
        g = (home * away) ** 0.5  # cancha neutral: ni ventaja ni desventaja
        hf = np.where(neu, g, home)
        af = np.where(neu, g, away)
        # ataque
        num = np.bincount(h, w * hg, n) + np.bincount(a, w * ag, n)
        den = np.bincount(h, w * hf * de[a] * media, n) + np.bincount(a, w * af * de[h] * media, n)
        att = (num + PSEUDO) / (den + PSEUDO)
        att /= att.mean()
        # defensa (goles concedidos)
        num = np.bincount(a, w * hg, n) + np.bincount(h, w * ag, n)
        den = np.bincount(a, w * hf * att[h] * media, n) + np.bincount(h, w * af * att[a] * media, n)
        de = (num + PSEUDO) / (den + PSEUDO)
        de /= de.mean()
        # ventaja de local
        cn = ~neu
        if cn.sum() > 20:
            home = np.sum(w[cn] * hg[cn]) / max(np.sum(w[cn] * att[h[cn]] * de[a[cn]] * media), 1e-9)
            away = np.sum(w[cn] * ag[cn]) / max(np.sum(w[cn] * att[a[cn]] * de[h[cn]] * media), 1e-9)
    peso = np.bincount(h, w, n) + np.bincount(a, w, n)
    return {"idx": idx, "att": att, "de": de, "home": float(home), "away": float(away), "media": float(media), "peso": peso}


def _tau(x, y, l, m, rho):
    if x == 0 and y == 0:
        return 1 - l * m * rho
    if x == 0 and y == 1:
        return 1 + l * rho
    if x == 1 and y == 0:
        return 1 + m * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


def goles_esperados(p, local, visita, neutral=False):
    i, j = p["idx"].get(local), p["idx"].get(visita)
    al = p["att"][i] if i is not None else 1.0
    dl = p["de"][i] if i is not None else 1.0
    av = p["att"][j] if j is not None else 1.0
    dv = p["de"][j] if j is not None else 1.0
    hf, af = p["home"], p.get("away", 1.0)
    if neutral:
        hf = af = (hf * af) ** 0.5
    lam = p["media"] * hf * al * dv
    mu = p["media"] * af * av * dl
    conocidos = (i is not None) and (j is not None)
    return lam, mu, conocidos


def probabilidades(lam, mu, rho=RHO):
    k = np.arange(MAX_GOLES + 1)
    fact = np.array([math.factorial(int(x)) for x in k], dtype=float)
    ph = np.exp(-lam) * lam ** k / fact
    pa = np.exp(-mu) * mu ** k / fact
    M = np.outer(ph, pa)
    for x in (0, 1):
        for y in (0, 1):
            M[x, y] *= _tau(x, y, lam, mu, rho)
    M /= M.sum()
    p1 = float(np.tril(M, -1).sum())
    px = float(np.trace(M))
    p2 = float(np.triu(M, 1).sum())
    tot = np.add.outer(k, k)
    over25 = float(M[tot >= 3].sum())
    btts = float(M[1:, 1:].sum())
    i, j = np.unravel_index(np.argmax(M), M.shape)
    return {"p1": p1, "px": px, "p2": p2, "over25": over25, "btts": btts,
            "marcador": f"{i}-{j}", "lam": float(lam), "mu": float(mu)}


def implicitas(c1, cx, c2):
    """Probabilidades del mercado sin margen (proporcional)."""
    try:
        v = np.array([1 / float(c1), 1 / float(cx), 1 / float(c2)])
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    if not np.all(np.isfinite(v)) or np.any(v <= 0):
        return None
    return v / v.sum()


def logloss(p, res):
    k = {"H": 0, "D": 1, "A": 2}[res]
    return -math.log(max(p[k], 1e-9))


def resultado(hg, ag):
    return "H" if hg > ag else ("A" if hg < ag else "D")
