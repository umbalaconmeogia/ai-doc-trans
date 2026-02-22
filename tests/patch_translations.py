"""Patch translated.json with sample Vietnamese translations for testing."""
import json
import sys
sys.path.insert(0, "src")

data = json.load(open("tests/out/translated.json", encoding="utf-8"))
translations = {
    "Product Name": "Ten san pham",
    "Description": "Mo ta",
    "Unit": "Don vi",
    "Raw material": "Nguyen lieu tho",
    "kg": "kg",
    "Finished goods": "Thanh pham",
    "pcs": "cai",
    "Total weight": "Tong trong luong",
    "ton": "tan",
    "Document Title": "Tieu de tai lieu",
    "Translation Test": "Kiem tra dich thuat",
    "Version": "Phien ban",
    "1.0": "1.0",
}
for seg in data:
    seg["target"] = translations.get(seg["source"], seg["source"])
    seg.setdefault("target_lang", "vi")  # Ensure target_lang for import without --tgt

json.dump(data, open("tests/out/translated_vi.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("Patched translated_vi.json")
