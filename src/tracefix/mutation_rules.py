"""Fixed mutation rules: the same small edits to the fixed lines for every run (Decided 3 Oct 2026).

Beside the model's mutants, Guard tries a fixed set of operator and constant swaps on the lines
the fix added or changed: comparisons, `and`/`or`, `is`/`in` and their negations, `+`/`-`,
`*`/`/`, `//` to `/`, `+=`/`-=`, `True`/`False`, `break`/`continue`, a dropped `not`, integers
off by one, and negated `if` conditions. They need no model and give the same mutants for the
same fix. Each one is a whole-line edit that goes through the same hygiene rules and runs as a
model mutant would.

Body mutants (Decided 5 Oct 2026, from cargo-mutants and PIT Descartes): the whole body of each
function holding a fixed line becomes `return <a plain value of its return type>`. A test that
still passes then never looked at what the function does ("pseudo-tested"). They span more
than the fixed lines, so Guard checks them without the line rules (see guard.rule_mutants).

Kinds (M11, NOTES 24): every edit carries one of the 10 kinds below. Guard takes them in turn, so
one of each fits under its cap of 10 and which kinds run no longer depends on line order. Two kinds
are from prove-your-tests: `drop_call` (a one-line call statement becomes `pass`) and `reraise` (a
bare `raise` before the first statement of an `except` body: does a test notice the handler?).

Report only (Decided 3 Oct 2026 by the developer): their kill rate is shown, but never counts
toward Guard's verdict, because some of them change nothing a caller can see (`<` to `<=` where
the two sides are never equal) and no test could kill those.
"""

import ast
import io
import keyword
import tokenize
from dataclasses import dataclass
from typing import Literal, get_args

from tracefix.prompts import mutator

RuleKind = Literal["body", "compare", "logic", "negate_if", "constant", "arithmetic", "membership",
                   "loop", "drop_call", "reraise"]  # fmt: skip
KINDS: tuple[RuleKind, ...] = get_args(RuleKind)  # the order Guard takes them in

COMPARE_SWAPS = {"<": "<=", "<=": "<", ">": ">=", ">=": ">", "==": "!=", "!=": "=="}
ARITHMETIC_SWAPS = {"+": "-", "-": "+", "+=": "-=", "-=": "+=", "//": "/"}
# Only between two operands: `*args`, `def f(a, *, b)` and `def f(a, /)` are not arithmetic.
BINARY_SWAPS = {"*": "/", "/": "*"}
WORD_SWAPS: dict[str, tuple[str, RuleKind]] = {
    "and": ("or", "logic"),
    "or": ("and", "logic"),
    "True": ("False", "constant"),
    "False": ("True", "constant"),
    "break": ("continue", "loop"),
    "continue": ("break", "loop"),
}
# A single comparison whose flipped operator already is its negation: `not (...)` would repeat it.
NEGATING_OPS = (ast.Eq, ast.NotEq, ast.Is, ast.IsNot, ast.In, ast.NotIn)
RERAISE_WORDS = "rule: re-raise at the start of the `except` body"


class RuleProposal(mutator.MutantProposal):
    """A rule edit and its kind. The kind is ours: the schema the model answers in has none."""

    kind: RuleKind


@dataclass(frozen=True)
class _Edit:
    line: int  # 1-based
    start: int  # character columns on that line
    end: int
    new: str
    kind: RuleKind
    description: str = ""  # default: `old` -> `new`


# Python 3.12+ splits f-strings into tokens; 3.11 keeps them whole. Skipping their insides gives
# the same mutants on every version (-1: never a token type on 3.11).
FSTRING_START = getattr(tokenize, "FSTRING_START", -1)
FSTRING_END = getattr(tokenize, "FSTRING_END", -1)
CLOSERS = (")", "]", "}")
LAYOUT = (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT)

# Plain values for a return annotation, as cargo-mutants picks them; anything else gets `None`.
TYPE_VALUES = {
    "int": ("0", "1"),
    "float": ("0.0", "1.0"),
    "str": ('""', '"xyzzy"'),
    "bool": ("True", "False"),
    "bytes": ('b""',),
    "list": ("[]",),
    "List": ("[]",),
    "dict": ("{}",),
    "Dict": ("{}",),
    "tuple": ("()",),
    "Tuple": ("()",),
}
VALUES_PER_FUNCTION = 2


def _ends_operand(tok: tokenize.TokenInfo | None) -> bool:
    """Whether `tok` can end the left operand of a binary operator."""
    if tok is None:
        return False
    if tok.type == tokenize.NAME:
        return not keyword.iskeyword(tok.string) or tok.string in ("True", "False", "None")
    return tok.type in (tokenize.NUMBER, tokenize.STRING, FSTRING_END) or tok.string in CLOSERS


def _off_by_one(token: str) -> list[str]:
    """`n+1` and `n-1` for an integer literal (negatives in brackets: `-1 ** 2` is -(1**2)), else
    nothing. A huge hex literal can't be written back in decimal (ValueError): skipped too."""
    try:
        value = ast.literal_eval(token)
        if type(value) is not int:
            return []
        return [str(n) if n >= 0 else f"({n})" for n in (value + 1, value - 1)]
    except (ValueError, SyntaxError):
        return []


def _previous(tokens: list[tokenize.TokenInfo], i: int) -> tokenize.TokenInfo | None:
    """The token before `tokens[i]`, past line breaks and comments inside brackets, so a `*`
    that starts a continuation line still sees its left operand."""
    j = i - 1
    while j >= 0 and tokens[j].type in LAYOUT:
        j -= 1
    return tokens[j] if j >= 0 else None


def _token_edits(tokens: list[tokenize.TokenInfo], fixed: frozenset[int]) -> list[_Edit]:
    edits = []
    depth = 0  # inside an f-string
    for i, tok in enumerate(tokens):
        depth += (tok.type == FSTRING_START) - (tok.type == FSTRING_END)
        (row, col), (end_row, end_col) = tok.start, tok.end
        if depth or row not in fixed or row != end_row:
            continue
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        prev = _previous(tokens, i)
        if tok.type == tokenize.OP and tok.string in COMPARE_SWAPS:
            edits.append(_Edit(row, col, end_col, COMPARE_SWAPS[tok.string], "compare"))
        elif tok.type == tokenize.OP and tok.string in ARITHMETIC_SWAPS:
            edits.append(_Edit(row, col, end_col, ARITHMETIC_SWAPS[tok.string], "arithmetic"))
        elif tok.type == tokenize.OP and tok.string in BINARY_SWAPS and _ends_operand(prev):
            edits.append(_Edit(row, col, end_col, BINARY_SWAPS[tok.string], "arithmetic"))
        elif tok.type == tokenize.NAME and tok.string in WORD_SWAPS:
            new, kind = WORD_SWAPS[tok.string]
            edits.append(_Edit(row, col, end_col, new, kind))
        elif tok.type == tokenize.NAME and tok.string == "is":
            if nxt and nxt.string == "not" and nxt.start[0] == row:
                edits.append(_Edit(row, col, nxt.end[1], "is", "membership"))
            else:
                edits.append(_Edit(row, col, end_col, "is not", "membership"))
        elif tok.type == tokenize.NAME and tok.string == "not":
            if nxt and nxt.string == "in" and nxt.start[0] == row:
                edits.append(_Edit(row, col, nxt.end[1], "in", "membership"))
            elif (nxt and nxt.start[0] == row and nxt.type not in LAYOUT
                  and not (prev and prev.string == "is")):  # fmt: skip
                edits.append(_Edit(row, col, nxt.start[1], "", "logic"))  # `not x` -> `x`
        elif tok.type == tokenize.NAME and tok.string == "in":
            if not (prev and prev.string == "not"):  # `for x in` won't compile: hygiene drops it
                edits.append(_Edit(row, col, end_col, "not in", "membership"))
        elif tok.type == tokenize.NUMBER:
            edits += [_Edit(row, col, end_col, new, "constant") for new in _off_by_one(tok.string)]
    return edits


def _char_col(line: str, byte_col: int) -> int:
    """ast columns count UTF-8 bytes; lines are indexed by character."""
    return len(line.encode("utf-8")[:byte_col].decode("utf-8", errors="replace"))


def _single_negating_compare(test: ast.expr) -> bool:
    return (isinstance(test, ast.Compare) and len(test.ops) == 1
            and isinstance(test.ops[0], NEGATING_OPS))  # fmt: skip


def _negated(test: ast.expr) -> bool:
    """`if not x`: dropping the `not` already negates it, `not (not x)` would repeat that."""
    return isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not)


def _negation_edits(tree: ast.AST, lines: list[str], fixed: frozenset[int]) -> list[_Edit]:
    edits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if test.lineno not in fixed or test.end_lineno != test.lineno:
            continue
        if _single_negating_compare(test) or _negated(test):
            continue
        line = lines[test.lineno - 1]
        start = _char_col(line, test.col_offset)
        end = _char_col(line, test.end_col_offset or 0)
        edits.append(_Edit(test.lineno, start, end, f"not ({line[start:end]})", "negate_if"))
    return edits


def _is_call(value: ast.expr) -> bool:
    """`f()` or `await f()`."""
    return isinstance(value.value if isinstance(value, ast.Await) else value, ast.Call)


def _drop_call_edits(tree: ast.AST, lines: list[str], fixed: frozenset[int]) -> list[_Edit]:
    """A call statement on one fixed line becomes `pass`. A statement that shares its line keeps
    its neighbours: only its own columns change (`a(); b()` -> `pass; b()`)."""
    edits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Expr) or not _is_call(node.value):
            continue
        if node.lineno not in fixed or node.end_lineno != node.lineno:
            continue
        line = lines[node.lineno - 1]
        start = _char_col(line, node.col_offset)
        end = _char_col(line, node.end_col_offset or 0)
        edits.append(_Edit(node.lineno, start, end, "pass", "drop_call"))
    return edits


def _is_bare_raise(node: ast.stmt) -> bool:
    return isinstance(node, ast.Raise) and node.exc is None


def _reraise_edits(tree: ast.AST, lines: list[str], fixed: frozenset[int]) -> list[_Edit]:
    """A bare `raise` on its own line before the first statement of an `except` body, when that
    statement or the `except` line is fixed. Skipped: one-line handlers (no line of its own to
    add) and a body that already starts with a bare `raise` (the same code)."""
    edits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        first = node.body[0]
        if _is_bare_raise(first) or not {node.lineno, first.lineno} & fixed:
            continue
        line = lines[first.lineno - 1]
        start = _char_col(line, first.col_offset)
        indent = line[:start]
        if indent.strip():
            continue  # `except E: x`, or the statement shares a line with the header's end
        cr = "\r" if line.endswith("\r") else ""
        new = f"raise{cr}\n{indent}"
        edits.append(_Edit(first.lineno, start, start, new, "reraise", RERAISE_WORDS))
    return edits


def _has_bare_cr(head: str) -> bool:
    """A `\\r` with no `\\n` after it, even inside a string: `ast` counts it as a line break and
    `split("\\n")` does not, so ast's line numbers would point at the wrong lines (verifier B1)."""
    return "\r" in head.replace("\r\n", "")


def rule_proposals(path: str, head: str, fixed: frozenset[int]) -> list[RuleProposal]:
    """Every rule edit on the fixed lines of `head`, in line and column order. Each replaces one
    whole line, so it starts on that line exactly once (the hygiene rules check that)."""
    try:
        tree = ast.parse(head)
        tokens = list(tokenize.generate_tokens(io.StringIO(head).readline))
    except (SyntaxError, ValueError, tokenize.TokenError):
        return []
    lines = head.split("\n")
    edits = _token_edits(tokens, fixed)
    if not _has_bare_cr(head):
        edits += _negation_edits(tree, lines, fixed)
        edits += _drop_call_edits(tree, lines, fixed)
        edits += _reraise_edits(tree, lines, fixed)
    proposals = []
    for e in sorted(edits, key=lambda e: (e.line, e.start, e.end, e.new)):
        line = lines[e.line - 1]
        old = line[e.start : e.end]
        new_line = line[: e.start] + e.new + line[e.end :]
        description = f"rule: `{old}` -> `{e.new}`" if e.new else f"rule: drop `{old.strip()}`"
        proposals.append(
            RuleProposal(
                path=path,
                line=e.line,
                original=line,
                replacement=new_line,
                description=e.description or description,
                kind=e.kind,
            )
        )
    return proposals


# --- body mutants --------------------------------------------------------------------------------

Function = ast.FunctionDef | ast.AsyncFunctionDef


def _type_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Subscript):
        node = node.value  # list[int] -> list
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr  # typing.List -> List
    return None


def _optional(node: ast.expr) -> ast.expr | None:
    """X for `X | None`, `None | X` and `Optional[X]`, else None."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        for side, other in ((node.left, node.right), (node.right, node.left)):
            if isinstance(side, ast.Constant) and side.value is None:
                return other
    if isinstance(node, ast.Subscript) and _type_name(node) == "Optional":
        return node.slice
    return None


def return_values(returns: ast.expr | None) -> tuple[str, ...]:
    """Source text of the plain values a body mutant returns, for a return annotation."""
    if returns is None or (isinstance(returns, ast.Constant) and returns.value is None):
        return ("None",)
    if isinstance(returns, ast.Constant) and isinstance(returns.value, str):  # -> "int"
        try:
            return return_values(ast.parse(returns.value, mode="eval").body)
        except (SyntaxError, ValueError, RecursionError):
            return ("None",)
    inner = _optional(returns)
    if inner is not None:
        return ("None", *return_values(inner))[:VALUES_PER_FUNCTION]
    return TYPE_VALUES.get(_type_name(returns) or "", ("None",))[:VALUES_PER_FUNCTION]


def _own_nodes(node: ast.AST) -> list[ast.AST]:
    """Nodes in a function's body, not inside a nested function, lambda or class. A loop, not
    recursion: a 1,500-term expression must not stop every rule mutant (verifier S1)."""
    found: list[ast.AST] = []
    todo = list(ast.iter_child_nodes(node))
    while todo:
        child = todo.pop()
        found.append(child)
        if not isinstance(child, Function | ast.Lambda | ast.ClassDef):
            todo.extend(ast.iter_child_nodes(child))
    return found


def _is_generator(func: Function) -> bool:
    return any(isinstance(n, ast.Yield | ast.YieldFrom) for n in _own_nodes(func))


def _changed_functions(tree: ast.AST, fixed: frozenset[int]) -> list[Function]:
    """The innermost function holding each fixed line, in line order, each once."""
    functions = [n for n in ast.walk(tree) if isinstance(n, Function)]
    found: dict[int, Function] = {}
    for line in sorted(fixed):
        holding = [f for f in functions if f.lineno <= line <= (f.end_lineno or f.lineno)]
        if holding:
            inner = min(holding, key=lambda f: (f.end_lineno or f.lineno) - f.lineno)
            found.setdefault(id(inner), inner)
    return sorted(found.values(), key=lambda f: f.lineno)


def _first_replaced(func: Function) -> ast.stmt | None:
    """The first statement to replace (a docstring stays), or None if the body can't be cut out
    as whole lines: only a docstring, a one-line `def`, or a statement sharing a line."""
    body = func.body
    first = body[0]
    docstring = (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                 and isinstance(first.value.value, str))  # fmt: skip
    if docstring:
        if len(body) == 1 or body[1].lineno == first.end_lineno:
            return None
        return body[1]
    return None if first.lineno == func.lineno else first


def body_proposals(path: str, head: str, fixed: frozenset[int]) -> list[RuleProposal]:
    """For each function holding a fixed line (generators skipped), its body from the first
    statement after the docstring replaced by `return <value>`, one proposal per value. A file
    with a bare `\\r` gets none: the cut would land on the wrong lines (_has_bare_cr)."""
    if _has_bare_cr(head):
        return []
    try:
        tree = ast.parse(head)
    except (SyntaxError, ValueError, RecursionError):
        return []
    lines = head.split("\n")
    proposals = []
    for func in _changed_functions(tree, fixed):
        first = _first_replaced(func)
        if first is None or _is_generator(func):
            continue
        replaced = lines[first.lineno - 1 : func.end_lineno]
        indent = replaced[0][: len(replaced[0]) - len(replaced[0].lstrip())]
        if len(indent.encode("utf-8")) != first.col_offset:
            continue  # the statement does not start its line
        cr = "\r" if replaced[-1].endswith("\r") else ""
        for value in return_values(func.returns):
            proposals.append(
                RuleProposal(
                    path=path,
                    line=first.lineno,
                    original="\n".join(replaced),
                    replacement=f"{indent}return {value}{cr}",
                    description=f"rule: body of `{func.name}` -> `return {value}`",
                    kind="body",
                )
            )
    return proposals
