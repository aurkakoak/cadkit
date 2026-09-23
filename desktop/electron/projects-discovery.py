"""Find obvious Python project exports without importing or executing a model."""
import ast
import json
import os
from pathlib import Path
import sys


SKIP = {"build", "dist", "node_modules", "venv", "env", "site-packages", "__pycache__"}
MAX_FILES = 240
MAX_DIRECTORIES = 100
MAX_DEPTH = 5
MAX_FILE_BYTES = 512 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024


def module_statements(statements):
    """Visit conditional module declarations, never function or class bodies."""
    for node in statements:
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__"
                and len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq)
                and len(node.test.comparators) == 1
                and isinstance(node.test.comparators[0], ast.Constant)
                and node.test.comparators[0].value == "__main__"):
            yield from module_statements(node.orelse)
            continue
        for field in ("body", "orelse", "finalbody"):
            yield from module_statements(getattr(node, field, ()))
        for handler in getattr(node, "handlers", ()):
            yield from module_statements(handler.body)


def project_names(tree):
    names = set()
    for node in module_statements(tree.body):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = (node.target,)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(alias.asname or alias.name for alias in node.names)
            continue
        else:
            continue
        for target in targets:
            names.update(child.id for child in ast.walk(target) if isinstance(child, ast.Name))
    return sorted(name for name in names if name == "PROJECT" or name.endswith("_PROJECT"))


def discover(directory):
    selected = Path(directory).resolve()
    files, roots, warnings = [], [selected], []
    visited = size = 0
    truncated = False
    for current, directories, filenames in os.walk(selected, followlinks=False):
        visited += 1
        here = Path(current)
        depth = len(here.relative_to(selected).parts)
        directories[:] = sorted(name for name in directories
                                if not name.startswith(".") and name not in SKIP
                                and not (here / name).is_symlink())
        if depth >= MAX_DEPTH:
            truncated |= bool(directories)
            directories[:] = []
        if visited > MAX_DIRECTORIES:
            truncated = True
            break
        for filename in sorted(filenames, key=lambda name: (name != "project.py", name)):
            source = here / filename
            if source.suffix != ".py" or source.is_symlink():
                continue
            if len(files) >= MAX_FILES or size >= MAX_TOTAL_BYTES:
                truncated = True
                break
            try:
                length = source.stat().st_size
                if length > MAX_FILE_BYTES or size + length > MAX_TOTAL_BYTES:
                    truncated = True
                    files.append((source, ()))
                    continue
                # Bytes let ast.parse honor Python's source encoding declaration.
                content = source.read_bytes()
                size += len(content)
                tree = ast.parse(content, filename=str(source))
            except (OSError, SyntaxError, UnicodeError, ValueError) as error:
                warnings.append(f"Could not inspect {source.relative_to(selected)}: {error}")
                files.append((source, ()))
                continue
            exports = project_names(tree)
            files.append((source, exports))
            level = max((node.level for node in ast.walk(tree)
                         if isinstance(node, ast.ImportFrom)), default=0)
            root = source.parent
            for _ in range(level):
                root = root.parent
            # Regular packages and namespace packages both need their import root.
            package = source.parent
            while (package / "__init__.py").is_file():
                package = package.parent
            roots.extend((root, package))
        if len(files) >= MAX_FILES or size >= MAX_TOTAL_BYTES:
            break

    import_root = Path(os.path.commonpath(roots))
    entries = []
    for source, names in files:
        module = list(source.relative_to(import_root).with_suffix("").parts)
        if module[-1] == "__init__":
            module.pop()
        if not module or not all(part.isidentifier() for part in module):
            if names:
                warnings.append(f"{source.name} needs an explicit Python import reference.")
            continue
        for name in names:
            reference = f"{'.'.join(module)}:{name}"
            entries.append({"projectDir": str(import_root), "reference": reference,
                            "label": reference, "file": str(source)})
    entries.sort(key=lambda entry: (Path(entry["file"]).name != "project.py",
                                    not entry["reference"].endswith(":PROJECT"),
                                    entry["reference"]))
    if truncated:
        warnings.append("Folder scan reached its limit. Choose a smaller folder or enter an import reference.")
    return {"directory": str(selected), "entries": entries, "warnings": warnings[:12]}


if __name__ == "__main__":
    print(json.dumps(discover(sys.argv[1])))
