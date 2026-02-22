# Prompt dịch segments.json bằng Cursor IDE

**Mục đích:** Thay thế lệnh `ai-doc-trans translate` — dùng Cursor để dịch file `segments.json` từ tiếng Việt sang tiếng Anh, tạo ra file output tương thích với lệnh `import`.

---

## Prompt gửi cho Cursor

```
Hãy dịch file segments.json từ tiếng Việt sang tiếng Anh theo yêu cầu sau:

**Input:** segments.json (array JSON, mỗi object có: source, structure, source_lang, source_hash, source_id, position)

**Output:** translated.json — giữ nguyên cấu trúc và mọi field gốc, thêm field "target" (bản dịch) và "target_lang" (ngôn ngữ đích).

**Quy tắc:**
1. Mỗi object trong output phải có đầy đủ: source, source_hash, source_id, structure, source_lang, target_lang, position, target
2. Giữ nguyên source_hash, source_id, structure, source_lang, position — không thay đổi
3. "target_lang" = "en" (cùng cấp với source_lang, thể hiện ngôn ngữ đích)
4. "target" = bản dịch tiếng Anh của "source"
5. Thuật ngữ: đọc từ docs/sample/glossary_global.csv (vd: khoáng vi lượng → trace minerals, nguyên liệu gốc → raw material, GMP/HACCP/ISO giữ nguyên). Quy tắc không dịch: đọc docs/sample/rules_global.csv (do_not_translate_pattern)
6. Format ngày tháng: "Tháng 3-5/2026" → "March-May 2026", "Tháng 8-9/2026" → "August-September 2026"
7. Nếu source là số, mã, hoặc không cần dịch → target = source (giữ nguyên)

**Output format (mẫu):**
[
  {"source": "...", "source_hash": "...", "source_id": 1, "structure": "cell", "source_lang": "vi", "target_lang": "en", "position": "...", "target": "..."}
]

**Quy trình bắt buộc — Agent tự xử lý batch và merge:**
File segments.json rất lớn (~2500+ segment). Bạn PHẢI tự động:
1. Đọc segments.json, đếm tổng số segment
2. Chia thành các batch ~80–100 segment (vd: batch 1 = index 0–99, batch 2 = 100–199, ...)
3. Xử lý từng batch: dịch toàn bộ segment trong batch, tạo array đã dịch (có field target và target_lang)
4. Gộp kết quả tất cả batch theo đúng thứ tự → một array hoàn chỉnh
5. Ghi array cuối cùng vào translated.json

Không yêu cầu người dùng can thiệp. Thực hiện đủ vòng lặp cho đến khi hết segment.
```

---

## Sau khi có translated.json

Chạy import để ghi vào TM:

```bash
ai-doc-trans import translated.json --project 2
```

(File có `target_lang` nên không cần `--tgt`. File cũ thiếu `target_lang` thì dùng `--tgt en`.)

---

## Lưu ý

- **Cursor IDE:** Đọc glossary và rules từ file (`docs/sample/glossary_global.csv`, `docs/sample/rules_global.csv`) vì không truy cập DB.
- **Lệnh translate:** Mặc định đọc glossary và rules từ DB (--tm, --project). Dùng `--glossary <path>` và `--rules <path>` để chỉ định file CSV thay cho DB.
