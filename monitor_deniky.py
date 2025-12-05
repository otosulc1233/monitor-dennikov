# -*- coding: utf-8 -*-
"""
Monitoring denníkov (Pravda, Denník N, Aktuality, Plus 1 deň)
-------------------------------------------------------------
Beh cez GitHub Actions (cron každých X minút)

Funkcie:
- stiahne RSS kanály
- nájde nové články s danými kľúčovými slovami
- výsledky zapíše do alerts_log.csv
- vypíše nález do logu (v Actions)

Závislosti:
    pip install feedparser
"""

import os
import json
import feedparser
from datetime import datetime

# ==========================
# KONFIGURÁCIA
# ==========================

# Súbory v repozitári
SEEN_FILE = "seen_articles.json"
ALERT_LOG_FILE = "alerts_log.csv"

# Prefix do logu (iba text, žiadne e-maily)
EMAIL_SUBJECT_PREFIX = "[MONITORING DENNIKY]"

# Globálne kľúčové slová – UPRAV PODĽA SEBA
KEYWORDS = [
    "ministerstvo vnútra",
    "minister vnútra",
    "cestovný pas",
    "pasy",
    "doklady",
    "eDoklady",
    "krízová situácia",
    "mimoriadna situácia",
    "bezpečnosť",
    "útok",
    "atentát",
    "šutaj eštok"
    "eštok",
    "hamran",
  
]

# RSS zdroje – URL si vieš doladiť podľa toho, čo presne chceš sledovať
SOURCES = [
    {
        "name": "DennikN",
        "rss_url": "https://dennikn.sk/feed",
        "extra_keywords": [],
    },
    {
        "name": "Aktuality",
        "rss_url": "https://www.aktuality.sk/rss/",
        "extra_keywords": [],
    },
    {
        "name": "Pravda",
        # RSS feed pre domáce správy (stabilný XML feed)
        # podľa RSS katalógov: spravy.pravda.sk/domace/rss/xml
        "rss_url": "https://spravy.pravda.sk/domace/rss/xml",
        "extra_keywords": [],
    },
    {
        "name": "SME",
        # Hlavné správy SME – historický RSS endpoint
        # ak by časom robil bordel, vieme SME vypnúť alebo nahradiť
        "rss_url": "http://rss.sme.sk/rss/rss.asp?sek=spravy",
        "extra_keywords": [],
    },
    {
        "name": "Plus1Den",
        # Plus One Day / Pluska – RSS feed xml
        "rss_url": "https://www1.pluska.sk/rss.xml",
        "extra_keywords": [],
    },
]



# ==========================
# POMOCNÉ FUNKCIE
# ==========================

def load_seen(path: str):
    """Načíta zoznam už videných článkov zo súboru JSON."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # ak je súbor poškodený, začneme odznova
        return {}


def save_seen(data: dict, path: str):
    """Uloží zoznam videných článkov do JSON súboru."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_text(text: str) -> str:
    """Jednoduchá normalizácia textu na porovnávanie kľúčových slov."""
    if not text:
        return ""
    return text.lower()


def article_matches_keywords(entry, keywords):
    """
    Skontroluje, či článok obsahuje niektoré z kľúčových slov
    v názve alebo v perexe / zhrnutí.
    """
    title = entry.get("title", "")
    summary = entry.get("summary", "") or entry.get("description", "")

    haystack = normalize_text(f"{title} {summary}")

    for kw in keywords:
        if normalize_text(kw) in haystack:
            return True
    return False


def format_email_body(matches):
    """
    Vytvorí textový blok (ako e-mail), ale len na vypísanie do logu.
    matches: list dictov s kľúčmi: source, title, link, published, summary
    """
    lines = []
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    lines.append("Monitoring denníkov – nové články s vybranými kľúčovými slovami")
    lines.append(f"Čas spustenia: {now_str}")
    lines.append("")

    for m in matches:
        lines.append(f"Zdroj: {m['source']}")
        lines.append(f"Názov: {m['title']}")
        if m.get("published"):
            lines.append(f"Publikované: {m['published']}")
        lines.append(f"Link: {m['link']}")
        if m.get("summary"):
            lines.append("")
            lines.append("Perex / zhrnutie:")
            lines.append(m["summary"])
        lines.append("-" * 80)

    return "\n".join(lines)


def send_email(subject: str, body: str):
    """
    Pôvodne tu malo byť odosielanie e-mailu.
    Teraz len vypíšeme obsah do logu (GitHub Actions) – žiadny e-mail sa neposiela.
    """
    print("\n" + "=" * 80)
    print("NOTIFIKÁCIA (len log, e-mail sa neposlal)")
    print("PREDMET:", subject)
    print("-" * 80)
    print(body)
    print("=" * 80 + "\n")


def append_alert_log(matches):
    """
    Zapíše nájdené články do CSV súboru ALERT_LOG_FILE.
    Každý riadok: čas_beh, zdroj, publikované, názov, link.
    """
    header = "run_time;source;published;title;link\n"
    file_exists = os.path.exists(ALERT_LOG_FILE)

    run_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    lines = []
    for m in matches:
        # nahradíme ; v texte, aby nerozbilo CSV
        title = (m["title"] or "").replace(";", ",")
        link = (m["link"] or "").replace(";", ",")
        published = (m.get("published") or "").replace(";", ",")
        source = (m["source"] or "").replace(";", ",")

        line = f"{run_time};{source};{published};{title};{link}\n"
        lines.append(line)

    mode = "a" if file_exists else "w"
    with open(ALERT_LOG_FILE, mode, encoding="utf-8") as f:
        if not file_exists:
            f.write(header)
        f.writelines(lines)

    print(f"Zapísaných {len(lines)} článkov do {ALERT_LOG_FILE}")


def ensure_source_key(seen: dict, source_name: str):
    """Zabezpečí, že v 'seen' existuje kľúč pre daný zdroj."""
    if source_name not in seen:
        seen[source_name] = []
    return seen


def fetch_source(source: dict, global_keywords: list, seen: dict):
    """
    Stiahne RSS daného zdroja a vráti nové články, ktoré:
      - ešte neboli videné
      - zodpovedajú kľúčovým slovám

    POZOR: aj keď je feed "bozo" (nie úplne validný XML),
    skúšame z neho vytiahnuť položky – veľa médií má chyby v RSS,
    ale dá sa to čítať.
    """
    name = source["name"]
    rss_url = source["rss_url"]
    extra_keywords = source.get("extra_keywords", [])

    # Spojenie globálnych + lokálnych kľúčových slov
    keywords = global_keywords + extra_keywords

    print(f"Spracúvam zdroj: {name} ({rss_url})")

    feed = feedparser.parse(rss_url)

    if feed.bozo:
        # len upozorníme, ale NEVRACIAME – ideme skúsiť entries
        print(f"  UPOZORNENIE: Problém pri čítaní RSS ({name}): {feed.bozo_exception}")

    if not getattr(feed, "entries", None):
        print(f"  Žiadne položky v RSS (alebo sa nepodarilo načítať).")
        return []

    matches = []

    for entry in feed.entries:
        link = entry.get("link") or ""
        uid = link or entry.get("id") or entry.get("title")

        if not uid:
            continue

        # ak sme už tento článok videli, preskočíme
        if uid in seen[name]:
            continue

        # označíme ako videný (nezáleží, či spĺňa keywordy – nech to už znova neriešime)
        seen[name].append(uid)

        # filtrovanie podľa kľúčových slov
        if article_matches_keywords(entry, keywords):
            title = entry.get("title", "").strip()
            summary = (entry.get("summary", "") or entry.get("description", "")).strip()
            published = entry.get("published", "") or entry.get("updated", "")

            matches.append({
                "source": name,
                "title": title,
                "link": link,
                "summary": summary,
                "published": published,
            })

    print(f"  Nové relevantné články: {len(matches)}")
    return matches



# ==========================
# HLAVNÁ FUNKCIA
# ==========================

def main():
    print("=" * 80)
    print("Spúšťam monitoring denníkov...")
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    print(f"Čas spustenia: {now_str}")

    seen = load_seen(SEEN_FILE)

    all_matches = []

    for src in SOURCES:
        seen = ensure_source_key(seen, src["name"])
        matches = fetch_source(src, KEYWORDS, seen)
        all_matches.extend(matches)

    # Uložíme aktualizovaný zoznam videných článkov
    save_seen(seen, SEEN_FILE)

    if not all_matches:
        print("Žiadne nové články s kľúčovými slovami.")
        return

    # zapíšeme ich do CSV logu
    append_alert_log(all_matches)

    # vypíšeme detailný prehľad do logu
    subject_time = datetime.now().strftime("%d.%m.%Y %H:%M")
    subject = f"{EMAIL_SUBJECT_PREFIX} {subject_time} – {len(all_matches)} článkov"
    body = format_email_body(all_matches)

    send_email(subject, body)
    print("Hotovo.")


if __name__ == "__main__":
    main()
