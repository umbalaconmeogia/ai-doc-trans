# CLI sample

## CLI syntax

ai-doc-trans extract    <input> --output <path> [--tm] [--project] [--source-lang] [--tag-open/close]
ai-doc-trans translate  <segments> --output <path> --tgt <lang> [--mode full|update] [--batch-size] [--glossary <csv>] [--rules <csv>]
ai-doc-trans import     <translated> [--tgt <lang>] [--tm] [--project]
ai-doc-trans rebuild    <input> --output <path> --tgt <lang> [--tm] [--project]
ai-doc-trans compare    <source> <target> [--output]
ai-doc-trans project    create <name> / list
ai-doc-trans glossary   import <csv> --project / export <csv> [--project] [--source-lang] [--tgt]
ai-doc-trans rules      export <csv> [--project] / import <csv> --project <id>

## CLI sample

ai-doc-trans extract    <input> --output <path> [--tm] [--project] [--source-lang] [--tag-open/close]
ai-doc-trans translate  <segments> --output <path> --tgt <lang> [--mode full|update] [--batch-size] [--glossary <csv>] [--rules <csv>]
ai-doc-trans import     <translated> [--tgt <lang>] [--tm] [--project]
ai-doc-trans rebuild    <input> --output <path> --tgt <lang> [--tm] [--project]
ai-doc-trans compare    <source> <target> [--output]
ai-doc-trans project    create <name> / list
ai-doc-trans glossary   import <csv> --project / export <csv> [--project] [--source-lang] [--tgt]
ai-doc-trans rules      export <csv> [--project] / import <csv> --project <id>