"""Actionable errors: every problem names a file, an id, what is wrong, and what to do."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Problem:
    """One validation or lint finding."""

    file: str
    subject: str
    message: str
    hint: str = ""
    severity: str = "error"  # error | warn
    rule: str = ""

    def format(self, root: Path | None = None) -> str:
        """Human one-liner: ``file: [subject] message — hint``."""
        f = self.file
        if root is not None:
            try:
                f = str(Path(self.file).relative_to(root))
            except ValueError:
                pass
        tag = f" ({self.rule})" if self.rule else ""
        hint = f"\n    → {self.hint}" if self.hint else ""
        return f"{self.severity.upper()}{tag} {f}: [{self.subject}] {self.message}{hint}"

    def to_dict(self) -> dict[str, str]:
        """JSON-friendly form."""
        return {
            "severity": self.severity,
            "rule": self.rule,
            "file": self.file,
            "subject": self.subject,
            "message": self.message,
            "hint": self.hint,
        }


@dataclass
class Problems:
    """A growing list of findings; ``raise_if_any`` turns it into an exception."""

    items: list[Problem] = field(default_factory=list)

    def add(
        self,
        file: Path | str,
        subject: str,
        message: str,
        hint: str = "",
        severity: str = "error",
        rule: str = "",
    ) -> None:
        """Append a finding."""
        self.items.append(Problem(str(file), subject, message, hint, severity, rule))

    @property
    def errors(self) -> list[Problem]:
        """Only the blocking findings."""
        return [p for p in self.items if p.severity == "error"]

    @property
    def warnings(self) -> list[Problem]:
        """Only the non-blocking findings."""
        return [p for p in self.items if p.severity == "warn"]

    def __bool__(self) -> bool:
        return bool(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def raise_if_any(self) -> None:
        """Raise :class:`ModelError` if there is at least one error."""
        if self.errors:
            raise ModelError(self)


class N2FError(Exception):
    """Base class for all napkin2factory errors."""

    exit_code = 1


class ModelError(N2FError):
    """The product model failed to load or validate."""

    exit_code = 1

    def __init__(self, problems: Problems, summary: str = "the product model has problems") -> None:
        self.problems = problems
        super().__init__(summary)

    def __str__(self) -> str:
        return "\n".join(p.format() for p in self.problems.errors)


class EnvironmentProblem(N2FError):
    """Something about the machine, not the model (missing tool, bad directory)."""

    exit_code = 4


class GateBlocked(N2FError):
    """A gate (release, close) refused; the message says what to do."""

    exit_code = 3


class CheckFailed(N2FError):
    """``n2f check`` found at least one failing check."""

    exit_code = 2
