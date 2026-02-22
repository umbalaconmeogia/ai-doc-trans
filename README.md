# ai-doc-trans

Công cụ dịch tài liệu kỹ thuật và business với Translation Memory (TM). Hỗ trợ Excel, Word, PowerPoint — giữ nguyên định dạng, tái sử dụng bản dịch qua TM.

**Phase hiện tại:** Excel (PoC). Word và PowerPoint sẽ triển khai ở các phase sau.

---

## Yêu cầu

- **Python 3.10+**
- Windows / macOS / Linux

---

## Cài đặt

Mở terminal (Command Prompt, PowerShell, hoặc Terminal), di chuyển vào **thư mục gốc của dự án** (chứa `pyproject.toml`) rồi chạy:

**Bước 1 — Tạo virtual environment (khuyến nghị):**

```bash
python -m venv .venv
```

Kích hoạt (bắt buộc trước khi chạy `pip install` — nếu không, package sẽ cài vào Python hệ thống thay vì venv):

- **Windows:** `.venv\Scripts\activate`
- **macOS / Linux:** `source .venv/bin/activate`

*Lưu ý: Mỗi lần mở terminal mới cần kích hoạt lại; `pip install` chỉ cần chạy một lần.*

**Bước 2 — Cài package:**

**Cách 1 — Cài dạng editable (khuyến nghị khi phát triển):**

```bash
pip install -e .
```

- Tạo liên kết tới mã nguồn thay vì copy vào site-packages.
- Khi bạn sửa code, thay đổi **áp dụng ngay** — không cần chạy lại `pip install`.
- Phù hợp khi bạn đang phát triển hoặc tự sửa code ai-doc-trans.

**Cách 2 — Cài bình thường:**

```bash
pip install .
```

- Copy mã nguồn vào site-packages.
- Mỗi lần **cập nhật code**, cần chạy lại `pip install .` (hoặc `pip install -U .`) để áp dụng thay đổi.
- Phù hợp khi chỉ dùng tool, không sửa code.

---

## Cách chạy

Sau khi cài xong, bạn có thể chạy lệnh bằng một trong các cách sau:

| Hệ điều hành | Lệnh |
|--------------|------|
| **Windows** | `ai-doc-trans` hoặc `py -m ai_doc_trans` |
| **macOS / Linux** | `ai-doc-trans` hoặc `python3 -m ai_doc_trans` |

**Ví dụ:**

```bash
ai-doc-trans project list
```

hoặc (fallback nếu script chưa trong PATH):

```bash
py -m ai_doc_trans project list
```

*Lưu ý: Nếu dùng `pip install -e .`, thông thường `ai-doc-trans` sẽ được thêm vào PATH và có thể gọi trực tiếp.*

---

## Quick Start — Luồng cơ bản cho người mới

Thứ tự thực tế khi bắt đầu với ai-doc-trans:

### 1. Kiểm tra / tạo project

```bash
ai-doc-trans project list
ai-doc-trans project create "Sample Project"
```

### 2. Tạo và import translation rule, glossary

Export rule, edit csv, then import it.
```bash
ai-doc-trans rules export --project 2 rules_global.csv
# Edit CSV file.
ai-doc-trans rules import --project 2 rules_global.csv
```

Export glossary, edit csv, then import it.
```bash
ai-doc-trans glossary export --project 2 glossary_global.csv
# Edit CSV file.
ai-doc-trans glossary import --project 2 glossary_global.csv
```

### 3. Extract segments từ file Excel

Extract dùng `translation_rules` (project) để lọc bỏ segment không cần dịch (vd. mã hàng hóa, pattern regex). Cần `--project` (id) nếu có rules riêng cho project. Dùng `ai-doc-trans project list` để xem danh sách id.

```bash
ai-doc-trans extract input.xlsx --output segments.json --project 2 --source-lang vi
```

### 4. Dịch (tạo translated_segments)

- **Dịch toàn bộ:** `--mode full`
- **Chỉ dịch mới/thiếu (dùng TM):** `--mode update`
- Glossary và rules mặc định đọc từ DB. Dùng `--glossary <csv>` và `--rules <csv>` để chỉ định file thay cho DB.

```bash
ai-doc-trans translate segments.json --output translated.json --tgt vi --mode full --project 2
# Hoặc dùng file thay DB:
ai-doc-trans translate segments.json --output translated.json --tgt vi --mode full --project 2 --glossary glossary.csv --rules rules.csv
```

### 4. Import bản dịch vào TM

```bash
ai-doc-trans import translated.json --project 2
```

(File translated có `target_lang` trong mỗi segment nên không cần `--tgt`. File cũ thiếu `target_lang` thì dùng `--tgt vi`.)

### 5. Rebuild — xuất file Excel đã dịch

Rebuild dùng cùng `translation_rules` với extract; segment cần dịch nhưng **không có trong TM** → **báo lỗi**, không xuất file.

```bash
ai-doc-trans rebuild input.xlsx --output output_vi.xlsx --tgt en --project 2
```

### 6. (Tùy chọn) So sánh source và target

```bash
ai-doc-trans compare input.xlsx output_vi.xlsx --output report.txt
```

---

## Các lệnh chính

| Lệnh | Mô tả |
|------|-------|
| `extract` | Lọc segment (bỏ non-text, áp dụng `do_not_translate_pattern` từ TM), ghi segment_sources, xuất segments_file |
| `translate` | Dịch segments (AI hoặc TM) → translated_segments |
| `import` | Ghi translated_segments vào TM DB |
| `rebuild` | Extract lại, áp dụng `do_not_translate_pattern`, tra TM → thay bằng bản dịch; **báo lỗi nếu segment thiếu bản dịch** |
| `compare` | So sánh file gốc và file đã dịch |
| `project create/list` | Quản lý project trong TM |
| `glossary import/export` | Import/export glossary CSV; import cần --project, xóa glossary của project đó và thay mới |
| `rules export/import` | Export/import translation_rules ra/vào CSV; import cần --project, xóa rules của project đó và thay mới |
| `segment export/import` | Xuất segment translations từ TM ra CSV / import CSV vào TM |

Tham số chung: `--tm` (đường dẫn TM DB, mặc định `data/doc_trans.db`), `--project` (project id, mặc định 1 = global). `extract` và `rebuild` cần `--project` để load đúng `translation_rules`.

---

## Cấu trúc thư mục

```
ai-doc-trans/
├── src/ai_doc_trans/ # Mã nguồn
├── data/             # TM DB (SQLite), nằm ngoài git
├── glossaries/       # CSV glossary (tham khảo)
├── docs/             # Tài liệu thiết kế
└── tests/            # Test
```

---

## translation_rules

Extract và rebuild dùng `translation_rules` (bảng trong TM DB) để lọc segment:
- `do_not_translate_pattern`: regex — segment match thì bỏ qua (không đưa vào segments_file, không tra TM)
- `instruction`: hướng dẫn cho AI khi dịch

**Export/import qua CSV** (thuận tiện hơn SQL, tái sử dụng giữa các project):

```bash
ai-doc-trans rules export rules.csv                    # xuất tất cả
ai-doc-trans rules export rules.csv --project 1        # chỉ project global (id=1)
ai-doc-trans rules import rules.csv --project 1        # xóa rules của project, insert từ CSV
```

CSV: `project_id`, `project_name` (tham khảo), `rule_name`, `rule_type`, `content`, `remarks`. Project đích khi import chỉ định qua `--project`.

---

## glossary

Từ vựng dịch: term → translation theo project.

**Export/import qua CSV** (tương tự rules):

```bash
ai-doc-trans glossary export glossary.csv                    # xuất tất cả
ai-doc-trans glossary export glossary.csv --project 1        # chỉ project 1 (global)
ai-doc-trans glossary export glossary.csv --source-lang en --tgt vi  # lọc theo ngôn ngữ
ai-doc-trans glossary import glossary.csv --project 1        # xóa glossary của project, insert từ CSV
```

CSV: `project_id`, `project_name` (tham khảo), `term`, `source_lang`, `target_lang`, `translation`, `context`, `remarks`.

---

## segment (CSV export/import)

Xuất/nhập segment translations **trực tiếp giữa TM DB và CSV** (không qua JSON). Mỗi row = mapping source → target theo ngôn ngữ. **Lưu ý:** CSV phù hợp văn bản đơn giản.

```bash
ai-doc-trans segment export -o translated.csv --tgt en --project 2   # TM → CSV
# Chỉnh sửa translated.csv (vd. trong Excel)
ai-doc-trans segment import translated.csv --tgt en --project 2     # CSV → TM
```

CSV columns: `source`, `target`, `source_lang`, `target_lang`, `structure`, `position`.

---

## Tài liệu thêm

- [Basic Design (BD)](docs/DesignDocument/BD.md) — Thiết kế kỹ thuật, mô tả lệnh chi tiết, sample translation_rules
- [System Requirements (SR)](docs/DesignDocument/SR.md) — Yêu cầu hệ thống

---

## License

Xem file [LICENSE](LICENSE).
