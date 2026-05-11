"""Narrare Architecture Constraint Checker — shared types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class Violation:
    file: Path
    line: int
    rule: str
    detail: str
    approved: bool = False
    approval_reason: str = ""


@dataclass
class CheckResult:
    violations: list[Violation] = field(default_factory=list[Violation])
    approved_exceptions: list[Violation] = field(default_factory=list[Violation])
    files_checked: int = 0
