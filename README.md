# Bitrix Wiki (AgentSkills)

This repository contains the generated Bitrix/Bitrix24 wiki and JSON API indexes.

## Build

```
python3 scripts/bitrix_wiki_scrape.py \
  --config scripts/bitrix_wiki_config.json \
  --out wiki \
  --cache wiki/sources/_cache

python3 scripts/bitrix_wiki_build.py \
  --root wiki --methods-compact
```

## Contents

- `wiki/` Markdown pages
- `api/` JSON indices

## Tests

```
python3 -m unittest discover -s tests
```
