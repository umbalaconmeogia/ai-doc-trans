
```bash

# 1. Kiểm tra / tạo project
# 2. Import translation rule, glossary
# 3. Extract segments từ file Excel
# 3.1. Export/edit/import nội dung segment
ai-doc-trans project list

ai-doc-trans rules import --project 1 docs/sample/rules_global.csv
ai-doc-trans glossary import --project 1 glossary_global.csv
ai-doc-trans project create "Financial data of Trace Mineral Project"
ai-doc-trans extract "data/Financial data of Trace Mineral Project_20260222.vi.xlsx" --output segments.json --project 2 --source-lang vi
ai-doc-trans segment export -o translated.csv --tgt en --project 2

ai-doc-trans segment import docs/sample/translated.csv --project 2

# 3.2 Create  csv
ai-doc-trans segment export -o docs/sample/translated.csv --tgt en --project 2

# 4. Dịch (tạo translated_segments)
ai-doc-trans translate segments.json --output translated.json --tgt en --mode full --project 2 \
  --glossary docs/sample/glossary_global.csv \
  --rules docs/sample/rules_global.csv


### 4. Import bản dịch vào TM
ai-doc-trans import translated.json --project 2

### 5. Rebuild — xuất file Excel đã dịch
ai-doc-trans rebuild "data/Financial data of Trace Mineral Project_20260222.vi.xlsx" --output "data/Financial data of Trace Mineral Project_20260222.en.xlsx" --tgt en --project 2

```