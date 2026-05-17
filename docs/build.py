# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "markdown>=3.5",
# ]
# ///
# version: 0.2
# canonical: https://gist.github.com/brandonleon/d408efca8a6652edfbc449286f694978

"""Build docs/index.html from docs/index.md using docs/_template.html."""

import pathlib
import re
import sys
import urllib.request

import markdown

HERE = pathlib.Path(__file__).parent

_VERSION = "0.2"
_RAW_BASE = "https://gist.githubusercontent.com/brandonleon/d408efca8a6652edfbc449286f694978/raw"
_SCRIPT_RAW_URL   = f"{_RAW_BASE}/build.py"
_TEMPLATE_RAW_URL = f"{_RAW_BASE}/_template.html"


def check_for_updates() -> None:
    try:
        with urllib.request.urlopen(_SCRIPT_RAW_URL, timeout=5) as resp:
            remote = resp.read().decode()
        m = re.search(r"^# version:\s*(.+)$", remote, re.MULTILINE)
        if m:
            remote_version = m.group(1).strip()
            if remote_version != _VERSION:
                script_path = pathlib.Path(__file__).resolve()
                print(
                    f"notice: a newer version of build.py is available "
                    f"({_VERSION} → {remote_version}).\n"
                    f"  To update: curl -o {script_path} {_SCRIPT_RAW_URL}"
                )
    except Exception:
        pass  # network unavailable or gist unreachable — skip silently


def bootstrap_template() -> None:
    """Download _template.html from the gist if it doesn't exist locally."""
    template_path = HERE / "_template.html"
    if template_path.exists():
        return
    print("_template.html not found — downloading from gist...")
    try:
        with urllib.request.urlopen(_TEMPLATE_RAW_URL, timeout=10) as resp:
            template_path.write_bytes(resp.read())
        print(f"  Saved {template_path.relative_to(HERE.parent)}")
    except Exception as exc:
        print(f"error: could not download _template.html: {exc}", file=sys.stderr)
        sys.exit(1)


def read_project_name() -> str:
    """Read [project] name from ../pyproject.toml, fall back to 'Docs'."""
    toml_path = HERE.parent / "pyproject.toml"
    if not toml_path.exists():
        return "Docs"
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        # Python < 3.11: parse just the name field with regex
        m = re.search(r'^name\s*=\s*["\'](.+?)["\']', toml_path.read_text(encoding="utf-8"), re.MULTILINE)
        return m.group(1) if m else "Docs"
    with open(toml_path, "rb") as fh:
        return tomllib.load(fh).get("project", {}).get("name", "Docs")


def extract_title(md_text: str) -> str:
    m = re.search(r"^#\s+(.+)$", md_text, re.MULTILINE)
    return m.group(1).strip() if m else "Docs"


def build() -> None:
    check_for_updates()
    bootstrap_template()

    md_path = HERE / "index.md"
    template_path = HERE / "_template.html"
    out_path = HERE / "index.html"

    if not md_path.exists():
        print(f"error: {md_path} not found", file=sys.stderr)
        sys.exit(1)

    project = read_project_name()
    md_text = md_path.read_text(encoding="utf-8")
    title   = extract_title(md_text)

    md = markdown.Markdown(
        extensions=["toc", "fenced_code", "tables"],
        extension_configs={
            "toc": {
                "title": "Contents",
                "toc_depth": "2-3",
            }
        },
    )
    content_html = md.convert(md_text)
    toc_html = md.toc

    template = template_path.read_text(encoding="utf-8")
    output = (
        template
        .replace("{{ title }}", title)
        .replace("{{ project }}", project)
        .replace("{{ toc }}", toc_html)
        .replace("{{ content }}", content_html)
    )

    out_path.write_text(output, encoding="utf-8")
    print(f"Built {out_path.relative_to(HERE.parent)}")


if __name__ == "__main__":
    build()
