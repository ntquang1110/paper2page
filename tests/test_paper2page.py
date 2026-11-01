"""Test chạy offline, không cần mạng. Dựng một PDF nhỏ tại chỗ rồi chạy cả dây chuyền.

Chạy:  python -m pytest tests -q
"""

from __future__ import annotations

import json
import os
import re
import sys

import pymupdf
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from paper2page.cli import run  # noqa: E402
from paper2page.extract import extract_pdf, normalize_text  # noqa: E402
from paper2page.gate import check  # noqa: E402
from paper2page.render import sanitize  # noqa: E402
from paper2page.understand import build, evidence_class  # noqa: E402

BODY = [
    ("ABSTRACT", 14),
    ("Weaned piglets suffer diarrhea. This study tested coated zinc oxide at 500 mg Zn/kg "
     "against 2,000 mg Zn/kg in a total of 126 cross-bred piglets (7.0 ± 0.5 kg).", 10),
    ("INTRODUCTION", 14),
    ("Early weaning causes intestinal disorders and the diarrhea rate increased by 35% in the "
     "control group, which suggests a role for the gut barrier. The objective of this study "
     "was to test whether coated ZnO could replace the traditional dose.", 10),
    ("MATERIALS AND METHODS", 14),
    ("A total of 126 cross-bred piglets were randomly allocated into three groups and fed a "
     "basal diet or a basal diet supplemented with ZnO (2,000 mg Zn/kg) or C_ZnO (500 mg "
     "Zn/kg). The test lasted for 6 weeks. Intestinal morphology was measured as described.",
    10),
    ("RESULTS", 14),
    ("C_ZnO increased average daily gain (P < 0.05) and reduced the diarrhea rate to 4.7% "
     "compared with the control at 35%. The lactulose/mannitol ratio was decreased by 42% "
     "and villus height increased by 18%.", 10),
    ("Figure 1. Intestinal morphology of the ileum in each group.", 10),
    ("DISCUSSION", 14),
    ("The improved barrier function could explain the lower diarrhea rate, although the "
     "mechanism remains unclear and further studies are needed. This study was limited by a "
     "short test period and the trial did not measure the colonic microbiota.", 10),
    ("CONCLUSION", 14),
    ("Coated ZnO improved growth performance and alleviated diarrhea in weaned piglets.", 10),
    ("REFERENCES", 14),
    ("1. Smith J, et al. Zinc oxide in piglets. J Anim Sci. 2021;99:12.", 10),
    ("2. Lee K, et al. Gut barrier. Front Nutr. 2020;7:88.", 10),
]


@pytest.fixture(scope="module")
def sample_pdf(tmp_path_factory) -> str:
    path = str(tmp_path_factory.mktemp("pdf") / "sample.pdf")
    doc = pymupdf.open()
    page = doc.new_page()
    y = 60
    for text, size in BODY:
        rect = pymupdf.Rect(50, y, 545, y + 90)
        page.insert_textbox(rect, text, fontsize=size, fontname="helv", align=0)
        y += 16 + 13 * (len(text) // 95 + 1) if size == 10 else 26
    doc.save(path)
    doc.close()
    return path


def test_normalize_ligatures():
    assert normalize_text("signiﬁcant eﬀect inﬂammation") == "significant effect inflammation"
    assert normalize_text("10\u201320 mg") == "10-20 mg"
    out = normalize_text("dose \u2014 response")
    assert "\u2014" not in out
    assert "dose" in out and "response" in out


def test_extract_structure(sample_pdf):
    p = extract_pdf(sample_pdf)
    labels = [s.label for s in p.sections]
    assert "Tóm tắt" in labels
    assert "Kết quả" in labels
    assert "Tài liệu tham khảo" in labels
    assert len(p.references) >= 2
    assert any(f.kind == "figure" for f in p.figures)
    assert "126" in p.abstract


def test_numbers_kept_verbatim(sample_pdf):
    p = extract_pdf(sample_pdf)
    values = {st["value"] for st in p.stats}
    assert "4.7%" in values or any(v.startswith("4.7") for v in values)
    assert any("500" in v for v in values)
    d = {x["value"] for x in p.doses}
    assert any("500" in v for v in d)


def test_evidence_classes():
    assert evidence_class("Body weight increased by 18% in the treated group.") == "E"
    assert evidence_class("The effect may be explained by barrier function.") == "I"
    assert evidence_class("Coated ZnO improved growth performance overall.") == "H"
    assert evidence_class("Figure 3. Intestinal morphology of the ileum group.") in ("F", "H")


def test_understanding_and_sample(sample_pdf):
    u = build(extract_pdf(sample_pdf))
    assert u.n_claims_total > 5
    assert u.n_claims_shown <= 60
    assert u.key_numbers, "phải bóc được số then chốt"
    assert u.toc
    assert u.sample.startswith("126")
    assert u.flow, "phải dựng được bước quan hệ"
    assert not u.validate()


def test_sanitize_kills_dashes():
    assert "\u2014" not in sanitize("a \u2014 b")
    assert "\u2013" not in sanitize("1\u20132")


def test_gate_detects_violations(tmp_path):
    bad = tmp_path / "bad.html"
    bad.write_text(
        '<html><body><span class="tierlabel">Tầng 1</span>'
        '<table><tr><td>x</td></tr></table>'
        "<p style=\"font-size:11px\">dài \u2014 ngang</p></body></html>",
        encoding="utf-8",
    )
    res = check(str(bad))
    assert res["verdict"] == "FAIL"
    assert res["tables"] == 1 and res["em_dash"] == 1 and res["tier_labels"] == 1


def test_end_to_end_gate_pass(sample_pdf, tmp_path):
    out = tmp_path / "bai.html"
    model = tmp_path / "bai.json"
    info = run(sample_pdf, str(out), workdir=str(tmp_path / "work"), want_json=str(model))
    assert os.path.getsize(out) > 5000
    res = check(str(out))
    assert res["failures"] == [], res["failures"]
    assert res["tier_labels"] >= 3
    assert res["tables"] == 0
    assert res["min_font_declared"] >= 12
    data = json.loads(model.read_text(encoding="utf-8"))
    assert data["understanding"]["n_claims_total"] > 5
    assert re.search(r"\d", data["understanding"]["sample"])


def test_model_matches_schema(sample_pdf, tmp_path):
    fastjsonschema = pytest.importorskip("fastjsonschema", reason="cần fastjsonschema để kiểm schema")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    schema = json.load(open(os.path.join(root, "schema.json"), encoding="utf-8"))
    model = tmp_path / "m.json"
    run(sample_pdf, str(tmp_path / "s.html"), workdir=str(tmp_path / "w"), want_json=str(model))
    data = json.loads(model.read_text(encoding="utf-8"))
    fastjsonschema.compile(schema)(data)
