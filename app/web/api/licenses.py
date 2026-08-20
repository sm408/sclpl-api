"""Licenses API route.

Reads dependency license information from the pnpm lockfile and
pyproject.toml to provide a combined view of all project dependencies.
Uses regex parsing instead of PyYAML to avoid an extra dependency.
"""

from __future__ import annotations

import logging
import re
import tomllib
from pathlib import Path

from fastapi import APIRouter

from app.web.dto import CamelModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/licenses", tags=["licenses"])


class LicenseEntry(CamelModel):
    name: str
    version: str
    license: str = "UNKNOWN"
    source: str = "npm"  # "npm" or "python"


class LicenseListResponse(CamelModel):
    items: list[LicenseEntry]
    total: int


def _read_pnpm_licenses(web_dir: Path) -> list[LicenseEntry]:
    """Extract license info from pnpm-lock.yaml using regex parsing."""
    lockfile = web_dir / "pnpm-lock.yaml"
    if not lockfile.exists():
        return []

    entries: list[LicenseEntry] = []
    try:
        text = lockfile.read_text(encoding="utf-8")

        # Match package entries: lines like "  /package@version:" followed by indented properties
        # Pattern: package path line, then version/license indented below
        pkg_pattern = re.compile(
            r"^\s+'?/?([^@\s'']+?)@([^@\s':]+)'?:\s*$", re.MULTILINE
        )
        license_pattern = re.compile(r"^\s+license:\s*(.+)$", re.MULTILINE)
        version_pattern = re.compile(r"^\s+version:\s*(.+)$", re.MULTILINE)
        name_pattern = re.compile(r"^\s+name:\s*(.+)$", re.MULTILINE)

        # Split into package blocks
        lines = text.split("\n")
        current_pkg_path = ""
        current_name = ""
        current_version = ""
        current_license = ""
        in_packages = False
        seen: set[str] = set()

        for line in lines:
            # Detect packages section
            if line.strip() == "packages:":
                in_packages = True
                continue

            if not in_packages:
                continue

            # Top-level package entry (2 spaces, starts with /)
            pkg_match = re.match(r"^\s{2}'?/?([^@\s'']+?)@([^@\s':]+)'?:\s*$", line)
            if pkg_match:
                # Save previous entry
                if current_name and current_version:
                    key = f"{current_name}@{current_version}"
                    if key not in seen:
                        seen.add(key)
                        entries.append(LicenseEntry(
                            name=current_name,
                            version=current_version,
                            license=current_license or "UNKNOWN",
                            source="npm",
                        ))

                current_pkg_path = pkg_match.group(0)
                current_name = ""
                current_version = ""
                current_license = ""
                continue

            # Indented property within a package block
            if current_pkg_path:
                name_match = re.match(r"^\s{4}name:\s*(.+)$", line)
                if name_match:
                    current_name = name_match.group(1).strip().strip("'\"")
                    continue

                ver_match = re.match(r"^\s{4}version:\s*(.+)$", line)
                if ver_match:
                    current_version = ver_match.group(1).strip().strip("'\"")
                    continue

                lic_match = re.match(r"^\s{4}license:\s*(.+)$", line)
                if lic_match:
                    current_license = lic_match.group(1).strip().strip("'\"")
                    continue

        # Save last entry
        if current_name and current_version:
            key = f"{current_name}@{current_version}"
            if key not in seen:
                seen.add(key)
                entries.append(LicenseEntry(
                    name=current_name,
                    version=current_version,
                    license=current_license or "UNKNOWN",
                    source="npm",
                ))

    except Exception:
        logger.warning("Failed to parse pnpm-lock.yaml", exc_info=True)

    return entries


def _read_python_licenses(project_root: Path) -> list[LicenseEntry]:
    """Extract Python dependency info from pyproject.toml."""
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        return []

    entries: list[LicenseEntry] = []
    try:
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)

        deps = data.get("project", {}).get("dependencies", [])
        for dep in deps:
            # Simple parsing: "package>=1.0" -> name=package, version=>=1.0
            for sep in [">=", "<=", "==", "~=", "!=", ">", "<"]:
                if sep in dep:
                    name, version = dep.split(sep, 1)
                    entries.append(LicenseEntry(
                        name=name.strip(),
                        version=f"{sep}{version.strip()}",
                        license="See PyPI",
                        source="python",
                    ))
                    break
            else:
                entries.append(LicenseEntry(
                    name=dep.strip(),
                    version="",
                    license="See PyPI",
                    source="python",
                ))
    except Exception:
        logger.warning("Failed to parse pyproject.toml", exc_info=True)

    return entries


@router.get("", response_model=LicenseListResponse)
async def list_licenses() -> LicenseListResponse:
    """List all dependency licenses."""
    project_root = Path(__file__).parent.parent.parent.parent
    web_dir = project_root / "web"

    npm_entries = _read_pnpm_licenses(web_dir)
    py_entries = _read_python_licenses(project_root)

    all_entries = sorted(npm_entries + py_entries, key=lambda e: (e.source, e.name))
    return LicenseListResponse(items=all_entries, total=len(all_entries))
