"""Prueba rápida de la API (no imprime la clave)."""
import os, json, requests
K = os.environ.get("API_FOOTBALL_KEY", "")
B = "https://v3.football.api-sports.io"
H = {"x-apisports-key": K}
print("clave presente:", bool(K), "largo:", len(K))
def g(path, **p):
    r = requests.get(B + path, headers=H, params=p, timeout=40)
    j = r.json()
    return r.status_code, j.get("errors"), j.get("results"), j.get("response")
s = g("/status"); print("status:", s[0], s[1], json.dumps(s[3])[:300])
c, e, n, resp = g("/fixtures", date="2026-11-12")
print("fixtures hoy:", c, e, n)
if resp:
    seleccion = [f for f in resp if f["league"]["country"] == "World"]
    print("  de selecciones:", len(seleccion), [f"{f['teams']['home']['name']}-{f['teams']['away']['name']} ({f['league']['name']}, id {f['fixture']['id']})" for f in seleccion[:6]])
    col = [f for f in resp if f["league"]["country"] == "Colombia"]
    print("  Colombia:", [f"{f['teams']['home']['name']}-{f['teams']['away']['name']} ({f['league']['name']} {f['league']['season']})" for f in col[:5]])
c, e, n, resp = g("/injuries", date="2026-11-12")
print("lesiones hoy:", c, e, n, [f"{x['player']['name']} ({x['team']['name']}): {x['player']['reason']}" for x in (resp or [])[:8]])
c, e, n, resp = g("/odds", date="2026-11-12")
print("cuotas hoy:", c, e, n, (json.dumps(resp[0]["bookmakers"][0]["bets"][0])[:200] if resp else ""))
