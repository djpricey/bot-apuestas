"""Corrida diaria: descarga, re-ajusta, se evalúa y publica probabilidades."""
import json
import glob
import os
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from .config import DIAS_HISTORIA, XI_CANDIDATOS, EDGE_MIN
from .datos import descargar_resultados, descargar_proximos, descargar_selecciones, leer_manual
from .modelo import ajustar, goles_esperados, probabilidades, implicitas, logloss, resultado
from .evaluar import walk_forward, metricas, mejor_peso
from .libro import correr as correr_libro
from zoneinfo import ZoneInfo

PESO_SIN_HISTORIA = 0.5  # cuando no hay cuotas pasadas para aprender, confía mitad y mitad

SALIDA = os.path.join(os.path.dirname(__file__), "..", "docs", "data")
TZ = timezone(timedelta(hours=-5))  # Colombia


def _r(x, n=3):
    try:
        if x is None or (isinstance(x, float) and not np.isfinite(x)):
            return None
        return round(float(x), n)
    except (TypeError, ValueError):
        return None


def elegir_xi(liga_df, hoy):
    """Prueba cada 'olvido' en los últimos 120 días y se queda con el mejor."""
    mejor, mejor_ll = XI_CANDIDATOS[1], None
    desde = hoy - pd.Timedelta(days=120)
    for xi in XI_CANDIDATOS:
        pred = walk_forward(liga_df, xi, desde, paso_dias=14)
        if len(pred) < 40:
            continue
        ll = np.mean([logloss([r.p1, r.px, r.p2], resultado(r.hg, r.ag)) for r in pred.itertuples()])
        if mejor_ll is None or ll < mejor_ll:
            mejor, mejor_ll = xi, ll
    return mejor


def calificar_en_vivo(resultados):
    """Busca los resultados de las predicciones guardadas en días anteriores."""
    filas = []
    for f in sorted(glob.glob(os.path.join(SALIDA, "predicciones", "*.json"))):
        with open(f, encoding="utf-8") as fh:
            preds = json.load(fh).get("partidos", [])
        for p in preds:
            fecha = pd.Timestamp(p["fecha"])
            m = resultados[(resultados["liga"] == p["liga"]) & (resultados["home"] == p["local"]) &
                           (resultados["away"] == p["visita"]) &
                           ((resultados["fecha"] - fecha).abs() <= pd.Timedelta(days=2))]
            if m.empty:
                continue
            r = m.iloc[0]
            filas.append({"fecha": p["fecha"], "liga": p["liga"], "home": p["local"], "away": p["visita"],
                          "p1": p["p1"], "px": p["px"], "p2": p["p2"], "over25": p["over25"],
                          "c1": p.get("c1"), "cx": p.get("cx"), "c2": p.get("c2"),
                          "hg": float(r["hg"]), "ag": float(r["ag"])})
    return pd.DataFrame(filas).drop_duplicates(subset=["liga", "home", "away", "fecha"]) if filas else pd.DataFrame()


def elegir_escalera(partidos):
    """Pick del reto escalera: lo más probable con cuota entre 1.25 y 1.60, del día más cercano."""
    cands = []
    for p in partidos:
        f = p.get("final") or [p["p1"], p["px"], p["p2"]]
        nom = f"{p['local']} vs {p['visita']}"
        base = {"fecha": p["fecha"], "liga": p["liga"], "partido": nom}
        for lab, pj, c in ((f"Gana {p['local']}", f[0], p.get("c1")), (f"Gana {p['visita']}", f[2], p.get("c2"))):
            if c and 1.25 <= c <= 1.60 and pj >= 0.65 and pj * c - 1 >= -0.04:
                cands.append({**base, "seleccion": lab, "prob": _r(pj), "cuota_ref": c, "cuota_minima": _r(1.04 / pj, 2)})
        for lab, pj in ((f"{p['local']} o empate", f[0] + f[1]), (f"{p['visita']} o empate", f[2] + f[1])):
            if 0.70 <= pj <= 0.80:
                cands.append({**base, "seleccion": lab, "prob": _r(pj), "cuota_ref": None, "cuota_minima": _r(1.04 / pj, 2)})
        if p.get("co25") and p.get("cu25"):
            mk = 1 / p["co25"] / (1 / p["co25"] + 1 / p["cu25"])
            w = p.get("peso_modelo") or 0
            po = w * p["over25"] + (1 - w) * mk
            for lab, pj, c in (("Más de 2.5 goles", po, p["co25"]), ("Menos de 2.5 goles", 1 - po, p["cu25"])):
                if 1.25 <= c <= 1.60 and pj >= 0.65 and pj * c - 1 >= -0.04:
                    cands.append({**base, "seleccion": f"{lab} ({nom})", "prob": _r(pj), "cuota_ref": c, "cuota_minima": _r(1.04 / pj, 2)})
    if not cands:
        return None
    dia = min(c["fecha"] for c in cands)
    del_dia = sorted([c for c in cands if c["fecha"] == dia], key=lambda c: -c["prob"])
    elegido = dict(del_dia[0])
    elegido["alternativas"] = del_dia[1:3]
    elegido["nota"] = "Solo estadística: revisa bajas y alineaciones antes de jugarlo."
    return elegido


def main():
    os.makedirs(os.path.join(SALIDA, "predicciones"), exist_ok=True)
    ahora = datetime.now(TZ)
    hoy = pd.Timestamp(ahora.date())
    print("Descargando resultados…")
    res = descargar_resultados()
    if res.empty:
        raise SystemExit("No se pudo descargar ningún resultado; no se actualiza nada.")
    res = res[res["fecha"] >= hoy - pd.Timedelta(days=DIAS_HISTORIA)]
    print("Descargando selecciones…")
    sel_res, sel_prox = descargar_selecciones()
    man_res, man_prox = leer_manual(os.path.join(SALIDA, "..", "selecciones_manual.csv"))
    sel_res = pd.concat([x for x in (sel_res, man_res) if not x.empty], ignore_index=True) if (not sel_res.empty or not man_res.empty) else pd.DataFrame()
    if not sel_res.empty:
        sel_res = sel_res.sort_values("fecha").drop_duplicates(subset=["fecha", "home", "away"], keep="last")
        sel_res = sel_res[sel_res["fecha"] >= hoy - pd.Timedelta(days=4 * 365)]
        res = pd.concat([res, sel_res], ignore_index=True)
    print(f"  {len(res)} partidos jugados en {res['liga'].nunique()} ligas")
    print("Descargando próximos partidos…")
    prox = descargar_proximos()
    print(f"  próximos sin filtrar: {len(prox)}" + (f" ({prox['fecha'].min()} a {prox['fecha'].max()})" if not prox.empty else ""))
    extra = [x for x in (sel_prox, man_prox) if not x.empty]
    if extra:
        prox = pd.concat([prox] + extra, ignore_index=True) if not prox.empty else pd.concat(extra, ignore_index=True)
        prox = prox.drop_duplicates(subset=["liga", "fecha", "home", "away"], keep="last")
    if not prox.empty:
        prox = prox[(prox["fecha"] >= hoy) & (prox["fecha"] <= hoy + pd.Timedelta(days=7))]
    print(f"  {len(prox)} partidos próximos")

    params, evaluacion, fuerzas, todas_pred, pesos = {}, {}, {}, [], {}
    for liga, d in res.groupby("liga"):
        d = d.sort_values("fecha")
        xi = elegir_xi(d, hoy)
        p = ajustar(d, hoy + pd.Timedelta(days=1), xi)
        if p is None:
            continue
        params[liga] = p
        bt = walk_forward(d, xi, hoy - pd.Timedelta(days=365), paso_dias=7)
        w = mejor_peso(bt)
        sin_hist = w is None
        w = PESO_SIN_HISTORIA if sin_hist else w
        pesos[liga] = w
        bt = bt.assign(w=w)
        todas_pred.append(bt)
        m = metricas(bt, w)
        m["xi"] = xi
        m["peso_aprendido"] = not sin_hist
        m["partidos_usados"] = int(len(d))
        evaluacion[liga] = m
        inv = {v: k for k, v in p["idx"].items()}
        tabla = []
        for i in range(len(inv)):
            if p["peso"][i] < 3:
                continue
            tabla.append({"equipo": inv[i], "ataque": _r(p["att"][i], 2), "defensa": _r(p["de"][i], 2),
                          "fuerza": _r(p["att"][i] / p["de"][i], 2)})
        fuerzas[liga] = {"local": _r(p["home"], 2), "goles_partido": _r(2 * p["media"], 2),
                         "equipos": sorted(tabla, key=lambda x: -x["fuerza"])}
        print(f"  {liga}: xi={xi} peso_modelo={w} n={m.get('n')} ll_modelo={m.get('logloss_modelo_mismos')} ll_mercado={m.get('logloss_mercado')} ll_comb={m.get('logloss_combinado')} roi={m.get('roi_valor')}")

    global_bt = {"n": 0}
    if todas_pred:
        tp = pd.concat(todas_pred, ignore_index=True)
        partes = [metricas(g, g["w"].iloc[0]) for _, g in tp.groupby("liga")]
        tot = sum(x.get("apuestas_valor", 0) for x in partes)
        gan = sum((x.get("roi_valor") or 0) * x.get("apuestas_valor", 0) for x in partes)
        global_bt = metricas(tp, 1.0)
        global_bt["apuestas_valor"] = tot
        global_bt["roi_valor"] = round(gan / tot, 4) if tot else None
        global_bt["peso_modelo_promedio"] = round(float(np.mean(list(pesos.values()))), 2) if pesos else None

    # ---- predicciones de los próximos 7 días
    partidos = []
    for r in prox.itertuples():
        p = params.get(r.liga)
        if p is None:
            continue
        neutral = bool(getattr(r, "neutral", False) is True)
        lam, mu, ok = goles_esperados(p, r.home, r.away, neutral)
        if not ok:
            print(f"  sin datos de {r.home} o {r.away} ({r.liga})")
            continue
        pr = probabilidades(lam, mu)
        mk = implicitas(r.c1, r.cx, r.c2)
        w = pesos.get(r.liga, PESO_SIN_HISTORIA)
        valor = []
        comb = None
        if mk is not None:
            comb = w * np.array([pr["p1"], pr["px"], pr["p2"]]) + (1 - w) * mk
            for lab, pj, c in (("Local", comb[0], r.c1), ("Empate", comb[1], r.cx), ("Visita", comb[2], r.c2)):
                ev = pj * float(c) - 1
                if ev >= EDGE_MIN and pj >= 0.2:
                    valor.append({"seleccion": lab, "prob": _r(pj), "cuota": _r(c, 2), "ev": _r(ev)})
        if pd.notna(r.o25) and pd.notna(r.u25) and w >= 0.3:
            for lab, pj, c in (("Más de 2.5", pr["over25"], r.o25), ("Menos de 2.5", 1 - pr["over25"], r.u25)):
                ev = pj * float(c) - 1
                if ev >= EDGE_MIN:
                    valor.append({"seleccion": lab, "prob": _r(pj), "cuota": _r(c, 2), "ev": _r(ev)})
        inicio = None
        hs = str(r.hora) if pd.notna(r.hora) else ""
        if len(hs) >= 4 and ":" in hs:
            zona = ZoneInfo("America/Bogota") if r.liga == "Selecciones" else ZoneInfo("Europe/London")
            try:
                hh, mm = hs.split(":")[:2]
                inicio = datetime(r.fecha.year, r.fecha.month, r.fecha.day, int(hh), int(mm), tzinfo=zona).astimezone(TZ).isoformat(timespec="minutes")
            except ValueError:
                inicio = None
        partidos.append({
            "inicio": inicio,
            "fecha": r.fecha.strftime("%Y-%m-%d"),
            "hora_uk": str(r.hora) if (pd.notna(r.hora) and r.liga != "Selecciones") else "",
            "hora_col": str(r.hora) if (pd.notna(r.hora) and r.liga == "Selecciones" and str(r.hora) not in ("", "nan")) else "",
            "liga": r.liga, "local": r.home, "visita": r.away, "neutral": neutral,
            "p1": _r(pr["p1"]), "px": _r(pr["px"]), "p2": _r(pr["p2"]),
            "over25": _r(pr["over25"]), "btts": _r(pr["btts"]), "marcador": pr["marcador"],
            "goles_local": _r(lam, 2), "goles_visita": _r(mu, 2),
            "c1": _r(r.c1, 2), "cx": _r(r.cx, 2), "c2": _r(r.c2, 2), "co25": _r(r.o25, 2), "cu25": _r(r.u25, 2),
            "mercado": [_r(x) for x in mk] if mk is not None else None,
            "final": [_r(x) for x in comb] if comb is not None else None,
            "peso_modelo": w,
            "valor": valor,
        })

    escalera = elegir_escalera(partidos)
    meta = {"actualizado": ahora.isoformat(timespec="minutes"), "edge_min": EDGE_MIN}
    with open(os.path.join(SALIDA, "hoy.json"), "w", encoding="utf-8") as fh:
        json.dump({**meta, "escalera": escalera, "partidos": partidos}, fh, ensure_ascii=False, indent=1)
    # Guarda la foto de hoy para calificarla cuando se jueguen los partidos
    with open(os.path.join(SALIDA, "predicciones", f"{hoy.strftime('%Y-%m-%d')}.json"), "w", encoding="utf-8") as fh:
        json.dump({**meta, "partidos": partidos}, fh, ensure_ascii=False)

    correr_libro(os.path.join(SALIDA, "apuestas_bot.json"), partidos, res, ahora)
    vivo = calificar_en_vivo(res)
    en_vivo = metricas(vivo) if not vivo.empty else {"n": 0}
    with open(os.path.join(SALIDA, "evaluacion.json"), "w", encoding="utf-8") as fh:
        json.dump({**meta, "en_vivo": en_vivo, "backtest_global": global_bt, "por_liga": evaluacion},
                  fh, ensure_ascii=False, indent=1, default=lambda o: None)
    with open(os.path.join(SALIDA, "fuerzas.json"), "w", encoding="utf-8") as fh:
        json.dump({**meta, "ligas": fuerzas}, fh, ensure_ascii=False, indent=1)
    print(f"Listo: {len(partidos)} partidos con probabilidades; récord en vivo: {en_vivo.get('n', 0)} partidos calificados.")


if __name__ == "__main__":
    main()
