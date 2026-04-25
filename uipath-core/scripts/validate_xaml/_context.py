"""File context and validation result — shared across all modules."""

import os
import xml.etree.ElementTree as ET

from ._constants import _RE_COMMENT_OUT_BLOCK


class ValidationResult:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []

    def error(self, msg: str):
        self.errors.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)

    def ok(self, msg: str):
        self.info.append(msg)

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def summary(self, errors_only: bool = False) -> str:
        fname = os.path.basename(self.filepath)
        status = "PASS" if self.passed else "FAIL"
        lines = [f"\n{'='*60}", f"{status}  {fname}", f"{'='*60}"]
        for e in self.errors:
            lines.append(f"  [ERROR] {e}")
        for w in self.warnings:
            lines.append(f"  [WARN]  {w}")
        if not errors_only:
            for i in self.info:
                lines.append(f"  [OK] {i}")
        return "\n".join(lines)


class FileContext:
    """Holds file content read once and shared across all validators/lints."""
    __slots__ = ('filepath', 'content', 'tree', 'lines', 'active_content',
                 'target_version_band')

    def __init__(self, filepath: str, content: str | None = None,
                 tree: ET.Element | None = None,
                 target_version_band: str | None = None):
        self.filepath = filepath
        if content is None:
            try:
                with open(filepath, "r", encoding="utf-8-sig") as f:
                    self.content = f.read()
            except Exception:
                self.content = ""
        else:
            self.content = content
        self.tree = tree
        self.lines = self.content.splitlines() if self.content else []
        # active_content strips CommentOut blocks so lint rules don't
        # false-positive on disabled/commented-out activities.
        self.active_content = _RE_COMMENT_OUT_BLOCK.sub('', self.content) if self.content else ""
        self.target_version_band = target_version_band
