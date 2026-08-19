# Wreck Atlas

Atlante narrativo dei relitti marittimi. Non un database di puntini: un piccolo numero
di storie raccontate in profondità, ognuna con una propria identità visiva.

Schede pronte: **Nuestra Señora de Atocha** (1622), **Vasa** (1628).

## Avvio rapido

```bash
git clone <url> && cd wreck-atlas
npm install          # solo per i test (jsdom)
python3 build.py     # compila in dist/
npm run serve        # http://localhost:8000
```

Nessun framework, nessun bundler: HTML, CSS e JavaScript semplice. Python 3 solo
per il build, Node solo per i test.

## Come funziona

`data/wrecks.json` è l'unica fonte di verità sui relitti. Il build incorpora D3,
topojson-client e la cartografia Natural Earth dentro `dist/globo.html`, che risulta
così **completamente autonomo**: funziona senza rete.

`dist/mappa.html` è l'unica pagina che richiede internet (MapLibre da CDN, batimetria
GEBCO ed EMODnet via WMS) e lo dichiara, degradando su un elenco leggibile se la rete
non c'è.

## Struttura

| percorso | cosa |
|---|---|
| `data/wrecks.json` | i relitti: nome, anno, coordinate, profondità, stato, descrizione |
| `src/globe.template.html` | template del globo, con segnaposto sostituiti dal build |
| `src/pages/` | schede narrative e mappa, una pagina per file |
| `vendor/` | D3 (ISC), topojson-client (ISC), Natural Earth 1:50m (pubblico dominio) |
| `dist/` | generata dal build — non modificare a mano |
| `tests/run.js` | esegue ogni pagina in un DOM simulato e intercetta gli errori |

## Comandi

```bash
python3 build.py           # compila
python3 build.py --check   # valida i dati senza scrivere
node tests/run.js          # test runtime su dist/
npm run all                # build + test
```

## Aggiungere una scheda

1. Scrivi `src/pages/<nome>.html`. Deve avere **identità visiva propria**: font, palette
   e metafora di scorrimento nascono dalla storia di quella nave, non da un template.
2. In `data/wrecks.json` porta la nave a `"st": "ready"` con `"href": "<nome>.html"`,
   e la successiva a `"st": "next"`.
3. Aggiorna la chiusura della scheda precedente perché punti alla nuova.
4. `npm run all`.

## Dati e licenze

- Cartografia: [Natural Earth](https://www.naturalearthdata.com/), pubblico dominio.
- Batimetria: [GEBCO_2026 Grid](https://www.gebco.net/), sotto l'egida congiunta di
  IHO e IOC-UNESCO; [EMODnet Bathymetry](https://emodnet.ec.europa.eu/) per l'Europa.
- Motore cartografico: [D3](https://d3js.org/) e topojson-client, licenza ISC.
- Fonti storiche: dichiarate in fondo a ogni scheda.

Le posizioni sono **arrotondate e approssimate**, non utilizzabili per la navigazione né
per localizzare i siti. Per relitti militari e war graves non viene fornita alcuna
localizzazione di dettaglio.
