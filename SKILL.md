---
name: paper2page
description: "Use when biến bài báo khoa học thành một trang HTML đọc là hiểu."
version: 1.0.0
author: Nguyễn Thành Quang
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [research, paper, pdf, html, evidence, publish]
    related_skills: [paper-mechanism-map, pubmed-evidence-research, grounded-citations, html-deliverable-gate, publish]
---

# paper2page — bài báo khoa học thành một trang đọc là hiểu

Trigger: user gửi DOI, PMID, PMCID, mã arXiv, link bài báo, hoặc file PDF và nói "đọc hiểu bài này cho anh", "dựng trang cho anh", "bài này nói gì".

Repo: `D:/Hermes Proj/paper2page`. Công cụ chạy trên máy, không gọi mô hình ngôn ngữ.

## Chạy

```bash
cd "/d/Hermes Proj/paper2page" && export PYTHONUTF8=1
python -m paper2page <DOI|PMID|PMCID|arXiv|URL|file.pdf> -o <ten>.html --json <ten>.json --text --gate
```

Đọc kết quả in ra:

- `PDF nguồn ... (lấy qua: ...)`: nếu `lấy qua` rỗng nghĩa là không có bản toàn văn mở. Bảo sư phụ tải PDF về máy rồi truyền đường dẫn file. Không được kết luận là không đọc được bài.
- `Phần đọc được`: danh sách phần bóc đúng. Nếu chỉ có một hai dòng, hoặc lẫn tên tác giả, tên tạp chí, ngày tháng thì khâu bóc cấu trúc có vấn đề, xem mục Pitfalls.
- `Câu khẳng định N, hiển thị M`: N là tổng đếm được, M là số câu lên trang.
- `Cần đọc tay`: danh sách cảnh báo nội dung. Đọc hết, đừng bỏ qua.

## Việc bắt buộc sau khi chạy

1. Mở `--json` ra đọc `understanding.headline`, `key_numbers`, `flow`. Nếu câu chốt vô nghĩa hoặc số then chốt là ngưỡng p thì báo rõ là khâu bóc yếu, không giao trang như thể đã hiểu bài.
2. Chạy cổng kiểm: `python -m paper2page.gate bai.html`. Phải đạt, không đạt thì sửa mẫu chứ không sửa kết quả bằng tay.
3. Kiểm render bốn bề rộng bằng script Playwright của skill `html-deliverable-gate`. Cổng tĩnh không thay được bước đo trong trình duyệt.
4. Giao cho sư phụ: link preview cộng số liệu kiểm. Không gửi ảnh chụp trừ khi sư phụ hỏi.

## Nguyên tắc nội dung

- Số, đơn vị, ký hiệu thống kê giữ nguyên văn. Không dịch, không làm tròn lại.
- Câu tiếng Anh giữ nguyên tiếng gốc. Nhãn tiếng Việt là phần của công cụ.
- Nhãn bằng chứng E, F, I, H gán theo hình thức câu. Trang in cả bảng phân bố, để người đọc thấy bài dựa vào loại bằng chứng nào.
- Bài không nêu giới hạn thì ghi rõ là không nêu. Đó là điểm cần cảnh giác, không phải điểm cộng.

## Pitfalls

1. **Europe PMC thỉnh thoảng trả 503 hàng loạt.** Chuỗi dự phòng tự đi tiếp: Unpaywall, mẫu nhà xuất bản, arXiv. Đừng vội kết luận là không có bản toàn văn.
2. **PMC và MDPI chặn tải tự động** (403, trả về HTML). Frontiers, arXiv tải được. Khi cần bản PMC thì tải tay.
3. **PDF hai cột** làm thứ tự câu lệch. Trang luôn có số trang từng câu, phải giữ, đừng bỏ cho gọn.
4. **Chữ ghép kiểu ligature** (ﬁ, ﬂ, ﬀ) làm hỏng mọi biểu thức so khớp. Hàm `normalize_text` xử lý ngay khi bóc. Nếu thấy chữ kiểu "signi cantly" trong kết quả thì đã bỏ sót bước này.
5. **Mục Tài liệu tham khảo dễ vỡ thành hàng chục phần** vì mỗi mục bắt đầu bằng số. Cờ `in_refs` chặn việc này. Nếu thấy phần tên tác giả trong mục lục thì cờ đó bị hở.
6. **Không tự bịa số, không tự dịch, không thêm kết luận của mình vào trang.** Trang là bản đồ dẫn về bài gốc.

## Sau khi giao

Sư phụ muốn đọc thẳng thì publish lên `preview.thefirstonly.com` bằng skill `publish`. Bản HTML trong repo là bản gốc, không thay bằng bản đã publish.
