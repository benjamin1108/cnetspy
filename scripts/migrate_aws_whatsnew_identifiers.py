#!/usr/bin/env python3

import hashlib
import json
import sqlite3
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

import requests


API_URL = "https://aws.amazon.com/api/dirs/items/search"
API_BASE = "https://aws.amazon.com/api/dirs/items/search"
TAGS_FILTER = (
    "whats-new-v2#general-products#amazon-vpc|"
    "whats-new-v2#general-products#aws-direct-connect|"
    "whats-new-v2#general-products#amazon-route-53|"
    "whats-new-v2#general-products#elastic-load-balancing|"
    "whats-new-v2#general-products#amazon-cloudfront|"
    "whats-new-v2#general-products#amazon-api-gateway|"
    "whats-new-v2#marketing-marchitecture#networking-and-content-delivery|"
    "whats-new-v2#general-products#aws-global-accelerator|"
    "whats-new-v2#general-products#aws-transit-gateway|"
    "whats-new-v2#general-products#aws-vpn|"
    "whats-new-v2#general-products#aws-site-to-site|"
    "whats-new-v2#general-products#aws-client-vpn|"
    "whats-new-v2#general-products#aws-app-mesh|"
    "whats-new-v2#general-products#aws-privatelink|"
    "whats-new-v2#general-products#aws-network-firewall|"
    "whats-new-v2#general-products#amazon-vpc-lattice"
)


def normalize_source_url(url: str) -> str:
    if not url:
        return ""

    parsed = urlsplit(url)
    normalized_path = parsed.path.rstrip("/")

    while normalized_path.endswith("_msm_moved"):
        normalized_path = normalized_path[:-len("_msm_moved")]

    if normalized_path != "/":
        normalized_path += "/"

    return urlunsplit((parsed.scheme, parsed.netloc, normalized_path, "", ""))


def parse_api_date(timestamp: str) -> str:
    return (timestamp or "")[:10]


def extract_product_from_tags(tags: List[dict]) -> str:
    products = []
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        if tag.get("tagNamespaceId") == "whats-new-v2#general-products":
            product = tag.get("name", "")
            if product:
                products.append(product.replace("-", " ").title())

    if products:
        return ", ".join(products[:3])
    return "AWS Networking & Content Delivery"


def compute_identifier(item_id: str) -> str:
    return hashlib.md5(f"{API_BASE}|{item_id}".encode("utf-8")).hexdigest()[:12]


def score(row: sqlite3.Row) -> Tuple:
    return (
        1 if (row["analysis_filepath"] or "").strip() else 0,
        len(row["content_summary"] or ""),
        len(row["content_translated"] or ""),
        row["crawl_time"] or "",
        row["update_id"],
    )


def fetch_api_items() -> List[dict]:
    params = {
        "item.directoryId": "whats-new-v2",
        "sort_by": "item.additionalFields.postDateTime",
        "sort_order": "desc",
        "size": "100",
        "item.locale": "en_US",
        "tags.id": TAGS_FILTER,
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    items = []
    page = 0

    while True:
        params["page"] = str(page)
        response = requests.get(API_URL, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        payload = response.json()
        page_items = payload.get("items") or []
        if not page_items:
            break

        items.extend(page_items)
        if len(page_items) < int(params["size"]):
            break
        page += 1

    return items


def build_api_lookup(items: List[dict]) -> Tuple[Dict[str, dict], Dict[Tuple[str, str, str], List[dict]]]:
    by_url: Dict[str, dict] = {}
    by_business_key: Dict[Tuple[str, str, str], List[dict]] = defaultdict(list)

    for item in items:
        item_data = item.get("item", {})
        fields = item_data.get("additionalFields", {})
        url_path = fields.get("headlineUrl", "") or ""
        if url_path and not url_path.startswith("http"):
            if not url_path.startswith("/"):
                url_path = "/" + url_path
            full_url = f"https://aws.amazon.com{url_path}"
        else:
            full_url = url_path

        item_id = (item_data.get("id") or item_data.get("name") or "").strip()
        if not item_id:
            continue

        payload = {
            "item_id": item_id,
            "source_url": normalize_source_url(full_url),
            "title": (fields.get("headline", "") or "").strip(),
            "publish_date": parse_api_date(fields.get("postDateTime", "")),
            "product_name": extract_product_from_tags(item.get("tags", [])),
        }
        if payload["source_url"]:
            by_url[payload["source_url"]] = payload
        if payload["title"] and payload["publish_date"] and payload["product_name"]:
            by_business_key[
                (payload["title"], payload["publish_date"], payload["product_name"])
            ].append(payload)

    return by_url, by_business_key


def pick_match(
    row: sqlite3.Row,
    by_url: Dict[str, dict],
    by_business_key: Dict[Tuple[str, str, str], List[dict]],
) -> Optional[dict]:
    normalized_url = normalize_source_url(row["source_url"] or "")
    if normalized_url in by_url:
        return by_url[normalized_url]

    key = ((row["title"] or "").strip(), row["publish_date"] or "", row["product_name"] or "")
    candidates = by_business_key.get(key, [])
    if len(candidates) == 1:
        return candidates[0]

    for candidate in candidates:
        if candidate["source_url"] == normalized_url:
            return candidate

    return None


def main() -> int:
    db_path = sys.argv[1]
    api_items = fetch_api_items()
    by_url, by_business_key = build_api_lookup(api_items)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT
            update_id, source_url, source_identifier, title, publish_date, product_name,
            content_summary, content_translated, analysis_filepath, crawl_time
        FROM updates
        WHERE vendor = 'aws' AND source_channel = 'whatsnew'
        """
    ).fetchall()

    groups = defaultdict(list)
    unmatched = []

    for row in rows:
        match = pick_match(row, by_url, by_business_key)
        if not match:
            unmatched.append(row["update_id"])
            continue
        groups[compute_identifier(match["item_id"])].append((row, match))

    to_update = []
    to_delete = []

    for new_sid, items in groups.items():
        ranked_rows = sorted((row for row, _ in items), key=score, reverse=True)
        keeper = ranked_rows[0]
        keeper_match = next(match for row, match in items if row["update_id"] == keeper["update_id"])

        if (
            (keeper["source_identifier"] or "") != new_sid
            or normalize_source_url(keeper["source_url"] or "") != keeper_match["source_url"]
        ):
            to_update.append((keeper_match["source_url"], new_sid, keeper["update_id"]))

        for row, _ in items:
            if row["update_id"] != keeper["update_id"]:
                to_delete.append((row["update_id"],))

    cur.execute("BEGIN")
    if to_delete:
        cur.executemany("DELETE FROM quality_issues WHERE update_id = ?", to_delete)
        cur.executemany("DELETE FROM analysis_tasks WHERE update_id = ?", to_delete)
        cur.executemany("DELETE FROM updates WHERE update_id = ?", to_delete)
    if to_update:
        cur.executemany(
            """
            UPDATE updates
            SET source_url = ?, source_identifier = ?, updated_at = CURRENT_TIMESTAMP
            WHERE update_id = ?
            """,
            to_update,
        )
    conn.commit()

    print(
        json.dumps(
            {
                "rows_scanned": len(rows),
                "api_items": len(api_items),
                "matched_groups": len(groups),
                "unmatched": len(unmatched),
                "updated": len(to_update),
                "deleted": len(to_delete),
            },
            ensure_ascii=False,
        )
    )
    if unmatched:
        print("unmatched_update_ids=" + ",".join(unmatched[:20]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
