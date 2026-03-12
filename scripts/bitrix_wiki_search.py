#!/usr/bin/env python3
import argparse
import json
import os
import re


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def main() -> int:
    parser = argparse.ArgumentParser(description="Search Bitrix wiki index and content.")
    parser.add_argument("--root", required=True, help="Wiki root folder")
    parser.add_argument("--q", required=True, help="Query string (regex allowed)")
    parser.add_argument("--content", action="store_true", help="Search inside page content")
    parser.add_argument("--limit", type=int, default=20, help="Max results")
    parser.add_argument("--methods-only", action="store_true", help="Search only methods.json")
    args = parser.parse_args()

    index_path = os.path.join(args.root, "api", "methods.json" if args.methods_only else "index.json")
    data = load_json(index_path)
    pattern = re.compile(args.q, re.IGNORECASE)

    results = []
    for entity in data.get("entities", []):
        hay = f"{entity.get('id','')} {entity.get('title','')} {entity.get('source_url','')}"
        if pattern.search(hay):
            results.append(entity)
            continue
        if args.content:
            md_path = entity.get("body_md_path", "")
            if md_path and not os.path.isabs(md_path):
                md_path = os.path.join(args.root, md_path)
            if md_path and os.path.isfile(md_path):
                content = read_text(md_path)
                if pattern.search(content):
                    results.append(entity)

        if len(results) >= args.limit:
            break

    for entity in results:
        print(f"{entity.get('type')} :: {entity.get('title')} :: {entity.get('source_url')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
