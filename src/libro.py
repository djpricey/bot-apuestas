"""Libro de apuestas FICTICIAS del bot: apuesta solo, se liquida solo y lleva su bankroll.

Nunca usa plata real. Sirve para medir si lo que el bot 'cree' que es valor
de verdad gana a la larga, y para que el usuario pueda copiar sus apuestas.
"""
import json
import os
from datetime import datetime

import pandas as pd

BANKROLL_INICIAL = 100.0  # unidades ficticias
MAX_STAKE = 3.0
MIN_STAKE = 0.5


def _cargar(ruta):
    try:
        with open(ruta, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"bankroll_inicial": BANKROLL_INICIAL, "apuestas": []}


def _gana(sel, hg, ag, local, visita):
    if sel in ("Local", f"Gana {local}"):
        return hg > ag
    if sel in ("Visita", f"Gana {visita}"):
        return ag > hg
    if sel == "Empate":
        return hg == ag
    if sel.startswith("Más de 2.5"):
        return hg + ag >= 3
    if sel.startswith("Menos de 2.5"):
        return hg + ag <= 2
    return None


def liquidar(libro, resultados):
    for a in libro["apuestas"]:
        if a["estado"] != "pendiente":
            continue
        f = pd.Timestamp(a["fecha"])
        m = resultados[(resultados["liga"] == a["liga"]) & (resultados["home"] == a["local"]) &
                       (resultados["away"] == a["visita"]) & ((resultados["fecha"] - f).abs() <= pd.Timedelta(days=2))]
        if m.empty:
            continue
        r = m.iloc[0]
        g = _gana(a["seleccion"], float(r["hg"]), float(r["ag"]), a["local"], a["visita"])
        if g is None:
            continue
        a["resultado"] = f"{int(r['hg'])}-{int(r['ag'])}"
        a["estado"] = "ganada" if g else "perdida"
        a["ganancia"] = round(a["stake"] * (a["cuota"] - 1), 2) if g else -a["stake"]


def apostar(libro, partidos, ahora):
    ya = {a["id"] for a in libro["apuestas"]}
    nuevas = 0
    for p in partidos:
        inicio = p.get("inicio")
        if not inicio or datetime.fromisoformat(inicio) <= ahora:
            continue  # nunca apuesta un partido que ya empezó
        for v in p.get("valor", []):
            pid = f"{p['fecha']}|{p['liga']}|{p['local']}|{p['visita']}|{v['seleccion']}"
            if pid in ya:
                continue
            c, pr = float(v["cuota"]), float(v["prob"])
            kelly = (pr * c - 1) / (c - 1)
            stake = max(MIN_STAKE, min(MAX_STAKE, round(kelly / 4 * 100 * 2) / 2))
            libro["apuestas"].append({
                "id": pid, "fecha": p["fecha"], "inicio": inicio, "liga": p["liga"],
                "local": p["local"], "visita": p["visita"], "seleccion": v["seleccion"],
                "cuota": c, "prob": pr, "ev": v["ev"], "stake": stake,
                "estado": "pendiente", "resultado": "", "ganancia": 0.0,
                "creada": ahora.isoformat(timespec="minutes"),
            })
            ya.add(pid)
            nuevas += 1
    return nuevas


def resumen(libro):
    cerr = [a for a in libro["apuestas"] if a["estado"] in ("ganada", "perdida")]
    gan = sum(a["ganancia"] for a in cerr)
    jug = sum(a["stake"] for a in cerr)
    return {
        "bankroll": round(libro["bankroll_inicial"] + gan, 2),
        "ganancia": round(gan, 2),
        "roi": round(gan / jug, 4) if jug else None,
        "cerradas": len(cerr),
        "ganadas": sum(1 for a in cerr if a["estado"] == "ganada"),
        "pendientes": sum(1 for a in libro["apuestas"] if a["estado"] == "pendiente"),
    }


def correr(ruta, partidos, resultados, ahora):
    libro = _cargar(ruta)
    liquidar(libro, resultados)
    n = apostar(libro, partidos, ahora)
    libro["resumen"] = resumen(libro)
    libro["actualizado"] = ahora.isoformat(timespec="minutes")
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(libro, fh, ensure_ascii=False, indent=1)
    print(f"Libro ficticio: {n} apuestas nuevas; bankroll {libro['resumen']['bankroll']} u.")
