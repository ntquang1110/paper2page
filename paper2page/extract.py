"""Bóc cấu trúc bài báo từ PDF: phần, đoạn, trang, hình bảng, số liệu, tài liệu tham khảo.

Nguyên tắc: mọi đơn vị văn bản đều giữ số trang gốc để người đọc mở bài ra so lại được.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field, asdict
from typing import Optional

SECTION_ALIASES = {
    "abstract": "Tóm tắt",
    "summary": "Tóm tắt",
    "introduction": "Đặt vấn đề",
    "background": "Đặt vấn đề",
    "materials and methods": "Vật liệu và phương pháp",
    "material and methods": "Vật liệu và phương pháp",
    "methods": "Phương pháp",
    "method": "Phương pháp",
    "methodology": "Phương pháp",
    "results": "Kết quả",
    "results and discussion": "Kết quả và bàn luận",
    "discussion": "Bàn luận",
    "conclusion": "Kết luận",
    "conclusions": "Kết luận",
    "limitations": "Hạn chế",
    "acknowledgements": "Lời cảm ơn",
    "acknowledgments": "Lời cảm ơn",
    "references": "Tài liệu tham khảo",
    "funding": "Nguồn tài trợ",
    "supplementary": "Phụ lục",
    "data availability": "Dữ liệu",
    "conflict of interest": "Xung đột lợi ích",
}

STOP_SECTIONS = {"tài liệu tham khảo", "lời cảm ơn", "nguồn tài trợ", "phụ lục", "xung đột lợi ích"}

JUNK_HEAD_RE = re.compile(
    r"^(?:author contributions?|authors? contributions?|supplementary|supplemental|"
    r"abbreviations?|ethics? (?:statement|approval)|data availability|conflict of interest|"
    r"competing interests?|funding|acknowledge?ments?|credit authorship|orcid|keywords?|"
    r"highlights?|graphical abstract|table of contents|frontiers in|open access|"
    r"editor|reviewer|received|accepted|published|copyright|license)\b",
    re.I,
)

# Dòng trông như tiêu đề nhưng thực ra là mục lục tài liệu: "1 March 2022).", "3. Smith et al."
CITATION_HEAD_RE = re.compile(
    r"\b(?:19|20)\d{2}\b|\bet al\b|doi|https?://|"
    r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b",
    re.I,
)

# Ruột bìa nhà xuất bản, không phải nội dung khoa học
FRONT_FURNITURE_RE = re.compile(
    r"@|doi|frontiers|volume|article \d|edited by|reviewed by|received:|accepted:|published:|"
    r"correspondence|keyword|abbreviat|specialty section|state key laboratory|university|"
    r"college|institute|department|https?://|citation:|ORIGINAL RESEARCH|license|"
    r"citation|academy of|school of|hospital",
    re.I,
)

FIGURE_RE = re.compile(
    r"^(?:fig(?:ure)?\.?|hình)\s*(\d+[a-z]?)\s*[.:)]?\s*(.*)$", re.I
)
TABLE_RE = re.compile(r"^(?:tab(?:le)?\.?|bảng)\s*(\d+[a-z]?)\s*[.:)]?\s*(.*)$", re.I)

STAT_RE = re.compile(
    r"(?:"
    r"p\s*[<>=]\s*0?\.\d+|P\s*[<>=]\s*0?\.\d+"
    r"|n\s*=\s*\d+|\bN\s*=\s*\d+"
    r"|95\s*%\s*(?:CI|confidence interval)"
    r"|[±]\s*\d+(?:[.,]\d+)?"
    r"|\b\d+(?:[.,]\d+)?\s*(?:%|‰)"
    r"|\b\d+(?:[.,]\d+)?\s*(?:mg|g|kg|µg|ug|ng|mL|ml|L|µL|uL|mM|µM|uM|nM|ppm|IU|CFU|kcal|MJ|kJ|mm|cm|nm|µm|h|min|s|d|wk|week|day|month|year)s?\b"
    r"|\b\d+(?:[.,]\d+)?\s*(?:fold|log2FC|log10)"
    r")",
    re.I,
)

DOSE_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?(?:\s*-\s*\d+(?:[.,]\d+)?)?\s*"
    r"(?:mg|µg|ug|ng|g|IU|CFU|mM|µM|uM|nM|ppm|%)\s*"
    r"(?:[A-Z][a-z]?\s*)?(?:/\s*(?:kg|L|l|mL|ml|d|day|ton|h))?",
    re.I,
)

CAUSAL = [
    (r"\b(?:inhibit|inhibits|inhibited|inhibition of|block(?:s|ed)?|suppress(?:es|ed)?|reduc(?:es|ed|tion of)|decreas(?:es|ed)|downregulat(?:es|ed)|lower(?:s|ed)|attenuat(?:es|ed))\b", "⊣", "chặn hoặc làm giảm"),
    (r"\b(?:increas(?:es|ed)|enhanc(?:es|ed)|elevat(?:es|ed)|upregulat(?:es|ed)|promot(?:es|ed)|activat(?:es|ed)|increas(?:e|ing) of|improv(?:es|ed)|higher)\b", "→", "kích hoạt hoặc làm tăng"),
    (r"\b(?:no significant|did not|failed to|without effect)\b", "⊘", "không có tác động rõ"),
]
SYMBOL_LABEL = {
    "→": "kích hoạt / làm tăng",
    "⊣": "chặn / ức chế",
    "⊘": "không thấy tác động",
    "↑": "tăng",
    "↓": "giảm",
}

HEDGE_RE = re.compile(
    r"\b(?:may|might|could|suggest(?:s|ed|ing)?|possibly|potentially|likely|unclear|"
    r"partially|partly|appears?|seems?|warrant|further studies|future studies|remains? to be|"
    r"remains? unclear|we hypothesi[sz]e|speculat)\b",
    re.I,
)
LIMIT_RE = re.compile(
    r"\b(?:limitation|limited by|caveat|not assessed|was not measured|did not measure|"
    r"single (?:dose|strain|batch)|small sample|short[- ]term|further (?:studies|research|work)|"
    r"future (?:studies|research|work)|remains? (?:unclear|unknown|to be)|cannot be excluded|"
    r"no data|not determined|in vitro only)\b",
    re.I,
)
ACRONYM_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,7})\b")
ACRONYM_DEF_RE = re.compile(r"\b([A-Z][A-Za-z0-9\-]{2,40}?)\s*\(([A-Z][A-Z0-9]{1,7})\)")

CITATION_RE = re.compile(
    r"\b(?:et al\.?|doi\.org/10\.|PMID:?\s*\d+|10\.\d{4,9}/[^\s,;)\.]+)", re.I
)

# PDF hay trả chữ ghép kiểu ligature và nháy cong. Chuẩn hoá ngay lúc bóc để mọi
# biểu thức phía sau nhìn thấy chữ thường, và để đầu ra không lẫn ký tự lạ.
CHAR_FIX = {
    "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl",
    "\ufb05": "st", "\ufb06": "st",
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": ", ", "\u2212": "-", "\u2026": "...", "\u00a0": " ",
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u00ad": "",
}


def normalize_text(s: str) -> str:
    for bad, good in CHAR_FIX.items():
        if bad in s:
            s = s.replace(bad, good)
    return s


@dataclass
class Block:
    kind: str            # heading | para | caption | list | quote
    text: str
    page: int
    size: float = 0.0
    level: int = 0       # 1 bài, 2 phần chính, 3 phần con


@dataclass
class Section:
    key: str             # mã tiếng Anh để xử lý
    label: str           # nhãn hiển thị tiếng Việt
    raw_heading: str
    page: int
    blocks: list[Block] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(b.text for b in self.blocks)

    @property
    def words(self) -> int:
        return len(self.text.split())

    @property
    def subheads(self) -> list[str]:
        return [b.text for b in self.blocks if b.kind == "subhead"]


@dataclass
class Figure:
    kind: str            # figure | table
    number: str
    caption: str
    page: int


@dataclass
class Paper:
    source: dict
    title: str = ""
    abstract: str = ""
    sections: list[Section] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    stats: list[dict] = field(default_factory=list)
    doses: list[dict] = field(default_factory=list)
    body_font: float = 0.0
    pages: int = 0
    full_text_path: str = ""

    def section(self, key: str) -> Optional[Section]:
        """Nhận cả mã tiếng Anh (references) lẫn nhãn tiếng Việt (Tài liệu tham khảo)."""
        want = key.strip().lower()
        for s in self.sections:
            if want in (s.key.lower(), s.label.lower()):
                return s
        return None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["section_words"] = [{"label": s.label, "words": s.words} for s in self.sections]
        return d


def _norm_heading(line: str) -> str:
    h = re.sub(r"^[\d\.\s]+", "", line.strip()).strip(" .:0123456789")
    return h.lower()


def _sections_from_lines(lines: list[dict], body_size: float) -> list[Section]:
    """lines: [{text, page, size}] đã theo thứ tự đọc.

    Chỉ tiêu đề mức một mới mở phần mới. Tiêu đề con (Western Blotting Analysis,
    Statistical Analysis) nằm lại trong phần cha dưới dạng khối subhead, để mục lục
    không bị vụn thành ba chục dòng.
    """
    sections: list[Section] = []
    current: Optional[Section] = None
    seen: Counter = Counter()
    in_refs = False

    for ln in lines:
        raw = ln["text"].strip()
        if not raw:
            continue
        if in_refs:
            current.blocks.append(Block(kind="para", text=raw, page=ln["page"], size=ln["size"]))
            continue
        norm = _norm_heading(raw)
        if JUNK_HEAD_RE.match(raw):
            continue
        known = norm in SECTION_ALIASES
        is_main_numbered = bool(re.match(r"^\d{1,2}[.)]?\s+[A-Z]", raw)) and not re.match(
            r"^\d{1,2}\.\d", raw
        )
        short_enough = len(raw) <= 90 and not raw.endswith(".")
        big = ln["size"] >= body_size * 1.14 and short_enough
        if not known and len(raw) >= 8 and CITATION_HEAD_RE.search(raw):
            # dòng kiểu "1 March 2022)." hoặc mục tài liệu: trả về thân bài, không mở phần mới
            if current is None:
                current = Section(key="front", label="Đầu bài", raw_heading="", page=ln["page"])
                sections.append(current)
            current.blocks.append(Block(kind="para", text=raw, page=ln["page"], size=ln["size"]))
            continue

        if (known or is_main_numbered or big) and len(raw) <= 120:
            key = norm if known else re.sub(r"[^a-z ]+", "", norm).strip()
            if known and seen[key] == 0:
                seen[key] += 1
                current = Section(key=key, label=SECTION_ALIASES[key], raw_heading=raw, page=ln["page"])
                sections.append(current)
                if key == "references":
                    in_refs = True
                continue
            if is_main_numbered and not known and seen.get(key, 0) == 0 and 3 <= len(key) <= 60:
                seen[key] = 1
                label = re.sub(r"^\d{1,2}[.)]?\s*", "", raw).strip(" .")
                current = Section(key=key, label=label or raw, raw_heading=raw, page=ln["page"])
                sections.append(current)
                continue
            if big and not known and not is_main_numbered:
                # tiêu đề con: giữ trong phần cha
                if current is None:
                    current = Section(key="front", label="Đầu bài", raw_heading="", page=ln["page"])
                    sections.append(current)
                current.blocks.append(
                    Block(kind="subhead", text=raw.strip(" ."), page=ln["page"], size=ln["size"])
                )
                continue

        if current is None:
            current = Section(key="front", label="Đầu bài", raw_heading="", page=ln["page"])
            sections.append(current)
        current.blocks.append(
            Block(kind="para", text=raw, page=ln["page"], size=ln["size"])
        )
    for s in sections:
        for b in s.blocks:
            if FIGURE_RE.match(b.text) or TABLE_RE.match(b.text):
                b.kind = "caption"

    # gộp phần trùng nhãn: "Conclusion" rồi "conclusions" ở cùng trang là một phần
    merged: list[Section] = []
    by_label: dict[str, Section] = {}
    for s in sections:
        prev = by_label.get(s.label)
        if prev is not None and s.words < 400:
            prev.blocks.extend(s.blocks)
            continue
        by_label[s.label] = s
        merged.append(s)
    sections = merged
    return sections


def extract_pdf(path: str) -> Paper:
    import pymupdf  # noqa

    doc = pymupdf.open(path)
    paper = Paper(source={"kind": "pdf", "path": path})
    paper.pages = doc.page_count

    lines: list[dict] = []
    sizes: Counter = Counter()
    for pno in range(doc.page_count):
        page = doc[pno]
        d = page.get_text("dict")
        for blk in d.get("blocks", []):
            if blk.get("type") != 0:
                continue
            for line in blk.get("lines", []):
                txt = normalize_text("".join(sp.get("text", "") for sp in line.get("spans", [])))
                if not txt.strip():
                    continue
                size = max((round(sp.get("size", 0), 1) for sp in line.get("spans", [])), default=0.0)
                lines.append({"text": txt, "page": pno + 1, "size": size, "y": line.get("bbox", [0, 0, 0, 0])[1]})
                sizes[size] += len(txt)
    doc.close()

    if not lines:
        return paper

    # cỡ chữ thân bài = cỡ chiếm nhiều ký tự nhất trong khoảng 7 đến 13pt
    body_candidates = {s: n for s, n in sizes.items() if 7 <= s <= 13}
    body_size = max(body_candidates, key=body_candidates.get) if body_candidates else 10.0
    paper.body_font = body_size

    # tiêu đề bài: dòng cỡ lớn nhất ở trang 1, trước dòng abstract
    p1 = [l for l in lines if l["page"] == 1]
    head_pool = [l for l in p1 if l["size"] >= body_size * 1.2 and len(l["text"].strip()) > 12]
    if head_pool:
        top_size = max(l["size"] for l in head_pool)
        title_lines = [l["text"].strip() for l in head_pool if l["size"] >= top_size - 0.6][:4]
        paper.title = " ".join(title_lines).strip()

    paper.sections = _sections_from_lines(lines, body_size)

    # bỏ ruột bìa: mọi phần nằm trước Tóm tắt là tiêu đề, tên tạp chí, dòng đóng dấu
    abs_idx = next((i for i, s in enumerate(paper.sections) if s.key == "abstract"), None)
    if abs_idx is not None:
        paper.sections = paper.sections[abs_idx:]
    else:
        front = next((s for s in paper.sections if s.key == "front"), None)
        if front:
            body = [
                b.text for b in front.blocks
                if b.kind == "para" and len(b.text) > 300 and not FRONT_FURNITURE_RE.search(b.text)
            ]
            if body:
                paper.abstract = " ".join(body[:4])[:2500]
        paper.sections = [s for s in paper.sections if s.key != "front"]

    for s in paper.sections:
        if s.key == "abstract":
            paper.abstract = s.text
            break
    if not paper.abstract and paper.sections:
        for s in paper.sections:
            if s.key in ("front", "introduction"):
                paper.abstract = " ".join(b.text for b in s.blocks[:3])
                break

    # hình, bảng
    for s in paper.sections:
        for b in s.blocks:
            for rx, kind in ((FIGURE_RE, "figure"), (TABLE_RE, "table")):
                m = rx.match(b.text)
                if m:
                    paper.figures.append(
                        Figure(kind=kind, number=m.group(1), caption=b.text.strip(), page=b.page)
                    )
                    break

    # tài liệu tham khảo
    ref = paper.section("tài liệu tham khảo")
    if ref:
        joined = "\n".join(b.text for b in ref.blocks)
        parts = re.split(r"\n(?=\s*(?:\[\d+\]|\d{1,3}[.)])\s)", joined)
        paper.references = [p.strip() for p in parts if len(p.strip()) > 30][:200]

    # số liệu và liều, giữ nguyên văn
    for s in paper.sections:
        if s.label in STOP_SECTIONS:
            continue
        for b in s.blocks:
            for m in STAT_RE.finditer(b.text):
                paper.stats.append(
                    {"value": m.group(0), "section": s.label, "page": b.page, "sentence": b.text[:300]}
                )
            for m in DOSE_RE.finditer(b.text):
                paper.doses.append(
                    {"value": m.group(0).replace("\u2013", "-"), "agent_hint": _agent_hint(b.text, m.start()),
                     "section": s.label, "page": b.page}
                )
    return paper


def _agent_hint(sentence: str, pos: int) -> str:
    """Cụm danh từ gần nhất trước con số, cắt gọn, để biết liều này của chất nào."""
    left = sentence[:pos].strip()
    left = re.split(r"[.;]\s", left)[-1]
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", left)
    return " ".join(words[-4:])


def extract_text_dump(paper: Paper) -> str:
    out = [f"# {paper.title}", ""]
    for s in paper.sections:
        out.append(f"## {s.label} (trang {s.page})")
        for b in s.blocks:
            out.append(b.text)
        out.append("")
    return "\n".join(out)
