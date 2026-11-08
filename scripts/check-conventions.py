"""
Check the conventions a script can judge (docs/conventions.md)

Run by CI next to ruff, and locally the same way:
  python scripts/check-conventions.py

Checks every tracked text file for:
  width      comments, docstrings, dbt {# … #} blocks, and YAML descriptions
             within 80 columns
  banners    section banners exactly 80 columns wide
  ellipsis   "…" in prose (comments, docstrings, markdown), never three periods
  spelling   American spelling (color, canceled)

Exits non-zero with one line per problem. Rules a script can't judge, such as
comment periods, are left to review.
"""

# Import standard libraries
import ast
import re
import subprocess
import sys

WIDTH = 80

# Code files whose comments are checked: extensions, plus files with none
CODE_SUFFIXES = ('.py', '.sql', '.tf', '.yml', '.toml', '.txt', '.sh', '.sqlfluff', '.gitignore', '.dockerignore')
CODE_NAMES = ('Dockerfile',)

# British spellings the repo has used or might slip into; "analyses" (plural of
# analysis) is American too, so only the verb forms are listed
BRITISH = re.compile(
    r'\b(colour|behaviour|favour|honour|neighbour|organis|recognis|realis|summaris|analys(?:e|ed|ing)\b|'
    r'catalogue|licence|cancell(?:ed|ing)|modell(?:ed|ing)|labell(?:ed|ing)|travell(?:ed|ing)|centre|metre|'
    r'grey|whilst|amongst|programme|artefact)\w*',
    re.IGNORECASE,
)

# This file lists the spellings it looks for, so it skips itself
SELF = 'scripts/check-conventions.py'

BANNER = re.compile(r'^\s*(#|--) ?(═{10,}|── .* ─+)$')


def tracked_files():
    """Every file git tracks, except Terraform's lock file (generated)."""
    files = subprocess.run(['git', 'ls-files'], capture_output=True, text=True, check=True).stdout.split()
    return [f for f in files if not f.endswith('.lock.hcl')]


def prose_lines(path, lines):
    """
    Line numbers holding prose: comments, docstrings, dbt {# … #} blocks, and
    YAML descriptions.
    """
    prose = set()
    if path.endswith('.py'):
        for node in ast.walk(ast.parse('\n'.join(lines))):
            body = getattr(node, 'body', None)
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and body \
                    and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                prose.update(range(body[0].lineno, body[0].end_lineno + 1))
    if path.endswith('.sql'):
        inside = False
        for n, line in enumerate(lines, 1):
            inside = inside or '{#' in line
            if inside:
                prose.add(n)
            inside = inside and '#}' not in line
    if path.endswith('.yml'):
        folded_at = None
        for n, line in enumerate(lines, 1):
            indent = len(line) - len(line.lstrip())
            if folded_at is not None and (not line.strip() or indent > folded_at):
                prose.add(n)
                continue
            folded_at = indent if re.search(r'description: [>|]-?\s*$', line) else None
    for n, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith(('#', '--')) and not stripped.startswith('#!'):
            prose.add(n)
    return prose


def check(path):
    """Problems in one file, as 'path:line: message' strings."""
    try:
        with open(path, encoding='utf-8') as handle:
            lines = handle.read().splitlines()
    except (UnicodeDecodeError, IsADirectoryError):
        return []
    is_code = path.endswith(CODE_SUFFIXES) or path.rsplit('/', 1)[-1] in CODE_NAMES
    is_markdown = path.endswith('.md')
    prose = prose_lines(path, lines) if is_code else set()
    problems = []
    for n, line in enumerate(lines, 1):
        where = f'{path}:{n}:'
        if is_code and BANNER.match(line):
            if len(line) != WIDTH:
                problems.append(f'{where} banner is {len(line)} columns wide, not {WIDTH}')
        elif n in prose and len(line) > WIDTH:
            problems.append(f'{where} prose runs to {len(line)} columns (limit {WIDTH})')
        if (n in prose or is_markdown) and '...' in line:
            problems.append(f'{where} "..." in prose; use "…"')
        for match in (BRITISH.finditer(line) if path != SELF else ()):
            problems.append(f'{where} British spelling "{match.group(0)}"')
    return problems


# ── Check ─────────────────────────────────────────────────────────────────────

problems = [problem for path in tracked_files() for problem in check(path)]
for problem in problems:
    print(problem)
if problems:
    print(f'{len(problems)} convention problem(s); see docs/conventions.md', file=sys.stderr)
    sys.exit(1)
print('Conventions: all checks passed')
