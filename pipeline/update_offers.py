#!/usr/bin/env python3
"""Legge i volantini (PDF) con Claude e aggiorna offers.json."""
import base64, datetime as dt, hashlib, html, json, os, re, sys, time, urllib.request, urllib.robotparser
from urllib.parse import urlparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT, DONE, DROP = ROOT / "offers.json", ROOT / "pipeline" / "processed.json", ROOT / "volantini"
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
STORES = ["Billa", "Spar", "Hofer", "Lidl", "Penny", "Norma"]
ING = {"pasta": "pasta secca", "riso": "riso", "passata": "passata o polpa di pomodoro",
 "formaggio": "formaggio (Emmentaler, Gouda, grattugiato...)", "funghi": "funghi champignon",
 "pollo": "petto o filetto di pollo", "cosce": "cosce di pollo o pollo intero", "maiale": "lonza o filetto di maiale",
 "patate": "patate", "uova": "uova (prezzo al kg: calcola 60 g per uovo)", "cipolle": "cipolle",
 "lenticchie": "lenticchie", "carote": "carote", "ceci": "ceci", "peperoni": "peperoni", "tonno": "tonno in scatola",
 "manzo": "carne macinata (Faschiertes) di manzo o mista", "spinaci": "spinaci", "zucchine": "zucchine",
 "pane": "pane", "latte": "latte (prezzo al litro)", "yogurt": "yogurt", "avena": "fiocchi d'avena",
 "arance": "arance", "mele": "mele"}
TODAY = dt.date.today()
UA = "SpesaSmart/1.0 (lettura personale di volantini pubblici)"
PROMPT = """Questo documento (PDF o testo di una pagina web) contiene le offerte di un supermercato austriaco. Catena: __STORE__. Estrai SOLO le offerte alimentari che corrispondono a queste chiavi:
__KEYS__
Rispondi con un unico oggetto JSON, senza altro testo:
{"store": "Billa|Spar|Hofer|Lidl|Penny", "offers": [{"i": "<chiave>", "p": <euro al kg>, "d": "AAAA-MM-GG", "a": "AAAA-MM-GG", "prodotto": "<nome nel volantino>"}]}
Regole: se è il testo di una pagina web, la validità è nel titolo della sezione (es. 'Mo. 16.11. bis Do. 19.11.'); usa il prezzo scontato (non quello 'statt'); "p" è sempre in euro al kg (al litro per il latte), calcolato dal peso della confezione se serve; "d" e "a" sono primo e ultimo giorno di validità di quella pagina o offerta (anno __YEAR__ se non indicato); se l'offerta richiede più confezioni usa il prezzo ridotto; ignora ciò che non sei sicuro di aver letto bene."""

def ask(client, kind, payload, hint):
    prompt = PROMPT.replace("__KEYS__", "\n".join(f"- {k}: {v}" for k, v in ING.items())).replace("__YEAR__", str(TODAY.year)).replace("__STORE__", hint or "da riconoscere")
    if kind == "pdf":
        doc = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": base64.b64encode(payload).decode()}}
    else:
        doc = {"type": "text", "text": "TESTO DELLA PAGINA:\n" + payload.decode("utf-8")[:150000]}
    msg = client.messages.create(model=MODEL, max_tokens=8000, messages=[{"role": "user", "content": [doc, {"type": "text", "text": prompt}]}])
    t = "".join(b.text for b in msg.content if b.type == "text")
    return json.loads(t[t.index("{"): t.rindex("}") + 1])

_robots = {}
def allowed(url):
    u = urlparse(url); base = f"{u.scheme}://{u.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser(base + "/robots.txt")
        try:
            rp.read()
        except Exception:
            rp = None
        _robots[base] = rp
    return bool(_robots[base]) and _robots[base].can_fetch(UA, url)

def get(url, binary=False):
    if not allowed(url):
        print("robots.txt non consente (o non leggibile):", url); return None
    time.sleep(2)
    try:
        d = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60).read()
    except Exception as e:
        print("download non riuscito:", url, e); return None
    return d if binary else d.decode("utf-8", "replace")

def page_to_text(h):
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", h, flags=re.S)
    h = re.sub(r'<img[^>]*?alt="([^"]*)"[^>]*>', r" \1 \n", h)
    h = re.sub(r"<[^>]+>", " ", h)
    return re.sub(r"[ \t]+", " ", html.unescape(h)).strip()

def collect(cfg):
    jobs = []
    for ch in cfg["chains"]:
        k, st = ch.get("kind"), ch["store"]
        if k == "page_pdf":
            h = get(ch["page"])
            for u in sorted(set(re.findall(ch["pdf_regex"], (h or "").replace("\\/", "/")))):
                d = get(u, True)
                if d and d[:5] == b"%PDF-":
                    jobs.append((u, "pdf", d, st, None))
        elif k == "page_text":
            for p in ch["pages"]:
                for n in (range(1, ch.get("max_pages", 20) + 1) if "{n}" in p else [0]):
                    h = get(p.replace("{n}", str(n)))
                    if not h:
                        break
                    t = page_to_text(h)
                    if "€" not in t:
                        t = html.unescape(h)[:150000]
                    if "{n}" in p and "€" not in t:
                        break
                    jobs.append((p.replace("{n}", str(n)), "text", t.encode(), st, None))
        elif k == "pdf_template":
            for off in (0, 1):
                y, w, _ = (TODAY + dt.timedelta(weeks=off)).isocalendar()
                for u in ch["pdf_urls"]:
                    d = get(u.format(kw=w, kw2=f"{w:02d}", yyyy=y), True)
                    if d and d[:5] == b"%PDF-":
                        jobs.append((u.format(kw=w, kw2=f"{w:02d}", yyyy=y), "pdf", d, st, None))
    return jobs

def clean(raw, hint=None):
    store = hint or raw.get("store")
    if store not in STORES:
        raise ValueError(f"catena non riconosciuta: {store}")
    out = []
    for o in raw.get("offers", []):
        try:
            i, p = o["i"], round(float(o["p"]), 2)
            d, a = dt.date.fromisoformat(o["d"]), dt.date.fromisoformat(o["a"])
        except Exception:
            continue
        if i in ING and 0.2 <= p <= 60 and d <= a and (a - d).days <= 21:
            out.append({"s": store, "i": i, "p": p, "d": d.isoformat(), "a": a.isoformat()})
    return store, out

def main(client=None):
    done = json.loads(DONE.read_text()) if DONE.exists() else {}
    data = json.loads(OUT.read_text()) if OUT.exists() else {"updated": "2000-01-01", "offers": []}
    jobs = collect(json.loads((ROOT / "pipeline" / "sources.json").read_text()))
    if DROP.exists():
        jobs += [(f.name, "pdf", f.read_bytes(), None, f) for f in sorted(DROP.glob("*.pdf"))]
    jobs = jobs[: int(os.environ.get("MAX_JOBS", "60"))]  # tetto di sicurezza sui costi
    if jobs and client is None:
        import anthropic
        client = anthropic.Anthropic()
    errors = new = 0
    for origin, kind, payload, hint, path in jobs:
        h = hashlib.sha256(payload).hexdigest()
        if h not in done:
            try:
                store, offs = clean(ask(client, kind, payload, hint), hint)
            except Exception as e:
                print("ERRORE", origin, e); errors += 1; continue
            data["offers"] += offs; new += len(offs)
            done[h] = {"origine": origin, "store": store, "data": TODAY.isoformat(), "offerte": len(offs)}
            print(f"{origin}: {store}, {len(offs)} offerte")
        if path:
            path.unlink()
    seen, keep = set(), []
    for o in data["offers"]:
        k = (o["s"], o["i"], o["p"], o["d"], o["a"])
        if k not in seen and dt.date.fromisoformat(o["a"]) >= TODAY - dt.timedelta(days=14):
            seen.add(k); keep.append(o)
    data["offers"] = keep
    if new:
        data["updated"] = TODAY.isoformat()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    DONE.write_text(json.dumps(done, ensure_ascii=False, indent=1))
    stale = (TODAY - dt.date.fromisoformat(data["updated"])).days
    print(f"offerte: {len(keep)}, nuove: {new}, ultimo aggiornamento {stale} giorni fa")
    if errors or stale > 10:
        sys.exit(1)

if __name__ == "__main__":
    main()
