"""Prueba: ¿se pueden leer las cuotas de BetPlay (plataforma Kambi) desde GitHub Actions?

No usa claves ni inicia sesión: solo pide las mismas páginas y datos públicos que carga el navegador.
Guarda lo que encuentra en docs/data/kambi_probe.json para revisarlo.
"""
import json
import re
import time
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
PAGINAS = ["https://betplay.com.co/apuestas", "https://betplay.com.co/", "https://betplay.com.co/apuestas#home"]
HOSTS = ["https://eu-offering-api.kambicdn.com", "https://us1-offering-api.kambicdn.com",
         "https://eu1.offering-api.kambicdn.com", "https://na-offering-api.kambicdn.com"]
CODIGOS = ["betplay", "betplayco", "bpco", "cecl", "ceco", "corredor", "betplaycol"]
RUTA = "/offering/v2018/{op}/listView/football/all/all/all/matches.json?lang=es_CO&market=CO&useCombined=true"


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*", "Accept-Language": "es-CO,es;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read(400_000).decode("utf-8", "replace")


def probar():
    out = {"paginas": [], "codigos_en_html": [], "intentos": [], "ok": None}
    encontrados = []
    for url in PAGINAS:
        try:
            st, html = _get(url)
            pistas = sorted(set(re.findall(r'(?:offering|kambi)[^"\'\s<>]{0,80}', html, re.I)))[:40]
            ops = re.findall(r'["\']?offering["\']?\s*[:=]\s*["\']([a-z0-9_]{2,20})["\']', html, re.I)
            encontrados += ops
            out["paginas"].append({"url": url, "status": st, "largo": len(html), "pistas": pistas, "offering": ops})
        except Exception as e:  # noqa: BLE001 - es una prueba, se registra todo
            out["paginas"].append({"url": url, "error": repr(e)[:200]})
        time.sleep(1)
    out["codigos_en_html"] = sorted(set(encontrados))
    for op in list(dict.fromkeys(encontrados + CODIGOS)):
        for host in HOSTS:
            url = host + RUTA.format(op=op)
            try:
                st, txt = _get(url)
                try:
                    data = json.loads(txt)
                    n = len(data.get("events", [])) if isinstance(data, dict) else 0
                except ValueError:
                    n = -1
                out["intentos"].append({"url": url, "status": st, "eventos": n, "inicio": txt[:200]})
                if n > 0 and not out["ok"]:
                    ev = data["events"][0]
                    out["ok"] = {"url": url, "eventos": n, "ejemplo": {
                        "evento": ev.get("event", {}).get("name"),
                        "grupo": ev.get("event", {}).get("group"),
                        "ofertas": [{"criterio": o.get("criterion", {}).get("label"),
                                     "cuotas": [(x.get("label"), x.get("odds")) for x in o.get("outcomes", [])]}
                                    for o in ev.get("betOffers", [])[:3]]}}
            except Exception as e:  # noqa: BLE001
                out["intentos"].append({"url": url, "error": repr(e)[:160]})
            time.sleep(0.5)
        if out["ok"]:
            break
    with open("docs/data/kambi_probe.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(json.dumps({"ok": out["ok"], "codigos_en_html": out["codigos_en_html"],
                      "paginas": [{k: p.get(k) for k in ("url", "status", "error", "offering")} for p in out["paginas"]]},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    probar()
