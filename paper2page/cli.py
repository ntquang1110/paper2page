"""Dòng lệnh: một bài báo vào, một trang HTML ra.

    python -m paper2page 10.1038/s41598-023-12345-6 -o bai.html
    python -m paper2page 37234567 -o bai.html --json mo-hinh.json
    python -m paper2page bai.pdf -o bai.html --gate
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys

from .extract import extract_pdf, extract_text_dump
from .gate import check
from .render import render_html
from .source import resolve
from .understand import build, kept_sections


def run(src: str, out: str, workdir: str = ".paper2page", want_json: str | None = None,
        keep_pdf: bool = True, dump_text: bool = False) -> dict:
    pdf, meta, xml = resolve(src, workdir=workdir, want_pdf=True)
    if pdf is None:
        raise SystemExit(
            f"Không lấy được PDF cho {src!r}. Không có bản toàn văn mở. "
            f"Tải PDF về máy rồi truyền đường dẫn file."
        )

    paper = extract_pdf(pdf)
    if not paper.sections:
        raise SystemExit(f"PDF {pdf} không bóc được chữ nào, có thể là bản scan cần OCR trước.")

    und = build(paper)
    meta_dict = {
        "title": meta.title, "authors": meta.authors, "journal": meta.journal, "year": meta.year,
        "doi": meta.doi, "pmid": meta.pmid, "pmcid": meta.pmcid, "license": meta.license,
        "source": {"kind": meta.source_kind, "ref": meta.source_ref, "pdf": os.path.abspath(pdf)},
        "generated": dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
    }

    html_out = render_html(paper, und, meta_dict)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html_out)

    if want_json:
        model = {
            "meta": meta_dict,
            "paper": {
                "title": paper.title, "abstract": paper.abstract, "pages": paper.pages,
                "body_font": paper.body_font, "n_stats": len(paper.stats),
                "n_refs": len(paper.references), "n_figures": len(paper.figures),
            },
            "understanding": und.to_dict(),
            "content_errors": und.validate(),
        }
        with open(want_json, "w", encoding="utf-8") as f:
            json.dump(model, f, ensure_ascii=False, indent=2)

    if dump_text:
        with open(os.path.splitext(out)[0] + ".txt", "w", encoding="utf-8") as f:
            f.write(extract_text_dump(paper))

    if not keep_pdf and os.path.isdir(workdir):
        shutil.rmtree(workdir, ignore_errors=True)

    return {
        "html": os.path.abspath(out),
        "pdf": os.path.abspath(pdf),
        "pdf_via": meta.pdf_via,
        "sections": [s.label for s in kept_sections(paper)],
        "claims": und.n_claims_total,
        "claims_shown": und.n_claims_shown,
        "evidence": und.evidence_counts,
        "content_errors": und.validate(),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="paper2page",
        description="Bài báo khoa học thành một trang HTML đọc là hiểu: ba tầng đọc, nhãn bằng chứng, số giữ nguyên văn.",
    )
    ap.add_argument("source", help="đường dẫn PDF, DOI, PMID, PMCID, mã arXiv, hoặc URL")
    ap.add_argument("-o", "--out", default="paper.html", help="file HTML đầu ra")
    ap.add_argument("--json", dest="json_out", help="ghi thêm mô hình trung gian ra JSON")
    ap.add_argument("--workdir", default=".paper2page", help="thư mục tải PDF về")
    ap.add_argument("--no-keep-pdf", action="store_true", help="xoá thư mục tải sau khi chạy")
    ap.add_argument("--text", action="store_true", help="xuất thêm bản chữ thô để đối chiếu")
    ap.add_argument("--gate", action="store_true", help="chạy cổng kiểm và trả mã lỗi nếu không đạt")
    a = ap.parse_args(argv)

    info = run(a.source, a.out, workdir=a.workdir, want_json=a.json_out,
               keep_pdf=not a.no_keep_pdf, dump_text=a.text)

    print(f"HTML      {info['html']}")
    print(f"PDF nguồn {info['pdf']} (lấy qua: {info['pdf_via']})")
    print(f"Phần đọc được: {', '.join(info['sections'])}")
    print(f"Câu khẳng định {info['claims']}, hiển thị {info['claims_shown']} · mức bằng chứng {info['evidence']}")
    if info["content_errors"]:
        print("Cần đọc tay:")
        for e in info["content_errors"]:
            print(f"  - {e}")

    if a.gate:
        res = check(info["html"])
        for k, v in res.items():
            if k not in ("failures",):
                print(f"  {k:20} {v}")
        if res["verdict"] != "PASS":
            for f in res["failures"]:
                print(f"  LỖI: {f}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
