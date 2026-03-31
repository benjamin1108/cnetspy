#!/usr/bin/env python3

import hashlib
import re
import sqlite3
import sys
from collections import defaultdict


def normalize_identifier_text(text: str) -> str:
    text = text or ""
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 \2", str(text))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def compute_source_identifier(row: sqlite3.Row) -> str:
    vendor = row["vendor"]
    content = normalize_identifier_text(row["content"] or row["description"] or "")

    if vendor == "gcp":
        parts = [
            row["source_url"] or "",
            row["publish_date"] or "",
            row["product_name"] or "",
            row["update_type"] or "",
            content,
        ]
    elif vendor == "volcengine":
        parts = [
            row["publish_date"] or "",
            row["product_name"] or "",
            (row["title"] or "").strip(),
            content,
        ]
    else:
        return row["source_identifier"] or ""

    return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()[:12]


def score(row: sqlite3.Row) -> tuple:
    return (
        1 if (row["analysis_filepath"] or "").strip() else 0,
        len(row["content_summary"] or ""),
        len(row["content_translated"] or ""),
        row["crawl_time"] or "",
        row["update_id"],
    )


def main() -> int:
    db_path = sys.argv[1]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT
            update_id, vendor, source_channel, source_url, source_identifier,
            title, description, content, publish_date, product_name, update_type,
            content_summary, content_translated, analysis_filepath, crawl_time
        FROM updates
        WHERE vendor IN ('gcp', 'volcengine') AND source_channel = 'whatsnew'
        """
    ).fetchall()

    groups = defaultdict(list)
    for row in rows:
        groups[(row["vendor"], compute_source_identifier(row))].append(row)

    to_delete = []
    to_update = []

    for (_, new_sid), items in groups.items():
        items = sorted(items, key=score, reverse=True)
        keeper = items[0]
        if (keeper["source_identifier"] or "") != new_sid:
            to_update.append((new_sid, keeper["update_id"]))
        for row in items[1:]:
            to_delete.append((row["update_id"],))

    cur.execute("BEGIN")
    if to_delete:
        cur.executemany("DELETE FROM updates WHERE update_id = ?", to_delete)
    if to_update:
        cur.executemany(
            "UPDATE updates SET source_identifier = ?, updated_at = CURRENT_TIMESTAMP WHERE update_id = ?",
            to_update,
        )
    conn.commit()

    print(
        {
            "rows_scanned": len(rows),
            "canonical_groups": len(groups),
            "deleted": len(to_delete),
            "updated": len(to_update),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
