# Wreck Atlas — istruzioni di progetto

Atlante narrativo dei relitti marittimi. Non compete con Wrecksite.eu sul numero di
punti (loro ne hanno ~215.000): compete sulla **profondità narrativa**. Venti schede
cinematografiche battono duecentomila puntini. Ogni decisione va pesata su questo.

Lingua del progetto e dei contenuti: **italiano**.

---

## Comandi

```bash
python3 build.py          # compila tutto in dist/
python3 build.py --check  # verifica solo la coerenza dei dati, non scrive
cd tests && npm install   # una volta sola
node tests/run.js         # esegue le pagine e intercetta gli errori runtime
```

Prima di dichiarare finito qualunque lavoro: `python3 build.py && node tests/run.js`.

---

## Architettura

```
data/wrecks.json          UNICA fonte di verità sui relitti
src/globe.template.html   template del globo, con segnaposto /*__D3__*/ ecc.
src/pages/*.html          schede narrative + mappa (una pagina, un file, autonoma)
vendor/                   D3, topojson-client, Natural Earth 1:50m (incorporati nel build)
dist/                     GENERATA. Non modificare mai a mano.
```

Il globo è **autonomo e offline**: D3, topojson e la cartografia vengono incorporati
nel file dal build. Non introdurre CDN nel globo — è la pagina che deve funzionare
sempre, ovunque, anche in anteprime che bloccano la rete.

`src/pages/mappa.html` è l'eccezione dichiarata: richiede internet (MapLibre da CDN,
tile GEBCO/EMODnet). Deve degradare mostrando comunque contenuto utile, mai una
pagina vuota o un solo messaggio d'errore.

---

## Regole di prodotto (non negoziabili)

1. **Una funzione, un solo meccanismo.** Se un'informazione è raggiungibile da due
   strade diverse nella stessa pagina, una delle due è un errore. Vale per l'interfaccia
   come per i dati.
2. **Ogni scheda ha un'identità visiva propria.** Font, palette, metafora di scorrimento
   e widget interattivo cambiano in base alla storia della nave. L'Atocha scende nel buio
   (Bodoni, oro su abisso, neve marina); il Vasa risale nella luce di un museo (Cormorant,
   quercia su Baltico, sedimento orizzontale). Non replicare un template: reinterpretarlo.
3. **Mai far dipendere una funzione da un'animazione.** Il click deve funzionare anche se
   i frame non arrivano (scheda in background, risparmio energetico, reduced-motion).
   L'animazione è condimento, non pasto.
4. **Niente `position: fixed` per pannelli contestuali.** Vivono nello schermo, non nella
   pagina, e finiscono sopra tutto il resto scorrendo. Ancorare al contenitore di riferimento.
5. **Distinguere sempre registrato / recuperato / mancante**, stimato da contato. Se una
   cifra è una stima, deve leggersi come stima ("circa trenta", "tra 150 e 250").
6. **Niente coordinate precise per relitti militari, war graves e siti a rischio saccheggio.**
   Le posizioni sono arrotondate e ogni scheda dichiara il proprio livello di confidenza.
   USS Arizona: cimitero di guerra, nessuna localizzazione di dettaglio.
7. **Nessuna immagine ospitata**: si linka agli archivi (Florida Memory, YouTube), non si
   ricaricano file altrui.
8. **Verificare i fatti prima di scriverli.** Ogni scheda ha una sezione FONTI in fondo.
   Se un dato non è verificabile, non entra o entra dichiarato come incerto.

---

## Trappole già pagate (non ripeterle)

- **Layer WMS GEBCO in minuscolo.** MapServer distingue maiuscole: `gebco_2026`, non
  `GEBCO_2026`. Endpoint stabile: `https://wms.gebco.net/2026/mapserv?`. Formato `image/jpeg`.
  WMS 1.3.0 vuole bbox `lat,lon` (`crs=`); 1.1.1 vuole `lon,lat` (`srs=`).
- **Clipping sferico a mano = ventagli chiari sul globo.** Ritagliare poligoni all'orizzonte
  è geometria non banale: usare `d3.geoPath` + `clipAngle(90)`. Mai reimplementarlo.
- **Proteggere le API del browser** prima dell'uso: `matchMedia`, `IntersectionObserver`.
  Senza guard, uno script muore alla prima riga e con lui l'intera pagina.
- **Texture `position:fixed` + scroll = banding.** Rimosse. Stessa cosa per `backdrop-filter`
  su pannelli che si muovono.
- **L'anteprima interna dell'app Claude blocca le richieste di rete.** Non è un bug del
  codice: mappa e batimetria vanno testate in un browser vero.

---

## Stato

> Questa sezione invecchia a ogni scheda. La fonte di verità è sempre
> `data/wrecks.json`; se i numeri qui sotto non tornano, ha ragione il JSON.
> Contarli: `python3 -c "import json,collections;print(collections.Counter(x['st'] for x in json.load(open('data/wrecks.json'))))"`

Aggiornato al 2026-08-26: **28 schede `ready`**, 13 `planned`, 1 `next`.
Prossima: **Vrouw Maria** (mercantile olandese 1771, dipinti di maestri — cambio di mare/secolo).

Pagine: 29 in italiano (`src/pages/`), 8 in inglese (`src/pages/en/`).

### i18n — filone attivo

Traduzione inglese in corso, **8 schede su 21** (Titanic, Lusitania, Endurance,
Mary Celeste, Bismarck, Erebus/Terror-Franklin, Atocha, Vasa). La riga "lingua del progetto: italiano" in cima resta
vera per i **contenuti nuovi**: si scrive prima in italiano, l'inglese segue.
Una scheda inglese vive in `src/pages/en/` e non sostituisce l'italiana.

Per aggiungere una scheda:
1. scrivere `src/pages/<nome>.html` con identità visiva propria;
2. in `data/wrecks.json` portare la nave a `"st":"ready"` con `"href":"<nome>.html"`,
   e la successiva a `"st":"next"`;
3. aggiornare la chiusura della scheda precedente perché punti a questa;
4. `python3 build.py && node tests/run.js`.

## Criterio di successo

Non le visite: lo **scroll mediano oltre i 3 minuti** su una scheda, e almeno tre email
non sollecitate da musei, archeologi o centri di immersione. Il form di iscrizione è
ancora scollegato: va agganciato a un servizio reale prima di qualunque promozione.
