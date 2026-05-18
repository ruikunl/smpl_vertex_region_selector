import re
import unittest
from pathlib import Path
from urllib.parse import unquote


LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)


def _anchor_for_heading(heading: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", heading)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.strip().lower()
    text = re.sub(r"[^\w\s\u4e00-\u9fff-]", "", text)
    return re.sub(r"\s+", "-", text).strip("-")


def _heading_anchors(markdown_path: Path) -> set[str]:
    text = markdown_path.read_text(encoding="utf-8")
    return {_anchor_for_heading(match.group(1)) for match in HEADING_RE.finditer(text)}


class DocsLinksTest(unittest.TestCase):
    def test_readme_and_docs_local_markdown_links_resolve(self):
        root = Path(__file__).resolve().parents[1]
        markdown_files = [root / "README.md", *sorted((root / "docs").glob("*.md"))]
        anchor_cache: dict[Path, set[str]] = {}

        for markdown_path in markdown_files:
            text = markdown_path.read_text(encoding="utf-8")
            for raw_target in LINK_RE.findall(text):
                target = raw_target.strip()
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                if target.startswith("<") and target.endswith(">"):
                    target = target[1:-1]
                path_part, separator, anchor = target.partition("#")
                linked_path = markdown_path if not path_part else (markdown_path.parent / unquote(path_part)).resolve()
                self.assertTrue(linked_path.exists(), f"{markdown_path} links to missing path {target!r}")

                if separator and anchor:
                    anchors = anchor_cache.setdefault(linked_path, _heading_anchors(linked_path))
                    self.assertIn(anchor.lower(), anchors, f"{markdown_path} links to missing anchor {target!r}")


if __name__ == "__main__":
    unittest.main()
