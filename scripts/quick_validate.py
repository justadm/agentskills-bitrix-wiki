#!/usr/bin/env python3
import argparse
import json
import os
import sys


REQUIRED_FIELDS = [
    "id",
    "type",
    "title",
    "source_url",
    "source_type",
    "tags",
    "body_md_path",
]


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description="Quick sanity check for wiki index.")
    parser.add_argument("--root", required=True, help="Wiki root folder")
    parser.add_argument("--limit", type=int, default=200, help="Max entities to check")
    args = parser.parse_args()

    index_path = os.path.join(args.root, "api", "index.json")
    if not os.path.isfile(index_path):
        print("index not found")
        return 2

    data = load_json(index_path)
    entities = data.get("entities", [])
    errors = 0
    checked = 0

    for i, e in enumerate(entities):
        for f in REQUIRED_FIELDS:
            if f not in e:
                errors += 1
                print(f"[{i}] missing field: {f}")
        if not isinstance(e.get("tags", []), list):
            errors += 1
            print(f"[{i}] tags must be list")

        md_path = e.get("body_md_path", "")
        if md_path:
            if os.path.isabs(md_path):
                errors += 1
                print(f"[{i}] body_md_path must be relative: {md_path}")
            else:
                full = os.path.join(args.root, md_path)
                if not os.path.isfile(full):
                    errors += 1
                    print(f"[{i}] body_md_path not found: {md_path}")

        checked += 1
        if checked >= args.limit:
            break

    if errors:
        print(f"quick validation failed: {errors} errors")
        return 1

    print(f"quick validation ok ({checked} checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
