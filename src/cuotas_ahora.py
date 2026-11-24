"""Cuotas actuales de BetPlay para los partidos pedidos: python -m src.cuotas_ahora "Lens,Lille" """
import sys
from src import kambi

CLAVES = ("Corners", "Cards", "Both Teams", "Total Goals", "Full Time", "Double Chance", "Draw No Bet")

def main(nombres):
    from datetime import datetime, timedelta, timezone
    global CLAVES
    if nombres.startswith("todo:"):
        nombres = nombres[5:]
        CLAVES = ("",)
    solo_lista = nombres.startswith("lista")
    if solo_lista:
        nombres = nombres[5:]
    horas = float(nombres[1:]) if nombres.startswith("@") else None
    pedidos = [n.strip().lower() for n in nombres.split(",") if n.strip()]
    ahora = datetime.now(timezone.utc)
    if nombres.startswith("ruta:"):
        ruta, nombres = nombres[5:].split("|")
        pedidos = [n.strip().lower() for n in nombres.split(",") if n.strip()]
        d = kambi._get(f"/listView/football/{ruta}/all/matches.json")
        lista = [{"id": e["event"]["id"], "nombre": e["event"]["name"], "inicio": e["event"]["start"],
                  "grupo": e["event"].get("group")} for e in d.get("events", [])]
    else:
        lista = kambi.partidos_futbol()
    for ev in lista:
        nom = (ev["nombre"] or "").lower()
        if horas is not None:
            try:
                t = datetime.fromisoformat((ev["inicio"] or "").replace("Z", "+00:00"))
            except ValueError:
                continue
            if not (ahora < t < ahora + timedelta(hours=horas)) or "cyber" in (ev["grupo"] or "").lower() \
                    or "esport" in nom or "(" in nom:
                continue
        elif "*" not in pedidos and not any(p in nom for p in pedidos):
            continue
        print(f"\n=== {ev['nombre']} | {ev['inicio']} | {ev['grupo']}")
        if solo_lista:
            continue
        d = kambi._get(f"/betoffer/event/{ev['id']}.json")
        for m in kambi._parse(d.get("betOffers", [])):
            if any(k in m["en"] for k in CLAVES) and "Half" not in m["en"]:
                print(f"{m['en'][:55]:55} {m['op']} {m['linea']} {m['cuota']}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
