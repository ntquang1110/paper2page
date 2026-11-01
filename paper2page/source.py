"""Lấy nguồn: PDF tại chỗ, DOI, PMID, PMCID, arXiv, hoặc URL.

Chuỗi dự phòng, thử lần lượt cho tới khi có PDF:
  1. Europe PMC      (bản toàn văn mở, nguồn số một cho y sinh và nông nghiệp)
  2. Unpaywall       (api.unpaywall.org, chỉ cần DOI, không cần khoá)
  3. Mẫu đường dẫn nhà xuất bản: Frontiers, Springer và BMC, PLOS, PeerJ
  4. arXiv           (bản in trước, tải trực tiếp)

Metadata luôn lấy được kể cả khi kho PDF chết: Crossref cho DOI, E-utilities cho PMID.
Không cào trang HTML của PubMed vì dính cookie wall.
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from typing import Optional

UA = "paper2page/1.0 (mailto:noreply@thefirstonly.com)"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)
TIMEOUT = 60
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"


@dataclass
class Meta:
    title: str = ""
    authors: list[str] = field(default_factory=list)
    journal: str = ""
    year: str = ""
    doi: str = ""
    pmid: str = ""
    pmcid: str = ""
    source_kind: str = ""
    source_ref: str = ""
    license: str = ""
    landing: str = ""
    pdf_via: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _get(url: str, binary: bool = False, accept: str = "*/*", ua: str = UA):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": accept})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def _json(url: str, ua: str = UA) -> dict:
    return json.loads(_get(url, accept="application/json", ua=ua))


def _clean_title(t: str) -> str:
    t = re.sub(r"<[^>]+>", "", t or "")
    return t.replace("\n", " ").strip().rstrip(".")


def _download(url: str, dest: str) -> str:
    data = _get(url, binary=True, accept="application/pdf, */*", ua=BROWSER_UA)
    if not data.startswith(b"%PDF"):
        raise ValueError(f"không phải PDF: {url} ({len(data)} byte)")
    with open(dest, "wb") as f:
        f.write(data)
    return dest


def _try_pdfs(candidates: list[tuple[str, str]], dest: str) -> tuple[Optional[str], str]:
    """candidates: [(nhãn, url)]. Trả về (đường dẫn, nhãn nguồn lấy được)."""
    errors = []
    for label, url in candidates:
        if not url:
            continue
        try:
            return _download(url, dest), label
        except Exception as e:  # noqa: BLE001
            errors.append(f"{label}: {type(e).__name__}")
    return None, "; ".join(errors[:6])


def detect_kind(src: str) -> tuple[str, str]:
    s = src.strip()
    if os.path.exists(s):
        return "file", s
    if re.fullmatch(r"\d{7,9}", s):
        return "pmid", s
    if re.fullmatch(r"PMC\d+", s, re.I):
        return "pmcid", s.upper()
    if re.match(r"^10\.\d{4,9}/\S+$", s):
        return "doi", s
    if re.match(r"^arXiv:\s*\d{4}\.\d{4,5}(v\d+)?$", s, re.I):
        return "arxiv", re.sub(r"^arXiv:\s*", "", s, flags=re.I)
    if re.fullmatch(r"\d{4}\.\d{4,5}(v\d+)?", s):
        return "arxiv", s
    if re.match(r"^https?://", s):
        m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", s)
        if m:
            return "arxiv", m.group(1)
        m = re.search(r"doi\.org/(10\.\d{4,9}/\S+)", s)
        if m:
            return "doi", m.group(1)
        m = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d{7,9})", s)
        if m:
            return "pmid", m.group(1)
        m = re.search(r"pmc\.ncbi\.nlm\.nih\.gov/articles/(PMC\d+)", s, re.I)
        if m:
            return "pmcid", m.group(1).upper()
        if s.lower().endswith(".pdf"):
            return "pdf_url", s
        return "landing", s
    raise ValueError(f"không nhận ra nguồn: {src!r}")


# ---------------------------------------------------------------- metadata


def _meta_from_epmc(rec: dict) -> Meta:
    m = Meta()
    m.title = _clean_title(rec.get("title") or "")
    m.authors = [a.strip() for a in (rec.get("authorString") or "").rstrip(".").split(",") if a.strip()]
    m.journal = (rec.get("journalInfo", {}).get("journal", {}) or {}).get("title", "") or ""
    m.year = str(rec.get("pubYear") or "")
    m.doi = rec.get("doi") or ""
    m.pmid = rec.get("pmid") or ""
    m.pmcid = rec.get("pmcid") or ""
    m.license = rec.get("license") or ""
    m.landing = f"https://doi.org/{m.doi}" if m.doi else ""
    return m


def _meta_from_crossref(doi: str) -> Meta:
    m = Meta(doi=doi, landing=f"https://doi.org/{doi}")
    try:
        cr = _json(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}")["message"]
    except Exception:
        return m
    m.title = _clean_title((cr.get("title") or [""])[0])
    m.journal = (cr.get("container-title") or [""])[0]
    m.year = str((cr.get("issued", {}).get("date-parts") or [[""]])[0][0] or "")
    m.authors = [
        f"{a.get('given','')} {a.get('family','')}".strip()
        for a in cr.get("author", [])[:40]
    ]
    lic = cr.get("license") or []
    m.license = (lic[0].get("URL") if lic else "") or ""
    return m


def _meta_from_pubmed(pmid: str) -> Meta:
    m = Meta(pmid=pmid, landing=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
    try:
        xml = _get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            f"?db=pubmed&id={pmid}&rettype=xml&retmode=xml"
        )
    except Exception:
        return m
    def grab(tag: str) -> str:
        mm = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xml, re.S)
        return re.sub(r"<[^>]+>", "", mm.group(1)).strip() if mm else ""
    m.title = _clean_title(grab("ArticleTitle"))
    m.journal = grab("Title")
    m.year = (re.search(r"<Year>(\d{4})</Year>", xml) or [None, ""])[1]
    m.authors = [
        f"{a} {b}".strip()
        for a, b in re.findall(r"<ForeName>(.*?)</ForeName>\s*<LastName>(.*?)</LastName>", xml)
    ][:40]
    doi = re.search(r'IdType="doi"[^>]*>([^<]+)<', xml)
    if doi:
        m.doi = doi.group(1)
        m.landing = f"https://doi.org/{m.doi}"
    pmc = re.search(r'IdType="pmc"[^>]*>(PMC\d+)<', xml)
    if pmc:
        m.pmcid = pmc.group(1)
    return m


# ---------------------------------------------------------------- pdf sources


def _epmc_records(kind: str, ref: str) -> list[dict]:
    q = {
        "doi": f'DOI:"{ref}"',
        "pmid": f"EXT_ID:{ref} AND SRC:MED",
        "pmcid": f"PMCID:{ref}",
    }[kind]
    try:
        d = _json(f"{EPMC}/search?query={urllib.parse.quote(q)}&format=json&resultType=core&pageSize=1")
    except Exception:
        return []
    return d.get("resultList", {}).get("result") or []


def _epmc_pdf_candidates(rec: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for u in (rec.get("fullTextUrlList", {}) or {}).get("fullTextUrl", []) or []:
        if (u.get("documentStyle") or "").lower() == "pdf":
            out.append(("europepmc", u.get("url", "")))
    pmcid = rec.get("pmcid") or ""
    if pmcid:
        out.append(("europepmc-file", f"https://europepmc.org/articles/{pmcid}?pdf=render"))
    return out


def _unpaywall_candidates(doi: str) -> list[tuple[str, str]]:
    try:
        d = _json(
            f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?email=noreply@thefirstonly.com"
        )
    except Exception:
        return []
    out: list[tuple[str, str]] = []
    for loc in [d.get("best_oa_location")] + (d.get("oa_locations") or []):
        if not loc:
            continue
        for key in ("url_for_pdf", "url"):
            u = loc.get(key) or ""
            if u.lower().endswith(".pdf") or key == "url_for_pdf":
                out.append(("unpaywall", u))
    return out


def _publisher_candidates(doi: str, pmcid: str = "") -> list[tuple[str, str]]:
    q = urllib.parse.quote(doi)
    out = [
        ("frontiers", f"https://www.frontiersin.org/articles/{doi}/pdf"),
        ("springer-bmc", f"https://link.springer.com/content/pdf/{doi}.pdf"),
        ("plos", f"https://journals.plos.org/plosone/article/file?id={doi}&type=printable"),
        ("peerj", f"https://peerj.com/articles/{doi.split('/')[-1]}.pdf"),
    ]
    if pmcid:
        out.append(("pmc", f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/"))
    return out


# ---------------------------------------------------------------- entry point


def resolve(src: str, workdir: str = ".", want_pdf: bool = True) -> tuple[Optional[str], Meta, Optional[str]]:
    """Trả về (đường dẫn PDF hoặc None, metadata, XML toàn văn hoặc None)."""
    kind, ref = detect_kind(src)
    meta = Meta(source_kind=kind, source_ref=ref)
    os.makedirs(workdir, exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", ref)[:80] or "paper"
    pdf_path = os.path.join(workdir, f"{slug}.pdf")

    if kind == "file":
        if not ref.lower().endswith(".pdf"):
            return None, meta, None
        if os.path.abspath(ref) != os.path.abspath(pdf_path):
            with open(ref, "rb") as a, open(pdf_path, "wb") as b:
                b.write(a.read())
        meta.pdf_via = "file"
        return pdf_path, meta, None

    if kind == "pdf_url":
        if not want_pdf:
            return None, meta, None
        path, via = _try_pdfs([("url", ref)], pdf_path)
        meta.pdf_via = via
        return path, meta, None

    if kind == "arxiv":
        meta.landing = f"https://arxiv.org/abs/{ref}"
        if not want_pdf:
            return None, meta, None
        path, via = _try_pdfs(
            [("arxiv", f"https://arxiv.org/pdf/{ref}"), ("arxiv-alt", f"https://export.arxiv.org/pdf/{ref}")],
            pdf_path,
        )
        meta.pdf_via = via
        return path, meta, None

    if kind == "landing":
        try:
            html = _get(ref, ua=BROWSER_UA)
        except Exception:
            html = ""
        m = re.search(r'(?:doi|DOI)"?\s*[:=]\s*"?(10\.\d{4,9}/[^"<\s&]+)', html or "")
        if m:
            return resolve(m.group(1), workdir, want_pdf)
        meta.landing = ref
        return None, meta, None

    # doi / pmid / pmcid: metadata trước, rồi tới kho PDF
    recs = _epmc_records(kind, ref)
    rec = recs[0] if recs else {}
    if rec:
        meta = _meta_from_epmc(rec)
        meta.source_kind, meta.source_ref = kind, ref
    elif kind == "doi":
        meta = _meta_from_crossref(ref)
        meta.source_kind, meta.source_ref = kind, ref
    elif kind == "pmid":
        meta = _meta_from_pubmed(ref)
        meta.source_kind, meta.source_ref = kind, ref
    elif kind == "pmcid":
        meta.pmcid = ref

    xml = None
    if rec:
        try:
            xml = _get(f"{EPMC}/{rec.get('source','MED')}/{rec.get('id','')}/fullTextXML")
        except Exception:
            xml = None

    if not want_pdf:
        return None, meta, xml

    cands: list[tuple[str, str]] = []
    if rec:
        cands += _epmc_pdf_candidates(rec)
    if meta.doi:
        cands += _unpaywall_candidates(meta.doi)
    cands += _publisher_candidates(meta.doi or ref, meta.pmcid or (ref if kind == "pmcid" else ""))

    path, via = _try_pdfs(cands, pdf_path)
    meta.pdf_via = via
    return path, meta, xml
