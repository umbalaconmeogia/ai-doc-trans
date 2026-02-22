from __future__ import annotations

import csv
import logging
import sys
from pathlib import Path

import click

from ai_doc_trans.engine.tm import (
    GLOSSARY_CSV_FIELDS,
    TM,
    DEFAULT_TM_PATH,
    TR_RULES_CSV_FIELDS,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# ---------------------------------------------------------------------------
# Shared options
# ---------------------------------------------------------------------------

def _tm_option(required: bool = False):
    return click.option(
        "--tm",
        default=DEFAULT_TM_PATH,
        show_default=True,
        help="Path to the TM SQLite database.",
    )


def _project_option():
    return click.option(
        "--project",
        default="1",
        show_default=True,
        help="Project id (default: 1 = global). Use 'project list' to see ids.",
    )


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------

@click.group()
def cli():
    """ai-doc-trans: Document translation tool with Translation Memory."""


# ---------------------------------------------------------------------------
# extract
# ---------------------------------------------------------------------------

@cli.command("extract")
@click.argument("input", type=click.Path(exists=True, path_type=Path))
@click.option("--output", required=True, type=click.Path(path_type=Path), help="Output segments_file.json path.")
@_tm_option()
@_project_option()
@click.option("--source-lang", default="en", show_default=True, help="Source language code.")
@click.option("--tag-open", default="{", show_default=True, help="Structure tag open character.")
@click.option("--tag-close", default="}", show_default=True, help="Structure tag close character.")
def cmd_extract(input, output, tm, project, source_lang, tag_open, tag_close):
    """Extract text segments from INPUT file into OUTPUT segments_file.json."""
    from ai_doc_trans.extractors.excel import ExcelExtractor
    from ai_doc_trans.io.segments import save_segments

    with TM(tm) as tm_db:
        project_id = tm_db.resolve_project_id(project)
        extractor = ExcelExtractor(
            tm=tm_db,
            source_lang=source_lang,
            project_id=project_id,
            tag_open=tag_open,
            tag_close=tag_close,
        )
        segments = list(extractor.extract(input))

    save_segments(segments, output)
    click.echo(f"Extracted {len(segments)} segments → {output}")


# ---------------------------------------------------------------------------
# translate
# ---------------------------------------------------------------------------

@cli.command("translate")
@click.argument("segments_file", type=click.Path(exists=True, path_type=Path))
@click.option("--output", required=True, type=click.Path(path_type=Path), help="Output translated_segments.json path.")
@click.option("--mode", default="full", show_default=True, type=click.Choice(["full", "update"]), help="Translation mode.")
@click.option("--tgt", required=True, help="Target language code (e.g. vi, ja).")
@_tm_option()
@_project_option()
@click.option("--batch-size", default=50, show_default=True, help="Segments per AI API batch.")
@click.option(
    "--glossary",
    type=click.Path(exists=True, path_type=Path),
    help="Glossary CSV path. When set, use file instead of DB.",
)
@click.option(
    "--rules",
    type=click.Path(exists=True, path_type=Path),
    help="Translation rules CSV path. When set, use file instead of DB.",
)
def cmd_translate(segments_file, output, mode, tgt, tm, project, batch_size, glossary, rules):
    """Translate SEGMENTS_FILE and write translated_segments to OUTPUT."""
    from ai_doc_trans.engine.translate import run_translate
    from ai_doc_trans.io.segments import load_segments, save_translated_segments

    segments = load_segments(segments_file)
    if not segments:
        click.echo("No segments to translate.")
        return

    with TM(tm) as tm_db:
        project_id = tm_db.resolve_project_id(project)
        translated = run_translate(
            segments=segments,
            target_lang=tgt,
            tm=tm_db,
            project_id=project_id,
            mode=mode,
            batch_size=batch_size,
            glossary_path=glossary,
            rules_path=rules,
        )

    save_translated_segments(translated, output)
    click.echo(f"Translated {len(translated)} segments ({mode} mode) → {output}")


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------

@cli.command("import")
@click.argument("translated_segments", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--tgt",
    help="Target language code. Optional when target_lang is present in the file.",
)
@_tm_option()
@_project_option()
def cmd_import(translated_segments, tgt, tm, project):
    """Import segments into the TM database.

    Accepts both source-only JSON (e.g. output of extract) and translated_segments
    (with target). When target is present, use --tgt or target_lang in file.
    """
    from ai_doc_trans.engine.importer import run_import
    from ai_doc_trans.io.segments import load_translated_segments

    translated = load_translated_segments(translated_segments)
    if not translated:
        raise click.UsageError("No segments to import.")
    has_targets = any(ts.target for ts in translated)
    target_lang = tgt or (translated[0].target_lang if translated else None)
    if has_targets and not target_lang:
        raise click.UsageError(
            "Target language required when file has targets: add target_lang to each segment, or use --tgt."
        )

    with TM(tm) as tm_db:
        project_id = tm_db.resolve_project_id(project)
        sources_ensured, targets_upserted = run_import(translated, target_lang, tm_db, project_id)

    msg = f"Imported {sources_ensured} segment sources"
    if targets_upserted:
        msg += f", {targets_upserted} translations"
    msg += f" into TM ({tm})"
    click.echo(msg)


# ---------------------------------------------------------------------------
# rebuild
# ---------------------------------------------------------------------------

@cli.command("rebuild")
@click.argument("input", type=click.Path(exists=True, path_type=Path))
@click.option("--output", required=True, type=click.Path(path_type=Path), help="Output (translated) Excel file path.")
@click.option("--tgt", required=True, help="Target language code.")
@_tm_option()
@_project_option()
def cmd_rebuild(input, output, tgt, tm, project):
    """Re-extract INPUT, look up translations in TM, write translated OUTPUT."""
    from ai_doc_trans.exceptions import MissingTranslationsError
    from ai_doc_trans.rebuilders.excel import ExcelRebuilder

    try:
        with TM(tm) as tm_db:
            project_id = tm_db.resolve_project_id(project)
            rebuilder = ExcelRebuilder(tm=tm_db, target_lang=tgt, project_id=project_id)
            replaced = rebuilder.rebuild(input, Path(output))
    except MissingTranslationsError as e:
        click.echo(str(e), err=True)
        sys.exit(1)

    click.echo(f"Rebuilt → {output}  ({replaced} cells replaced)")


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------

@cli.command("compare")
@click.argument("source_file", type=click.Path(exists=True, path_type=Path))
@click.argument("target_file", type=click.Path(exists=True, path_type=Path))
@click.option("--output", default=None, type=click.Path(path_type=Path), help="Write report to file instead of stdout.")
def cmd_compare(source_file, target_file, output):
    """Compare SOURCE_FILE and TARGET_FILE cell-by-cell using position info."""
    from ai_doc_trans.compare.excel import compare_excel, format_report

    results = compare_excel(source_file, target_file)
    report = format_report(results)

    if output:
        Path(output).write_text(report, encoding="utf-8")
        click.echo(f"Report written → {output}")
    else:
        click.echo(report)


# ---------------------------------------------------------------------------
# project group
# ---------------------------------------------------------------------------

@cli.group("project")
def project_group():
    """Manage projects in the TM database."""


@project_group.command("create")
@click.argument("name")
@_tm_option()
def project_create(name, tm):
    """Create a new project with NAME in the TM database."""
    with TM(tm) as tm_db:
        pid = tm_db.create_project(name)
    click.echo(f"Created project '{name}' with id={pid}")


@project_group.command("list")
@_tm_option()
def project_list(tm):
    """List all projects in the TM database."""
    with TM(tm) as tm_db:
        projects = tm_db.list_projects()
    if not projects:
        click.echo("No projects found.")
        return
    click.echo(f"{'ID':>4}  {'NAME':<30}  {'CREATED_AT'}")
    click.echo("-" * 60)
    for p in projects:
        click.echo(f"{p['id']:>4}  {p['name']:<30}  {p['created_at']}")


@project_group.command("clear")
@click.option("--project", required=True, help="Project id to clear all segment translations from.")
@_tm_option()
def project_clear(project, tm):
    """Delete all segment translations belonging to the specified project."""
    with TM(tm) as tm_db:
        project_id = tm_db.resolve_project_id(project)
        count = tm_db.clear_project_segments(project_id)
    click.echo(f"Cleared {count} segments from project {project!r} ({tm})")


# ---------------------------------------------------------------------------
# glossary group
# ---------------------------------------------------------------------------

@cli.group("glossary")
def glossary_group():
    """Import or export glossary entries."""


@glossary_group.command("import")
@click.argument("csv_file", type=click.Path(exists=True, path_type=Path))
@click.option("--project", required=True, help="Project id or name to import glossary into.")
@_tm_option()
def glossary_import(csv_file, project, tm):
    """Import glossary from CSV_FILE into the specified project.

    Deletes all existing glossary for that project, then inserts from CSV.
    CSV columns: project_id, project_name (reference only), term, source_lang, target_lang, translation, context, remarks.
    """
    with open(csv_file, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    with TM(tm) as tm_db:
        project_id = tm_db.resolve_project_id(project)
        count = tm_db.replace_glossary(project_id, rows)

    click.echo(f"Imported {count} glossary entries into project {project!r} ({tm}). Replaced existing entries.")


@glossary_group.command("export")
@click.argument("csv_file", type=click.Path(path_type=Path))
@click.option("--project", default=None, help="Project id or name. Omit to export all projects.")
@click.option("--source-lang", default=None, help="Source language. Omit to export all.")
@click.option("--tgt", default=None, help="Target language. Omit to export all.")
@_tm_option()
def glossary_export(csv_file, project, source_lang, tgt, tm):
    """Export glossary to CSV_FILE.

    CSV columns: project_id, project_name, term, source_lang, target_lang, translation, context, remarks.
    Use --project, --source-lang, --tgt to filter.
    """
    with TM(tm) as tm_db:
        project_id = tm_db.resolve_project_id(project) if project else None
        entries = tm_db.list_all_glossary_entries(
            project_id=project_id,
            source_lang=source_lang,
            target_lang=tgt,
        )

    Path(csv_file).parent.mkdir(parents=True, exist_ok=True)
    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=GLOSSARY_CSV_FIELDS, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(entries)
    click.echo(f"Exported {len(entries)} glossary entries → {csv_file}")


# ---------------------------------------------------------------------------
# segment group (CSV export/import for translated segments)
# ---------------------------------------------------------------------------

@cli.group("segment")
def segment_group():
    """Export or import translated segments to/from CSV for easy editing."""


@segment_group.command("export")
@click.option("--output", "-o", required=True, type=click.Path(path_type=Path), help="Output CSV path.")
@click.option("--tgt", required=True, help="Target language to export (e.g. vi, en).")
@click.option("--source-lang", default=None, help="Filter by source language. Omit to export all.")
@_tm_option()
@_project_option()
def segment_export(output, tgt, source_lang, tm, project):
    """Export segment translations from TM DB to CSV.

    CSV columns: source, target, source_lang, target_lang, structure, position.
    """
    from ai_doc_trans.io.segments_csv import export_tm_to_csv

    with TM(tm) as tm_db:
        project_id = tm_db.resolve_project_id(project)
        count = export_tm_to_csv(
            tm_db, output, project_id, tgt, source_lang=source_lang
        )
    click.echo(f"Exported {count} segments → {output}")


@segment_group.command("import")
@click.argument("csv_file", type=click.Path(exists=True, path_type=Path))
@click.option("--tgt", required=True, help="Target language (e.g. vi, en).")
@_tm_option()
@_project_option()
def segment_import(csv_file, tgt, tm, project):
    """Import CSV into TM DB (upsert segment_targets).

    CSV columns: source, target, source_lang, target_lang, structure, position.
    source_hash and source_id derived from TM (lookup by hash or create).
    """
    from ai_doc_trans.io.segments_csv import import_csv_to_tm

    with TM(tm) as tm_db:
        project_id = tm_db.resolve_project_id(project)
        count = import_csv_to_tm(csv_file, tm_db, project_id, target_lang=tgt)
    click.echo(f"Imported {count} translations into TM ({tm})")


# ---------------------------------------------------------------------------
# rules group (translation_rules export/import)
# ---------------------------------------------------------------------------

@cli.group("rules")
def rules_group():
    """Export or import translation rules (do_not_translate_pattern, instruction) to/from CSV."""


@rules_group.command("export")
@click.argument("csv_file", type=click.Path(path_type=Path))
@click.option("--project", default=None, help="Project id. Omit to export all projects.")
@_tm_option()
def rules_export(csv_file, project, tm):
    """Export translation rules to CSV_FILE.

    CSV columns: project_id, project_name, rule_name, rule_type, content, remarks.
    Use --project to export only one project's rules.
    """
    with TM(tm) as tm_db:
        project_id = tm_db.resolve_project_id(project) if project else None
        rules = tm_db.list_all_translation_rules(project_id)

    Path(csv_file).parent.mkdir(parents=True, exist_ok=True)
    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=TR_RULES_CSV_FIELDS, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rules)
    click.echo(f"Exported {len(rules)} translation rules → {csv_file}")


@rules_group.command("import")
@click.argument("csv_file", type=click.Path(exists=True, path_type=Path))
@click.option("--project", required=True, help="Project id to import rules into.")
@_tm_option()
def rules_import(csv_file, project, tm):
    """Import translation rules from CSV_FILE into the specified project.

    Deletes all existing rules for that project, then inserts rules from CSV.
    CSV columns: project_id, project_name (reference only), rule_name, rule_type, content, remarks.
    """
    with open(csv_file, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    with TM(tm) as tm_db:
        project_id = tm_db.resolve_project_id(project)
        count = tm_db.replace_translation_rules(project_id, rows)

    click.echo(f"Imported {count} translation rules into project {project!r} ({tm}). Replaced existing rules.")


if __name__ == "__main__":
    cli()
