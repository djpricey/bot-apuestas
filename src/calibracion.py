"""Calibración de los picks liquidados.

Uso: python -m src.calibracion RUTA/data.json
Escribe docs/calibracion.md con: acierto real vs probabilidad prometida,
por tipo de mercado y por tramo de cuota, más el balance en stakes.
La corrida diaria lo lee antes de analizar para ajustar probabilidades.
"""
import json, sys, re
from collections import defaultdict


def tipo(p):
    t = (p.get("mercado", "") + " " + p.get("seleccion", "")).lower()
    if "córner" in t or "corner" in t:
        base = "córners"
    elif "tarjeta" in t:
        base = "tarjetas"
    elif "ambos marcan" in t:
        base = "ambos marcan"
    elif "gol" in t:
        base = "goles"
    elif "empate" in t or "gana" in t or "1x2" in t or "doble" in t or "resultado" in t:
        base = "resultado"
    else:
        base = "otros"
    lado = ""
    if base in ("córners", "tarjetas", "goles"):
        lado = " más" if re.search(r"\bmás\b", t) else " menos" if "menos" in t else ""
    return base + lado


def tramo(c):
    return "1.25-1.60" if c < 1.6 else "1.60-2.20" if c < 2.2 else "2.20+"


def main(path):
    d = json.load(open(path))
    grupos = defaultdict(list)
    filas = []
    for r in d.get("reportes", []):
        for p in r.get("valor", []) + r.get("mas_probables", []):
            est = p.get("estado")
            c = p.get("cuota_ref") or 0
            pr = p.get("prob")
            if est not in ("ganada", "perdida") or c <= 1 or not pr:
                continue
            g = 1 if est == "ganada" else 0
            s = p.get("stake") or 1
            u = s * (c - 1) if g else -s
            fila = (r["fecha"], tipo(p), tramo(c), pr, g, s, u)
            filas.append(fila)
            grupos["TOTAL"].append(fila)
            grupos["mercado: " + fila[1]].append(fila)
            grupos["cuota " + fila[2]].append(fila)
    out = ["# Calibración (generado por src/calibracion.py)", "",
           f"Picks liquidados con probabilidad: {len(filas)}. Con menos de ~200 nada es concluyente; con menos de 20 en un grupo, solo es una pista.", "",
           "| Grupo | n | Prometido | Real | Diferencia | Stakes | Balance | ROI |",
           "|---|---|---|---|---|---|---|---|"]
    for k in sorted(grupos, key=lambda k: (k != "TOTAL", k)):
        f = grupos[k]
        n = len(f)
        prom = sum(x[3] for x in f) / n
        real = sum(x[4] for x in f) / n
        st = sum(x[5] for x in f)
        bal = sum(x[6] for x in f)
        out.append(f"| {k} | {n} | {prom:.0%} | {real:.0%} | {real - prom:+.0%} | {st:.1f} | {bal:+.2f} | {bal / st:+.0%} |")
    out += ["", "## Cómo usarlo",
            "- Si un grupo con n ≥ 20 sale con 'Real' más de 8 puntos por debajo de 'Prometido', recorta esas probabilidades (o deja de recomendar ese mercado) y anótalo en notas_analista.md.",
            "- Si sale por encima con n ≥ 20, el modelo es conservador ahí: puede pesar más que el mercado (65/35).",
            "- Con n < 20, no cambies nada por esta tabla; úsala solo como alerta."]
    open("docs/calibracion.md", "w").write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1])
