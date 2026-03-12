# Bitrix Wiki (AgentSkills)

This repository contains the generated Bitrix/Bitrix24 wiki and JSON API indexes.

## Build

```
python3 /Users/just/projects/AgentSkills/Bitrix/scripts/bitrix_wiki_scrape.py \
  --config /Users/just/projects/AgentSkills/Bitrix/scripts/bitrix_wiki_config.json \
  --out /Users/just/projects/AgentSkills/Bitrix/wiki \
  --cache /Users/just/projects/AgentSkills/Bitrix/wiki/sources/_cache

python3 /Users/just/projects/AgentSkills/Bitrix/scripts/bitrix_wiki_build.py \
  --root /Users/just/projects/AgentSkills/Bitrix/wiki --methods-compact
```

## Contents

- `wiki/` Markdown pages
- `api/` JSON indices
