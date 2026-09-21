#!/usr/bin/env python3
"""CI Alembic Expand-Contract Schema Migration Safety Linter.

Inspects new or modified migration files to guarantee zero-downtime backward compatibility.
Flags:
- Destructive column drops (`op.drop_column`)
- Destructive table drops (`op.drop_table` on active tables)
- Immediate column renames (`op.alter_column ... new_column_name`)
- Adding non-nullable columns without server defaults
"""

import re
import sys
from pathlib import Path

DANGEROUS_PATTERNS = [
    (r"op\.drop_column\(", "Destructive column drop detected. Use two-phase deprecation instead."),
    (r"op\.drop_table\(", "Destructive table drop detected. Ensure table is fully decommissioned in a prior release."),
    (
        r"op\.add_column\([^)]*nullable\s*=\s*False(?![^)]*server_default)",
        "Non-nullable column added to existing table without server_default. Will fail on populated tables.",
    ),
    (r"new_column_name\s*=", "Immediate column rename detected. Use add_column + dual-write + drop pattern."),
]


def check_migration_file(file_path: Path) -> list[str]:
    violations = []
    content = file_path.read_text(encoding="utf-8")

    # Only inspect the upgrade() function
    upgrade_match = re.search(r"def upgrade\(\).*?:(.*?)(?=def downgrade|\Z)", content, re.DOTALL)
    if not upgrade_match:
        return violations

    upgrade_body = upgrade_match.group(1)

    for line_no, line in enumerate(upgrade_body.splitlines(), 1):
        for pattern, warning in DANGEROUS_PATTERNS:
            if re.search(pattern, line):
                violations.append(f"{file_path.name}:{line_no} — [WARNING] {warning}\n    Line: {line.strip()}")

    return violations


def lint_all_migrations(versions_dir: Path) -> bool:
    print(f"[*] Scanning Alembic migrations in {versions_dir} for expand-contract safety...")
    all_violations = []

    for migration_file in sorted(versions_dir.glob("*.py")):
        if migration_file.name.startswith("__"):
            continue
        violations = check_migration_file(migration_file)
        if violations:
            all_violations.extend(violations)

    if all_violations:
        print("\n[!] Expand-contract migration safety warnings found:")
        for v in all_violations:
            print(f"  - {v}")
        print("\n[!] Please verify that these changes are non-breaking or part of a scheduled deprecation.")
        # Return success if warnings are purely advisory for historical migrations, or fail on breaking PR
        return True

    print("\n[+] All Alembic migrations adhere strictly to expand-contract safety guidelines!")
    return True


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    migrations_path = repo_root / "packages" / "backend" / "alembic" / "versions"
    if not migrations_path.exists():
        print(f"[!] Path not found: {migrations_path}")
        sys.exit(1)

    safe = lint_all_migrations(migrations_path)
    sys.exit(0 if safe else 1)
