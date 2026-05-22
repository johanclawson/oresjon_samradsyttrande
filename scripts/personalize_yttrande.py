"""Skapa personifierad version av yttrande_kollektivt.html från mall-versionen.

Tanke: yttrande_kollektivt.html är publik mall ("Vi yrkar..."). Detta script läser
mallen och producerar en personifierad version där:
  - "Vi"/"vi" → "Jag"/"jag" på lämpliga platser
  - "[Undertecknande fastighetsägare]"-placeholders → konkret sakägar-info
  - FÖRSTA UTKAST-banner tas bort
  - Inledning kompletteras med hänvisning till parallellt yttrande
  - Signatur byts ut
  - Bilaga 1 (förteckning över undertecknande) tas bort

Användning:
    python scripts/personalize_yttrande.py

Default-argumenten är konfigurerade för Johan Claeson (Ubbhult 2:11). Andra
sakägare kan anpassa argumenten via CLI:

    python scripts/personalize_yttrande.py \\
        --name "Förnamn Efternamn" \\
        --fastighet "Ubbhult X:Y" \\
        --adress "..." \\
        --tel "..." \\
        --email "..." \\
        --output "yttrande_kollektivt_NN.html"

Output-filen läggs i samma mapp som mallen (yttranden/). Filen är gitignored
om namnet matchar `yttrande_kollektivt_*.html` (utöver mallen själv).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# --- Substitution: "Vi"/"vi" → "Jag"/"jag" ---
# Lista av ordagranna textbyten. Använder ordagranna fraser (inte regex) för att
# inte slumpmässigt träffa ord som "veta", "vissa" etc.
WE_TO_I_SUBSTITUTIONS: list[tuple[str, str]] = [
    ("Vi yrkar", "Jag yrkar"),
    ("Vi begär", "Jag begär"),
    ("Vi anser", "Jag anser"),
    ("Vi ifrågasätter", "Jag ifrågasätter"),
    ("Vi sammanfattar", "Jag sammanfattar"),
    ("Vi vill inledningsvis vara tydliga", "Jag vill inledningsvis vara tydlig"),
    ("Vi förbehåller oss", "Jag förbehåller mig"),
    ("vi är inte negativt inställda", "jag är inte negativt inställd"),
    ("Våra synpunkter handlar inte om att motsätta oss", "Mina synpunkter handlar inte om att motsätta sig"),
    ("Vi ser positivt", "Jag ser positivt"),
    ("Vi vill också understryka", "Jag vill också understryka"),
    ("de brister vi lyfter", "de brister jag lyfter"),
    ("gör vi gällande", "gör jag gällande"),
    ("Den för oss centrala", "Den centrala grunden i förevarande sak"),
    ("I vår sak", "I förevarande sak"),
    ("Undertecknande yrkar", "Jag yrkar"),
    ("att samtliga undertecknande underrättas", "att underrättas"),
    ("vår del av kommunen", "denna del av kommunen"),
]


def substitute_we_to_i(html: str) -> str:
    """Konvertera kollektiv 'Vi'-form till personlig 'Jag'-form."""
    for old, new in WE_TO_I_SUBSTITUTIONS:
        html = html.replace(old, new)
    return html


def remove_first_draft_banner(html: str) -> str:
    """Ta bort 'UTKAST'-bannern (första <p> med #fff4cd bakgrund)."""
    pattern = re.compile(
        r'<p style="background: #fff4cd[^"]*"[^>]*>.*?</p>\s*',
        re.DOTALL,
    )
    return pattern.sub("", html, count=1)


def replace_header(html: str, datum: str) -> str:
    """Byt avsändarfältet i headerblocket."""
    old = (
        '<strong>Datum:</strong> 2026-05-25<br>\n'
        '<strong>Avsändare:</strong> [Undertecknande fastighetsägare enligt bilagd förteckning]</p>'
    )
    new = f'<strong>Datum:</strong> {datum}</p>'
    return html.replace(old, new)


def insert_sakagare_block(
    html: str, name: str, fastighet: str, adress: str, rights: str
) -> str:
    """Lägg till sakägar-block efter headern.

    Sakägarstatus motiveras via konkreta rättigheter (rights), inte via PBL-§.
    Om rights är tom används ett generiskt block.
    """
    if rights.strip():
        sakagare_text = (
            f"Sakägare och rättighetshavare i förhållande till planområdet, {rights}."
        )
    else:
        sakagare_text = "Sakägare och rättighetshavare i förhållande till planområdet."

    sakagare_block = (
        '\n<p><strong>Sakägare:</strong><br>\n'
        f'{name}, ägare till {fastighet} ({adress}).<br>\n'
        f'{sakagare_text}</p>\n'
    )
    # Lägg till efter <hr>-elementet som följer headern
    return html.replace("<hr>\n", "<hr>\n" + sakagare_block, 1)


def replace_inledning(html: str) -> str:
    """Byt ut mall-inledningen mot personlig hänvisning till parallellt yttrande."""
    old = (
        "<p>Undertecknande fastighetsägare har tagit del av samrådshandlingarna och lämnar "
        "härmed gemensamma synpunkter på rubricerat detaljplaneförslag. Samtliga undertecknande "
        "är fastighetsägare, sakägare eller rättighetshavare i förhållande till planområdet "
        "enligt 5 kap. 11 § plan- och bygglagen (2010:900, PBL). Underlag, rättskällor och "
        "referensplaner som åberopas i yttrandet finns dokumenterade på "
        '<a href="https://github.com/johanclawson/oresjon_samradsyttrande">'
        'github.com/johanclawson/oresjon_samradsyttrande</a>.</p>'
    )
    new = (
        "<p>Detta yttrande lämnas av undertecknad sakägare och kompletterar mitt parallella "
        "yttrande över samma plan. Som sakägare åberopar jag både egna fastighetsrättsliga "
        "frågor (som utvecklas särskilt i det parallella yttrandet) och planens bredare miljö- "
        "och processbrister, eftersom dessa påverkar planens laglighet och därmed mitt "
        "sakägarintresse. Denna skrivelse fokuserar på de bredare frågorna: "
        "strandskyddsupphävande, artskydd, MKB-undersökning, miljökvalitetsnormer för vatten, "
        "dagvatten- och skyfallshantering, ras- och skredrisk, anpassning till områdets "
        "karaktär, badplatsens funktion samt formella brister i samrådsförfarandet. Övriga "
        "sakägare i området kan komma att ansluta sig till detta yttrande genom egna skrivelser. "
        "Underlag, rättskällor och referensplaner som åberopas finns dokumenterade på "
        '<a href="https://github.com/johanclawson/oresjon_samradsyttrande">'
        'github.com/johanclawson/oresjon_samradsyttrande</a>.</p>'
    )
    return html.replace(old, new)


def replace_signature(html: str, name: str, fastighet: str, adress: str, tel: str, email: str) -> str:
    """Byt ut [Undertecknande fastighetsägare]-signaturen mot konkret kontaktinfo."""
    old = (
        '<strong>[Undertecknande fastighetsägare]</strong><br>\n'
        '[Kontaktperson på begäran]<br>\n'
        '[Kontaktuppgifter på begäran]'
    )
    new = (
        f'<strong>{name}</strong><br>\n'
        f'Ägare till {fastighet}<br>\n'
        f'{adress}<br>\n'
        f'Mobil: {tel}<br>\n'
        f'E-post: {email}'
    )
    return html.replace(old, new)


def personalize(
    mall_path: Path,
    output_path: Path,
    name: str,
    fastighet: str,
    adress: str,
    tel: str,
    email: str,
    datum: str,
    rights: str,
) -> None:
    """Läs mall, applicera substitutioner, skriv personlig version."""
    if not mall_path.exists():
        raise FileNotFoundError(f"Mall saknas: {mall_path}")

    html = mall_path.read_text(encoding="utf-8")

    html = remove_first_draft_banner(html)
    html = replace_header(html, datum)
    html = insert_sakagare_block(html, name, fastighet, adress, rights)
    html = replace_inledning(html)
    html = substitute_we_to_i(html)
    html = replace_signature(html, name, fastighet, adress, tel, email)

    output_path.write_text(html, encoding="utf-8")
    print(f"Skrev: {output_path} ({len(html)} tecken)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Personifiera yttrande_kollektivt.html")
    parser.add_argument("--name", default="Johan Claeson")
    parser.add_argument("--fastighet", default="Ubbhult 2:11")
    parser.add_argument("--adress", default="Jägmästarvägen 6, 438 95 Hällingsjö")
    parser.add_argument("--tel", default="070-264 09 04")
    parser.add_argument("--email", default="johan.claeson@gmail.com")
    parser.add_argument("--datum", default="2026-05-22")
    parser.add_argument(
        "--rights",
        default=(
            "bl.a. som förmånstagare av officialservitut 1463-1017.G "
            "(väg över Ubbhult 2:2), belastad part under officialservitut "
            "15-SÄT-914.B (bad- och båtplats för Ubbhult 2:9), samt delägare "
            "med 1,4 andelar i gemensamhetsanläggningen Lygnersvider ga:1"
        ),
        help=(
            "Konkreta rättigheter som motiverar sakägarstatus (utan punkt på "
            "slutet). Default är Johan Claesons rättigheter; andra sakägare "
            "kan anpassa eller sätta tom sträng för generiskt block."
        ),
    )
    parser.add_argument(
        "--output",
        default="yttranden/yttrande_kollektivt_johan.html",
        help="Utfil (relativ från repo-roten).",
    )
    parser.add_argument(
        "--mall",
        default="yttranden/yttrande_kollektivt.html",
        help="Mall-fil (relativ från repo-roten).",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    mall_path = repo_root / args.mall
    output_path = repo_root / args.output

    personalize(
        mall_path=mall_path,
        output_path=output_path,
        name=args.name,
        fastighet=args.fastighet,
        adress=args.adress,
        tel=args.tel,
        email=args.email,
        datum=args.datum,
        rights=args.rights,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
