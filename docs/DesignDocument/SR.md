# System Requirements (SR)

## 1. Tổng quan

Tài liệu này mô tả yêu cầu hệ thống cho công cụ/giải pháp dịch tài liệu kỹ thuật và business, hỗ trợ định dạng Excel, Word, PowerPoint.

---

## 2. Đối tượng tài liệu

- Tài liệu kỹ thuật IT
- Giới thiệu sản phẩm (ví dụ: khoáng vi lượng)
- Proposal dự án IT
- Đặc điểm: mang tính chuyên môn, không văn chương; yêu cầu độ chính xác về thuật ngữ (có thể có thuật ngữ riêng của khách hàng/dự án)

---

## 3. Yêu cầu chức năng

### 3.1 Chất lượng dịch

- Chất lượng dịch tốt, phù hợp ngữ cảnh chuyên môn
- Hỗ trợ glossary thuật ngữ (term → bản dịch) để đảm bảo tính nhất quán

### 3.2 Định dạng

- Giữ nguyên định dạng văn bản gốc (font, màu, cấu trúc, v.v.)
- Hỗ trợ lần lượt: **Excel** → **Word** → **PowerPoint** (từ đơn giản đến phức tạp)

### 3.3 Cấu trúc văn bản (Structure-aware)

- Khi dịch, cần truyền thông tin cấu trúc cho AI (heading level 1/2/3, list item, body paragraph, v.v.)
- Mục đích: AI dịch phù hợp ngữ cảnh (heading ngắn gọn, list song song, v.v.)
- Tag cấu trúc phải dùng cú pháp **ít trùng với văn bản thường**. Mặc định dùng `{` và `}` (vd. `{H1}`, `{H2}`), tương tự một số ngôn ngữ lập trình. Người dùng có thể **chỉ định ký tự open/close** khác hoặc **chỉ định luôn cả tag** tùy theo văn bản

### 3.4 Đa ngôn ngữ

- Cùng một văn bản gốc có thể dịch sang **nhiều ngôn ngữ đích** (`target_lang`)
- `source_lang` **đi theo segment** khi extract; văn bản gốc có thể lẫn lộn ngôn ngữ – đánh dấu per-segment giúp tránh xử lý nhiều lần sau này

### 3.5 Translation Memory (TM)

- Lưu mapping: (segment gốc, source_lang, target_lang) → bản dịch
- Đơn vị segment: đoạn văn hoặc object (text box, list item, cell Excel, v.v.)
- Cho phép tái sử dụng bản dịch cũ khi cập nhật tài liệu

---

## 4. Hai chế độ tái dịch thuật

Hệ thống phải phân biệt rõ hai trường hợp:

### 4.1 Chế độ Re-translate (Dịch lại toàn bộ)

**Điều kiện:** Cấu trúc file gốc không thay đổi, chỉ cần dịch lại do:

- Cập nhật thuật ngữ chuyên môn (glossary)
- Thay đổi yêu cầu dịch (phong cách, ngữ điệu, v.v.)

**Hành vi:**

- Gọi AI dịch lại **toàn bộ** nội dung
- **Không** phát hiện segment mới/sửa đổi
- Có thể cập nhật TM với bản dịch mới (optional, tùy thiết kế)

### 4.2 Chế độ Update (Cập nhật theo thay đổi file gốc)

**Điều kiện:** File gốc đã thay đổi, cần cập nhật bản dịch

**Hành vi:**

- Phát hiện các segment: **thêm mới**, **sửa đổi**
- Chỉ dịch các segment mới/sửa đổi qua AI
- Tái sử dụng bản dịch cũ cho các segment **không đổi** (từ TM)
- Bổ sung kết quả dịch mới vào TM

---

## 5. Yêu cầu phi chức năng

### 5.1 Hiệu suất / UX

- Giảm tối đa thời gian và công sức con người (tự động hóa extract, dịch, rebuild)

### 5.2 Phạm vi

- Không cần general translation tool; chỉ cần phục vụ tốt lĩnh vực tài liệu kỹ thuật và business

### 5.3 Giao diện

- **PoC:** CLI (command line)
- **Lâu dài:** GUI hoặc Web UI, chạy trên Windows / Mac / Ubuntu

### 5.4 Định dạng file phức tạp

- Với file MS Office có cấu trúc phức tạp (chart, object, định dạng đặc biệt), cần cân nhắc giải pháp như Excel COM (PowerShell trên Windows) để tránh vỡ định dạng

---

## 6. Chi phí & triển khai

- Sẵn sàng dùng tool/API trả phí nếu đáp ứng yêu cầu và chi phí hợp lý
- PoC có thể dùng phương án đơn giản hơn (Cursor IDE, API miễn phí); production có thể tích hợp AI API trả phí (DeepL, Gemini, GPT, Claude, v.v.)

---

## 7. Lộ trình ưu tiên

| Phase | Định dạng | Mô tả |
|-------|-----------|-------|
| 1 | Excel | PoC, TM cơ bản, CLI |
| 2 | Word | Structure-aware, TM đầy đủ |
| 3 | PowerPoint, GUI/Web | Mở rộng, giao diện người dùng |
