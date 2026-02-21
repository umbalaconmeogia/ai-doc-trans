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
│  │  Extractor  │───►│  Translation    │    │    Rebuilder    │             │
│  │             │    │  Engine         │    │ (extract+TM)    │             │
│  │ • Parse     │    │                 │    │ • Gắn bản dịch  │◄─── TM DB   │
│  │ • Segment   │    │ • AI / API      │    │ • Giữ format    │             │
│  │ • Structure │    │ • Glossary      │    │ • Output file   │             │
│  └─────────────┘    └────────┬────────┘    └─────────────────┘             │
│         │                    │                                              │
│         │                    │                                              │
│         ▼                    ▼                                              │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │              Translation Memory (TM)                         │           │
│  │  segments, glossary, translation_rules (theo project)        │           │
│  └─────────────────────────────────────────────────────────────┘           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Ba thành phần chính:**
1. **Extractor** – Đọc file, tách text thành segment, gắn metadata cấu trúc
2. **Translation Engine** – Dịch segment (qua AI/API), tra TM và Glossary
3. **Rebuilder** – Extract lại document, tra TM theo hash, gắn bản dịch, xuất file mới

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
- **Rebuild:** Extract lại document; tại mỗi vị trí, tính `source_hash` → tra TM → thay bằng bản dịch. Không dùng thứ tự; match theo hash.

**Khóa tra TM:** `(source_hash, source_lang, target_lang)`. Dùng `hash(source)` hoặc `hash(structure + source)` làm `source_hash`. Với tài liệu kỹ thuật, cùng một term trong các ngữ cảnh khác nhau (vd. heading vs body) có thể cần dịch khác – khi đó dùng `hash(structure + source)` để phân biệt.

---

## 3. Translation Memory (TM)

**Mục đích:** Lưu mapping segment gốc → bản dịch để tái sử dụng. Luôn có bảng **projects**; 1 TM DB có thể dùng cho nhiều project, glossary/translations dùng chung hoặc override theo project.

### 3.1 Cấu trúc DB (SQLite)

Tách riêng source và target; dùng **INTEGER id** cho `*_sources`, FK từ `*_targets`. `project_id = 1` = company-wide (chung, tên "global"); `project_id > 1` = theo project. Tra cứu: ưu tiên bản có `project_id` trùng, không có thì dùng `project_id = 1`. *Dùng 1 thay vì 0 để tránh vấn đề với SQLite.*

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  projects                                                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│  id             INTEGER   NOT NULL   -- PK; 1 = global (glossary/translations chung) │
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
│  position       TEXT                 -- Tham khảo: page số (docx, pptx), Sheet1!A1 (Excel) │
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
│  project_id     INTEGER   NOT NULL   -- 1 = chung; >1 = override theo project     │
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
│  project_id     INTEGER   NOT NULL   -- 1 = chung; >1 = theo project              │
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

┌─────────────────────────────────────────────────────────────────────────────────┐
│  translation_rules                                                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│  id             INTEGER   NOT NULL   -- PK, AUTOINCREMENT                         │
│  project_id     INTEGER   NOT NULL   -- 1 = chung; >1 = theo project              │
│  rule_type      TEXT      NOT NULL   -- do_not_translate_pattern, instruction     │
│  content        TEXT      NOT NULL   -- regex pattern hoặc instruction text       │
│  created_at     TEXT      NOT NULL   -- ISO 8601                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  PRIMARY KEY (id)                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Tra cứu:** Ưu tiên bản có `project_id` trùng với project hiện tại; không có thì dùng `project_id = 1`.

---

## 4. Luồng xử lý: translate + import (tách rời)

Tách rời **translate** (tạo translated_segments) và **import** (ghi vào TM DB) để linh hoạt cho PoC: có thể dùng Cursor IDE hoặc cách khác dịch, ghi translated_segments, rồi chạy import.

### 4.1 translate (tạo translated_segments, không ghi TM)

**Mode full** (tương đương re-translate):
```
[segments_file] → Translation Engine (AI dịch TOÀN BỘ, không dùng TM) → [translated_segments]
```

**Mode update** (tương đương update):
```
[segments_file] → Với mỗi segment: tra TM → có? dùng : gọi AI dịch → [translated_segments]
```

- Nguồn dịch: lệnh `translate` (AI/API), Cursor IDE, hoặc thủ công

### 4.2 import (ghi vào TM DB)

```
[segments_file] + [translated_segments] → match theo thứ tự → upsert segment_targets
```

- Độc lập với nguồn translated_segments
### 4.3 Rebuilder

```
[document gốc] + [translated_segments] → Rebuilder → [file mới]
```

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

| Định dạng | Unit segment | Structure | Ghi chú |
|-----------|--------------|-----------|---------|
| **Excel** | Cell text (tránh number, date, function) | `cell` (hoặc `header` nếu có) | Không dịch code sản phẩm (vd. NVL1000) – xử lý ở Extract hoặc dùng translation_rules |
| **Word** | Paragraph, list item, heading | `para`, `heading_1`, `heading_2`, `list_item` | position = page number |
| **PowerPoint** | Text trong shape, textbox, placeholder | `title`, `body`, `textbox` | position = slide number |

Phase 1 (Excel): có thể đơn giản hóa, chưa cần structure phức tạp. Phase 2 (Word) trở đi: áp dụng structure-aware đầy đủ.

---

## 7. Rebuilder

- **Input:** document gốc + TM DB (--tm, --tgt, --project). **Không** nhận translated_segments file.
- **Luồng:** Extract lại document → tại mỗi vị trí có text, tính `source_hash` → tra `segment_targets` trong TM → lấy `target_text` → thay thế. Match theo hash, không theo thứ tự.
- Giữ nguyên format (font, màu, border, v.v.)
- Với Excel phức tạp: có thể dùng COM (PowerShell) nếu thư viện làm vỡ format

**Phản biện / mở rộng:** Nếu cần rebuild mà chưa import (vd. dịch one-off, chưa muốn ghi TM), có thể hỗ trợ thêm chế độ rebuild từ translated_segments file. Mặc định: rebuild từ TM.

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
doctrans extract    <input> [--output <path>] [--tm <path>] [--project <name|id>] [--tag-open <char>] [--tag-close <char>]
doctrans translate  <segments_file> [--mode full|update] [--tgt <lang>] [--glossary <file>] [--tm <path>] [--project <name|id>] [--output <path>]
doctrans import     <translated_segments> [--tm <path>] [--project <name|id>] [--tgt <lang>]
doctrans rebuild    <input> [--output <path>] [--tm <path>] [--tgt <lang>] [--project <name|id>]
```

### 9.1 Luồng dữ liệu & vai trò TM DB

| Bước | Hành vi |
|------|---------|
| **extract** | Đọc document → tách segments → **ghi vào segment_sources trong TM DB** (insert if not exists) → **xuất segments_file** (danh sách segment theo thứ tự document) |
| **translate** | Đọc **segments_file** → tạo **translated_segments** (--mode full: dịch toàn bộ; --mode update: tra TM, dịch thiếu). Không ghi TM. Nguồn dịch: AI/API, Cursor IDE, hoặc thủ công |
| **import** | Đọc translated_segments (có source_hash/source_id) → match theo key, không theo thứ tự → **upsert segment_targets** vào TM DB |
| **rebuild** | Đọc document → extract lại → tra TM theo source_hash → thay bằng bản dịch → xuất file mới. Không nhận translated_segments |

**segments_file** = output của `extract`. **translated_segments** = segments_file + target cho mỗi segment; nên có đủ source_hash/source_id để import match theo key, không theo thứ tự.

**Tách translate + import:** translate chỉ tạo translated_segments; import ghi vào TM DB. Có thể dùng Cursor IDE dịch thay vì API, rồi chạy import. Linh hoạt cho PoC.  “mới/chưa dịch” (Trong translate --mode update: tra segment_targets theo (source_id, target_lang) — không có bản dịch thì gọi AI. Có thể truyền thêm các segment đã dịch làm context cho AI để thống nhất phong cách.

### 9.2 Format segments_file và translated_segments

**segments_file** (output của extract):
```json
[
  {"source": "Introduction", "structure": "heading_1", "source_lang": "en", "source_hash": "...", "source_id": 1, "position": "Sheet1!A1"}
]
```

**translated_segments** nên **bao gồm đầy đủ thông tin** từ segments_file cộng target, để import/rebuild chính xác, không phụ thuộc thứ tự:
```json
[
  {"source": "Introduction", "source_hash": "abc", "source_id": 1, "target": "Giới thiệu", "structure": "heading_1", "source_lang": "en"}
]
```
Với `source_hash`/`source_id`, import match theo key thay vì theo thứ tự.

### 9.3 Translate với file lớn

- **Extract**: Đọc toàn bộ file input (openpyxl/python-docx stream được).
- **Translate**: AI API có giới hạn token (vd. 8K–128K). Với segments_file rất lớn, cần **chia batch** (vd. 50–100 segment/batch) rồi gọi API từng batch; gộp kết quả vào translated_segments.
- **Cursor IDE thủ công**: Người dùng tự chia nhỏ khi dịch.
- **Đề xuất**: Lệnh `translate` hỗ trợ `--batch-size`; mặc định xử lý theo batch, tránh vượt giới hạn API. AI API/Cursor tự xử lý nếu input nhỏ.

### 9.4 Glossary vs translation_rules

| Thành phần | Nội dung | Lưu trữ |
|------------|----------|---------|
| **Glossary** | Từ vựng: term → translation | TM DB: `glossary_sources`, `glossary_targets` (theo project) |
| **Translation rules** | Quy tắc: pattern không dịch, instruction cho AI | TM DB: bảng `translation_rules` (theo project) |

**translation_rules** (schema trên): `rule_type` = `do_not_translate_pattern` | `instruction`; `content` = regex hoặc text.

Extract/translate dùng rules từ TM. Extract có thể bỏ qua cell match pattern; hoặc đánh dấu `no_translate`; translate copy nguyên văn.

### 9.5 Mô tả lệnh

| Lệnh | Mô tả |
|------|-------|
| `extract` | Đọc file, tách segments, ghi segment_sources, xuất segments_file |
| `translate` | Tạo translated_segments (--mode full: dịch toàn bộ; --mode update: tra TM trước). Không ghi TM |
| `import` | segments_file + translated_segments → upsert segment_targets vào TM DB |
| `rebuild` | Extract lại document, tra TM theo source_hash, thay bằng bản dịch; xuất file mới. Không nhận translated_segments |

**Tham số chung:**
- `--tag-open`, `--tag-close`: cho `extract`
- `--glossary`, `--tm`: cho `translate`, `import`. Glossary và translation_rules lấy từ TM DB (theo project). Có thể import glossary từ CSV
- `--batch-size`: cho `translate`, kích thước batch khi gọi API (mặc định xử lý theo batch)
- `--project`: chỉ định project (id hoặc name); mặc định 1 (global) khi dùng TM

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
├── data/                      # TM DB (SQLite): segments, glossary, translation_rules; nằm ngoài git (.gitignore)
├── glossaries/                # CSV từ vựng
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
