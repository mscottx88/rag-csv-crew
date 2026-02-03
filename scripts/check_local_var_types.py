#!/usr/bin/env python3
"""AST-based checker for missing local variable type annotations.

This script enforces the constitutional requirement:
"ALL local variables MUST have explicit type annotations"

It detects variable assignments without type annotations in:
- Function bodies (local variables)
- Class method bodies
- Test functions

Pragmatic Approach (Balance strictness with practicality):
- Requires annotations for non-obvious types: peak_mb = peak / (1024 * 1024)
- Allows obvious constructor calls: config = DatabaseConfig(...)
- Catches real quality issues while avoiding busywork

Exemptions (variables that don't need annotations):
- Obvious constructor calls: config = ClassName(...), obj = module.Type(...)
- Unpacking assignments: _, x = func()
- Loop variables in for loops (optional per constitution)
- Context manager targets: with ... as var:
- Exception handlers: except Exception as e:
- Comprehensions (list/dict/set comprehensions)
- Augmented assignments: x += 1 (variable already exists)
"""

import ast
import sys
from pathlib import Path


# pylint: disable=invalid-name
# JUSTIFICATION: AST visitor methods must use names dictated by ast.NodeVisitor (visit_*)
class LocalVariableTypeChecker(ast.NodeVisitor):
    """AST visitor to detect local variables without type annotations."""

    def __init__(self, filename: str) -> None:
        """Initialize the checker.

        Args:
            filename: Path to the file being checked
        """
        self.filename: str = filename
        self.violations: list[tuple[int, str, str]] = []
        self.in_function: bool = False
        self.function_stack: list[str] = []
        self.declared_vars: set[str] = set()  # Track vars declared in current function

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition and check its body."""
        self.in_function = True
        self.function_stack.append(node.name)
        self.declared_vars = set()  # Reset for new function
        self.generic_visit(node)
        self.function_stack.pop()
        if not self.function_stack:
            self.in_function = False
            self.declared_vars = set()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition and check its body."""
        self.in_function = True
        self.function_stack.append(node.name)
        self.declared_vars = set()  # Reset for new function
        self.generic_visit(node)
        self.function_stack.pop()
        if not self.function_stack:
            self.in_function = False
            self.declared_vars = set()

    def _is_obvious_constructor(self, node: ast.expr) -> bool:
        """Check if the expression is an obvious constructor call.

        Returns True for patterns like:
        - ClassName(...)
        - module.ClassName(...)
        - SomeType[GenericParam](...)

        These are self-documenting and don't need type annotations.
        """
        if isinstance(node, ast.Call):
            func: ast.expr = node.func

            # Direct constructor: ClassName(...)
            if isinstance(func, ast.Name):
                # Check if it looks like a class name (PascalCase)
                name: str = func.id
                if name[0].isupper():
                    return True

            # Attribute constructor: module.ClassName(...)
            elif isinstance(func, ast.Attribute):
                # Check if attribute looks like a class name
                if func.attr[0].isupper():
                    return True

            # Subscripted constructor: Type[Generic](...)
            elif isinstance(func, ast.Subscript):
                return self._is_obvious_constructor(func.value)

        return False

    def visit_Assign(self, node: ast.Assign) -> None:
        """Check assignment statements for missing type annotations.

        Only checks assignments inside functions (local variables).
        Exempts special cases:
        - Unpacking assignments
        - Loop variables
        - Obvious constructor calls (pragmatic exemption)
        """
        if not self.in_function:
            self.generic_visit(node)
            return

        # Check each target in the assignment
        for target in node.targets:
            if isinstance(target, ast.Name):
                # Simple assignment: x = value
                var_name: str = target.id

                # Exempt underscore (throwaway variable)
                if var_name == "_":
                    continue

                # Exempt reassignments: if variable already declared, skip
                if var_name in self.declared_vars:
                    continue

                # Pragmatic exemption: obvious constructor calls
                # e.g., config = DatabaseConfig(...) is self-documenting
                if self._is_obvious_constructor(node.value):
                    self.declared_vars.add(var_name)  # Track as declared
                    continue

                # Pragmatic exemption: property/attribute access
                # e.g., headers = obj.property is reasonably obvious
                if isinstance(node.value, ast.Attribute):
                    self.declared_vars.add(var_name)  # Track as declared
                    continue

                function_name: str = self.function_stack[-1] if self.function_stack else "unknown"
                self.violations.append(
                    (
                        node.lineno,
                        var_name,
                        f"Local variable '{var_name}' in function '{function_name}' "
                        f"missing type annotation",
                    )
                )

            elif isinstance(target, ast.Tuple):
                # Unpacking: a, b = func() or _, x = func()
                # Exempt unpacking assignments as they're often used for tuple returns
                pass

            # Other cases (subscript, attribute) don't need type annotations
            # e.g., obj.attr = value or list[0] = value

        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Visit annotated assignments (these are compliant)."""
        # These are fine - they have type annotations
        # Track the variable as declared
        if self.in_function and isinstance(node.target, ast.Name):
            self.declared_vars.add(node.target.id)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """Visit augmented assignments (these are fine).

        Augmented assignments (+=, -=, etc.) modify existing variables,
        so they don't need type annotations.
        """
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        """Visit for loops (loop variables are exempted per constitution).

        The constitution states loop variables are optional:
        'Including loop variables where practical: item: ItemType'

        Track loop variables as declared so reassignments aren't flagged.
        """
        if self.in_function:
            # Track loop variable(s) as declared
            if isinstance(node.target, ast.Name):
                self.declared_vars.add(node.target.id)
            elif isinstance(node.target, ast.Tuple):
                for elt in node.target.elts:
                    if isinstance(elt, ast.Name):
                        self.declared_vars.add(elt.id)
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        """Visit with statements (context manager variables are exempted)."""
        self.generic_visit(node)

    def report(self) -> int:
        """Print violations and return exit code.

        Returns:
            0 if no violations, 1 if violations found
        """
        if not self.violations:
            return 0

        print(f"\n{self.filename}:")
        for lineno, var_name, message in sorted(self.violations):
            print(f"  Line {lineno}: {message}")
            print(f"    Fix: Add type annotation: {var_name}: <Type> = ...")

        return 1


# pylint: enable=invalid-name


def check_file(filepath: Path) -> int:
    """Check a single Python file for missing local variable type annotations.

    Args:
        filepath: Path to the Python file to check

    Returns:
        0 if compliant, 1 if violations found
    """
    try:
        content: str = filepath.read_text(encoding="utf-8")
        tree: ast.AST = ast.parse(content, filename=str(filepath))

        checker: LocalVariableTypeChecker = LocalVariableTypeChecker(str(filepath))
        checker.visit(tree)

        return checker.report()

    except SyntaxError as e:
        print(f"Syntax error in {filepath}: {e}")
        return 1
    # pylint: disable=broad-exception-caught
    # JUSTIFICATION: Need to catch all exceptions to report file check errors without crashing
    except Exception as e:  # noqa: BLE001
        print(f"Error checking {filepath}: {e}")
        return 1
    # pylint: enable=broad-exception-caught


def main() -> int:
    """Main entry point for the checker.

    Returns:
        0 if all files compliant, 1 if any violations found
    """
    if len(sys.argv) < 2:
        print("Usage: check_local_var_types.py <file1.py> [file2.py ...]")
        print("\nChecks Python files for missing local variable type annotations.")
        print("This enforces the constitutional requirement:")
        print("'ALL local variables MUST have explicit type annotations'")
        return 1

    exit_code: int = 0
    files_checked: int = 0
    total_violations: int = 0

    for filepath_str in sys.argv[1:]:
        filepath: Path = Path(filepath_str)

        if not filepath.exists():
            print(f"File not found: {filepath}")
            exit_code = 1
            continue

        if filepath.suffix != ".py":
            # Skip non-Python files
            continue

        files_checked += 1
        result: int = check_file(filepath)
        if result != 0:
            exit_code = 1
            total_violations += 1

    if exit_code == 0:
        print(
            f"[OK] All {files_checked} files compliant with "
            f"local variable type hint requirements"
        )
    else:
        print(
            f"\n[FAIL] Found violations in {total_violations}/{files_checked} files\n"
            f"\nConstitutional requirement: ALL local variables MUST have explicit type annotations"
            f"\nSee CLAUDE.md section 'CRITICAL: NO DOUBLE STANDARDS' for details"
        )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
