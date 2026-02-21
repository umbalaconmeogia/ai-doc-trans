# Basic Design (BD)

Thiết kế cơ bản cho công cụ dịch tài liệu, dựa trên [SR.md](./SR.md).

---

## 1. Kiến trúc tổng quan

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              doc-trans                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐             │
│  │  Extractor  │───►│  Translation    │───►│    Rebuilder    │             │
│  │             │    │  Engine         │    │                 │             │
│  │ • Parse     │    │                 │    │ • Gắn bản dịch  │             │
│  │ • Segment   │    │ • AI / API      │    │ • Giữ format    │             │
│  │ • Structure │    │ • Glossary      │    │ • Output file   │             │
│  └─────────────┘    └────────┬────────┘    └─────────────────┘             │
│         │                    │                                              │
│         │                    │                                              │
│         ▼                    ▼                                              │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │              Translation Memory (TM)                         │           │
│  │  segment_sources + segment_targets (normalized)              │           │
│  └─────────────────────────────────────────────────────────────┘           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Ba thành phần chính:**
1. **Extractor** – Đọc file, tách text thành segment, gắn metadata cấu trúc
2. **Translation Engine** – Dịch segment (qua AI/API), tra TM và Glossary
3. **Rebuilder** – Gắn bản dịch vào đúng vị trí, xuất file mới

---

## 2. Mô hình Segment

Mỗi đơn vị dịch (segment) gồm:

| Thuộc tính | Mô tả |
|------------|-------|
| `source` | Văn bản gốc |
| `structure` | Loại: `cell`, `para`, `heading_1`, `heading_2`, `list_item`, `textbox`, … (phục vụ structure-aware dịch) |
| `source_lang` | Ngôn ngữ nguồn **đi theo segment** (vd. `en`, `vi`). Văn bản gốc có thể lẫn lộn ngôn ngữ – đánh dấu per-segment khi extract. Gán cả document chưa dùng đến |
| `target_lang` | Ngôn ngữ đích (vd. `vi`, `ja`). Cùng source có thể dịch sang nhiều ngôn ngữ |

**Không dùng** `id` (định danh trong tài liệu) hoặc `path` – vì:

- **Excel:** Cell không có id cố định; `sheet!A1` sẽ sai khi đổi tên sheet hoặc chèn row/column
- **Word / PPT:** Paragraph, list item, shape thường không có id cố định trong format file; có thể thay đổi khi chỉnh sửa
- **Rebuild:** Chỉ cần duyệt document theo **cùng thứ tự** như khi extract, tìm đúng `source` rồi thay bằng bản dịch – không cần path

**Khóa tra TM:** `(source_hash, source_lang, target_lang)`. Dùng `hash(source)` hoặc `hash(structure + source)` làm `source_hash`. Với tài liệu kỹ thuật, cùng một term trong các ngữ cảnh khác nhau (vd. heading vs body) có thể cần dịch khác – khi đó dùng `hash(structure + source)` để phân biệt.

---

## 3. Translation Memory (TM)

**Mục đích:** Lưu mapping segment gốc → bản dịch để tái sử dụng. Luôn có bảng **projects**; 1 TM DB có thể dùng cho nhiều project, glossary/translations dùng chung hoặc override theo project.

### 3.1 Cấu trúc DB (SQLite)

Tách riêng source và target; dùng **INTEGER id** cho `*_sources`, FK từ `*_targets`. `project_id = 0` = company-wide (chung); `project_id > 0` = theo project. Tra cứu: ưu tiên bản có `project_id` trùng, không có thì dùng `project_id = 0`.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  projects                                                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│  id             INTEGER   NOT NULL   -- PK; 0 = global (glossary/translations chung) │
│  name           TEXT      NOT NULL   -- Tên project                               │
│  created_at     TEXT      NOT NULL   -- ISO 8601                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  PRIMARY KEY (id)                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│  segment_sources                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│  id             INTEGER   NOT NULL   -- PK, AUTOINCREMENT                         │
│  source_hash    TEXT      NOT NULL   -- UNIQUE, tra cứu insert/lookup             │
│  source_text    TEXT      NOT NULL   -- Văn bản gốc                               │
│  source_lang    TEXT      NOT NULL   -- Mã ngôn ngữ nguồn (en, vi, ...)          │
│  structure      TEXT                 -- cell, para, heading_1, list_item, ...     │
│  created_at     TEXT      NOT NULL   -- ISO 8601                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  PRIMARY KEY (id), UNIQUE (source_hash)                                           │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         │ 1 ────── N
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  segment_targets                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│  source_id      INTEGER   NOT NULL   -- FK → segment_sources.id                  │
│  target_lang    TEXT      NOT NULL   -- Mã ngôn ngữ đích                         │
│  project_id     INTEGER   NOT NULL   -- 0 = chung; >0 = override theo project     │
│  target_text    TEXT      NOT NULL   -- Bản dịch                                  │
│  created_at     TEXT      NOT NULL   -- ISO 8601                                  │
│  updated_at     TEXT      NOT NULL   -- ISO 8601                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  PRIMARY KEY (source_id, target_lang, project_id)                                 │
│  FOREIGN KEY (source_id) REFERENCES segment_sources(id) ON DELETE CASCADE         │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│  glossary_sources                                                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│  id             INTEGER   NOT NULL   -- PK, AUTOINCREMENT                         │
│  term           TEXT      NOT NULL   -- Thuật ngữ gốc                             │
│  source_lang    TEXT      NOT NULL   -- Ngôn ngữ nguồn                            │
│  project_id     INTEGER   NOT NULL   -- 0 = chung; >0 = theo project              │
│  context        TEXT                 -- Ngữ cảnh (optional)                       │
│  created_at     TEXT      NOT NULL   -- ISO 8601                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  PRIMARY KEY (id), UNIQUE (term, source_lang, project_id)                         │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         │ 1 ────── N
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  glossary_targets                                                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│  source_id      INTEGER   NOT NULL   -- FK → glossary_sources.id                 │
│  target_lang    TEXT      NOT NULL   -- Ngôn ngữ đích                             │
│  translation    TEXT      NOT NULL   -- Bản dịch thuật ngữ                         │
│  created_at     TEXT      NOT NULL   -- ISO 8601                                  │
│  updated_at     TEXT      NOT NULL   -- ISO 8601                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  PRIMARY KEY (source_id, target_lang)                                             │
│  FOREIGN KEY (source_id) REFERENCES glossary_sources(id) ON DELETE CASCADE        │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Tra cứu:** Ưu tiên bản có `project_id` trùng với project hiện tại; không có thì dùng `project_id = 0`.

---

## 4. Luồng xử lý theo chế độ

### 4.1 Chế độ Re-translate

```
[Input file] → Extractor → [Segments] + ghi segment_sources (TM DB) → segments_file
                                │
                                ▼
                    Translation Engine (AI dịch TOÀN BỘ, không dùng TM)
                                │
                                ▼
                    Ghi segment_targets với bản dịch mới
                                │
                                ▼
[Output file] ← Rebuilder ← [Segments + translations]
```

- Không tra TM để tái sử dụng
- Input: glossary mới, yêu cầu dịch mới (phong cách, ngữ điệu)

### 4.2 Chế độ Update

```
[Input file (đã sửa)] → Extractor → [Segments] + ghi segment_sources (TM DB)
                                            │
                                            ▼
                         Với mỗi segment: tra segment_targets (source_id, target_lang)
                                            │
                    ┌───────────────────────┴───────────────────────┐
                    ▼                                               ▼
            [Đã có bản dịch trong TM]                  [Chưa có bản dịch]
                    │                                               │
                    ▼                                               ▼
              Dùng bản dịch từ TM                           Gọi AI dịch
                    │                                               │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                              Ghi segment_targets (mới) cho các segment vừa dịch
                                            │
                                            ▼
[Output] ← Rebuilder ← [Segments + translations]
```

- **Không cần** so sánh với extract cũ; TM DB là nguồn “đã dịch”
- Tra TM: có bản dịch → dùng; không có → AI dịch rồi ghi TM

---

## 5. Structure-aware Translation

Extractor gắn tag cấu trúc cho mỗi segment. Translation Engine đưa vào prompt.

**Cú pháp tag (configurable):**

| Mức | Mô tả |
|-----|-------|
| **Mặc định** | Ký tự open `{`, close `}` → `{H1}`, `{H2}`, `{P}`, `{LI}`, … (bắt chước ngôn ngữ lập trình, ít xuất hiện trong văn bản thường) |
| **Tùy chỉnh** | Người dùng chỉ định ký tự open/close khác (vd. `‹›`, `【】`) nếu văn bản chứa nhiều `{` hoặc `}` |
| **Tag tùy chỉnh** | Người dùng chỉ định luôn cả format tag (vd. `##HEADING##`, `__P__`) |

Ví dụ (mặc định):

```
{H1} Introduction
{H2} System Overview
{P} The system provides...
{LI} Feature A
{LI} Feature B
```

**Prompt gợi ý:** "You are translating a technical document. Tags {H1}, {H2}, {LI}, {P} indicate structure. Translate text only, keep tags unchanged. Headings: concise. List items: parallel structure."

---

## 6. Extractor theo định dạng

`source_lang` gắn **per-segment** khi extract. Với tài liệu lẫn lộn ngôn ngữ, gắn sẵn giúp translation engine và TM xử lý đúng mà không cần detect lại. (Gán ở document level có thể chưa dùng.)

| Định dạng | Unit segment | Structure |
|-----------|--------------|-----------|
| **Excel** | Cell (hoặc range có nội dung) | `cell` (hoặc `header` nếu có) |
| **Word** | Paragraph, list item, heading | `para`, `heading_1`, `heading_2`, `list_item` |
| **PowerPoint** | Text trong shape, textbox, placeholder | `title`, `body`, `textbox` |

Phase 1 (Excel): có thể đơn giản hóa, chưa cần structure phức tạp. Phase 2 (Word) trở đi: áp dụng structure-aware đầy đủ.

---

## 7. Rebuilder

- Nhận: danh sách segment + bản dịch (theo **đúng thứ tự** extract)
- Duyệt document theo cùng thứ tự extract; tại mỗi vị trí, tìm đúng `source` → thay bằng bản dịch tương ứng
- Không dùng path/id; chỉ dựa vào thứ tự và nội dung source
- Giữ nguyên format (font, màu, border, v.v.)
- Với Excel phức tạp: có thể dùng COM (PowerShell) nếu thư viện open source làm vỡ format

---

## 8. Công nghệ đề xuất (PoC)

| Thành phần | Công nghệ |
|------------|-----------|
| Ngôn ngữ | Python 3.x (đa nền tảng) |
| TM | SQLite |
| Excel | `openpyxl` (hoặc fallback COM trên Windows) |
| Word | `python-docx` |
| PowerPoint | `python-pptx` |
| AI | API (Gemini, GPT, Claude) hoặc integration Cursor/script |
| CLI | `argparse` hoặc `click` |

---

## 9. Giao diện CLI (PoC)

Tách riêng các lệnh để tránh ôm quá nhiều xử lý vào một CLI:

```
doctrans extract     <input> [--output <path>] [--tm <path>] [--project <name|id>] [--tag-open <char>] [--tag-close <char>]
doctrans re-trans    <segments_file> [--tgt <lang>] [--glossary <file>] [--tm <path>] [--project <name|id>] [--output <path>]
doctrans update-trans <segments_file> [--tgt <lang>] [--glossary <file>] [--tm <path>] [--project <name|id>] [--output <path>]
doctrans rebuild     <input_file> <translated_segments> [--output <path>]
```

### 9.1 Luồng dữ liệu & vai trò TM DB

| Bước | Hành vi |
|------|---------|
| **extract** | Đọc document → tách segments → **ghi vào segment_sources trong TM DB** (insert if not exists) → **xuất segments_file** (danh sách segment theo thứ tự document) |
| **re-trans** | Đọc **segments_file** (output của extract) → dịch toàn bộ qua AI → ghi segment_targets → xuất translated_segments |
| **update-trans** | Đọc **segments_file** (output của extract hiện tại) → tra TM DB: segment đã có bản dịch? dùng; chưa có? gọi AI → ghi segment_targets → xuất translated_segments |
| **rebuild** | Nhận document gốc + translated_segments → gắn bản dịch → xuất file mới |

**segments_file** = output của `extract`, **không** phải export từ TM DB. Là file trung gian chứa segments theo thứ tự document (vd. JSON). Các lệnh re-trans, update-trans **đọc** segments_file làm input.

**update-trans:** Không cần so sánh segments_old vs segments_new. Việc xác định “mới/chưa dịch” nằm trong TM DB: tra segment_targets theo (source_id, target_lang) — không có bản dịch thì gọi AI. Có thể truyền thêm các segment đã dịch làm context cho AI để thống nhất phong cách.

### 9.2 Format segments_file (gợi ý)

```json
[
  {"source": "Introduction", "structure": "heading_1", "source_lang": "en"},
  {"source": "Overview of the system.", "structure": "para", "source_lang": "en"}
]
```

Có thể bổ sung `source_hash` hoặc `source_id` (nếu đã insert vào TM) để tra cứu nhanh hơn.

### 9.3 Mô tả lệnh

| Lệnh | Mô tả |
|------|-------|
| `extract` | Đọc file, tách segments, ghi segment_sources, xuất segments_file |
| `re-trans` | Dịch toàn bộ qua AI (bỏ qua TM), ghi segment_targets, xuất translated_segments |
| `update-trans` | Tra TM; segment chưa có dịch thì gọi AI; ghi segment_targets; xuất translated_segments |
| `rebuild` | Gắn bản dịch vào document gốc theo thứ tự; xuất file mới |

**Tham số chung:**
- `--tag-open`, `--tag-close`: cho `extract`
- `--glossary`, `--tm`: cho `re-trans`, `update-trans`
- `--project`: chỉ định project (id hoặc name); mặc định 0 (global) khi dùng TM

---

## 10. Cấu trúc thư mục đề xuất

```
doc-trans/
├── src/
│   ├── extractors/
│   │   ├── base.py
│   │   ├── excel.py
│   │   ├── word.py
│   │   └── pptx.py
│   ├── engine/
│   │   ├── translator.py      # AI/API wrapper
│   │   ├── tm.py              # Translation Memory
│   │   └── glossary.py
│   ├── rebuilders/
│   │   ├── excel.py
│   │   └── ...
│   └── cli.py
├── tm/                        # TM DB (SQLite), có thể dùng chung nhiều project
├── glossaries/
└── tests/
```

---

## 11. Rủi ro & giảm thiểu

| Rủi ro | Giảm thiểu |
|--------|------------|
| Thư viện làm vỡ format Excel/Word | Fallback COM (PowerShell) trên Windows; test với file thật |
| API dịch tốn phí | PoC dùng free tier / Cursor; production chọn API phù hợp |
| Segment quá dài | Chia segment theo giới hạn token của model |
| Rebuild sai vị trí | Đảm bảo extract/rebuild cùng thứ tự duyệt; validate sau rebuild |
