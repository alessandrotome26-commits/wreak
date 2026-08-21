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
import math
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "wrecks.json"
ROUTES = ROOT / "data" / "routes.json"
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


def load_routes():
    if not ROUTES.exists():
        return {}
    return json.loads(ROUTES.read_text(encoding="utf-8"))


def build_pages(wrecks, routes):
    """Copia le pagine, riallinea l'array WRECKS (mappa) e inietta le mappe-rotta."""
    payload = "var WRECKS=" + json.dumps(wrecks, ensure_ascii=False) + ";"
    by_href = {w["href"]: w for w in wrecks if w.get("href")}
    pages = {}
    for p in sorted((SRC / "pages").glob("*.html")):
        html = p.read_text(encoding="utf-8")
        if re.search(r"var WRECKS=\[.*?\];", html, re.S):
            html = re.sub(r"var WRECKS=\[.*?\];", payload, html, count=1, flags=re.S)
        if "<!--ROUTEMAP-->" in html:
            route = routes.get(p.name)
            if not route:
                raise SystemExit(f"{p.name}: manca la rotta in data/routes.json")
            w = by_href.get(p.name)
            if not w:
                raise SystemExit(f"{p.name}: nessun relitto con href={p.name} per la rotta")
            fig = render_route(route, (w["lon"], w["lat"]), route["palette"])
            html = html.replace("<!--ROUTEMAP-->", fig)
        pages[p.name] = html
    return pages


#  ─── mappe-rotta (generate al build dalle coste reali, offline) ──────────────

_LAND_CACHE = None


def _land_polygons():
    """Decodifica vendor/land-50m.json (TopoJSON) in poligoni [ [ (lon,lat)... ] ]."""
    global _LAND_CACHE
    if _LAND_CACHE is not None:
        return _LAND_CACHE
    topo = json.loads((VENDOR / "land-50m.json").read_text(encoding="utf-8"))
    sc = topo["transform"]["scale"]
    tr = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sc[0] + tr[0], y * sc[1] + tr[1]))
        arcs.append(pts)

    def ring(idx_list):
        coords = []
        for idx in idx_list:
            seg = arcs[idx] if idx >= 0 else arcs[-idx - 1][::-1]
            coords.extend(seg[1:] if coords else seg)
        return coords

    polys = []
    for geom in topo["objects"]["land"]["geometries"]:
        if geom["type"] == "MultiPolygon":
            for poly in geom["arcs"]:
                polys.append([ring(r) for r in poly])
        elif geom["type"] == "Polygon":
            polys.append([ring(r) for r in geom["arcs"]])
    _LAND_CACHE = polys
    return polys


def _gc_interp(a, b, n):
    """Punti lungo il grande cerchio tra a e b (lon,lat gradi), per archi morbidi."""
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    d = 2 * math.asin(math.sqrt(
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2))
    if d < 1e-9:
        return [a, b]
    out = []
    for i in range(n + 1):
        f = i / n
        A = math.sin((1 - f) * d) / math.sin(d)
        B = math.sin(f * d) / math.sin(d)
        x = A * math.cos(lat1) * math.cos(lon1) + B * math.cos(lat2) * math.cos(lon2)
        y = A * math.cos(lat1) * math.sin(lon1) + B * math.cos(lat2) * math.sin(lon2)
        z = A * math.sin(lat1) + B * math.sin(lat2)
        out.append((math.degrees(math.atan2(y, x)),
                    math.degrees(math.atan2(z, math.sqrt(x * x + y * y)))))
    return out


def _seg_ix(a, b, val, axis):
    if axis == 0:
        t = 0 if b[0] == a[0] else (val - a[0]) / (b[0] - a[0])
        return (val, a[1] + t * (b[1] - a[1]))
    t = 0 if b[1] == a[1] else (val - a[1]) / (b[1] - a[1])
    return (a[0] + t * (b[0] - a[0]), val)


def _clip_poly(pts, rect):
    """Ritaglio Sutherland-Hodgman di un anello ai bordi del riquadro."""
    minx, miny, maxx, maxy = rect
    edges = [
        (lambda p: p[0] >= minx, 0, minx),
        (lambda p: p[0] <= maxx, 0, maxx),
        (lambda p: p[1] >= miny, 1, miny),
        (lambda p: p[1] <= maxy, 1, maxy),
    ]
    for inside, axis, val in edges:
        if not pts:
            return []
        out = []
        prev = pts[-1]
        for cur in pts:
            if inside(cur):
                if not inside(prev):
                    out.append(_seg_ix(prev, cur, val, axis))
                out.append(cur)
            elif inside(prev):
                out.append(_seg_ix(prev, cur, val, axis))
            prev = cur
        pts = out
    return pts


def _decimate(pts, tol=1.0):
    out = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) >= tol:
            out.append(p)
    return out


def render_route(route, wreck_lonlat, pal):
    """SVG autonomo della rotta: coste reali ritagliate + percorso fatto/da fare."""
    frm = (route["from"]["lon"], route["from"]["lat"])
    to = (route["to"]["lon"], route["to"]["lat"])
    via = [(v["lon"], v["lat"]) for v in route.get("via", [])]
    via_after = [(v["lon"], v["lat"]) for v in route.get("via_after", [])]
    if route.get("wreck"):
        wr = (route["wreck"]["lon"], route["wreck"]["lat"])
    else:
        wr = tuple(wreck_lonlat)
    # ordine delle tappe: origine, scali raggiunti, naufragio, scali mancati, meta
    done_pts = [frm] + via + [wr]
    plan_pts = [wr] + via_after + [to]
    allpts = [frm] + via + [wr] + via_after + [to]

    lons = [p[0] for p in allpts]
    lats = [p[1] for p in allpts]
    lon0, lon1 = min(lons), max(lons)
    lat0, lat1 = min(lats), max(lats)
    padx = max((lon1 - lon0) * 0.18, 4.0)
    pady = max((lat1 - lat0) * 0.18, 3.0)
    lon0 -= padx; lon1 += padx; lat0 -= pady; lat1 += pady
    lat0 = max(lat0, -84); lat1 = min(lat1, 84)
    latc = (lat0 + lat1) / 2
    cosc = max(math.cos(math.radians(latc)), 0.2)

    W = 640.0
    ppd = W / max((lon1 - lon0) * cosc, 1e-6)
    H = (lat1 - lat0) * ppd
    H = max(280.0, min(H, 520.0))

    def proj(lon, lat):
        return ((lon - lon0) * cosc * ppd, (lat1 - lat) * ppd)

    # terraferma: ritaglia al riquadro la sola costa visibile, poi decima i punti
    rect = (-6.0, -6.0, W + 6.0, H + 6.0)
    land_paths = []
    for poly in _land_polygons():
        for ring in poly:
            rl = [p[0] for p in ring]
            ra = [p[1] for p in ring]
            if max(rl) < lon0 or min(rl) > lon1 or max(ra) < lat0 or min(ra) > lat1:
                continue
            proj_ring = [proj(lon, lat) for lon, lat in ring]
            clipped = _decimate(_clip_poly(proj_ring, rect))
            if len(clipped) < 3:
                continue
            xs = [p[0] for p in clipped]
            ys = [p[1] for p in clipped]
            if (max(xs) - min(xs)) * (max(ys) - min(ys)) < 9:
                continue
            land_paths.append(
                "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in clipped) + "Z")
    land_d = " ".join(land_paths)

    def polyline(waypoints, seg=26):
        chain = []
        for i in range(len(waypoints) - 1):
            arc = _gc_interp(waypoints[i], waypoints[i + 1], seg)
            for lon, lat in (arc if i == 0 else arc[1:]):
                x, yv = proj(lon, lat)
                chain.append(f"{x:.1f},{yv:.1f}")
        return "M" + "L".join(chain)

    done_d = polyline(done_pts)
    plan_d = polyline(plan_pts)

    def marker(pt, label, kind):
        x, yv = proj(*pt)
        anchor = "start" if x < W * 0.62 else "end"
        tx = x + (12 if anchor == "start" else -12)
        ty = yv + 4
        if kind == "wreck":
            g = (f'<g><line x1="{x-7:.1f}" y1="{yv-7:.1f}" x2="{x+7:.1f}" y2="{yv+7:.1f}" '
                 f'stroke="{pal["wreck"]}" stroke-width="2.4"/>'
                 f'<line x1="{x-7:.1f}" y1="{yv+7:.1f}" x2="{x+7:.1f}" y2="{yv-7:.1f}" '
                 f'stroke="{pal["wreck"]}" stroke-width="2.4"/>')
            tcol = pal["wreck"]
        elif kind == "to":
            g = (f'<g><circle cx="{x:.1f}" cy="{yv:.1f}" r="6" fill="none" '
                 f'stroke="{pal["plan"]}" stroke-width="1.6" stroke-dasharray="2 2"/>')
            tcol = pal["label"]
        else:
            g = (f'<g><circle cx="{x:.1f}" cy="{yv:.1f}" r="5" fill="{pal["port"]}" '
                 f'stroke="{pal["bg"]}" stroke-width="1.4"/>')
            tcol = pal["port"] if kind == "from" else pal["label"]
        g += (f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="{anchor}" '
              f'font-family="IBM Plex Mono, monospace" font-size="11" fill="{tcol}">'
              f'{label}</text></g>')
        return g

    marks = [marker(frm, route["from"]["n"], "from")]
    for v in route.get("via", []):
        marks.append(marker((v["lon"], v["lat"]), v["n"], "via"))
    marks.append(marker(wr, route.get("wreck_label", "il naufragio"), "wreck"))
    for v in route.get("via_after", []):
        marks.append(marker((v["lon"], v["lat"]), v["n"], "via"))
    marks.append(marker(to, route["to"]["n"] + " — mai raggiunta", "to"))

    svg = (
        f'<svg viewBox="0 0 {W:.0f} {H:.0f}" role="img" '
        f'style="width:100%;height:auto;display:block" '
        f'aria-label="La rotta prevista: da {route["from"]["n"]} verso {route["to"]["n"]}, '
        f'con il punto del naufragio">'
        f'<rect x="0" y="0" width="{W:.0f}" height="{H:.0f}" fill="{pal["bg"]}"/>'
        f'<path d="{land_d}" fill="{pal["land"]}" fill-rule="evenodd" '
        f'stroke="{pal["coast"]}" stroke-width="0.8" stroke-linejoin="round"/>'
        f'<path d="{plan_d}" fill="none" stroke="{pal["plan"]}" stroke-width="1.8" '
        f'stroke-dasharray="3 5" stroke-linecap="round" opacity="0.9"/>'
        f'<path d="{done_d}" fill="none" stroke="{pal["done"]}" stroke-width="2.4" '
        f'stroke-linecap="round"/>'
        + "".join(marks)
        + f'<text x="16" y="24" font-family="IBM Plex Mono, monospace" font-size="9.5" '
        f'letter-spacing="1" fill="{pal["label"]}" opacity="0.75">ROTTA PREVISTA · '
        f'TRATTO CONTINUO = COMPIUTO · TRATTEGGIO = MAI PERCORSO</text>'
        + "</svg>"
    )
    fig = (
        f'<figure class="routemap" style="margin-top:22px;border:1px solid {pal["coast"]};'
        f'background:{pal["bg"]};padding:16px 16px 12px">{svg}'
        f'<figcaption style="font-family:IBM Plex Mono, monospace;font-size:11px;'
        f'color:{pal["label"]};letter-spacing:.04em;margin-top:10px">{route["caption"]}'
        f'</figcaption></figure>'
    )
    return fig


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

    routes = load_routes()
    globe = build_globe(wrecks)
    pages = build_pages(wrecks, routes)
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
