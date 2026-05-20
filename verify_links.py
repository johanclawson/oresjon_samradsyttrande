"""Verifiera alla länkar i README.md och yttranden/*.md.

- Externa HTTP(S)-länkar: HEAD-anrop (fallback till GET) med rimlig timeout.
- Lokala relativa filer: verifiera att filen existerar (rätt relativt md-filens plats).

Skriver en sammanställning per fil och en samlad rapport över trasiga länkar.
"""

from __future__ import annotations

import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import urllib.error
import urllib.request

ROOT = Path(__file__).parent
TARGET_FILES = [ROOT / "README.md", *sorted((ROOT / "yttranden").glob("*.md"))]
TIMEOUT = 15
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)

LINK_RE = re.compile(r"\[([^\[\]]*)\]\(([^)]+)\)")


def extract_links() -> list[tuple[Path, str, str, int]]:
    """Returnera [(md_path, linktext, url, radnr), ...]."""
    out: list[tuple[Path, str, str, int]] = []
    for md in TARGET_FILES:
        if not md.exists():
            continue
        for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            for m in LINK_RE.finditer(line):
                text, url = m.group(1), m.group(2)
                out.append((md, text, url, lineno))
    return out


def check_local(url: str, md_path: Path) -> tuple[bool, str]:
    path_part = url.split("#")[0].split("?")[0]
    target = (md_path.parent / path_part).resolve()
    if target.exists():
        return True, "OK"
    return False, f"saknas: {target}"


def check_http(url: str) -> tuple[bool, str]:
    url_base = url.split("#")[0]
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(
            url_base, method=method, headers={"User-Agent": USER_AGENT}
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                code = resp.status
                if 200 <= code < 400:
                    note = f"HTTP {code}"
                    if method == "GET":
                        note += " (HEAD ej stödd)"
                    return True, note
                return False, f"HTTP {code}"
        except urllib.error.HTTPError as e:
            if e.code in (405, 501) and method == "HEAD":
                continue
            return False, f"HTTP {e.code}: {e.reason}"
        except urllib.error.URLError as e:
            return False, f"URLError: {e.reason}"
        except TimeoutError:
            return False, f"timeout efter {TIMEOUT}s"
        except Exception as e:  # noqa: BLE001
            return False, f"{type(e).__name__}: {e}"
    return False, "okänt fel"


def main() -> int:
    links = extract_links()

    unique_http: set[str] = set()
    local_pairs: list[tuple[str, Path]] = []
    for md_path, _text, url, _line in links:
        if url.startswith(("http://", "https://")):
            unique_http.add(url)
        else:
            local_pairs.append((url, md_path))

    out = sys.stdout.buffer
    out.write(
        f"Hittade {len(links)} länkar totalt: {len(unique_http)} unika externa, "
        f"{len(local_pairs)} lokala\n\n".encode("utf-8")
    )
    out.flush()

    # Lokala (snabbt).
    local_results: list[tuple[str, Path, bool, str]] = []
    for url, md in local_pairs:
        ok, reason = check_local(url, md)
        local_results.append((url, md, ok, reason))

    # Externa parallellt.
    out.write(b"Kontrollerar externa URL:er...\n")
    out.flush()
    http_results: dict[str, tuple[bool, str]] = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(check_http, url): url for url in unique_http}
        for i, fut in enumerate(as_completed(futures), 1):
            url = futures[fut]
            http_results[url] = fut.result()
            ok, _ = http_results[url]
            mark = "OK " if ok else "FEL"
            out.write(
                f"  [{i}/{len(unique_http)}] {mark}  {url[:90]}\n".encode("utf-8")
            )
            out.flush()

    out.write(b"\n=== SAMMANSTALLNING ===\n")
    broken_http = [(u, r[1]) for u, r in http_results.items() if not r[0]]
    broken_local = [(u, str(md), r) for u, md, ok, r in local_results if not ok]

    out.write(
        f"Externa: {len(http_results) - len(broken_http)}/{len(http_results)} OK, "
        f"{len(broken_http)} trasiga\n".encode("utf-8")
    )
    out.write(
        f"Lokala:  {len(local_results) - len(broken_local)}/{len(local_results)} OK, "
        f"{len(broken_local)} trasiga\n\n".encode("utf-8")
    )

    if broken_http:
        out.write(b"TRASIGA EXTERNA URL:er:\n")
        for url, reason in broken_http:
            out.write(f"  [{reason}] {url}\n".encode("utf-8"))
        out.write(b"\n")

    if broken_local:
        out.write(b"TRASIGA LOKALA LANKAR:\n")
        for url, md, reason in broken_local:
            out.write(f"  [{reason}] {url}  (i {md})\n".encode("utf-8"))
        out.write(b"\n")

    return 0 if not (broken_http or broken_local) else 1


if __name__ == "__main__":
    sys.exit(main())
