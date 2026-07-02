"""SVRL report parsing — findings + signal summary (ADR-2026-07-01, D3/D10).

SVRL (Schematron Validation Report Language, ISO/IEC 19757-3) is the XML
report a Schematron run produces. This module parses an SVRL document into a
:class:`SvrlSummary`: the individual findings plus the aggregate counts and
the ``finding_rule_ids_by_severity`` map that feed the validator's ``o.*``
signal surface.

Design rules carried from the ADR:

- **Both ``svrl:failed-assert`` and ``svrl:successful-report`` are active
  findings**, handled identically. A ``<report>`` can carry a
  publisher-authored error, so the element type must never drive severity.
- **Severity resolves ``@flag`` → ``@role`` → fail-closed ``ERROR``.**
  ``fatal``/``error`` → ERROR, ``warning``/``warn`` → WARNING,
  ``info``/``information`` → INFO. A finding with neither attribute is
  fail-closed to ERROR and logged for pack-curation review — nothing
  publisher-authored is silently downgraded.
- **``svrl:fired-rule`` counts rules/contexts evaluated**, *not* assertions
  that fired — surfaced as ``fired_rule_count``, never an "assertion count".
- **Findings are volume-capped, never silently** (D10): when a document blows
  ``max_findings`` the parser keeps the first N ordered ERROR → WARNING →
  INFO (document order within a severity) and reports how many were
  suppressed. The caller renders the explicit truncation finding.

This is the CANONICAL parser for the whole pipeline: the validator backend
container parses Saxon's SVRL with it to build ``SchematronOutputs``, and the
Django app re-exports it (``validibot.validations.validators.schematron.svrl``)
for its fixture/round-trip tests. It lives beside the envelope models because
it defines the same protocol boundary — SVRL in, the D2 signal contract out.
Deliberately framework-free: plain-string severities, ``defusedxml``-only
parsing, no Django.

Different Schematron compilers emit slightly different SVRL dialects; parsing
is defensive (namespace-tolerant, attribute-tolerant) and covered by the
unit tests in this repo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from defusedxml import ElementTree as SafeET
from defusedxml.common import (
    DTDForbidden,
    EntitiesForbidden,
    ExternalReferenceForbidden,
)

logger = logging.getLogger(__name__)

# The SVRL namespace from ISO/IEC 19757-3. Some tools emit un-namespaced
# SVRL; matching is namespace-tolerant (see _local_name).
SVRL_NS = "http://purl.oclc.org/dsdl/svrl"

# Plain-string severities (shared-envelope compatible; Django maps them to
# its own Severity enum in validator.py).
SEVERITY_ERROR = "ERROR"
SEVERITY_WARNING = "WARNING"
SEVERITY_INFO = "INFO"

# Rank used both for the "most severe wins" duplicate-rule-id rule and the
# ERROR → WARNING → INFO truncation ordering (D10).
_SEVERITY_RANK = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 1, SEVERITY_INFO: 2}

# @flag / @role values → severity. Lowercased before lookup.
_SEVERITY_FROM_ATTR = {
    "fatal": SEVERITY_ERROR,
    "error": SEVERITY_ERROR,
    "warning": SEVERITY_WARNING,
    "warn": SEVERITY_WARNING,
    "info": SEVERITY_INFO,
    "information": SEVERITY_INFO,
}

# Default findings cap — mirrors SCHEMATRON_MAX_FINDINGS in security.py
# (kept as a literal here so this module stays import-light and pure).
DEFAULT_MAX_FINDINGS = 500


class SvrlParseError(ValueError):
    """Raised when SVRL content cannot be parsed as XML."""


@dataclass(frozen=True)
class SvrlFinding:
    """One active SVRL finding (a failed assert or a successful report).

    ``rule_id`` is the publisher's native identifier (``BR-CO-15``,
    ``PEPPOL-EN16931-R010``, or a fixture's ``VB-*`` id) taken from the
    element's ``@id``; it becomes ``ValidationFinding.code`` downstream (D10).
    ``flag`` and ``role`` carry the raw attributes for provenance.
    """

    rule_id: str
    message: str
    severity: str  # SEVERITY_ERROR | SEVERITY_WARNING | SEVERITY_INFO
    location: str = ""  # SVRL @location XPath into the submitted document
    flag: str = ""
    role: str = ""
    element: str = ""  # "failed-assert" | "successful-report"


@dataclass
class SvrlSummary:
    """Parsed SVRL: findings plus the aggregate ``o.*`` signal values.

    ``finding_rule_ids_by_severity`` is the D2-pinned CEL map contract:
    ``{rule_id: severity_string}`` so ``"BR-CO-15" in o.finding_rule_ids_by_severity``
    is key membership and ``o.finding_rule_ids_by_severity["BR-CO-15"] == "ERROR"``
    is a severity-aware gate. When one rule id fires at several severities,
    the most severe wins.
    """

    findings: list[SvrlFinding] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    fired_rule_count: int = 0
    finding_rule_ids_by_severity: dict[str, str] = field(default_factory=dict)
    findings_truncated: bool = False
    findings_suppressed_count: int = 0

    @property
    def passed(self) -> bool:
        """A Schematron run passes iff there are no ERROR-level findings (D3)."""
        return self.error_count == 0


def parse_svrl(
    svrl_content: str | bytes,
    *,
    max_findings: int = DEFAULT_MAX_FINDINGS,
) -> SvrlSummary:
    """Parse an SVRL document into findings + the signal summary.

    Args:
        svrl_content: The SVRL report as produced by a Schematron run
            (lxml.isoschematron for XSLT-1.0 fixtures; Saxon in production).
        max_findings: Volume cap (D8/D10). The kept findings are the first N
            ordered ERROR → WARNING → INFO; the summary records how many were
            suppressed so the caller can surface an explicit truncation
            finding — truncation is never silent.

    Raises:
        SvrlParseError: If the content is empty or not well-formed XML.
            SVRL comes from our own engine, but defusedxml is used anyway as
            defence in depth.
    """
    if not svrl_content or not str(svrl_content).strip():
        raise SvrlParseError("Empty SVRL content.")

    raw = (
        svrl_content.encode("utf-8") if isinstance(svrl_content, str) else svrl_content
    )
    try:
        root = SafeET.fromstring(raw, forbid_dtd=True)
    except (EntitiesForbidden, ExternalReferenceForbidden, DTDForbidden) as exc:
        raise SvrlParseError(
            "SVRL contains forbidden constructs (entities/DTD).",
        ) from exc
    except SafeET.ParseError as exc:
        raise SvrlParseError(f"Invalid SVRL XML: {exc}") from exc

    summary = SvrlSummary()
    all_findings: list[SvrlFinding] = []

    for element in root.iter():
        name = _local_name(element.tag)
        if name == "fired-rule":
            summary.fired_rule_count += 1
        elif name in ("failed-assert", "successful-report"):
            all_findings.append(_parse_finding(element, name))

    # Aggregate counts + the rule-id map over ALL findings (pre-cap): the
    # signal surface must reflect the true totals even when the persisted
    # findings list is truncated.
    for finding in all_findings:
        if finding.severity == SEVERITY_ERROR:
            summary.error_count += 1
        elif finding.severity == SEVERITY_WARNING:
            summary.warning_count += 1
        else:
            summary.info_count += 1

        if finding.rule_id:
            existing = summary.finding_rule_ids_by_severity.get(finding.rule_id)
            if (
                existing is None
                or _SEVERITY_RANK[finding.severity] < _SEVERITY_RANK[existing]
            ):
                summary.finding_rule_ids_by_severity[finding.rule_id] = finding.severity
        else:
            logger.warning(
                "SVRL %s finding has no @id; kept without a rule id (message=%r)",
                finding.element,
                finding.message[:120],
            )

    # Volume cap (D10): keep ERROR findings first, then WARNING, then INFO,
    # preserving document order within each severity band.
    if max_findings > 0 and len(all_findings) > max_findings:
        ordered = sorted(
            all_findings,
            key=lambda f: _SEVERITY_RANK[f.severity],
        )
        summary.findings = ordered[:max_findings]
        summary.findings_truncated = True
        summary.findings_suppressed_count = len(all_findings) - max_findings
        logger.warning(
            "SVRL findings truncated: kept %d of %d (cap=%d)",
            max_findings,
            len(all_findings),
            max_findings,
        )
    else:
        summary.findings = all_findings

    return summary


def _parse_finding(element, element_name: str) -> SvrlFinding:
    """Map one failed-assert / successful-report element to a finding.

    Severity resolution is the D3 chain: ``@flag`` first, then ``@role``,
    then fail-closed to ERROR with a log line for pack-curation review.
    """
    flag = (element.get("flag") or "").strip()
    role = (element.get("role") or "").strip()

    severity = _SEVERITY_FROM_ATTR.get(flag.lower())
    if severity is None:
        severity = _SEVERITY_FROM_ATTR.get(role.lower())
    if severity is None:
        severity = SEVERITY_ERROR
        rule_id_for_log = (element.get("id") or "").strip()
        logger.warning(
            "SVRL %s (id=%r) has no recognisable @flag/@role "
            "(flag=%r, role=%r); fail-closed to ERROR",
            element_name,
            rule_id_for_log,
            flag,
            role,
        )

    return SvrlFinding(
        rule_id=(element.get("id") or "").strip(),
        message=_finding_text(element),
        severity=severity,
        location=(element.get("location") or "").strip(),
        flag=flag,
        role=role,
        element=element_name,
    )


def _finding_text(element) -> str:
    """Extract the human-readable message from a finding's svrl:text child.

    Joins all descendant text of every ``svrl:text`` child (publisher
    messages may contain inline markup like ``<emph>``), collapsing internal
    whitespace — SVRL text is authored with layout newlines that mean nothing.
    """
    parts: list[str] = []
    for child in element:
        if _local_name(child.tag) == "text":
            parts.append(" ".join("".join(child.itertext()).split()))
    return " ".join(p for p in parts if p).strip()


def _local_name(tag: object) -> str:
    """Strip any XML namespace from a tag name (namespace-tolerant matching)."""
    text = str(tag)
    if text.startswith("{"):
        return text.split("}", 1)[1]
    return text
