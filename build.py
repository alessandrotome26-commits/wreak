#!/usr/bin/env python3
"""
Wreck Atlas — build.

Compila il sito in dist/ :
  - globe.template.html + vendor + data  ->  dist/globo.html   (file autonomo, offline)
  - src/pages/*.html                     ->  dist/             (copiate, con dati riallineati)
  - data/wrecks.json                     ->  dist/relitti.geojson

Uso:
    python3 build.py            costruisce tutto
    python3 build.py --check    non scrive niente, verifica solo la coerenza

Regola del progetto: data/wrecks.json e' l'unica fonte di verita' per i relitti.
Nessun file in dist/ va modificato a mano: viene rigenerato.
"""

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "wrecks.json"
SRC = ROOT / "src"
VENDOR = ROOT / "vendor"
DIST = ROOT / "dist"

REQUIRED_KEYS = {"n", "y", "lat", "lon", "d", "st", "f"}
VALID_STATES = {"ready", "next", "planned"}


def load_wrecks():
    wrecks = json.loads(DATA.read_text(encoding="utf-8"))
    problems = []
    for i, w in enumerate(wrecks):
        missing = REQUIRED_KEYS - set(w)
        if missing:
            problems.append(f"[{i}] {w.get('n','?')}: campi mancanti {sorted(missing)}")
        if w.get("st") not in VALID_STATES:
            problems.append(f"[{i}] {w.get('n','?')}: stato '{w.get('st')}' non valido")
        if w.get("st") == "ready" and not w.get("href"):
            problems.append(f"[{i}] {w.get('n','?')}: stato 'ready' senza href alla scheda")
        if w.get("href") and not (SRC / "pages" / w["href"]).exists():
            problems.append(f"[{i}] {w.get('n','?')}: href '{w['href']}' non esiste in src/pages/")
        if not (-90 <= w.get("lat", 999) <= 90) or not (-180 <= w.get("lon", 999) <= 180):
            problems.append(f"[{i}] {w.get('n','?')}: coordinate fuori range")
    if problems:
        print("ERRORI NEI DATI:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    return wrecks


def build_globe(wrecks):
    tpl = (SRC / "globe.template.html").read_text(encoding="utf-8")
    out = (
        tpl.replace("/*__D3__*/", (VENDOR / "d3.min.js").read_text(encoding="utf-8"))
        .replace("/*__TOPO__*/", (VENDOR / "topojson-client.min.js").read_text(encoding="utf-8"))
        .replace("/*__LAND__*/", (VENDOR / "land-50m.json").read_text(encoding="utf-8"))
        .replace("/*__WRECKS__*/", json.dumps(wrecks, ensure_ascii=False))
    )
    for marker in ("/*__D3__*/", "/*__TOPO__*/", "/*__LAND__*/", "/*__WRECKS__*/"):
        assert marker not in out, f"segnaposto non sostituito: {marker}"
    return out


def build_pages(wrecks):
    """Copia le pagine e riallinea l'array WRECKS dove e' incorporato (mappa)."""
    payload = "var WRECKS=" + json.dumps(wrecks, ensure_ascii=False) + ";"
    pages = {}
    for p in sorted((SRC / "pages").glob("*.html")):
        html = p.read_text(encoding="utf-8")
        if re.search(r"var WRECKS=\[.*?\];", html, re.S):
            html = re.sub(r"var WRECKS=\[.*?\];", payload, html, count=1, flags=re.S)
        pages[p.name] = html
    return pages


def build_geojson(wrecks):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {k: v for k, v in w.items() if k not in ("lat", "lon")},
                "geometry": {"type": "Point", "coordinates": [w["lon"], w["lat"]]},
            }
            for w in wrecks
        ],
    }


def main():
    check_only = "--check" in sys.argv
    wrecks = load_wrecks()
    print(f"dati: {len(wrecks)} relitti, {sum(1 for w in wrecks if w['st']=='ready')} con scheda pronta")

    globe = build_globe(wrecks)
    pages = build_pages(wrecks)
    geo = build_geojson(wrecks)

    if check_only:
        print("--check: dati e template coerenti, niente scritto.")
        return

    DIST.mkdir(exist_ok=True)
    (DIST / "globo.html").write_text(globe, encoding="utf-8")
    print(f"  dist/globo.html        {len(globe)//1024} KB")
    for name, html in pages.items():
        (DIST / name).write_text(html, encoding="utf-8")
        print(f"  dist/{name:<18} {len(html)//1024} KB")
    (DIST / "relitti.geojson").write_text(json.dumps(geo, ensure_ascii=False, indent=1), encoding="utf-8")
    print("  dist/relitti.geojson")

    if (SRC / "index.html").exists():
        shutil.copy(SRC / "index.html", DIST / "index.html")
    else:
        shutil.copy(DIST / "globo.html", DIST / "index.html")
        print("  dist/index.html        (copia del globo: e' la pagina d'ingresso)")

    print("\nfatto. Apri dist/index.html in un browser.")


if __name__ == "__main__":
    main()
