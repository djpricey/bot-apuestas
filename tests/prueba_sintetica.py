"""Prueba sin internet: genera ligas falsas con fuerzas conocidas y corre todo el flujo."""
import math, sys, os
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import src.main as M
from src.modelo import probabilidades

rng = np.random.default_rng(7)

def liga_falsa(nombre, n=18, dias=700):
    att = rng.normal(0, 0.25, n); de = rng.normal(0, 0.2, n)
    eq = [f"{nombre[:3]}{i}" for i in range(n)]
    filas, prox = [], []
    hoy = pd.Timestamp(M.datetime.now(M.TZ).date())
    for d in range(dias, -8, -3):
        fecha = hoy - pd.Timedelta(days=d)
        perm = rng.permutation(n)
        for k in range(0, n, 2):
            i, j = perm[k], perm[k+1]
            lam = math.exp(0.25 + 0.2 + att[i] - de[j]); mu = math.exp(0.2 + att[j] - de[i])
            pr = probabilidades(lam, mu, 0)
            c = [1 / (pr["p1"] * 1.05), 1 / (pr["px"] * 1.05), 1 / (pr["p2"] * 1.05)]
            fila = {"home": eq[i], "away": eq[j], "fecha": fecha, "hora": "20:00", "liga": nombre,
                    "c1": c[0], "cx": c[1], "c2": c[2], "o25": 1/(pr["over25"]*1.05), "u25": 1/((1-pr["over25"])*1.05)}
            if fecha < hoy:
                filas.append({**fila, "hg": rng.poisson(lam), "ag": rng.poisson(mu)})
            else:
                prox.append({**fila, "hg": np.nan, "ag": np.nan})
    return pd.DataFrame(filas), pd.DataFrame(prox)

R, P = zip(*[liga_falsa(x) for x in ["Liga Uno", "Liga Dos"]])
M.descargar_resultados = lambda: pd.concat(R, ignore_index=True)
M.descargar_proximos = lambda: pd.concat(P, ignore_index=True)
M.main()
