import re
from pathlib import Path

import yaml


class ItemLoader:
    """Loads a single announcement item: YAML frontmatter + Markdown body.

    Note (security): this only parses text into fields. It never
    interprets or acts on anything found inside item_id/date/source/body —
    all of it is treated as untrusted data by every downstream node.
    """

    FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)

    def __init__(self, path):
        self.path = Path(path)
        self.filename = self.path.name

        meta, title, body = self._parse()
        self.item_id = meta.get("item_id")
        self.date = meta.get("date")
        self.source = meta.get("source")
        self.title = title
        self.body = body.strip()
        # text used for embedding: title + body, frontmatter excluded
        self.text = f"{title}\n\n{self.body}".strip() if title else self.body

    def _parse(self):
        raw = self.path.read_text(encoding="utf8")
        match = self.FRONTMATTER_RE.match(raw)

        if not match:
            raise ValueError(f"Missing/invalid frontmatter in {self.path}")

        fm_block, rest = match.groups()
        meta = yaml.safe_load(fm_block) or {}

        title_match = re.search(r"^#\s+(.+)$", rest, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else ""
        body = re.sub(r"^#\s+.+$", "", rest, count=1, flags=re.MULTILINE)

        return meta, title, body


class KnowledgeBaseLoader:
    """Loads every announcement item from the inbox / knowledge_base folder."""

    def __init__(self, kb_dir):
        self.kb_dir = Path(kb_dir)

    def load_all(self):
        return [ItemLoader(path) for path in sorted(self.kb_dir.glob("*.md"))]
