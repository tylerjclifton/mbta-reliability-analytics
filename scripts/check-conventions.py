"""
Conventions check — the rules in docs/conventions.md a script can judge

Run by CI after ruff, and locally the same way:
  python scripts/check-conventions.py

Layout:
  width      prose within 80 columns; tables and code samples within 120
  banners    section banners exactly 80 columns wide
Wording:
  ellipsis   "…" in prose, never three periods
  spelling   American spelling (color, canceled)
Punctuation, by what each piece of prose is for:
  titles     a file's first line, and the text inside a ═ box: one line, no
             period; a file's title block ends with a blank line
  labels     import-group labels, a list file's group headings, and
             end-of-line comments: no period
  prose      every other paragraph ends with a period (or ":", "?", "…", or
             a URL)
  lists      the items of one list end the same way
  YAML       descriptions end with a period

Prose means comments, docstrings, dbt {# … #} blocks, and YAML descriptions. A
line indented past its block's prose, or with aligned columns (a gap of two or
more spaces), is a table or code line. Exits non-zero with one line per
problem.
"""

# Import standard libraries
import ast
import io
import re
import subprocess
import sys
import tokenize

WIDTH = 80

# A table or code sample can't be rewrapped without losing its shape, so it may
# run to the code limit.
CODE_WIDTH = 120

# Code files whose prose is checked: extensions, plus files with none.
CODE_SUFFIXES = ('.py', '.sql', '.tf', '.yml', '.toml', '.txt', '.sh', '.sqlfluff', '.gitignore', '.dockerignore')
CODE_NAMES = ('Dockerfile',)

# Files that are lists of entries, whose one-line comments can head a group.
LIST_FILES = ('requirements.txt', 'requirements-dev.txt', '.gitignore', '.dockerignore')

# British spellings the repo has used or might slip into. "Analyses" (plural of
# analysis) is American too, so only the verb forms are listed.
BRITISH = re.compile(
    r'\b(colour|behaviour|favour|honour|neighbour|organis|recognis|realis|summaris|analys(?:e|ed|ing)\b|'
    r'catalogue|licence|cancell(?:ed|ing)|modell(?:ed|ing)|labell(?:ed|ing)|travell(?:ed|ing)|centre|metre|'
    r'grey|whilst|amongst|programme|artefact)\w*',
    re.IGNORECASE,
)

# This file lists the spellings it looks for, so it skips itself.
SELF = 'scripts/check-conventions.py'

BANNER = re.compile(r'^\s*(#|--) ?(═{10,}|── .* ─+)$')
ALIGNED = re.compile(r'\S {2,}\S')
LIST_MARKER = re.compile(r'^(\d+\.|[-*•]) +')
DIRECTIVE = re.compile(r'^(noqa|type: |fmt: |pragma|shellcheck|pylint)')
ENDINGS = ('.', ':', '?', '…', '.)', '."', ".'", '.`', '?"', "?'")


def tracked_files():
    """Every file git tracks, except Terraform's lock file (generated)."""
    files = subprocess.run(['git', 'ls-files'], capture_output=True, text=True, check=True).stdout.split()
    return [f for f in files if not f.endswith('.lock.hcl')]


def ends_a_paragraph(text):
    """Whether prose ends the way an explanation should."""
    text = text.rstrip()
    return text.endswith(ENDINGS) or re.search(r'https?://\S+$', text) is not None


def without_code_spans(text):
    """Text with each `code span` blanked, so its spacing isn't read as columns."""
    return re.sub(r'`[^`]*`', lambda match: 'x' * len(match.group(0)), text)


# ── Prose lines ───────────────────────────────────────────────────────────────

def docstring_spans(text):
    """[(first line, last line, is_module)] of every Python docstring."""
    spans = []
    for node in ast.walk(ast.parse(text)):
        body = getattr(node, 'body', None)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and body \
                and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            spans.append((body[0].lineno, body[0].end_lineno, isinstance(node, ast.Module)))
    return spans


def jinja_spans(text):
    """[(first line, last line, is_header)] of every dbt {# … #} block."""
    spans = []
    for match in re.finditer(r'\{#.*?#\}', text, re.S):
        first = text[:match.start()].count('\n') + 1
        last = text[:match.end()].count('\n') + 1
        spans.append((first, last, not text[:match.start()].strip()))
    return spans


def yaml_spans(lines):
    """[(first line, last line)] of every folded YAML description."""
    spans, start, indent = [], None, 0
    for n, line in enumerate(lines + [''], 1):
        depth = len(line) - len(line.lstrip())
        if start is not None and line.strip() and depth > indent:
            continue
        if start is not None and n - 1 >= start:
            spans.append((start, n - 1))
        start = None
        if re.search(r'description: [>|]-?\s*$', line):
            start, indent = n + 1, depth
    return spans


def comments(path, text):
    """[(line, column, body, is_end_of_line)] for every # or -- comment."""
    found = []
    if path.endswith('.py'):
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT:
                end_of_line = token.line[:token.start[1]].strip() != ''
                found.append((token.start[0], token.start[1], token.string[1:], end_of_line))
        return found
    marker = '--' if path.endswith('.sql') else '#'
    for n, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith(('#!', '{#', '#}')):
            continue
        if stripped.startswith(marker):
            found.append((n, len(line) - len(stripped), stripped[len(marker):], False))
        elif not path.endswith('.sql'):
            match = re.search(r'\s#\s(.*)$', line)
            before = line[:match.start()] if match else ''
            if match and before.strip() and before.count('"') % 2 == 0 and before.count("'") % 2 == 0:
                found.append((n, match.start() + 1, ' ' + match.group(1), True))
    return found


def prose_lines(path, text, lines):
    """{line: column where its block's prose starts}, for the width check."""
    prose = {}

    def block(first, last):
        texts = [lines[n - 1] for n in range(first, last + 1)
                 if lines[n - 1].strip() and not re.search(r'"""|\{#|#\}', lines[n - 1])]
        base = min((len(t) - len(t.lstrip()) for t in texts), default=0)
        prose.update({n: base for n in range(first, last + 1)})

    if path.endswith('.py'):
        for first, last, _ in docstring_spans(text):
            block(first, last)
    if path.endswith('.sql'):
        for first, last, _ in jinja_spans(text):
            block(first, last)
    if path.endswith('.yml'):
        for first, last in yaml_spans(lines):
            block(first, last)
    for n, column, _, end_of_line in comments(path, text):
        if not end_of_line and n not in prose:
            prose[n] = column + (2 if lines[n - 1].lstrip().startswith('--') else 1) + 1
    return prose


def limit(line, base):
    """80 for prose; 120 for a table or code line."""
    start = len(re.match(r'^\s*(?:#|--)?\s*', line).group(0))
    return CODE_WIDTH if start >= base + 2 or ALIGNED.search(without_code_spans(line[start:])) else WIDTH


# ── Punctuation ───────────────────────────────────────────────────────────────

def kinds(numbered, base):
    """
    [(line, kind, text)] with kind 'blank', 'banner', 'table', or 'prose'. A
    line hanging under a numbered or bulleted prose line continues it.
    """
    out, hang = [], None
    for n, text in numbered:
        indent = len(text) - len(text.lstrip())
        aligned = ALIGNED.search(without_code_spans(text.strip()))
        if not text.strip():
            kind, hang = 'blank', None
        elif re.match(r'^ ?(═{10,}|── .* ─+)\s*$', text):
            kind, hang = 'banner', None
        elif hang is not None and indent == hang and not aligned:
            kind = 'prose'
        elif indent >= base + 2 or aligned:
            kind, hang = 'table', None
        else:
            kind = 'prose'
            marker = LIST_MARKER.match(text.strip())
            hang = indent + len(marker.group(0)) if marker else None
        out.append((n, kind, text))
    return out


def paragraphs(items):
    """Split [(line, kind, text)] into runs of one kind; blanks and banners stand alone."""
    groups, current = [], []
    for item in items:
        if item[1] in ('blank', 'banner'):
            if current:
                groups.append(current)
            groups.append([item])
            current = []
            continue
        if current and current[-1][1] != item[1]:
            groups.append(current)
            current = []
        current.append(item)
    if current:
        groups.append(current)
    return groups


def check_list(path, run, problems):
    """The items of one list or table end the same way."""
    base = min(len(t) - len(t.lstrip()) for _, _, t in run)
    items = []
    for n, _, text in run:
        if len(text) - len(text.lstrip()) == base or not items:
            items.append([n, text])
        else:
            items[-1][1] = text
    endings = {text.rstrip().endswith('.') for _, text in items if not text.rstrip().endswith((':', ','))}
    if len(items) > 1 and len(endings) == 2:
        problems.append(f'{path}:{items[0][0]}: list mixes items with and without a closing period')


def check_block(path, items, problems, titled=False, is_label=lambda run, k, groups: False):
    """Each paragraph of one comment block, docstring, or dbt comment, by its role."""
    groups = paragraphs(items)
    seen_prose = False
    for k, run in enumerate(groups):
        kind = run[0][1]
        if kind == 'table':
            check_list(path, run, problems)
            continue
        if kind != 'prose':
            continue
        first, last = run[0][0], run[-1]
        boxed = k > 0 and groups[k - 1][0][1] == 'banner' and '═' in groups[k - 1][0][2]
        if (titled and not seen_prose) or boxed:
            if len(run) > 1:
                problems.append(f'{path}:{first}: title runs to {len(run)} lines; keep it to one')
            if last[2].rstrip().endswith('.'):
                problems.append(f'{path}:{last[0]}: title ends with a period')
        elif is_label(run, k, groups):
            if last[2].rstrip().endswith('.'):
                problems.append(f'{path}:{last[0]}: label ends with a period')
        elif not ends_a_paragraph(last[2]):
            problems.append(f'{path}:{last[0]}: paragraph needs a closing period')
        seen_prose = True


def check_punctuation(path, text, lines, problems):
    """Titles, labels, explanations, and lists in every comment and docstring."""
    found = comments(path, text)
    for n, _, body, end_of_line in found:
        if end_of_line and body.rstrip().endswith('.') and not DIRECTIVE.match(body.strip()):
            problems.append(f'{path}:{n}: end-of-line comment ends with a period')

    # Consecutive full-line comments form a block.
    blocks = []
    for n, _, body, end_of_line in found:
        if end_of_line or DIRECTIVE.match(body.strip()):
            continue
        if blocks and n == blocks[-1][-1][0] + 1:
            blocks[-1].append((n, body))
        else:
            blocks.append([(n, body)])
    first_code = next((n for n, line in enumerate(lines, 1)
                       if line.strip() and not line.lstrip().startswith(('#', '--', '{#'))
                       and line.strip() != 'version: 2'), len(lines) + 1)
    is_list_file = path.rsplit('/', 1)[-1] in LIST_FILES
    for b, block in enumerate(blocks):
        numbered = [(n, body[1:] if body.startswith(' ') else body) for n, body in block]
        titled = b == 0 and block[0][0] < first_code and not path.endswith(('.py', '.sql'))
        if titled and block[-1][0] < len(lines) and lines[block[-1][0]].strip():
            problems.append(f'{path}:{block[-1][0]}: title block needs a blank line after it')

        def is_label(run, k, groups):
            words = run[0][2].strip()
            if path.endswith('.py') and words.startswith('Import ') and len(run) == 1:
                return True
            after = lines[run[-1][0]].strip() if run[-1][0] < len(lines) else ''
            return is_list_file and len(run) == 1 and k == len(groups) - 1 and after and not after.startswith('#')

        check_block(path, kinds(numbered, 0), problems, titled, is_label)

    # Docstrings and dbt {# … #} blocks: a module's or a model's first line is
    # its title.
    spans = []
    if path.endswith('.py'):
        spans = docstring_spans(text)
    if path.endswith('.sql'):
        spans = jinja_spans(text)
    for first, last, is_header in spans:
        numbered = []
        for n in range(first, last + 1):
            line = re.sub(r'"""|\{#-?|-?#\}', '', lines[n - 1])
            if n in (first, last) and not line.strip():
                continue
            numbered.append((n, line))
        base = min((len(t) - len(t.lstrip()) for _, t in numbered if t.strip()), default=0)
        check_block(path, kinds(numbered, base), problems, titled=is_header)

    # YAML descriptions are prose.
    if path.endswith('.yml'):
        for _, last in yaml_spans(lines):
            final = lines[last - 1].strip()
            if final and not final.endswith(('.', '}}')):
                problems.append(f'{path}:{last}: description needs a closing period')
        for n, line in enumerate(lines, 1):
            match = re.match(r'^\s*description: (.+)$', line)
            value = match.group(1).strip().strip('"\'') if match else ''
            if value and value not in ('>', '|', '>-', '|-') and not value.endswith(('.', '}}')):
                problems.append(f'{path}:{n}: description needs a closing period')


# ── Check ─────────────────────────────────────────────────────────────────────

def check(path):
    """Problems in one file, as 'path:line: message' strings."""
    try:
        with open(path, encoding='utf-8') as handle:
            text = handle.read()
    except (UnicodeDecodeError, IsADirectoryError):
        return []
    lines = text.splitlines()
    is_code = path.endswith(CODE_SUFFIXES) or path.rsplit('/', 1)[-1] in CODE_NAMES
    is_markdown = path.endswith('.md')
    prose = prose_lines(path, text, lines) if is_code else {}
    problems = []
    for n, line in enumerate(lines, 1):
        where = f'{path}:{n}:'
        if is_code and BANNER.match(line):
            if len(line) != WIDTH:
                problems.append(f'{where} banner is {len(line)} columns wide, not {WIDTH}')
        elif n in prose and len(line) > limit(line, prose[n]):
            problems.append(f'{where} runs to {len(line)} columns (limit {limit(line, prose[n])})')
        if (n in prose or is_markdown) and '...' in line:
            problems.append(f'{where} "..." in prose; use "…"')
        for match in (BRITISH.finditer(line) if path != SELF else ()):
            problems.append(f'{where} British spelling "{match.group(0)}"')
    if is_code:
        check_punctuation(path, text, lines, problems)
    return problems


problems = [problem for path in tracked_files() for problem in check(path)]
for problem in problems:
    print(problem)
if problems:
    print(f'{len(problems)} convention problem(s); see docs/conventions.md', file=sys.stderr)
    sys.exit(1)
print('Conventions: all checks passed')
