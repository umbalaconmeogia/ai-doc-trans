from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# CSV columns for translation_rules export/import
TR_RULES_CSV_FIELDS = ["project_id", "project_name", "rule_name", "rule_type", "content", "remarks"]

# CSV columns for glossary export/import
GLOSSARY_CSV_FIELDS = ["project_id", "project_name", "term", "source_lang", "target_lang", "translation", "context", "remarks"]

# Sentinel: target_lang empty or this value = apply to all target languages
TARGET_LANG_ANY = ""

DEFAULT_TM_PATH = "data/ai_doc_trans.db"

_DDL = """
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER NOT NULL,
    name        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS segment_sources (
    id          INTEGER NOT NULL,
    project_id  INTEGER NOT NULL,
    source_hash TEXT    NOT NULL,
    source_text TEXT    NOT NULL,
    source_lang TEXT    NOT NULL,
    structure   TEXT,
    position    TEXT,
    created_at  TEXT    NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (source_hash, project_id)
);

CREATE INDEX IF NOT EXISTS idx_segment_sources_hash_project
    ON segment_sources(source_hash, project_id);

CREATE TABLE IF NOT EXISTS segment_targets (
    source_id   INTEGER NOT NULL,
    target_lang TEXT    NOT NULL,
    target_text TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    PRIMARY KEY (source_id, target_lang),
    FOREIGN KEY (source_id) REFERENCES segment_sources(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS glossary_sources (
    id          INTEGER NOT NULL,
    term        TEXT    NOT NULL,
    source_lang TEXT    NOT NULL,
    project_id  INTEGER NOT NULL DEFAULT 1,
    context     TEXT,
    remarks     TEXT,
    created_at  TEXT    NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (term, source_lang, project_id)
);

CREATE TABLE IF NOT EXISTS glossary_targets (
    source_id   INTEGER NOT NULL,
    target_lang TEXT    NOT NULL,
    translation TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    PRIMARY KEY (source_id, target_lang),
    FOREIGN KEY (source_id) REFERENCES glossary_sources(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS translation_rules (
    id          INTEGER NOT NULL,
    project_id  INTEGER NOT NULL DEFAULT 1,
    rule_name   TEXT,
    rule_type   TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    remarks     TEXT,
    created_at  TEXT    NOT NULL,
    PRIMARY KEY (id)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TM:
    """Translation Memory backed by SQLite."""

    def __init__(self, db_path: str | Path = DEFAULT_TM_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(_DDL)
        # Ensure global project exists
        self._conn.execute(
            "INSERT OR IGNORE INTO projects (id, name, created_at) VALUES (1, 'global', ?)",
            (_now(),),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "TM":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def create_project(self, name: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO projects (name, created_at) VALUES (?, ?)",
            (name, _now()),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def list_projects(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, name, created_at FROM projects ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]

    def resolve_project_id(self, project: str | int) -> int:
        """Accept project id only (int or str digit). Use 'ai-doc-trans project list' to see ids."""
        if isinstance(project, int):
            return project
        s = str(project)
        if s.isdigit():
            return int(s)
        raise ValueError(
            f"Project id expected (integer), got {project!r}. "
            "Use 'ai-doc-trans project list' to see project ids."
        )

    # ------------------------------------------------------------------
    # Segments
    # ------------------------------------------------------------------

    def get_or_create_source(
        self,
        source_hash: str,
        source_text: str,
        source_lang: str,
        structure: str,
        project_id: int,
        position: Optional[str] = None,
    ) -> int:
        row = self._conn.execute(
            "SELECT id FROM segment_sources WHERE source_hash = ? AND project_id = ?",
            (source_hash, project_id),
        ).fetchone()
        if row:
            return row["id"]
        cur = self._conn.execute(
            """INSERT INTO segment_sources
               (source_hash, source_text, source_lang, structure, project_id, position, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (source_hash, source_text, source_lang, structure, project_id, position, _now()),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_target(self, source_id: int, target_lang: str) -> Optional[str]:
        """Look up translation by source_id and target_lang."""
        row = self._conn.execute(
            """SELECT target_text FROM segment_targets
               WHERE source_id = ? AND target_lang = ?""",
            (source_id, target_lang),
        ).fetchone()
        return row["target_text"] if row else None

    def get_source_id_by_hash(
        self, source_hash: str, project_id: int
    ) -> Optional[int]:
        """Look up segment_sources.id by (source_hash, project_id). Returns None if not found."""
        row = self._conn.execute(
            "SELECT id FROM segment_sources WHERE source_hash = ? AND project_id = ?",
            (source_hash, project_id),
        ).fetchone()
        return row["id"] if row is not None else None

    def get_target_by_hash(
        self, source_hash: str, target_lang: str, project_id: int
    ) -> Optional[str]:
        """Look up translation by hash (used in rebuild). Source is project-specific."""
        sid = self.get_source_id_by_hash(source_hash, project_id)
        if sid is None:
            return None
        return self.get_target(sid, target_lang)

    def upsert_target(
        self,
        source_id: int,
        target_lang: str,
        target_text: str,
    ) -> None:
        now = _now()
        self._conn.execute(
            """INSERT INTO segment_targets
               (source_id, target_lang, target_text, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(source_id, target_lang)
               DO UPDATE SET target_text = excluded.target_text,
                             updated_at  = excluded.updated_at""",
            (source_id, target_lang, target_text, now, now),
        )
        self._conn.commit()

    def clear_project_segments(self, project_id: int) -> int:
        """Delete all segment_sources (and cascade to segment_targets) for the project.
        Returns the number of segment_sources deleted.
        """
        cur = self._conn.execute(
            "DELETE FROM segment_sources WHERE project_id = ?", (project_id,)
        )
        self._conn.commit()
        return cur.rowcount

    def list_segment_translations(
        self,
        project_id: int,
        target_lang: str,
        source_lang: str | None = None,
    ) -> list[dict]:
        """List segment translations for export (segment_sources + segment_targets).

        Returns rows with: source, target, source_lang, target_lang, structure, position.
        """
        query = """SELECT ss.source_text AS source, st.target_text AS target,
                          ss.source_lang, st.target_lang, ss.structure, ss.position
                   FROM segment_sources ss
                   JOIN segment_targets st ON st.source_id = ss.id
                   WHERE ss.project_id = ? AND st.target_lang = ?"""
        params: list[object] = [project_id, target_lang]
        if source_lang is not None:
            query += " AND ss.source_lang = ?"
            params.append(source_lang)
        query += " ORDER BY ss.id"
        rows = self._conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def list_all_segments_for_export(
        self,
        project_id: int,
        target_lang: str,
        source_lang: str | None = None,
    ) -> list[dict]:
        """List ALL segment sources for export, with target when available (empty if none).

        Uses LEFT JOIN so segments without translation are included.
        Returns rows with: source, target, source_lang, target_lang, structure, position.
        """
        query = """SELECT ss.source_text AS source,
                          COALESCE(st.target_text, '') AS target,
                          ss.source_lang AS source_lang,
                          ? AS target_lang,
                          ss.structure,
                          ss.position
                   FROM segment_sources ss
                   LEFT JOIN segment_targets st
                     ON st.source_id = ss.id AND st.target_lang = ?
                   WHERE ss.project_id = ?"""
        params: list[object] = [target_lang, target_lang, project_id]
        if source_lang is not None:
            query += " AND ss.source_lang = ?"
            params.append(source_lang)
        query += " ORDER BY ss.id"
        rows = self._conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Glossary
    # ------------------------------------------------------------------

    def get_glossary(
        self, source_lang: str, target_lang: str, project_id: int
    ) -> list[tuple[str, str]]:
        """Return list of (term, translation) for given langs and project (+ global).
        Entries with target_lang empty apply to all target languages.
        Exact target_lang overrides empty; project-specific overrides global.
        """
        rows = self._conn.execute(
            """SELECT gs.term, gt.translation, gt.target_lang AS gt_target_lang
               FROM glossary_sources gs
               JOIN glossary_targets gt ON gt.source_id = gs.id
               WHERE gs.source_lang = ? AND (gt.target_lang = ? OR gt.target_lang = ?)
                 AND gs.project_id IN (1, ?)
               ORDER BY gs.project_id DESC,
                        CASE WHEN gt.target_lang = ? THEN 0 ELSE 1 END""",
            (source_lang, target_lang, TARGET_LANG_ANY, project_id, target_lang),
        ).fetchall()
        seen: dict[str, str] = {}
        for r in rows:
            if r["term"] not in seen:
                seen[r["term"]] = r["translation"]
        return list(seen.items())

    def upsert_glossary_entry(
        self,
        term: str,
        source_lang: str,
        project_id: int,
        target_lang: str,
        translation: str,
        context: Optional[str] = None,
        remarks: Optional[str] = None,
    ) -> None:
        now = _now()
        self._conn.execute(
            """INSERT INTO glossary_sources (term, source_lang, project_id, context, remarks, created_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(term, source_lang, project_id) DO NOTHING""",
            (term, source_lang, project_id, context, remarks, now),
        )
        row = self._conn.execute(
            "SELECT id FROM glossary_sources WHERE term=? AND source_lang=? AND project_id=?",
            (term, source_lang, project_id),
        ).fetchone()
        source_id = row["id"]
        self._conn.execute(
            """INSERT INTO glossary_targets (source_id, target_lang, translation, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(source_id, target_lang)
               DO UPDATE SET translation = excluded.translation,
                             updated_at  = excluded.updated_at""",
            (source_id, target_lang, translation, now, now),
        )
        self._conn.commit()

    def export_glossary(self, source_lang: str, target_lang: str, project_id: int) -> list[dict]:
        rows = self._conn.execute(
            """SELECT gs.term, gs.source_lang, gt.target_lang, gt.translation, gs.context, gs.remarks
               FROM glossary_sources gs
               JOIN glossary_targets gt ON gt.source_id = gs.id
               WHERE gs.source_lang = ? AND gt.target_lang = ? AND gs.project_id = ?
               ORDER BY gs.term""",
            (source_lang, target_lang, project_id),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_all_glossary_entries(
        self,
        project_id: Optional[int] = None,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
    ) -> list[dict]:
        """List all glossary entries for export.

        Returns list of dicts with keys: project_id, project_name, term, source_lang,
        target_lang, translation, context, remarks. Optional filters by project, source_lang, target_lang.
        """
        query = """SELECT gs.project_id, p.name AS project_name, gs.term, gs.source_lang,
                          gt.target_lang, gt.translation, gs.context, gs.remarks
                   FROM glossary_sources gs
                   JOIN glossary_targets gt ON gt.source_id = gs.id
                   JOIN projects p ON p.id = gs.project_id
                   WHERE 1=1"""
        params: list[object] = []
        if project_id is not None:
            query += " AND gs.project_id = ?"
            params.append(project_id)
        if source_lang:
            query += " AND gs.source_lang = ?"
            params.append(source_lang)
        if target_lang:
            query += " AND (gt.target_lang = ? OR gt.target_lang = ?)"
            params.extend([target_lang, TARGET_LANG_ANY])
        query += " ORDER BY gs.project_id, gs.term"
        rows = self._conn.execute(query, params).fetchall()
        result = [dict(r) for r in rows]
        for d in result:
            if d.get("context") is None:
                d["context"] = ""
            if d.get("remarks") is None:
                d["remarks"] = ""
        return result

    def replace_glossary(self, project_id: int, entries: list[dict]) -> int:
        """Delete all glossary entries for project_id, then insert from list.

        project_id from command line; CSV project_id/project_name ignored.
        Each entry dict: term, source_lang, target_lang, translation; context, remarks optional.
        Returns number of entries inserted (rows in glossary_targets).
        """
        self._conn.execute(
            "DELETE FROM glossary_sources WHERE project_id = ?", (project_id,)
        )
        count = 0
        now = _now()
        for e in entries:
            term = (e.get("term") or "").strip()
            source_lang = (e.get("source_lang") or "").strip()
            raw_tgt = (e.get("target_lang") or "").strip()
            target_lang = raw_tgt if raw_tgt else TARGET_LANG_ANY  # empty = apply to all languages
            translation = (e.get("translation") or "").strip()
            context = (e.get("context") or "").strip() or None
            remarks = (e.get("remarks") or "").strip() or None
            if not all([term, source_lang, translation]):
                continue
            row = self._conn.execute(
                "SELECT id FROM glossary_sources WHERE term=? AND source_lang=? AND project_id=?",
                (term, source_lang, project_id),
            ).fetchone()
            if row is None:
                self._conn.execute(
                    """INSERT INTO glossary_sources (term, source_lang, project_id, context, remarks, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (term, source_lang, project_id, context, remarks, now),
                )
                row = self._conn.execute(
                    "SELECT id FROM glossary_sources WHERE term=? AND source_lang=? AND project_id=?",
                    (term, source_lang, project_id),
                ).fetchone()
            assert row is not None
            source_id = row["id"]
            self._conn.execute(
                """INSERT INTO glossary_targets (source_id, target_lang, translation, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(source_id, target_lang)
                   DO UPDATE SET translation = excluded.translation, updated_at = excluded.updated_at""",
                (source_id, target_lang, translation, now, now),
            )
            count += 1
        self._conn.commit()
        return count

    # ------------------------------------------------------------------
    # Translation rules
    # ------------------------------------------------------------------

    def get_translation_rules(self, project_id: int) -> list[tuple[str, str]]:
        """Return list of (rule_type, content) for project + global."""
        rows = self._conn.execute(
            """SELECT rule_type, content FROM translation_rules
               WHERE project_id IN (1, ?)
               ORDER BY project_id DESC""",
            (project_id,),
        ).fetchall()
        return [(r["rule_type"], r["content"]) for r in rows]

    def add_translation_rule(
        self,
        project_id: int,
        rule_type: str,
        content: str,
        rule_name: Optional[str] = None,
        remarks: Optional[str] = None,
    ) -> int:
        cur = self._conn.execute(
            """INSERT INTO translation_rules (project_id, rule_type, content, rule_name, remarks, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (project_id, rule_type, content, rule_name or None, remarks or None, _now()),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def list_all_translation_rules(
        self, project_id: Optional[int] = None
    ) -> list[dict]:
        """List all translation rules, optionally filtered by project_id.

        Returns list of dicts with keys: project_id, project_name, rule_name, rule_type, content, remarks.
        """
        if project_id is not None:
            rows = self._conn.execute(
                """SELECT tr.project_id, p.name AS project_name, tr.rule_name, tr.rule_type, tr.content, tr.remarks
                   FROM translation_rules tr
                   JOIN projects p ON p.id = tr.project_id
                   WHERE tr.project_id = ?
                   ORDER BY tr.project_id, tr.id""",
                (project_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT tr.project_id, p.name AS project_name, tr.rule_name, tr.rule_type, tr.content, tr.remarks
                   FROM translation_rules tr
                   JOIN projects p ON p.id = tr.project_id
                   ORDER BY tr.project_id, tr.id"""
            ).fetchall()
        result = [dict(r) for r in rows]
        for d in result:
            if d.get("rule_name") is None:
                d["rule_name"] = ""
            if d.get("remarks") is None:
                d["remarks"] = ""
        return result

    def replace_translation_rules(
        self, project_id: int, rules: list[dict]
    ) -> int:
        """Delete all translation rules for project_id, then insert rules from list.

        project_id comes from command line; CSV project_id/project_name are ignored.
        Each rule dict must have: rule_type, content. rule_name, remarks optional.
        Returns number of rules inserted.
        """
        self._conn.execute(
            "DELETE FROM translation_rules WHERE project_id = ?", (project_id,)
        )
        count = 0
        now = _now()
        for r in rules:
            rule_type = (r.get("rule_type") or "").strip()
            content = (r.get("content") or "").strip()
            if not rule_type or not content:
                continue
            rule_name = (r.get("rule_name") or "").strip() or None
            remarks = (r.get("remarks") or "").strip() or None
            self._conn.execute(
                """INSERT INTO translation_rules (project_id, rule_type, content, rule_name, remarks, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (project_id, rule_type, content, rule_name, remarks, now),
            )
            count += 1
        self._conn.commit()
        return count
