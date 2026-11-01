# PAPER2PAGE

Một bài báo khoa học vào, một trang HTML ra, đọc là hiểu.

Trang ra có ba tầng đọc: 5 giây để biết có nên đọc tiếp, 1 phút để nắm bố cục và chỗ đặt bằng chứng, đọc kỹ để soi từng câu khẳng định kèm số trang gốc.

Công cụ chạy hoàn toàn trên máy, không gọi mô hình ngôn ngữ. Mọi thứ trên trang là số đếm được từ chính file PDF: cấu trúc phần, câu khẳng định, con số, liều, hình bảng, tài liệu tham khảo. Không có chỗ nào để bịa.

## Vì sao làm cái này

Đọc một bài báo tốn 30 tới 60 phút, mà phần lớn thời gian là đi tìm: bài này hỏi gì, làm trên bao nhiêu con, số nằm ở đâu, tác giả tự giới hạn chỗ nào. Ba thứ đó máy đếm được. Việc của trang này là đếm sẵn và xếp lại, để người đọc dùng đầu cho việc đánh giá thay vì cho việc dò.

Nguyên tắc không thương lượng:

1. Số, đơn vị, ký hiệu thống kê giữ nguyên văn, không dịch, không làm tròn lại.
2. Câu trích giữ nguyên tiếng gốc. Nhãn và phần dẫn giải là tiếng Việt.
3. Mỗi câu khẳng định có nhãn mức bằng chứng và vị trí phần với số trang.
4. Không có dữ liệu thì ghi rõ là chưa nêu. Không suy diễn thành kết luận.

## Cài

```bash
pip install -r requirements.txt
```

Cần Python 3.10 trở lên. Không cần khoá API, không cần tài khoản.

## Dùng

```bash
# từ DOI
python -m paper2page 10.3389/fnut.2022.819722 -o bai.html

# từ PMID hoặc PMCID
python -m paper2page 35234567 -o bai.html
python -m paper2page PMC8890123 -o bai.html

# từ mã arXiv, hoặc link bài, hoặc file PDF đã tải
python -m paper2page 2301.00001 -o bai.html
python -m paper2page https://doi.org/10.3389/fnut.2022.819722 -o bai.html
python -m paper2page "D:/bai-bao.pdf" -o bai.html

# kèm cổng kiểm, mô hình trung gian, và bản chữ thô để đối chiếu
python -m paper2page 10.3389/fnut.2022.819722 -o bai.html --json mo-hinh.json --text --gate
```

Cổng kiểm trả mã lỗi khác 0 khi trang không đạt, nên ghép được vào dây chuyền tự động.

## Lấy PDF từ đâu

Thử lần lượt, dừng ở cái đầu tiên chạy được:

1. **Europe PMC**, bản toàn văn mở, mạnh nhất cho y sinh, nông nghiệp, dinh dưỡng.
2. **Unpaywall**, chỉ cần DOI, không cần khoá.
3. **Mẫu đường dẫn nhà xuất bản**: Frontiers, Springer và BMC, PLOS, PeerJ, PMC.
4. **arXiv**, bản in trước.

Metadata vẫn lấy được kể cả khi kho PDF chết: DOI đi qua Crossref, PMID đi qua E-utilities. Không cào trang HTML của PubMed vì dính cookie wall.

Bài không có bản toàn văn mở thì tải PDF về máy rồi truyền đường dẫn file. Công cụ không vượt paywall.

## Mức bằng chứng

Gán theo **hình thức câu**, không theo cảm nhận, nên kiểm lại được bằng mắt:

| Nhãn | Nghĩa | Ví dụ |
|---|---|---|
| **E** | Số đo nằm ngay trong câu | `villus height increased by 18%` |
| **F** | Câu chỉ trỏ tới hình hoặc bảng | `as shown in Figure 2, ...` |
| **I** | Suy luận hoặc cơ chế đề xuất | `may be explained by barrier function` |
| **H** | Khẳng định không kèm số | `coated ZnO improved growth performance` |

Trang in cả bảng phân bố E, F, I, H. Bài mà 80% câu là H thì đó là thông tin về bài, không phải lỗi của công cụ.

## Cổng kiểm

Nằm trong repo, chạy được độc lập: `python -m paper2page.gate bai.html`

| Luật | Ngưỡng |
|---|---|
| Thẻ `<table>` | 0, số liệu so sánh dựng bằng thanh CSS |
| Gạch ngang dài U+2013, U+2014 | 0 |
| Chữ Hán, ký tự hỏng U+FFFD | 0 |
| Cỡ chữ khai báo nhỏ nhất | từ 12px |
| Tầng đọc có nhãn `tierlabel` | từ 3 |
| Tài nguyên ngoài | 0, file tự chứa |

Cổng in ra số đếm chứ không in chữ ĐẠT suông, để biết bản mới có thật sự khác bản cũ.

Kiểm ở mức render thì dùng thêm script Playwright bốn bề rộng 360, 390, 768, 1440 để đo cỡ chữ thật và tràn ngang. Cổng tĩnh là điều kiện cần, không phải điều kiện đủ.

## Kết quả chạy thật

Bài thử: Coated Zinc Oxide Improves Growth Performance of Weaned Piglets via Gut Microbiota, Front. Nutr. 2022, DOI 10.3389/fnut.2022.819722, PDF 12 trang.

| Số đo | Giá trị |
|---|---|
| Phần bóc đúng | 5: Đặt vấn đề, Vật liệu và phương pháp, Kết quả, Bàn luận, Kết luận |
| Câu khẳng định | 378, hiển thị 60 câu đáng đọc nhất |
| Phân bố bằng chứng | E 66, F 6, I 12, H 294 |
| Con số giữ nguyên văn | 173 |
| Hình và bảng | 10 |
| Tài liệu tham khảo | 55 |
| Cổng kiểm tĩnh | ĐẠT, 0 bảng, 0 gạch dài, 0 chữ Hán, cỡ chữ nhỏ nhất 12px |
| Bốn bề rộng 360, 390, 768, 1440 | Không tràn ngang, không chữ dưới 12px |

Bản HTML của bài này nằm ở `docs/index.html`, mở được trực tiếp.

## Cấu trúc

```
paper2page/
  source.py      lấy PDF và metadata, chuỗi dự phòng bốn tầng
  extract.py     bóc cấu trúc: phần, tiêu đề con, hình bảng, số, liều, tài liệu
  understand.py  dựng mô hình hiểu: ba tầng, nhãn bằng chứng, luồng quan hệ, phê bình
  render.py      dựng HTML, làm sạch ký tự trước khi in
  gate.py        cổng kiểm sáu luật, in số đếm
  cli.py         dòng lệnh
  templates/     mẫu HTML, một file tự chứa
tests/           test offline, dựng PDF tại chỗ, không cần mạng
docs/            bản HTML mẫu, dùng cho GitHub Pages
```

## Giới hạn đã biết

- PDF scan không có lớp chữ thì phải OCR trước. Công cụ báo lỗi rõ chứ không đoán.
- Bài hai cột có hình chen giữa dòng có thể làm thứ tự câu bị lệch. Trang này luôn ghi số trang để người đọc đối chiếu lại.
- Nhãn bằng chứng theo hình thức câu. Câu có số chưa chắc đúng thiết kế, vẫn phải đọc phần phương pháp.
- Bản đồ quan hệ cắt cụm từ quanh từ nối, đọc như chỉ dẫn chứ không phải câu hoàn chỉnh. Câu gốc luôn có trong mục gập ngay dưới.
- Một số nhà xuất bản chặn tải tự động. Khi đó tải PDF bằng tay rồi truyền đường dẫn file.

## Chạy test

```bash
python -m pytest tests -q
```

Test dựng một PDF nhỏ tại chỗ rồi chạy cả dây chuyền, gồm cả ca cổng kiểm phải báo lỗi.

## Giấy phép

MIT.
