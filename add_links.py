"""Lägg till länkar till MÖD-praxis, lagrum, EU-direktiv och lokala dokument
i yttranden/*.md.

Strategi:
  - Identifiera befintliga markdown-länkar `[text](url)` och bevara dem orörda.
  - Kör regex-ersättningar ENBART på textsegment utanför befintliga länkar.
  - Detta hindrar nästade länkar även när delsträngar (t.ex. "plankarta")
    råkar finnas i en URL-väg.

Skriptet är idempotent: en andra körning på samma fil lägger inte till nya
länkar eftersom alla mål redan ligger inne i `[...](...)`-block.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent
MD_FILES = sorted(ROOT.glob("yttranden/*.md"))

# --- MÖD-domar ---
MOD_CASES: dict[str, str] = {
    "MÖD 2017:49": "https://lagen.nu/dom/mod/2017:49",
    "MÖD 2014:4": "https://lagen.nu/dom/mod/2014:4",
    "MÖD 2013:20": "https://lagen.nu/dom/mod/2013:20",
    "MÖD 2022:5": "https://lagen.nu/dom/mod/2022:5",
    "MÖD 2019:2": "https://lagen.nu/dom/mod/2019:2",
    "MÖD P 2498-22": "https://www.strandskyddsdomar.se/detaljplan-inom-lis-omrade-upphavs-da-den-inte-tillgodoser-fri-passage/",
    # MÖD P 5876-18 har tagits bort från domstol.se. Länkar till lokal kopia.
    "MÖD P 5876-18": "../domar/MOD_P5876-18.pdf",
    "MÖD P 9670-20": "https://www.strandskyddsdomar.se/upphavd-detaljplan-pa-grund-av-att-utredning-saknas/",
    # MÖD P 2387-20 har också tagits bort från domstol.se. Vi har bara sammanfattning lokalt.
    "MÖD P 2387-20": "../domar/MOD_P2387-20_betydande_olagenhet.md",
    "MÖD M 11789-21": "https://www.strandskyddsdomar.se/fri-passage-varnas-i-lis-omrade/",
}

# Målnummer-bara (utan MÖD-prefix), pekar på samma URL.
ALIASES: dict[str, str] = {
    "P 11166-16": MOD_CASES["MÖD 2017:49"],
    "P 2823-13": MOD_CASES["MÖD 2014:4"],
    "P 2699-12": MOD_CASES["MÖD 2013:20"],
    "P 7791-21": MOD_CASES["MÖD 2022:5"],
    "P 7022-18": MOD_CASES["MÖD 2019:2"],
    "P 2498-22": MOD_CASES["MÖD P 2498-22"],
    "P 5876-18": MOD_CASES["MÖD P 5876-18"],
    "P 9670-20": MOD_CASES["MÖD P 9670-20"],
    "P 2387-20": MOD_CASES["MÖD P 2387-20"],
    "M 11789-21": MOD_CASES["MÖD M 11789-21"],
}

# --- Lagrum ---
LAG_SFS: dict[str, str] = {
    "PBL": "2010:900",
    "plan- och bygglagen": "2010:900",
    "MB": "1998:808",
    "miljöbalken": "1998:808",
    "artskyddsförordningen": "2007:845",
    "AL": "1973:1149",
    "anläggningslagen": "1973:1149",
    "FBL": "1970:988",
    "fastighetsbildningslagen": "1970:988",
}


def lagrum_url(sfs: str, kap: str | None, paragraf: str) -> str:
    p = paragraf.replace(" ", "").lower()
    if kap:
        return f"https://lagen.nu/{sfs}#K{kap}P{p}"
    return f"https://lagen.nu/{sfs}#P{p}"


# --- EU-direktiv och övriga externa referenser ---
# Ordning: längre, mer specifika mönster först. Hindrar att kortare
# delsträngar (t.ex. "Weser-domen") matchar inne i en längre fras
# som redan har länkats.
EU_REFS: list[tuple[str, str]] = [
    (
        r"habitatdirektivet\s+\(?92/43[/-]?EEG\)?",
        "https://eur-lex.europa.eu/eli/dir/1992/43/oj",
    ),
    (
        r"fågeldirektivet\s+\(?2009/147[/-]?EG\)?",
        "https://eur-lex.europa.eu/eli/dir/2009/147/oj",
    ),
    (
        r"ramdirektivet\s+för\s+vatten\s+\(?2000/60[/-]?EG\)?",
        "https://eur-lex.europa.eu/eli/dir/2000/60/oj",
    ),
    (
        r"vattendirektivet\s+\(?2000/60[/-]?EG\)?",
        "https://eur-lex.europa.eu/eli/dir/2000/60/oj",
    ),
    (
        r"Weser-domen\s+\(C-461/13\)",
        "https://eur-lex.europa.eu/legal-content/SV/TXT/?uri=CELEX:62013CJ0461",
    ),
    (r"habitatdirektivet", "https://eur-lex.europa.eu/eli/dir/1992/43/oj"),
    (r"fågeldirektivet", "https://eur-lex.europa.eu/eli/dir/2009/147/oj"),
    (r"ramdirektivet\s+för\s+vatten", "https://eur-lex.europa.eu/eli/dir/2000/60/oj"),
    (r"vattendirektivet", "https://eur-lex.europa.eu/eli/dir/2000/60/oj"),
    (r"Weser-domen", "https://eur-lex.europa.eu/legal-content/SV/TXT/?uri=CELEX:62013CJ0461"),
    (r"92/43[/-]?EEG", "https://eur-lex.europa.eu/eli/dir/1992/43/oj"),
    (r"2009/147[/-]?EG", "https://eur-lex.europa.eu/eli/dir/2009/147/oj"),
    (r"2000/60[/-]?EG", "https://eur-lex.europa.eu/eli/dir/2000/60/oj"),
    (r"C-461/13", "https://eur-lex.europa.eu/legal-content/SV/TXT/?uri=CELEX:62013CJ0461"),
]

# --- Lokala dokument (relativa från yttranden/-mappen) ---
# Längre/mer specifika mönster först.
LOCAL_DOCS: list[tuple[str, str]] = [
    (
        r"Länsstyrelsens\s+granskningsyttrande\s+över\s+(?:Fördjupad\s+översiktsplan\s+\()?FÖP(?:\))?\s+Mark\s+Nordväst",
        "../op/Granskningsyttrande_FOP_Mark_Nordvast.pdf",
    ),
    (
        r"Fördjupad\s+översiktsplan\s+\(FÖP\)\s+Mark\s+Nordväst",
        "../op/Granskningsyttrande_FOP_Mark_Nordvast.pdf",
    ),
    (
        r"granskningsyttrande\s+över\s+FÖP\s+Mark\s+Nordväst",
        "../op/Granskningsyttrande_FOP_Mark_Nordvast.pdf",
    ),
    (
        r"FÖP\s+Mark\s+Nordväst",
        "../op/Granskningsyttrande_FOP_Mark_Nordvast.pdf",
    ),
    (r"LIS-tillägget(s)?", "../op/LIS_Landsbygdsutveckling_strandnara_lagen.pdf"),
    (r"planbeskrivning(en|ens)?", "../planhandlingar/planbeskrivning.pdf"),
    (r"plankartan?(s)?", "../planhandlingar/plankarta.pdf"),
    (r"illustrationsplan(en)?", "../planhandlingar/illustrationsplan.pdf"),
]


# --- Hjälpfunktion som ersätter ENDAST utanför befintliga länkar ---
MD_LINK_RE = re.compile(r"\[[^\[\]]*\]\([^)]+\)")


def replace_outside_links(text: str, pattern: re.Pattern, repl) -> tuple[str, int]:
    """Applicera ersättning endast i textsegment som ligger UTANFÖR
    redan-länkad text. Returnerar (ny_text, antal_ersättningar).
    """
    parts: list[str] = []
    last_end = 0
    n_total = 0
    for link_m in MD_LINK_RE.finditer(text):
        # Bearbeta segment innan länken.
        segment = text[last_end : link_m.start()]
        new_segment, n = pattern.subn(repl, segment)
        n_total += n
        parts.append(new_segment)
        # Behåll länken oförändrad.
        parts.append(link_m.group(0))
        last_end = link_m.end()
    # Sista segmentet efter sista länken.
    tail = text[last_end:]
    new_tail, n = pattern.subn(repl, tail)
    n_total += n
    parts.append(new_tail)
    return "".join(parts), n_total


# --- Länkare ---


def link_mod_cases(text: str) -> tuple[str, int]:
    total = 0
    for label, url in MOD_CASES.items():
        flexible = re.escape(label).replace(r"\ ", r"\s+")
        pattern = re.compile(flexible)

        def repl(m: re.Match, u: str = url) -> str:
            display = re.sub(r"\s+", " ", m.group(0))
            return f"[{display}]({u})"

        text, n = replace_outside_links(text, pattern, repl)
        total += n

    for alias, url in ALIASES.items():
        flexible = re.escape(alias).replace(r"\ ", r"\s+")
        # Förebygg matchning intill "MÖD " — det fångas redan av MOD_CASES.
        pattern = re.compile(rf"(?<![\[\w-]){flexible}")

        def repl(m: re.Match, u: str = url) -> str:
            display = re.sub(r"\s+", " ", m.group(0))
            return f"[{display}]({u})"

        text, n = replace_outside_links(text, pattern, repl)
        total += n
    return text, total


def link_lagrum(text: str) -> tuple[str, int]:
    lag_keys_sorted = sorted(LAG_SFS.keys(), key=len, reverse=True)
    # Bygg lag-mönster som tolererar radbrytning inuti lagnamnet
    # (t.ex. "plan-\n  och bygglagen" från pandoc-wrap).
    def flexible_lag(name: str) -> str:
        escaped = re.escape(name)
        return escaped.replace(r"\ ", r"\s+")

    lag_pat_str = "|".join(flexible_lag(k) for k in lag_keys_sorted)

    paragraf_pat = r"\d+(?:\s+[a-z](?!\w))?(?:\s*(?:--|och|,)\s*\d+(?:\s+[a-z](?!\w))?)*"
    stycke_pat = (
        r"(?:\s*(?:första|andra|tredje|fjärde|femte)\s+stycket"
        r"(?:\s+\d+(?:\s*(?:,|och)\s*\d+)*)?"
        r"(?:\s+och\s+(?:första|andra|tredje|fjärde|femte)\s+stycket)?)?"
    )
    punkt_pat = r"(?:\s*p\.\s+\d+(?:\s*(?:,|och)\s*\d+)*)?"

    pattern = re.compile(
        rf"(?P<kap>\d+)\s*kap\.\s+"
        rf"(?P<paragraf>{paragraf_pat})\s*§§?"
        rf"{stycke_pat}{punkt_pat}"
        rf"\s+(?P<lag>{lag_pat_str})",
        flags=re.DOTALL,
    )

    def repl(m: re.Match) -> str:
        kap = m.group("kap")
        para_text = m.group("paragraf")
        para_m = re.match(r"\d+(?:\s+[a-z](?!\w))?", para_text)
        paragraf = para_m.group(0) if para_m else para_text
        # Normalisera lagnamnet (radbrytning → mellanslag) för dict-uppslag.
        lag_raw = re.sub(r"\s+", " ", m.group("lag")).strip()
        sfs = LAG_SFS.get(lag_raw)
        if sfs is None:
            return m.group(0)
        url = lagrum_url(sfs, kap, paragraf)
        display = re.sub(r"\s+", " ", m.group(0))
        return f"[{display}]({url})"

    text, n_kap = replace_outside_links(text, pattern, repl)

    # Form 2: "N a § artskyddsförordningen" utan kapitel.
    pattern2 = re.compile(
        rf"(?<![\d.])(?P<paragraf>\d+(?:\s+[a-h])?)\s+§\s+"
        rf"(?P<lag>artskyddsförordningen)"
    )

    def repl2(m: re.Match) -> str:
        paragraf = m.group("paragraf")
        lag = m.group("lag")
        sfs = LAG_SFS[lag]
        url = lagrum_url(sfs, None, paragraf)
        display = re.sub(r"\s+", " ", m.group(0))
        return f"[{display}]({url})"

    text, n_nokap = replace_outside_links(text, pattern2, repl2)

    # Form 4: "X1 § ... och/samt [X2 § ... LAG](url)" — länka X1 till samma SFS.
    # Kör innan Form 3 för att fånga den vanligaste sammansatta varianten.
    pattern_combined = re.compile(
        rf"(?P<kap1>\d+)\s*kap\.\s+"
        rf"(?P<para1>{paragraf_pat})\s*§§?"
        rf"{stycke_pat}{punkt_pat}"
        rf"(?P<sep>\s+(?:och|samt|och\s+även)\s+)"
        rf"(?P<link>\[[^\]]*\]\(https://lagen\.nu/(?P<sfs>[\d:]+)#[^)]+\))",
        flags=re.DOTALL,
    )

    def repl_combined(m: re.Match) -> str:
        kap = m.group("kap1")
        para_text = m.group("para1")
        para_m = re.match(r"\d+(?:\s+[a-z](?!\w))?", para_text)
        paragraf = para_m.group(0) if para_m else para_text
        sfs = m.group("sfs")
        url = lagrum_url(sfs, kap, paragraf)
        # Bygg om: länka X1, behåll mellanrum och X2-länk.
        # Vi tar hela matchen och plockar ut X1-delen (allt före "sep").
        full = m.group(0)
        sep_start = m.start("sep") - m.start()
        x1_part = full[:sep_start]
        rest = full[sep_start:]
        x1_display = re.sub(r"\s+", " ", x1_part)
        return f"[{x1_display}]({url}){rest}"

    # OBS: replace_outside_links hoppar över befintliga länkar, men hela vår
    # match innehåller länken som sista del. Vi vill ändå köra. Använder
    # därför pattern.subn direkt här (lookbehind på X1 skyddar mot att
    # matcha inuti annan länk).
    pattern_combined_with_lb = re.compile(
        rf"(?<!\[)" + pattern_combined.pattern, flags=re.DOTALL
    )
    text, n_combined = pattern_combined_with_lb.subn(repl_combined, text)

    # Form 3: Omvänd ordning "LAG X kap. Y §" (eller "Y--Z §§").
    # T.ex. "fastighetsbildningslagen 7 kap. 4--5 §§".
    pattern3 = re.compile(
        rf"(?P<lag>{lag_pat_str})\s+"
        rf"(?P<kap>\d+)\s*kap\.\s+"
        rf"(?P<paragraf>{paragraf_pat})\s*§§?",
        flags=re.DOTALL,
    )

    def repl3(m: re.Match) -> str:
        kap = m.group("kap")
        para_text = m.group("paragraf")
        para_m = re.match(r"\d+(?:\s+[a-z](?!\w))?", para_text)
        paragraf = para_m.group(0) if para_m else para_text
        # Normalisera lagnamnet för uppslag i LAG_SFS
        # (whitespace kan ha radbrutits; ersätt med ' ').
        lag_raw = re.sub(r"\s+", " ", m.group("lag"))
        # Hitta vilken nyckel som matchar.
        sfs = None
        for k, v in LAG_SFS.items():
            if k.lower() == lag_raw.lower():
                sfs = v
                break
        if sfs is None:
            return m.group(0)  # ovanlig variant; lämna olänkad
        url = lagrum_url(sfs, kap, paragraf)
        display = re.sub(r"\s+", " ", m.group(0))
        return f"[{display}]({url})"

    text, n_rev = replace_outside_links(text, pattern3, repl3)

    return text, n_kap + n_nokap + n_rev + n_combined


def link_external_refs(text: str) -> tuple[str, int]:
    total = 0
    for pat_str, url in EU_REFS:
        pattern = re.compile(pat_str, flags=re.IGNORECASE)

        def repl(m: re.Match, u: str = url) -> str:
            return f"[{m.group(0)}]({u})"

        text, n = replace_outside_links(text, pattern, repl)
        total += n
    return text, total


def link_local_docs(text: str) -> tuple[str, int]:
    total = 0
    for pat_str, url in LOCAL_DOCS:
        pattern = re.compile(pat_str)

        def repl(m: re.Match, u: str = url) -> str:
            return f"[{m.group(0)}]({u})"

        text, n = replace_outside_links(text, pattern, repl)
        total += n
    return text, total


# --- Drivare ---


def process_file(path: Path) -> tuple[int, int, int, int]:
    original = path.read_text(encoding="utf-8")
    text = original

    text, mod_n = link_mod_cases(text)
    text, lagrum_n = link_lagrum(text)
    text, eu_n = link_external_refs(text)
    text, local_n = link_local_docs(text)

    if text != original:
        path.write_text(text, encoding="utf-8")
    return mod_n, lagrum_n, eu_n, local_n


def main() -> None:
    for path in MD_FILES:
        mod, lagrum, eu, local = process_file(path)
        print(
            f"{path.name}: +{mod} MÖD, +{lagrum} lagrum, +{eu} EU/Weser, +{local} lokala"
        )


if __name__ == "__main__":
    main()
