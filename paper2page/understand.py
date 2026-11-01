"""Dựng mô hình hiểu bài báo.

Ba tầng đọc:
  Tầng 1 (5 giây)  : một câu chốt, cỡ mẫu, ba con số then chốt, kết luận của tác giả.
  Tầng 2 (1 phút)  : mục lục từng phần kèm một dòng mục đích.
  Tầng 3 (đọc kỹ)  : từng câu khẳng định có nhãn bằng chứng, bản đồ cơ chế, số liệu, giới hạn.

Mức bằng chứng, gán tự động theo hình thức câu, không theo cảm nhận:
  E  số đo nằm ngay trong câu, có số và đơn vị
  F  câu trỏ tới hình hoặc bảng (Figure 2, Table 1), số nằm ngoài câu chữ
  I  câu suy luận, cơ chế đề xuất, có từ để ngữ như suggest, may, could
  H  câu khẳng định không kèm số
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field, asdict

from .extract import (
    ACRONYM_DEF_RE,
    CAUSAL,
    CITATION_RE,
    DOSE_RE,
    FIGURE_RE,
    HEDGE_RE,
    LIMIT_RE,
    STAT_RE,
    TABLE_RE,
    SYMBOL_LABEL,
    Paper,
)

EVIDENCE_LABEL = {
    "E": "Số đo trong câu",
    "F": "Bằng chứng ở hình hoặc bảng",
    "I": "Suy luận hoặc cơ chế đề xuất",
    "H": "Khẳng định không kèm số",
}

SKIP_SECTIONS = {"Tài liệu tham khảo", "Lời cảm ơn", "Nguồn tài trợ", "Xung đột lợi ích", "Phụ lục"}

JUNK_LABEL_RE = re.compile(
    r"arxiv|preprint|doi\b|http|www\.|received|accepted|published|copyright|"
    r"\b\d{4}\.\d{4,5}\b|^\W*$",
    re.I,
)

CLAIM_CAP = 60

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])")


def sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    out = []
    for s in SENT_SPLIT.split(text):
        s = s.strip()
        if len(s) < 40:
            continue
        if CITATION_RE.search(s) and len(s) < 60:
            continue
        letters = sum(ch.isalpha() for ch in s)
        if letters < len(s) * 0.55:          # dòng toàn số, mã, ký hiệu
            continue
        if re.fullmatch(r"[\W\d]+", s):
            continue
        out.append(s)
    return out


def is_junk_section(sec, title: str = "") -> bool:
    """Bỏ đầu bài, dòng đóng dấu của nhà xuất bản, tiêu đề bài lọt vào mục lục, phần quá ngắn."""
    if sec.key == "front" or sec.label in SKIP_SECTIONS:
        return True
    lab = sec.label.strip()
    if JUNK_LABEL_RE.search(lab):
        return True
    if title and lab.lower()[:40] == title.lower().strip()[:40]:
        return True
    if sec.words < 30:
        return True
    return False


def kept_sections(paper) -> list:
    return [s for s in paper.sections if not is_junk_section(s, paper.title)]


def evidence_class(sentence: str) -> str:
    has_stat = bool(STAT_RE.search(sentence))
    points_to_visual = bool(FIGURE_RE.match(sentence) or TABLE_RE.match(sentence)) or bool(
        re.search(r"\b(?:fig(?:ure)?|tab(?:le)?)\.?\s*\d", sentence, re.I)
    )
    hedged = bool(HEDGE_RE.search(sentence))
    if points_to_visual and not has_stat:
        return "F"
    if has_stat and not hedged:
        return "E"
    if hedged:
        return "I"
    if has_stat:
        return "E"
    return "H"


@dataclass
class Claim:
    text: str
    section: str
    page: int
    evidence: str
    is_limitation: bool = False
    is_open: bool = False


@dataclass
class FlowStep:
    subject: str
    symbol: str
    object: str
    sentence: str
    page: int

    @property
    def symbol_label(self) -> str:
        return SYMBOL_LABEL.get(self.symbol, self.symbol)


@dataclass
class Understanding:
    headline: str = ""
    conclusion: str = ""
    sample: str = ""
    sample_note: str = ""
    key_numbers: list[dict] = field(default_factory=list)
    toc: list[dict] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    evidence_counts: dict = field(default_factory=dict)
    n_claims_total: int = 0
    n_claims_shown: int = 0
    section_totals: dict = field(default_factory=dict)
    flow: list[FlowStep] = field(default_factory=list)
    limitations: list[Claim] = field(default_factory=list)
    limitations_source: str = ""
    open_questions: list[Claim] = field(default_factory=list)
    critique: list[str] = field(default_factory=list)
    glossary: list[dict] = field(default_factory=list)
    doses: list[dict] = field(default_factory=list)
    figure_index: list[dict] = field(default_factory=list)
    section_weights: list[dict] = field(default_factory=list)
    method_sentences: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def validate(self) -> list[str]:
        """Cổng kiểm nội dung: trả về danh sách lỗi, rỗng nghĩa là đạt."""
        errs: list[str] = []
        if not self.headline:
            errs.append("thiếu câu chốt tầng 1")
        if len(self.claims) < 5:
            errs.append(f"quá ít câu khẳng định: {len(self.claims)}")
        if not self.limitations:
            errs.append("không tìm được mục giới hạn nào, cần đọc tay phần bàn luận")
        if not self.toc:
            errs.append("không dựng được mục lục")
        if not self.key_numbers:
            errs.append("không bóc được số liệu nào")
        unstamped = [c for c in self.claims if not c.section or not c.page]
        if unstamped:
            errs.append(f"{len(unstamped)} câu khẳng định thiếu vị trí nguồn")
        return errs


def _sample_size(paper: Paper) -> str:
    return _sample(paper)[0]


def _sample(paper: Paper) -> tuple[str, str]:
    """Trả về (số hiển thị to, ghi chú nhỏ). Tách ra để ô số không bị ngắt dòng xấu."""
    txt = paper.abstract + "\n" + "\n".join(s.text for s in paper.sections if s.label not in SKIP_SECTIONS)
    cands = [int(c) for c in re.findall(r"\bn\s*=\s*(\d+)", txt)]
    cands += [int(c) for c in re.findall(r"[Aa]\s+total\s+of\s+(\d+)", txt)]
    cands += [int(c) for c in re.findall(r"(\d+)\s+(?:cross-?bred\s+)?(?:piglets|mice|rats|chicks|calves|lambs|patients|subjects|animals)\b", txt, re.I)]
    cands = [c for c in cands if c >= 4]
    if not cands:
        return "", ""
    top = max(cands)
    note = f"nhóm nhỏ nhất {min(cands)}" if min(cands) < top else ""
    return f"{top} con", note


def _headline(paper: Paper, concl: str) -> str:
    if concl:
        first = sentences(concl)
        if first:
            return first[0]
    ab = sentences(paper.abstract)
    return ab[-1] if ab else (paper.title or "Chưa bóc được tóm tắt")


def _key_numbers(paper: Paper, top: int = 3) -> list[dict]:
    """Ba con số then chốt: ưu tiên câu kết luận, rồi tóm tắt, rồi kết quả.
    Giữ nguyên văn, kèm câu chứa nó để người đọc tự đối chiếu."""
    out: list[dict] = []
    seen: set[str] = set()
    order = ["Kết luận", "Tóm tắt", "Kết quả", "Kết quả và bàn luận", "Bàn luận"]

    def prefer(st: dict) -> int:
        """Phần trăm và số lần thay đổi là kết quả. Liều thuốc là đầu vào, xếp sau."""
        v = st["value"]
        if "%" in v:
            return 0
        if re.search(r"fold|log2FC", v, re.I):
            return 1
        if re.search(r"mg/kg|g/kg|ppm|IU", v, re.I):
            return 3
        return 2

    pool = sorted(
        (st for st in paper.stats if st["section"] in order),
        key=lambda st: (order.index(st["section"]), prefer(st)),
    )
    pool += sorted(
        (st for st in paper.stats if st["section"] not in order),
        key=prefer,
    )

    def useful(v: str) -> bool:
        v = v.strip()
        if re.fullmatch(r"\d{1,2}", v):
            return False
        if re.match(r"^[pP]\s*[<>=]", v):          # ngưỡng ý nghĩa, không phải kết quả
            return False
        if re.match(r"^n\s*=", v, re.I):           # cỡ mẫu đã có ô riêng ở tầng một
            return False
        if re.fullmatch(r"[±]?\s*\d+([.,]\d+)?", v):
            return False
        # đơn vị phải tách khỏi số, tránh bắt nhầm mã kiểu "3D" hay "B16044"
        if "%" not in v and not re.match(r"^[±]?\s*\d+([.,]\d+)?\s+\S", v):
            return False
        return True

    for st in pool:
        v = st["value"].strip()
        key = re.sub(r"\s+", "", v.lower())
        if key in seen:
            continue
        if not useful(v):
            continue
        seen.add(key)
        out.append(st)
        if len(out) >= top:
            break
    return out


def _toc(paper: Paper) -> list[dict]:
    out = []
    for s in kept_sections(paper):
        ss = sentences(s.text)
        purpose = ss[0][:220] if ss else ""
        out.append(
            {"label": s.label, "page": s.page, "words": s.words, "first": purpose,
             "n_sentences": len(ss), "anchors": s.key}
        )
    return out


EDGE_STOP = {
    "the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for", "with", "by",
    "was", "were", "is", "are", "be", "been", "both", "also", "that", "this", "these",
    "those", "than", "as", "while", "but", "not", "no", "significantly", "markedly",
    "effectively", "significantly,", "compared", "respectively", "however", "thus",
    "there", "which", "who", "it", "its", "their", "these", "then", "when", "where",
}


def _trim(fragment: str, take_last: bool, window: int = 7) -> str:
    """Cắt cụm danh từ sát ký hiệu quan hệ, bỏ từ nối ở hai đầu."""
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-]{1,}", fragment)
    words = [w for w in words if w.lower() not in EDGE_STOP]
    picked = words[-window:] if take_last else words[:window]
    while picked and picked[0].lower() in EDGE_STOP:
        picked.pop(0)
    while picked and picked[-1].lower() in EDGE_STOP:
        picked.pop()
    out: list[str] = []
    for w in picked:
        if out and out[-1].lower() == w.lower():
            continue
        out.append(w)
    return " ".join(out)


def _flow(paper: Paper, cap: int = 14) -> list[FlowStep]:
    steps: list[FlowStep] = []
    for s in kept_sections(paper):
        for b in s.blocks:
            if b.kind == "caption":
                continue
            for sent in sentences(b.text):
                for rx, sym, _ in CAUSAL:
                    m = re.search(rx, sent, re.I)
                    if not m:
                        continue
                    left = sent[: m.start()]
                    right = sent[m.end():]
                    subj = _trim(left, take_last=True) or "chủ thể"
                    obj = _trim(right, take_last=False) or "đối tượng"
                    steps.append(FlowStep(subject=subj, symbol=sym, object=obj, sentence=sent, page=b.page))
                    break
    # giữ bước không trùng đuôi câu, ưu tiên phần kết quả và bàn luận
    uniq: list[FlowStep] = []
    seen: set[str] = set()
    for st in steps:
        k = st.sentence[:80].lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(st)
    return uniq[:cap]


def _glossary(paper: Paper, cap: int = 18) -> list[dict]:
    text = paper.abstract + "\n" + "\n".join(s.text for s in paper.sections)
    found: dict[str, str] = {}
    for m in ACRONYM_DEF_RE.finditer(text):
        full, abbr = m.group(1).strip(), m.group(2)
        if abbr in {"THE", "AND", "FOR", "WITH", "TABLE", "FIGURE", "CI", "SD", "SE", "USA", "DNA", "RNA"}:
            continue
        found.setdefault(abbr, full)
    counts = Counter(re.findall(r"\b[A-Z][A-Z0-9]{1,7}\b", text))
    out = [{"abbr": a, "full": f, "count": counts.get(a, 0)} for a, f in found.items()]
    out.sort(key=lambda x: -x["count"])
    return out[:cap]


def _method_sentences(paper: Paper, cap: int = 12) -> list[dict]:
    out: list[dict] = []
    for s in kept_sections(paper):
        if s.label not in ("Phương pháp", "Vật liệu và phương pháp"):
            continue
        for b in s.blocks:
            for sent in sentences(b.text):
                if re.search(
                    r"\b(?:were|was|randomly|allocated|assigned|divided|supplemented|fed|"
                    r"incubated|cultured|measured|determined|analy[sz]ed|n\s*=|for\s+\d+\s*(?:d|days|wk|weeks))\b",
                    sent,
                    re.I,
                ):
                    out.append({"text": sent, "page": b.page})
    # bỏ trùng
    seen = set()
    dedup = []
    for m in out:
        k = m["text"][:60]
        if k in seen:
            continue
        seen.add(k)
        dedup.append(m)
    return dedup[:cap]


def build(paper: Paper) -> Understanding:
    u = Understanding()
    concl_sec = paper.section("kết luận")
    concl_text = concl_sec.text if concl_sec else ""
    if not concl_text:
        for label in ("Kết quả và bàn luận", "Bàn luận", "Tóm tắt"):
            sec = next((s for s in paper.sections if s.label == label), None)
            if sec:
                concl_text = " ".join(sentences(sec.text)[-2:])
                break

    u.conclusion = " ".join(sentences(concl_text)[:2])[:600]
    u.headline = _headline(paper, u.conclusion)
    u.sample, u.sample_note = _sample(paper)
    u.key_numbers = _key_numbers(paper)
    u.toc = _toc(paper)
    u.flow = _flow(paper)
    u.glossary = _glossary(paper)
    u.doses = paper.doses[:14]
    u.method_sentences = _method_sentences(paper)
    u.figure_index = [
        {"kind": "Hình" if f.kind == "figure" else "Bảng", "number": f.number,
         "caption": f.caption[:300], "page": f.page}
        for f in paper.figures[:40]
    ]
    u.section_weights = [{"label": t["label"], "words": t["words"]} for t in u.toc]

    pool: list[Claim] = []
    for s in kept_sections(paper):
        for b in s.blocks:
            if b.kind in ("caption",):
                continue
            for sent in sentences(b.text):
                ev = evidence_class(sent)
                c = Claim(
                    text=sent[:520],
                    section=s.label,
                    page=b.page,
                    evidence=ev,
                    is_limitation=bool(LIMIT_RE.search(sent)),
                    is_open=bool(
                        re.search(
                            r"\b(?:further|future|remains? (?:unclear|unknown|to be determined)|"
                            r"not (?:yet )?(?:known|assessed|measured)|needs? (?:to be |to confirm))",
                            sent,
                            re.I,
                        )
                    ),
                )
                pool.append(c)

    # hiển thị có chọn lọc: câu có số đo và câu tự giới hạn lên trước, phần còn lại vẫn đếm đủ
    weight = {"E": 4, "F": 3, "I": 2, "H": 1}

    def rank(c: Claim) -> tuple:
        bonus = 2 if (c.is_limitation or c.is_open) else 0
        length_bonus = 1 if 120 <= len(c.text) <= 400 else 0
        return (-(weight[c.evidence] + bonus + length_bonus), c.page)

    ordered = sorted(pool, key=rank)
    u.claims = ordered[:CLAIM_CAP]
    u.n_claims_total = len(pool)
    u.n_claims_shown = len(u.claims)
    u.evidence_counts = dict(Counter(c.evidence for c in pool))
    u.section_totals = dict(Counter(c.section for c in pool))

    # giới hạn: ưu tiên câu ở phần hạn chế và bàn luận
    lims = [c for c in pool if c.is_limitation]
    lims.sort(key=lambda c: (0 if c.section == "Hạn chế" else 1, c.page))
    if lims:
        u.limitations = lims[:12]
        u.limitations_source = "explicit"
    else:
        # bài không tự nêu giới hạn: lấy câu để ngữ ở phần bàn luận, ghi rõ là câu để ngữ
        hedged = [
            c for c in pool
            if HEDGE_RE.search(c.text)
            and c.section in ("Bàn luận", "Kết quả và bàn luận", "Kết luận", "Hạn chế")
        ]
        u.limitations = hedged[:8]
        u.limitations_source = "hedge" if hedged else "none"
    u.open_questions = [c for c in pool if c.is_open][:10]
    u.critique = _critique(paper, pool, u)
    return u


def _critique(paper: Paper, pool: list[Claim], u: Understanding) -> list[str]:
    """Phê bình bằng số đếm được, không bằng lời khen. Mỗi dòng đều kiểm lại được."""
    out: list[str] = []
    n = len(pool)
    counts = Counter(c.evidence for c in pool)
    if n:
        e, h = counts.get("E", 0), counts.get("H", 0)
        out.append(
            f"{n} câu khẳng định: {e} câu có số đo ngay trong câu ({round(100*e/n,1)}%), "
            f"{h} câu không kèm số nào ({round(100*h/n,1)}%). "
            f"Câu không kèm số chỉ kiểm được bằng hình hoặc bảng gốc."
        )
    full = paper.abstract + "\n" + "\n".join(s.text for s in kept_sections(paper))
    ns = [int(x) for x in re.findall(r"\bn\s*=\s*(\d+)", full)]
    if ns:
        out.append(
            f"Bài nêu cỡ mẫu {len(ns)} lần, nhỏ nhất {min(ns)}, lớn nhất {max(ns)}. "
            f"Cỡ mẫu nhỏ nhất là mức chịu lực của kết luận."
        )
    figs = len(paper.figures)
    if paper.pages and figs:
        out.append(
            f"{figs} hình và bảng cho {paper.pages} trang, trung bình {round(paper.pages/figs,1)} trang một hình. "
            f"Số liệu nằm phần lớn ở hình, không ở câu chữ."
        )
    if len(paper.stats) and len(paper.doses):
        agents = {d.get("agent_hint", "") for d in paper.doses if d.get("agent_hint")}
        out.append(
            f"Bóc được {len(paper.stats)} con số và {len(paper.doses)} liều hoặc nồng độ, "
            f"gắn với {len(agents)} cụm chất thử. Liều trong ống nghiệm và liều cho con vật "
            f"cách nhau xa, không suy thẳng từ ống nghiệm ra chuồng được."
        )
    if u.limitations_source == "explicit":
        out.append(f"Bài tự nêu {len(u.limitations)} chỗ giới hạn. Có tự giới hạn là điểm cộng.")
    elif u.limitations_source == "hedge":
        out.append(
            f"Bài không có mục giới hạn riêng. {len(u.limitations)} câu dùng từ để ngữ ở phần bàn luận "
            f"là chỗ tác giả chưa dám chắc, đọc kỹ trước khi trích."
        )
    else:
        out.append("Bài không nêu giới hạn và không có câu để ngữ nào. Đây là điểm cần cảnh giác, không phải điểm cộng.")
    return out
