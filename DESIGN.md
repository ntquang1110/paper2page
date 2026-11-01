# DESIGN

Hệ thống thiết kế của trang đầu ra. Chỉnh ở đây thì chỉnh cả `paper2page/templates/paper.html.j2`.

## Token

```
nền kem     #fcfaf5     chữ chính  #1a3300
thẻ         #ffffff     chữ phụ    #3f5325
vàng nhấn   #ffe95c     chữ mờ     #6b7a5a
đường kẻ    #e2ddd0
E #1a3300   F #2f6f8f   I #a6741a   H #7d8570
```

Chữ trên nền màu dùng mực đậm hoặc trắng đậm, không dùng xám. Vàng chỉ làm nền nhãn, không làm nền chữ dài.

## Chữ

Chữ tiêu đề Bricolage Grotesque, thân bài Inter, có hệ dự phòng hệ thống. Một file tự chứa, không nạp font từ mạng.

Cỡ chữ: 30 và 36 cho tiêu đề bài, 24 cho câu chốt, 21 cho mục, 16 cho thân, 12 cho nhãn. **Không có cỡ nào dưới 12px**, kể cả nhãn nhỏ nhất, vì cổng kiểm đếm cả khai báo lẫn cỡ chữ sau khi render ở 360px.

## Ba tầng đọc

Mỗi tầng mở đầu bằng một nhãn `<span class="tierlabel">`. Cổng kiểm đếm node theo class này, nên đổi chữ trong nhãn được, bỏ class là hỏng cổng.

1. **Tầng 1, đọc 5 giây**: một câu chốt lấy từ kết luận tác giả, bốn ô số (cỡ mẫu, số liệu, hình bảng, số câu), kết luận nguyên văn, ba con số then chốt.
2. **Tầng 2, đọc 1 phút**: mục lục từng phần kèm số trang và số từ, hai nhóm thanh CSS: phân bố mức bằng chứng, và bài dành bao nhiêu chữ cho phần nào.
3. **Tầng 3, đọc kỹ**: bản đồ quan hệ, cách làm theo thứ tự bài, liều và nồng độ, hình bảng, từng câu khẳng định theo phần, phê bình số liệu máy đếm được, câu để ngữ, câu hỏi bỏ ngỏ, từ điển viết tắt, cách tự kiểm.

## Luật trình bày

- **Không dùng thẻ `<table>`.** Số liệu so sánh dựng bằng thanh CSS: nhãn và giá trị nằm **ngoài** thanh, không nhét chữ vào trong thanh ngắn.
- **Nhãn giá trị luôn nằm ngoài track**, thanh có `min-width:3px` để mốc nhỏ vẫn nhìn thấy.
- **Danh sách dài thì gập** bằng `<details>`. Trang dài mà mở hết là không đọc được trên điện thoại.
- **Không emoji làm biểu tượng.** Ký hiệu `→ ⊣ ⊘ ↑ ↓` là dữ liệu, phải kèm bảng chú giải.
- **Không gạch ngang dài, không chữ Hán, không ký tự hỏng.** Hàm `sanitize` xử lý trước khi in, cổng kiểm đếm lại sau khi in.
- **Bản in**: có `@media print`, nền trắng, không cắt khối giữa trang.

## Nhịp bố cục

Thân trang rộng tối đa 920px, lề 16px trên điện thoại và 24px từ 680px trở lên. Lưới ô số hai cột trên điện thoại, bốn cột trên màn rộng. Không dùng hiệu ứng chuyển động ngoài một nhịp nhỏ, và tôn trọng `prefers-reduced-motion`.
