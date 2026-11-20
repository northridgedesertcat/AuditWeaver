"""Check local Markdown destinations without fetching external resources."""

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
LOCAL_ONLY = {"document", "devtools"}
REFERENCE = re.compile(r'^\s{0,3}\[([^\]]+)\]:\s*(<[^>]+>|\S+)')
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


@dataclass(frozen=True)
class Issue:
    path: Path
    line: int
    target: str
    reason: str


def prose_lines(text):
    """Ignore fenced and inline code when inspecting documentation links."""
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            run = marker.group(1)
            if fence is None:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence):
                fence = None
            continue
        if fence is None:
            yield number, re.sub(r"(`+).*?\1", "", line)


def inline_destinations(line):
    """Read inline link/image destinations, including balanced parentheses."""
    for match in re.finditer(r"(?<!\\)\]\(", line):
        start = match.end()
        while start < len(line) and line[start].isspace():
            start += 1
        if start < len(line) and line[start] == "<":
            end = line.find(">", start + 1)
            if end != -1:
                yield line[start + 1:end]
            continue
        end, depth = start, 0
        while end < len(line):
            char = line[end]
            if char == "\\":
                end += 2
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            elif char.isspace() and depth == 0:
                break
            end += 1
        yield re.sub(r"\\([() ])", r"\1", line[start:end])


def markdown_destinations(text):
    lines = list(prose_lines(text))
    definitions = {}
    for number, line in lines:
        definition = REFERENCE.match(line)
        if definition:
            key = " ".join(definition.group(1).lower().split())
            target = definition.group(2).strip("<>")
            definitions[key] = target
            yield number, target
    for number, line in lines:
        if REFERENCE.match(line):
            continue
        for target in inline_destinations(line):
            yield number, target
        for match in re.finditer(r"\[([^\]]+)\]\[([^\]]*)\]", line):
            key = " ".join((match.group(2) or match.group(1)).lower().split())
            if key not in definitions:
                yield number, f"missing-reference:{key}"


def target_issue(source, target, root):
    if target.startswith("missing-reference:"):
        return "undefined Markdown reference"
    if not target or target.startswith(("#", "//")):
        return None
    if target.lower().startswith("file:") or re.match(r"^[A-Za-z]:[\\/]", target):
        return "machine-specific path; use a repository-relative link"
    if "\\" in target:
        return "backslash in destination; use forward slashes"
    if SCHEME.match(target):
        return None
    parsed = urlsplit(target)
    if parsed.path.startswith("/"):
        return "absolute path; use a repository-relative link"
    destination = (source.parent / unquote(parsed.path)).resolve()
    try:
        relative = destination.relative_to(root.resolve())
    except ValueError:
        return "destination leaves the repository"
    if relative.parts and relative.parts[0] in LOCAL_ONLY:
        return "shared documentation links into a local-only directory"
    if not destination.exists():
        return "destination does not exist"
    return None


def check_file(source, root=ROOT):
    issues = []
    for line, target in markdown_destinations(source.read_text(encoding="utf-8-sig")):
        reason = target_issue(source, target, root)
        if reason:
            issues.append(Issue(source, line, target, reason))
    return issues


def ignored_link_issues(paths, root=ROOT):
    links = {}
    for source in paths:
        for line, target in markdown_destinations(source.read_text(encoding="utf-8-sig")):
            if not target or target.startswith(("#", "//")) or SCHEME.match(target):
                continue
            if target_issue(source, target, root):
                continue
            destination = (source.parent / unquote(urlsplit(target).path)).resolve()
            relative = destination.relative_to(root.resolve()).as_posix()
            links.setdefault(relative, []).append((source, line, target))
    if not links:
        return []
    result = subprocess.run(
        ["git", "check-ignore", "-z", "--stdin"], cwd=root,
        input="\0".join(links).encode("utf-8") + b"\0", capture_output=True,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
    return [Issue(source, line, target, "destination is ignored by Git")
            for relative in result.stdout.decode("utf-8").split("\0") if relative
            for source, line, target in links[relative]]


def shared_markdown(root=ROOT):
    paths = set(root.glob("*.md"))
    paths.update((root / "docs").rglob("*.md"))
    # Include module-local tracked references, but not runtime knowledge/prompt inputs.
    tracked = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files", "-z", "*.md"],
        cwd=root, check=True, capture_output=True,
    ).stdout.decode("utf-8").split("\0")
    paths.update(root / name for name in tracked
                 if name and Path(name).name == "README.md" and not name.startswith("resources/"))
    return sorted(path for path in paths if path.is_file())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Optional Markdown files, relative to the repository")
    args = parser.parse_args(argv)
    paths = [ROOT / name for name in args.paths] if args.paths else shared_markdown()
    issues = [issue for path in paths for issue in check_file(path)]
    issues.extend(ignored_link_issues(paths))
    for issue in issues:
        print(f"{issue.path.relative_to(ROOT)}:{issue.line}: {issue.reason}: {issue.target}")
    print(f"Checked {len(paths)} Markdown files: {len(issues)} issue(s). External URLs and heading fragments were not checked.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
