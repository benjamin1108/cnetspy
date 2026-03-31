#!/usr/bin/env python3
"""
审计 gcp/whatsnew 的高置信近重复，不修改数据库。

分组键：
- vendor='gcp'
- source_channel='whatsnew'
- source_url
- publish_date
- product_name

在组内对正文做规范化，并计算两两相似度。
仅输出高度相似的候选，供人工确认。
"""

from __future__ import annotations

import re
import sqlite3
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable


def normalize_text(text: str) -> str:
    if not text:
        return ""
    normalized = str(text)
    normalized = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 \2", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


@dataclass
class Row:
    update_id: str
    source_identifier: str
    source_url: str
    publish_date: str
    product_name: str
    title: str
    content: str
    normalized: str


def fetch_rows(conn: sqlite3.Connection) -> list[Row]:
    rows = conn.execute(
        """
        SELECT
            update_id,
            COALESCE(source_identifier, ''),
            COALESCE(source_url, ''),
            COALESCE(publish_date, ''),
            COALESCE(product_name, ''),
            COALESCE(title, ''),
            COALESCE(content, description, '')
        FROM updates
        WHERE vendor = 'gcp' AND source_channel = 'whatsnew'
        ORDER BY source_url, publish_date, product_name, source_identifier
        """
    ).fetchall()

    result: list[Row] = []
    for row in rows:
        content = row[6] or ""
        result.append(
            Row(
                update_id=row[0],
                source_identifier=row[1],
                source_url=row[2],
                publish_date=row[3],
                product_name=row[4],
                title=row[5],
                content=content,
                normalized=normalize_text(content),
            )
        )
    return result


def group_rows(rows: Iterable[Row]) -> dict[tuple[str, str, str], list[Row]]:
    groups: dict[tuple[str, str, str], list[Row]] = {}
    for row in rows:
        key = (row.source_url, row.publish_date, row.product_name)
        groups.setdefault(key, []).append(row)
    return {k: v for k, v in groups.items() if len(v) > 1}


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def main(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = fetch_rows(conn)
    groups = group_rows(rows)

    highly_similar = []
    exact_matches = []

    for key, grouped in groups.items():
        for i in range(len(grouped)):
            for j in range(i + 1, len(grouped)):
                left = grouped[i]
                right = grouped[j]
                if not left.normalized or not right.normalized:
                    continue
                if left.normalized == right.normalized:
                    exact_matches.append((key, left, right, 1.0))
                    continue
                ratio = similarity(left.normalized, right.normalized)
                if ratio >= 0.97:
                    highly_similar.append((key, left, right, ratio))

    highly_similar.sort(key=lambda item: item[3], reverse=True)

    print(
        {
            "total_rows": len(rows),
            "duplicate_groups_by_url_date_product": len(groups),
            "exact_normalized_pairs": len(exact_matches),
            "very_high_similarity_pairs_ge_0_97": len(highly_similar),
        }
    )

    print("\nTop exact normalized matches:")
    for key, left, right, ratio in exact_matches[:20]:
        print(
            "\t".join(
                [
                    key[1],
                    key[2],
                    left.title[:80],
                    left.update_id,
                    right.update_id,
                    f"{ratio:.3f}",
                ]
            )
        )

    print("\nTop near matches:")
    for key, left, right, ratio in highly_similar[:20]:
        print(
            "\t".join(
                [
                    key[1],
                    key[2],
                    left.title[:80],
                    left.update_id,
                    right.update_id,
                    f"{ratio:.3f}",
                ]
            )
        )

    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: audit_gcp_near_duplicates.py <sqlite_db_path>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
