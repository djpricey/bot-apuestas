"""Cuotas actuales de BetPlay para los partidos pedidos: python -m src.cuotas_ahora "Lens,Lille" """
import sys
from src import kambi

CLAVES = ("Corners", "Cards", "Both Teams", "Total Goals", "Full Time")

def main(nombres):
    pedidos = [n.strip().lower() for n in nombres.split(",") if n.strip()]
    for ev in kambi.partidos_futbol():
        nom = (ev["nombre"] or "").lower()
        if not any(p in nom for p in pedidos):
            continue
        print(f"\n=== {ev['nombre']} | {ev['inicio']} | {ev['grupo']}")
        d = kambi._get(f"/betoffer/event/{ev['id']}.json")
        for m in kambi._parse(d.get("betOffers", [])):
            if any(k in m["en"] for k in CLAVES) and "Half" not in m["en"]:
                print(f"{m['en'][:55]:55} {m['op']} {m['linea']} {m['cuota']}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
