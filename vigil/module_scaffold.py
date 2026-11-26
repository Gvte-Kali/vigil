"""Create a local module draft without registering it for execution."""
import re

import yaml

from .core import Manifest

SLUG = re.compile(r"[a-z][a-z0-9_-]{0,47}")


def create_module_draft(state, name):
    if not SLUG.fullmatch(name):
        raise ValueError("use 1–48 lowercase letters, digits, hyphens or underscores")
    root = state.parent.resolve() / "module-drafts"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink() or root.resolve().is_relative_to("/investigation"):
        raise ValueError("invalid drafts directory")
    target = root / name
    manifest = Manifest(
        schema_version=1, api_version=1, id=f"local.{name}", version="0.1.0",
        name=name, category="analysis", entrypoint="module.py",
        dependencies=[], capabilities=[],
    )
    target.mkdir(mode=0o700)
    files = {
        "module.yaml": yaml.safe_dump(manifest.model_dump(), sort_keys=False),
        "module.py": '"""Local Vigil module draft."""\n',
        "README.md": f"# {name}\n\nDescribe inputs, outputs, permissions and limitations.\n",
        "CHANGELOG.md": "# Changelog\n\n## 0.1.0\n\nInitial draft.\n",
    }
    for filename, contents in files.items():
        (target / filename).write_text(contents, encoding="utf-8")
    return target
