# Basic Design (BD)

Thiết kế cơ bản cho công cụ dịch tài liệu, dựa trên [SR.md](./SR.md).

---

## 1. Kiến trúc tổng quan

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            ai-doc-trans                                      │
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

**Khóa tra TM:** `(source_hash, source_lang, target_lang)`. Dùng `sha256(source_text)` làm `source_hash` (UTF-8, hex digest). Mỗi `source_text` chỉ có 1 bản ghi trong `segment_sources` (per project). Hash algorithm cố định, không thay đổi sau khi có dữ liệu trong TM.

---

## 3. Translation Memory (TM)

**Mục đích:** Lưu mapping segment gốc → bản dịch để tái sử dụng. Luôn có bảng **projects**; 1 TM DB có thể dùng cho nhiều project, glossary/translations dùng chung hoặc override theo project.

### 3.1 Cấu trúc DB (SQLite)

Tách riêng source và target; dùng **INTEGER id** cho `*_sources`, FK từ `*_targets`. `project_id = 1` = company-wide (chung, tên "global"); `project_id > 1` = theo project. **Segment:** `segment_sources` có `project_id`; mỗi source thuộc đúng một project, không fallback. `segment_targets` phụ thuộc `source_id` nên không cần `project_id`. **Glossary / rules:** Tra cứu ưu tiên bản project trùng, không có thì dùng `project_id = 1`. *Dùng 1 thay vì 0 để tránh vấn đề với SQLite.*

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
│  project_id     INTEGER   NOT NULL   -- Mỗi source thuộc đúng một project        │
│  source_hash    TEXT      NOT NULL   -- Tra cứu insert/lookup (theo project)      │
│  source_text    TEXT      NOT NULL   -- Văn bản gốc                               │
│  source_lang    TEXT      NOT NULL   -- Mã ngôn ngữ nguồn (en, vi, ...)          │
│  structure      TEXT                 -- cell, para, heading_1, list_item, ...     │
│  position       TEXT                 -- Tham khảo: page số (docx, pptx), Sheet1!A1 (Excel) │
│  created_at     TEXT      NOT NULL   -- ISO 8601                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  PRIMARY KEY (id), UNIQUE (source_hash, project_id)                               │
│  INDEX idx_segment_sources_hash_project ON segment_sources(source_hash, project_id) │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         │ 1 ────── N
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  segment_targets                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│  source_id      INTEGER   NOT NULL   -- FK → segment_sources.id                  │
│  target_lang    TEXT      NOT NULL   -- Mã ngôn ngữ đích                         │
│  target_text    TEXT      NOT NULL   -- Bản dịch                                  │
│  created_at     TEXT      NOT NULL   -- ISO 8601                                  │
│  updated_at     TEXT      NOT NULL   -- ISO 8601                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  PRIMARY KEY (source_id, target_lang)                                             │
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
│  remarks        TEXT                 -- Ghi chú (optional)                        │
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
│  target_lang    TEXT      NOT NULL   -- Ngôn ngữ đích; "" = áp dụng mọi ngôn ngữ  │
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
│  rule_name      TEXT                 -- Tên mô tả rule (dễ hiểu)                  │
│  rule_type      TEXT      NOT NULL   -- do_not_translate_pattern, instruction     │
│  content        TEXT      NOT NULL   -- regex pattern hoặc instruction text       │
│  remarks        TEXT                 -- Ghi chú (optional)                        │
│  created_at     TEXT      NOT NULL   -- ISO 8601                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  PRIMARY KEY (id)                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Tra cứu:** **Segment:** Tra `(source_hash, project_id)` trong `segment_sources`, không fallback. **Glossary / rules:** Ưu tiên bản có `project_id` trùng với project hiện tại; không có thì dùng `project_id = 1`. **Glossary target_lang:** rỗng (`""`) = áp dụng cho mọi ngôn ngữ; target_lang cụ thể override target_lang rỗng.

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
[document gốc] + TM DB → Rebuilder → [file mới]
```

### 4.4 Compare (Excel)

```
[source_file] + [target_file] → Compare → [báo cáo diff]
```

Dùng thông tin `position` (sheet!cell) từ source để tìm ô tương ứng trong target, so sánh nội dung. Hỗ trợ kiểm tra sau rebuild: source có text, target có bản dịch hay không.

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
| **Excel** | Cell text (bỏ number, date, formula ở tầng extractor; bỏ mã hàng hóa qua `do_not_translate_pattern`) | `cell` (hoặc `header` nếu có) | Lọc tại extract; rebuild dùng cùng logic lọc |
| **Word** | Paragraph, list item, heading | `para`, `heading_1`, `heading_2`, `list_item` | position = page number |
| **PowerPoint** | Text trong shape, textbox, placeholder | `title`, `body`, `textbox` | position = slide number |

Phase 1 (Excel): có thể đơn giản hóa, chưa cần structure phức tạp. Phase 2 (Word) trở đi: áp dụng structure-aware đầy đủ.

---

## 7. Rebuilder

- **Input:** document gốc + TM DB (--tm, --tgt, --project). **Không** nhận translated_segments file.
- **Luồng:** Extract lại document → tại mỗi vị trí có text:
  1. Match `do_not_translate_pattern` → giữ nguyên, không tra TM
  2. Không match → tính `source_hash` → tra `segment_targets` trong TM → lấy `target_text` → thay thế
  3. **Không tìm thấy trong TM → báo lỗi** (liệt kê các segment thiếu bản dịch, dừng hoặc xuất báo cáo lỗi tùy option). Không âm thầm bỏ qua.
- Rebuild dùng **cùng bộ `translation_rules`** với extract → đảm bảo nhất quán, không có segment "lọt qua extract nhưng không có trong TM"
- Giữ nguyên format (font, màu, border, v.v.)
- Với Excel phức tạp: có thể dùng COM (PowerShell) nếu thư viện làm vỡ format

**Phản biện / mở rộng:** Nếu cần rebuild mà chưa import (vd. dịch one-off, chưa muốn ghi TM), có thể hỗ trợ thêm chế độ rebuild từ translated_segments file. Mặc định: rebuild từ TM.

---

## 8. Công nghệ đề xuất (PoC)

| Thành phần | Công nghệ |
|------------|-----------|
| Ngôn ngữ | Python 3.x (đa nền tảng) |
| TM | SQLite |
| Excel | `openpyxl` (Phase 1: đủ dùng vì chỉ update cell value, giữ nguyên format. Fallback COM trên Windows nếu cần xử lý chart/object phức tạp ở phase sau) |
| Word | `python-docx` |
| PowerPoint | `python-pptx` |
| AI | API (Gemini, GPT, Claude) hoặc integration Cursor/script |
| CLI | `click` (đề xuất: hỗ trợ subcommand group tốt hơn argparse, dễ mở rộng) |

---

## 9. Giao diện CLI (PoC)

Tách riêng các lệnh để tránh ôm quá nhiều xử lý vào một CLI. CLI dùng `click` với subcommand group. `--output` bắt buộc truyền (không có default).

```
ai-doc-trans extract    <input> --output <path> [--tm <path>] [--project <id>] [--source-lang <lang>] [--tag-open <char>] [--tag-close <char>]
ai-doc-trans translate  <segments_file> --output <path> [--mode full|update] [--tgt <lang>] [--tm <path>] [--project <id>] [--batch-size <n>] [--glossary <csv>] [--rules <csv>]
ai-doc-trans import     <translated_segments> [--tm <path>] [--project <id>] [--tgt <lang>]  # --tgt optional when target_lang in file
ai-doc-trans rebuild    <input> --output <path> [--tm <path>] [--tgt <lang>] [--project <id>]
ai-doc-trans compare    <source_file> <target_file> [--output <path>] [--tm <path>]
ai-doc-trans project    create <name>
ai-doc-trans project    list
ai-doc-trans glossary   import <csv> --project <id> [--tm <path>]
ai-doc-trans glossary   export <csv> [--project <id>] [--source-lang] [--tgt] [--tm <path>]
ai-doc-trans segment    export -o <csv> --tgt <lang> [--tm] [--project] / import <csv> --tgt <lang> [--tm] [--project]
ai-doc-trans rules      export <csv> [--project <id>] [--tm <path>]
ai-doc-trans rules      import <csv> --project <id> [--tm <path>]
```

### 9.1 Luồng dữ liệu & vai trò TM DB

| Bước | Hành vi |
|------|---------|
| **extract** | Đọc document → tách segments (dedupe theo source_hash) → **ghi vào segment_sources trong TM DB** (insert if not exists) → **xuất segments_file** (1 record/unique source_text) |
| **translate** | Đọc **segments_file** → tạo **translated_segments**. Glossary và rules mặc định từ DB; dùng --glossary, --rules để chỉ định file CSV thay DB. Nguồn dịch: AI/API, Cursor IDE, hoặc thủ công. |
| **import** | Đọc translated_segments (có source_hash/source_id) → match theo key, không theo thứ tự → **upsert segment_targets** vào TM DB |
| **rebuild** | Đọc document → extract lại → áp dụng `do_not_translate_pattern` (giữ nguyên) → tra TM theo source_hash → thay bằng bản dịch → xuất file mới. **Báo lỗi nếu segment cần dịch không có trong TM.** Không nhận translated_segments |

**segments_file** = output của `extract` — mỗi source_text unique (1 record). **translated_segments** = segments_file + target; import match theo source_hash/source_id, không theo thứ tự.

**Tách translate + import:** translate chỉ tạo translated_segments; import ghi vào TM DB. Có thể dùng Cursor IDE dịch thay vì API, rồi chạy import. Linh hoạt cho PoC.  “mới/chưa dịch” (Trong translate --mode update: tra segment_targets theo (source_id, target_lang) — không có bản dịch thì gọi AI. Có thể truyền thêm các segment đã dịch làm context cho AI để thống nhất phong cách.

### 9.2 Format segments_file và translated_segments

**segments_file** (output của extract, unique by source_hash):
```json
[
  {"source": "Introduction", "structure": "heading_1", "source_lang": "en", "source_hash": "...", "source_id": 1, "position": "Sheet1!A1"}
]
```

**translated_segments** nên **bao gồm đầy đủ thông tin** từ segments_file cộng target và target_lang, để import/rebuild chính xác, không phụ thuộc thứ tự:
```json
[
  {"source": "Introduction", "source_hash": "abc", "source_id": 1, "target": "Giới thiệu", "structure": "heading_1", "source_lang": "en", "target_lang": "vi"}
]
```
- `target_lang` cùng cấp với `source_lang`, mô tả ngôn ngữ đích. Import đọc từ file; `--tgt` tùy chọn (override hoặc fallback cho file cũ thiếu target_lang).
- Với `source_hash`/`source_id`, import match theo key thay vì theo thứ tự.

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

**`do_not_translate_pattern` áp dụng ở cả extract lẫn rebuild** (dùng cùng một bộ rules từ TM DB):
- **Extract:** segment match pattern → bỏ qua hoàn toàn, không đưa vào segments_file, không ghi TM
- **Rebuild:** vị trí match pattern → bỏ qua, giữ nguyên text gốc, không tra TM

Vì cả hai bước dùng cùng logic lọc, segments_file chỉ chứa những segment thực sự cần dịch. TM không bị pollute bởi entry "dịch = nguyên văn". Không dùng đánh dấu `no_translate`.

Các trường hợp áp dụng `do_not_translate_pattern`:
- Mã hàng hóa, mã sản phẩm (vd. `NVL\d+`, `SP-\d+`) → match regex pattern
- Cell không phải kiểu text (number, date, formula) → lọc ở tầng extractor (không phụ thuộc translation_rules)

**`instruction`** chỉ dùng ở bước translate: đưa vào prompt AI.

#### 9.4.1 Sample translation_rules

Ví dụ SQL để thêm rules (project_id = 1 = global):

```sql
-- Bỏ qua mã nguyên vật liệu (vd. NVL1000, NVL2001)
INSERT INTO translation_rules (project_id, rule_name, rule_type, content, created_at)
VALUES (1, 'Mã NVL', 'do_not_translate_pattern', 'NVL\d+', datetime('now'));

-- Bỏ qua mã sản phẩm (vd. SP-001, SP-123)
INSERT INTO translation_rules (project_id, rule_name, rule_type, content, created_at)
VALUES (1, 'Mã sản phẩm', 'do_not_translate_pattern', 'SP-\d+', datetime('now'));

-- Instruction cho AI khi dịch
INSERT INTO translation_rules (project_id, rule_name, rule_type, content, created_at)
VALUES (1, 'Style headings', 'instruction', 'Translate headings concisely. Keep technical terms consistent with glossary.', datetime('now'));
```

Pattern là **regex** (Python `re`). Ví dụ thêm: `^[A-Z]{2,4}\d{4,}$` (mã dạng AB1234), `^\d+$` (chỉ số).

#### 9.4.2 rules export / import (CSV)

Thay vì chạy SQL, có thể export/import translation_rules qua CSV để thuận tiện và tái sử dụng giữa các project.

**CSV format:** `project_id`, `project_name`, `rule_name`, `rule_type`, `content`, `remarks` (project_id/project_name trong CSV chỉ để tham khảo; rule_name, remarks tùy chọn)

- **export:** Xuất rules ra CSV. `--project` để lọc theo project; bỏ qua thì xuất tất cả.
- **import:** Chỉ định `--project` trên command line. Xóa **toàn bộ rules của project đó**, rồi insert từng dòng CSV vào project đó. Cột project_id/project_name trong CSV không dùng khi import.

#### 9.4.3 glossary export / import (CSV)

Tương tự rules, glossary export/import qua CSV để thuận tiện và tái sử dụng giữa các project.

**CSV format:** `project_id`, `project_name`, `term`, `source_lang`, `target_lang`, `translation`, `context`, `remarks` (project_id/project_name trong CSV chỉ để tham khảo)

- **target_lang rỗng (null hoặc ""):** Áp dụng cho **mọi ngôn ngữ đích**. Tra cứu ưu tiên bản dịch theo target_lang cụ thể, không có thì dùng bản target_lang rỗng.
- **export:** Xuất glossary ra CSV. `--project`, `--source-lang`, `--tgt` tùy chọn để lọc; bỏ qua thì xuất tất cả.
- **import:** Chỉ định `--project` trên command line. Xóa **toàn bộ glossary của project đó**, rồi insert từng dòng CSV vào project đó.

#### 9.4.4 segment export / import (CSV)

Export/import segment translations **trực tiếp giữa TM DB và CSV** (không qua JSON). Dễ chỉnh sửa trong Excel. **Nhược điểm:** CSV phù hợp văn bản đơn giản.

**CSV format:** `source`, `target`, `source_lang`, `target_lang`, `structure`, `position`. `source_hash` và `source_id` không lưu; tra/ghi qua TM theo hash khi import.

- **export:** Xuất từ TM DB ra CSV. Cần `--tgt`, `--project`. Tùy chọn `--source-lang` để lọc.
- **import:** Đọc CSV, ghi thẳng vào TM DB (upsert segment_targets). Hash tính từ source text; tra TM để lấy/tạo source_id. Cần `--tgt`, `--project`.

**Luồng:** extract → translate → import (ghi TM) → segment export (TM → CSV) → edit CSV → segment import (CSV → TM) → rebuild.

### 9.5 Mô tả lệnh

| Lệnh | Mô tả |
|------|-------|
| `extract` | Đọc file, lọc segment (bỏ non-text, áp dụng `do_not_translate_pattern`), ghi segment_sources, xuất segments_file |
| `translate` | Tạo translated_segments (--mode full: dịch toàn bộ; --mode update: tra TM trước). Không ghi TM |
| `import` | translated_segments → upsert segment_targets vào TM DB (match theo source_hash/source_id, không theo thứ tự) |
| `rebuild` | Extract lại document, áp dụng `do_not_translate_pattern` (giữ nguyên), tra TM theo source_hash → thay bằng bản dịch; **báo lỗi nếu segment cần dịch không có trong TM**; xuất file mới |
| `compare` | So sánh file Excel gốc và file đã dịch theo position (sheet!cell). Output báo cáo diff source vs target |
| `project create` | Tạo project mới trong TM DB |
| `project list` | Liệt kê tất cả project trong TM DB |
| `project clear` | Xóa toàn bộ segments (segment_sources + cascade segment_targets) thuộc project chỉ định |
| `glossary import` | Import glossary từ CSV vào project chỉ định; **xóa glossary của project đó**, insert lại từ CSV |
| `glossary export` | Export glossary ra CSV (--project, --source-lang, --tgt để lọc; bỏ qua = xuất tất cả) |
| `segment export` | Xuất segment translations từ TM DB ra CSV |
| `segment import` | Import CSV thẳng vào TM DB (upsert segment_targets) |
| `rules export` | Export translation_rules ra CSV (theo project hoặc tất cả) |
| `rules import` | Import translation_rules từ CSV vào project chỉ định; **xóa rules của project đó**, insert lại từ CSV. Cho phép tái sử dụng rules giữa các project |

**Tham số chung:**
- `--output`: bắt buộc truyền cho `extract`, `translate`, `rebuild` (không có default)
- `--tag-open`, `--tag-close`: cho `extract`. Mặc định `{`, `}`
- `--source-lang`: cho `extract`. Ngôn ngữ nguồn mặc định per-document (Phase 1)
- `--tm`: đường dẫn TM DB. Mặc định `data/doc_trans.db`
- `--project`: chỉ định project id; mặc định 1 (global)
- `--batch-size`: cho `translate`, kích thước batch khi gọi AI API (mặc định 50)
- `--mode full|update`: cho `translate`. Glossary và translation_rules lấy từ TM DB (theo project)

---

## 10. Cấu trúc thư mục đề xuất

```
ai-doc-trans/
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
| Thư viện làm vỡ format Excel/Word | Phase 1: openpyxl chỉ update `.value`, không đổi format → an toàn. Fallback COM (PowerShell) ở phase sau nếu cần chart/object |
| API dịch tốn phí | PoC dùng free tier / Cursor; production chọn API phù hợp |
| Segment quá dài | Chia batch qua `--batch-size`; mặc định 50 segment/batch |
| Rebuild sai vị trí | Extract/rebuild cùng thứ tự duyệt; dùng `compare` để validate source vs target sau rebuild |
| Hash algorithm thay đổi | `sha256(source_text)` cố định; không đổi khi đã có dữ liệu trong TM DB |
