import ast
import re
from typing import Any, Dict, List

SENSITIVE_VAR_PATTERN = re.compile(
    r"(api[_-]?key|secret|password|passwd|pwd|auth[_-]?token|access[_-]?token|private[_-]?key)",
    re.IGNORECASE,
)
SAFE_PLACEHOLDERS = {"", "none", "null", "changeme", "your_api_key", "example", "placeholder"}


class _SingleFunctionComplexityVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.complexity = 1

    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.complexity += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return


def _rate_complexity(score: int) -> str:
    if score <= 5:
        return "Low (Simple)"
    if score <= 10:
        return "Moderate"
    return "High (Refactor Recommended)"


def analyze_python_code(source_code: str, filename: str = "snippet.py") -> Dict[str, Any]:
    if not source_code or not source_code.strip():
        raise ValueError("Source code cannot be empty or whitespace only.")
    try:
        tree = ast.parse(source_code, filename=filename)
    except SyntaxError as exc:
        raise ValueError(f"Python SyntaxError at line {exc.lineno}: {exc.msg}") from exc

    lines = source_code.splitlines()
    non_empty_loc = sum(1 for line in lines if line.strip() and not line.strip().startswith("#"))
    functions: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            visitor = _SingleFunctionComplexityVisitor()
            for child in node.body:
                visitor.visit(child)
            functions.append({
                "name": node.name,
                "lineno": node.lineno,
                "complexity": visitor.complexity,
                "rating": _rate_complexity(visitor.complexity),
            })
        elif isinstance(node, ast.Assign):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                secret_val = node.value.value.strip()
                if len(secret_val) >= 6 and secret_val.lower() not in SAFE_PLACEHOLDERS:
                    for target in node.targets:
                        if isinstance(target, ast.Name) and SENSITIVE_VAR_PATTERN.search(target.id):
                            warnings.append({
                                "lineno": node.lineno,
                                "variable": target.id,
                                "message": f"Potential hardcoded credential assigned to '{target.id}'.",
                            })

    functions.sort(key=lambda item: item["lineno"])
    warnings.sort(key=lambda item: item["lineno"])
    avg_complexity = round(sum(f["complexity"] for f in functions) / len(functions), 2) if functions else 1.0
    max_complexity = max((f["complexity"] for f in functions), default=1)

    return {
        "filename": filename,
        "total_loc": non_empty_loc,
        "function_count": len(functions),
        "average_complexity": avg_complexity,
        "max_complexity": max_complexity,
        "functions": functions,
        "warnings": warnings,
    }
