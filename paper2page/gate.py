"""Cổng kiểm trang HTML đầu ra. Chạy sau mỗi lần render, trước khi giao.

Năm luật cứng:
  1. 0 thẻ <table>            (số liệu so sánh dựng bằng thanh CSS)
  2. 0 gạch ngang dài         (U+2013, U+2014)
  3. 0 chữ Hán, 0 ký tự hỏng  (U+FFFD)
  4. cỡ chữ khai báo nhỏ nhất từ 12px
  5. đủ 3 tầng đọc, mỗi tầng có class tierlabel

In ra số đếm, không in chữ PASS suông. Có số mới biết bản mới có thật sự khác bản cũ.
"""

from __future__ import annotations

import json
import re
import sys

CJK_RE = re.compile(r"[\u3000-\u9fff\uac00-\ud7af\uff00-\uffef]")
DASH_RE = re.compile(r"[\u2013\u2014]")
FONT_RE = re.compile(r"font-size:\s*([\d.]+)px")
EXTERNAL_ASSET_RE = re.compile(r"<(?:img|script|link|iframe)\b[^>]*(?:src|href)\s*=\s*\"https?://", re.I)


def check(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        s = f.read()

    sizes = sorted({float(x) for x in FONT_RE.findall(s)})
    tiers = len(re.findall(r'class="[^"]*\btierlabel\b', s))
    res = {
        "path": path,
        "bytes": len(s.encode("utf-8")),
        "tables": s.lower().count("<table"),
        "em_dash": len(DASH_RE.findall(s)),
        "cjk": len(CJK_RE.findall(s)),
        "replacement_char": s.count("\ufffd"),
        "min_font_declared": min(sizes) if sizes else 0.0,
        "tier_labels": tiers,
        "external_assets": len(EXTERNAL_ASSET_RE.findall(s)),
        "details": s.lower().count("<details"),
        "bars": len(re.findall(r'class="fill', s)),
        "claims_rendered": len(re.findall(r'class="claim"', s)),
    }

    failures = []
    if res["tables"] != 0:
        failures.append(f"còn {res['tables']} thẻ table, luật là 0")
    if res["em_dash"] != 0:
        failures.append(f"còn {res['em_dash']} gạch ngang dài, luật là 0")
    if res["cjk"] != 0:
        failures.append(f"còn {res['cjk']} ký tự Hán, luật là 0")
    if res["replacement_char"] != 0:
        failures.append(f"còn {res['replacement_char']} ký tự hỏng U+FFFD")
    if res["min_font_declared"] < 12:
        failures.append(f"cỡ chữ nhỏ nhất khai báo {res['min_font_declared']}px, luật là từ 12px")
    if res["tier_labels"] < 3:
        failures.append(f"chỉ có {res['tier_labels']} nhãn tầng đọc, luật là từ 3")
    if res["external_assets"] != 0:
        failures.append(f"còn {res['external_assets']} tài nguyên ngoài, yêu cầu file tự chứa")

    res["failures"] = failures
    res["verdict"] = "PASS" if not failures else "FAIL"
    return res


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("dùng: python -m paper2page.gate <file.html> [--json]", file=sys.stderr)
        return 2
    path = argv[0]
    res = check(path)
    if "--json" in argv:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        for k, v in res.items():
            print(f"{k:22} {v}")
    return 0 if res["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
