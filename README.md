# Nocciola – la spesa furba · Wien

App (PWA) che costruisce un menu settimanale equilibrato con le offerte dei supermercati di Vienna.

**Indirizzo dell'app:** https://lucasalice1997-commits.github.io/spesasmart-wien/

Installazione sul telefono:
- Android (Chrome): menu ⋮, "Installa app".
- iPhone (Safari): Condividi, "Aggiungi alla schermata Home".

## Cosa c'è nel repository

| File / cartella | A cosa serve |
|---|---|
| `index.html` | L'app (versione Nocciola del 20/11/2026) |
| `offers.json` | Le offerte che l'app mostra (solo quelle valide il giorno in cui la apri) |
| `manifest.webmanifest`, `sw.js`, `icon-*.png`, `apple-touch-icon.png` | Installazione sul telefono e funzionamento offline |
| `volantini/` | Carica qui i PDF dei volantini: vengono letti e poi cancellati da soli |
| `pipeline/` | Script che legge volantini e pagine ufficiali e aggiorna `offers.json` |
| `.github/workflows/update-offers.yml` | Avvio automatico dello script (lun, mer, gio, ven alle 05:00 UTC) |

L'app è pubblicata con GitHub Pages (Settings → Pages → branch `main`, cartella `/ (root)`).

## Aggiornamento automatico delle offerte (facoltativo)

Finché non imposti la chiave, l'automazione si salta da sola senza errori e l'app usa `offers.json` così com'è.

1. Su https://console.anthropic.com crea una chiave API solo per questo progetto e imposta un limite di spesa mensile basso (per esempio 5 USD).
2. **Non incollare la chiave in chat, nei file o nel codice.**
3. Nel repository: Settings → Secrets and variables → Actions → New repository secret. Nome `ANTHROPIC_API_KEY`, valore la chiave.
4. Actions → "Aggiorna offerte" → Run workflow. Verde: `offers.json` aggiornato. Rosso: copia l'errore (senza chiavi) e chiedi a Claude.

Note:
- Billa, Hofer, Penny e Norma vengono letti dalle pagine ufficiali rispettando robots.txt. Per Spar e Lidl carica i PDF in `volantini/`.
- Lo script legge al massimo 60 documenti per esecuzione. Controlla la spesa sulla console dopo la prima settimana.
- Il repository è pubblico: non inserire mai chiavi o dati personali nei file.
- L'uso è pensato per un'app personale. Prima di distribuirla ad altri, controlla i termini d'uso delle catene.
