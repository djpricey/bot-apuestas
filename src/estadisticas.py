"""Estadísticas por equipo (casa y fuera) para analizar tiros, tiros a puerta, atajadas, córners, tarjetas y faltas.

Fuente: football-data.co.uk (los mismos CSV del modelo). No es un modelo de apuestas: es la base de datos
para que el análisis no dependa de buscar cada número en la web.
"""
import json
import os

import pandas as pd

CAMPOS = {  # nombre: (columna del equipo cuando es local, columna del equipo cuando es visitante)
    "goles": ("hg", "ag"), "tiros": ("ti_l", "ti_v"), "tiros_puerta": ("tp_l", "tp_v"),
    "corners": ("co_l", "co_v"), "tarjetas": ("tj_l", "tj_v"), "faltas": ("fa_l", "fa_v"),
}


def _media(serie):
    s = pd.to_numeric(serie, errors="coerce").dropna()
    return round(float(s.mean()), 2) if len(s) else None


def _bloque(d, lado):
    """Promedios a favor y en contra de un equipo en sus partidos de casa (lado='l') o fuera (lado='v')."""
    out = {"n": int(len(d))}
    for nombre, (cl, cv) in CAMPOS.items():
        fav, con = (cl, cv) if lado == "l" else (cv, cl)
        out[nombre] = _media(d[fav])
        out[nombre + "_contra"] = _media(d[con])
    # atajadas del portero propio = tiros a puerta del rival - goles recibidos
    tp_r, gol_r = (d["tp_v"], d["ag"]) if lado == "l" else (d["tp_l"], d["hg"])
    out["atajadas"] = _media(pd.to_numeric(tp_r, errors="coerce") - pd.to_numeric(gol_r, errors="coerce"))
    tp_p, gol_p = (d["tp_l"], d["hg"]) if lado == "l" else (d["tp_v"], d["ag"])
    out["atajadas_rival"] = _media(pd.to_numeric(tp_p, errors="coerce") - pd.to_numeric(gol_p, errors="coerce"))
    return out


def por_equipo(df, hoy, ultimos=10, dias=400):
    df = df[df["fecha"] >= hoy - pd.Timedelta(days=dias)]
    res = {}
    for liga, d in df.groupby("liga"):
        eqs = {}
        for eq in sorted(set(d["home"]) | set(d["away"])):
            casa = d[d["home"] == eq].sort_values("fecha").tail(ultimos)
            fuera = d[d["away"] == eq].sort_values("fecha").tail(ultimos)
            if len(casa) + len(fuera) < 4:
                continue
            eqs[eq] = {"casa": _bloque(casa, "l"), "fuera": _bloque(fuera, "v"),
                       "ultimo": d[(d["home"] == eq) | (d["away"] == eq)]["fecha"].max().strftime("%Y-%m-%d")}
        if eqs:
            res[liga] = eqs
    return res


def arbitros(df, hoy, dias=730):
    d = df[(df["fecha"] >= hoy - pd.Timedelta(days=dias)) & df["arbitro"].notna()]
    out = {}
    for (liga, arb), g in d.groupby(["liga", "arbitro"]):
        if len(g) >= 5:
            out.setdefault(liga, {})[str(arb)] = {"n": int(len(g)), "tarjetas": _media(g["tj_l"] + g["tj_v"]),
                                                 "faltas": _media(g["fa_l"] + g["fa_v"])}
    return out


def generar(df, hoy, salida):
    """Escribe docs/data/estadisticas.json y devuelve el dict (liga -> equipo -> casa/fuera)."""
    if df is None or df.empty:
        return {}
    eq = por_equipo(df, hoy)
    datos = {"actualizado": hoy.strftime("%Y-%m-%d"), "fuente": "football-data.co.uk",
             "nota": "Promedios de los últimos 10 partidos en casa y 10 fuera. atajadas = tiros a puerta del rival - goles recibidos.",
             "equipos": eq, "arbitros": arbitros(df, hoy)}
    with open(os.path.join(salida, "estadisticas.json"), "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False)
    n = sum(len(v) for v in eq.values())
    print(f"  estadísticas: {n} equipos en {len(eq)} ligas (tiros, tiros a puerta, atajadas, córners, tarjetas, faltas)")
    return eq
