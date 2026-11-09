#!/usr/bin/env python3
"""Stage 1: acquire source texts for a proposal.

Usage:
    python scripts/authoring/acquire.py <slug> REF [REF ...]

A REF is a DOI, an OpenAlex work id (W...), an http(s) URL, or a local PDF.
For a work, the open-access PDF comes from OpenAlex (or Unpaywall when a
mailto is configured), is converted to TEI by the local Grobid service
(scripts/authoring/grobid-compose.yaml) and to plain text. A web page is
reduced to its main text. When Grobid cannot convert a PDF, its text layer
is extracted with pdftotext (poppler); a PDF without a text layer (an image
scan) is recorded as image_only_pdf. Texts go to work/<slug>/sources/, metadata to
work/<slug>/meta/, and one line per REF to work/<slug>/meta/acquired.jsonl.
Unavailable texts are recorded as such; nothing is guessed.
"""
import argparse
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import openalex  # noqa: E402
from net import ROOT, Client  # noqa: E402

GROBID = "http://127.0.0.1:8070/api/processFulltextDocument"
TEI = "{http://www.tei-c.org/ns/1.0}"


def key_for(ref: str) -> str:
    if re.match(r"^W\d+$", ref):
        return ref
    return re.sub(r"[^a-z0-9]+", "-", ref.lower()).strip("-")[:60] + "-" + hashlib.sha1(ref.encode()).hexdigest()[:6]


def tei_to_text(tei: bytes) -> str:
    from lxml import etree
    root = etree.fromstring(tei)
    parts = []
    for path in (f".//{TEI}titleStmt/{TEI}title", f".//{TEI}abstract", f".//{TEI}body"):
        for el in root.iterfind(path):
            parts.append(" ".join(" ".join(el.itertext()).split()))
    return "\n\n".join(p for p in parts if p)


def grobid(pdf: bytes, session) -> bytes:
    r = session.post(GROBID, files={"input": ("paper.pdf", pdf, "application/pdf")}, timeout=300)
    r.raise_for_status()
    return r.content


def pdf_to_text(pdf: bytes, key: str, sources: Path, session) -> tuple[str, str]:
    """(status, how): Grobid first, then the PDF's own text layer."""
    try:
        tei = grobid(pdf, session)
        (sources / f"{key}.tei.xml").write_bytes(tei)
        (sources / f"{key}.txt").write_text(tei_to_text(tei))
        return "ok", "grobid"
    except Exception:
        pass
    if shutil.which("pdftotext"):
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(pdf)
            tmp.flush()
            text = subprocess.run(["pdftotext", "-layout", tmp.name, "-"], capture_output=True, text=True).stdout
        if len(text.split()) > 50:
            (sources / f"{key}.txt").write_text(text)
            return "ok", "pdftotext"
        return "image_only_pdf", "no text layer"
    return "conversion_failed", "grobid failed and pdftotext is not installed"


def unpaywall_pdf(client: Client, doi: str) -> str | None:
    mailto = client.config.get("mailto")
    if not mailto:
        return None
    d = client.json(f"https://api.unpaywall.org/v2/{doi}", params={"email": mailto})
    loc = (d or {}).get("best_oa_location") or {}
    return loc.get("url_for_pdf")


def acquire_work(client: Client, ref: str, sources: Path, meta: Path) -> dict:
    w = openalex.work(client, ref)
    if w is None:
        return {"ref": ref, "status": "unresolved"}
    key = openalex.short_id(w["id"])
    (meta / f"{key}.openalex.json").write_text(json.dumps(w, indent=1))
    rec = {"ref": ref, "key": key, "openalex_id": key, "doi": w.get("doi"), "title": w.get("title"),
           "year": w.get("publication_year"), "is_retracted": w.get("is_retracted")}
    doi = (w.get("doi") or "").replace("https://doi.org/", "")
    url = openalex.oa_pdf_url(w) or (unpaywall_pdf(client, doi) if doi else None)
    if not url:
        return rec | {"status": "no_open_access_pdf"}
    r = client.get(url)
    if r.status_code != 200 or not r.content.startswith(b"%PDF"):
        return rec | {"status": "pdf_unavailable", "pdf_url": url}
    status, how = pdf_to_text(r.content, key, sources, client.session)
    rec |= {"status": status, "pdf_url": url, "converted_by": how}
    return rec | ({"text": f"sources/{key}.txt"} if status == "ok" else {})


def acquire_url(client: Client, url: str, sources: Path) -> dict:
    import trafilatura
    r = client.get(url)
    key = key_for(url)
    if r.status_code != 200:
        return {"ref": url, "key": key, "status": f"http_{r.status_code}"}
    text = trafilatura.extract(r.text) or ""
    if not text.strip():
        return {"ref": url, "key": key, "status": "no_main_text"}
    (sources / f"{key}.txt").write_text(text)
    return {"ref": url, "key": key, "status": "ok", "text": f"sources/{key}.txt"}


def acquire_pdf(client: Client, path: Path, sources: Path) -> dict:
    key = key_for(path.name)
    status, how = pdf_to_text(path.read_bytes(), key, sources, client.session)
    rec = {"ref": str(path), "key": key, "status": status, "converted_by": how}
    return rec | ({"text": f"sources/{key}.txt"} if status == "ok" else {})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("slug")
    ap.add_argument("refs", nargs="+")
    a = ap.parse_args(argv)
    base = ROOT / "work" / a.slug
    sources, meta = base / "sources", base / "meta"
    sources.mkdir(parents=True, exist_ok=True)
    meta.mkdir(parents=True, exist_ok=True)
    client = Client()
    today = datetime.date.today().isoformat()
    with open(meta / "acquired.jsonl", "a") as log:
        for ref in a.refs:
            if Path(ref).is_file():
                rec = acquire_pdf(client, Path(ref), sources)
            elif re.match(r"^(10\.|https://doi\.org/|W\d+$)", ref):
                rec = acquire_work(client, ref, sources, meta)
            elif re.match(r"^https?://", ref):
                rec = acquire_url(client, ref, sources)
            else:
                rec = {"ref": ref, "status": "unrecognized"}
            rec["retrieved"] = today
            log.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(json.dumps(rec, ensure_ascii=False))


if __name__ == "__main__":
    main()
