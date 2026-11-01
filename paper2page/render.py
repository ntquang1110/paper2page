"""Dựng HTML một trang từ mô hình hiểu bài báo.

Cổng kiểm được cài sẵn trong khâu này, không phải khâu hậu kiểm:
  1. không dùng thẻ <table>, mọi bảng số thành thẻ hoặc thanh CSS
  2. sạch gạch ngang dài, sạch chữ Hán, sạch ký tự thay thế hỏng
  3. cỡ chữ nhỏ nhất khai báo từ 12px trở lên
  4. đủ ba tầng đọc, mỗi tầng có nhãn class tierlabel
  5. một file tự chứa, không CDN, không ảnh ngoài
"""

from __future__ import annotations

import html
import json
import os
import re

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import __version__
from .extract import Paper, SYMBOL_LABEL
from .understand import EVIDENCE_LABEL, Understanding, kept_sections

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

CJK_RE = re.compile(r"[\u3000-\u9fff\uac00-\ud7af\uff00-\uffef]")
DASH_RE = re.compile(r"[\u2013\u2014]")


def sanitize(text: str) -> str:
    """Làm sạch trước khi đưa vào HTML. Bắt buộc, vì cổng kiểm đếm gạch ngang dài."""
    if not text:
        return ""
    out = text
    out = out.replace("\u2014", ", ").replace("\u2013", "-")
    out = out.replace("\u2026", "...").replace("\u00a0", " ").replace("\u2212", "-")
    out = CJK_RE.sub("", out)
    out = out.replace("\ufffd", "")
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip()


def _split_sentences_for_reading(text: str, limit: int = 2) -> str:
    from .understand import sentences

    return " ".join(sentences(text)[:limit])


def build_context(paper: Paper, und: Understanding, meta: dict) -> dict:
    counts = und.evidence_counts
    total_claims = max(1, sum(counts.values()))
    evidence_bars = [
        {
            "key": k,
            "label": EVIDENCE_LABEL[k],
            "count": counts.get(k, 0),
            "pct": round(100.0 * counts.get(k, 0) / total_claims, 1),
        }
        for k in ("E", "F", "I", "H")
    ]

    max_words = max([s["words"] for s in und.section_weights] or [1])
    weight_bars = [
        {
            "label": s["label"],
            "words": s["words"],
            "pct": round(100.0 * s["words"] / max_words, 1),
        }
        for s in und.section_weights
    ]

    sections_rendered = []
    by_section: dict[str, list] = {}
    for c in und.claims:
        by_section.setdefault(c.section, []).append(c)
    subheads_by_label = {s.label: s.subheads for s in kept_sections(paper)}
    for t in und.toc:
        claims = by_section.get(t["label"], [])
        total = und.section_totals.get(t["label"], len(claims))
        sections_rendered.append(
            {
                "label": t["label"],
                "page": t["page"],
                "words": t["words"],
                "lead": sanitize(t["first"]),
                "n_claims": len(claims),
                "n_claims_total": total,
                "n_hidden": max(0, total - len(claims)),
                "subheads": [sanitize(x) for x in subheads_by_label.get(t["label"], [])][:12],
                "claims": [
                    {
                        "text": sanitize(c.text),
                        "page": c.page,
                        "evidence": c.evidence,
                        "evidence_label": EVIDENCE_LABEL[c.evidence],
                        "flag": "hạn chế" if c.is_limitation else ("bỏ ngỏ" if c.is_open else ""),
                    }
                    for c in claims
                ],
            }
        )

    return {
        "version": __version__,
        "meta": meta,
        "paper": {
            "title": sanitize(paper.title) or "(bài không in tiêu đề rõ)",
            "pages": paper.pages,
            "body_font": paper.body_font,
        },
        "u": {
            "headline": sanitize(und.headline),
            "conclusion": sanitize(und.conclusion),
            "sample": sanitize(und.sample),
            "sample_note": sanitize(und.sample_note),
            "key_numbers": [
                {"value": sanitize(k["value"]), "section": k["section"], "page": k["page"],
                 "sentence": sanitize(k["sentence"])}
                for k in und.key_numbers
            ],
            "toc": [
                {"label": t["label"], "page": t["page"], "words": t["words"],
                 "lead": sanitize(t["first"])}
                for t in und.toc
            ],
            "flow": [
                {"subject": sanitize(f.subject), "symbol": f.symbol,
                 "object": sanitize(f.object), "sentence": sanitize(f.sentence),
                 "page": f.page, "symbol_label": f.symbol_label}
                for f in und.flow
            ],
            "limitations": [
                {"text": sanitize(c.text), "section": c.section, "page": c.page}
                for c in und.limitations
            ],
            "limitations_source": und.limitations_source,
            "critique": [sanitize(c) for c in und.critique],
            "open_questions": [
                {"text": sanitize(c.text), "section": c.section, "page": c.page}
                for c in und.open_questions
            ],
            "glossary": und.glossary,
            "doses": [
                {"value": sanitize(d["value"]), "agent": sanitize(d.get("agent_hint", "")),
                 "section": d["section"], "page": d["page"]}
                for d in und.doses
            ],
            "methods": [
                {"text": sanitize(m["text"]), "page": m["page"]} for m in und.method_sentences
            ],
            "figures": [
                {"kind": f["kind"], "number": f["number"], "caption": sanitize(f["caption"]),
                 "page": f["page"]}
                for f in und.figure_index
            ],
            "sections": sections_rendered,
            "n_claims": len(und.claims),
            "n_claims_total": und.n_claims_total,
            "n_claims_shown": und.n_claims_shown,
            "n_refs": len(paper.references),
            "n_stats": len(paper.stats),
            "n_figures": len(paper.figures),
        },
        "evidence_bars": evidence_bars,
        "weight_bars": weight_bars,
        "symbol_legend": [
            {"symbol": s, "label": SYMBOL_LABEL[s]} for s in ("→", "⊣", "⊘", "↑", "↓")
        ],
        "evidence_legend": [
            {"key": k, "label": EVIDENCE_LABEL[k]} for k in ("E", "F", "I", "H")
        ],
        "source_label": sanitize(_source_line(meta)),
        "generated": meta.get("generated", ""),
    }


def _source_line(meta: dict) -> str:
    """Một dòng đọc được, không đổ JSON thô: file PDF nào, lấy qua đường nào, dựng lúc nào."""
    src = meta.get("source", {}) or {}
    pdf = os.path.basename(src.get("pdf", "") or "") or src.get("ref", "")
    via = meta.get("pdf_via") or ""
    parts = [f"bản PDF {pdf}"]
    if via:
        parts.append(f"lấy qua {via}")
    if meta.get("generated"):
        parts.append(f"dựng lúc {meta['generated']}")
    return " · ".join(parts)


def render_html(paper: Paper, und: Understanding, meta: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tpl = env.get_template("paper.html.j2")
    return tpl.render(**build_context(paper, und, meta))
