#!/usr/bin/env python3
"""Prepara i dati per una nuova scheda: aggiorna gli stati in data/wrecks.json.

    python3 scripts/nuova-scheda.py "RMS Titanic" titanic.html "Endurance"

Marca la prima nave come pronta con il suo href, e l'ultima come prossima.
Non genera l'HTML: la scheda si scrive a mano, ogni nave ha la sua identità.
"""
import json, sys
from pathlib import Path

DATA = Path(__file__).parent.parent / "data" / "wrecks.json"

if len(sys.argv) < 3:
    print(__doc__)
    sys.exit(1)

pronta, href = sys.argv[1], sys.argv[2]
prossima = sys.argv[3] if len(sys.argv) > 3 else None

wrecks = json.loads(DATA.read_text(encoding="utf-8"))
nomi = [w["n"] for w in wrecks]
for nome in filter(None, [pronta, prossima]):
    if nome not in nomi:
        print(f"'{nome}' non è in data/wrecks.json. Disponibili:")
        for n in nomi:
            print("  -", n)
        sys.exit(1)

for w in wrecks:
    if w["n"] == pronta:
        w["st"], w["href"] = "ready", href
        print(f"  {pronta}: pronta -> {href}")
    elif prossima and w["n"] == prossima:
        w["st"] = "next"
        w.pop("href", None)
        print(f"  {prossima}: prossima")
    elif w["st"] == "next" and w["n"] != prossima:
        w["st"] = "planned"

DATA.write_text(json.dumps(wrecks, ensure_ascii=False, indent=1), encoding="utf-8")
print("\ndata/wrecks.json aggiornato. Ora: scrivi src/pages/" + href + ", poi 'npm run all'.")
