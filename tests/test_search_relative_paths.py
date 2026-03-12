import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestSearchRelativePaths(unittest.TestCase):
    def test_search_resolves_relative_md_path(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "bitrix_wiki_search.py"

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            api_dir = root / "api"
            wiki_dir = root / "wiki"
            api_dir.mkdir(parents=True, exist_ok=True)
            wiki_dir.mkdir(parents=True, exist_ok=True)

            md_path = wiki_dir / "sample.md"
            md_path.write_text("Hello CRM", encoding="utf-8")

            index = {
                "version": "1.0",
                "generated_at": "2026-03-12",
                "entities": [
                    {
                        "id": "sample",
                        "type": "guide",
                        "title": "Sample",
                        "source_url": "https://example.test",
                        "body_md_path": "wiki/sample.md",
                    }
                ],
            }
            (api_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")

            result = subprocess.run(
                [
                    "python3",
                    str(script),
                    "--root",
                    str(root),
                    "--q",
                    "crm",
                    "--content",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("Sample", result.stdout)


if __name__ == "__main__":
    unittest.main()
