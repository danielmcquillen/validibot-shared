"""Unit tests for the canonical SVRL parser (ADR-2026-07-01, D3/D10).

``validibot_shared.schematron.svrl`` is the pure SVRL → findings/summary
parser both consumers rely on — the validator backend container (parsing
Saxon's SVRL into ``SchematronOutputs``) and the Django app (fixture and
round-trip tests). These tests feed it canned SVRL documents and pin the
D3/D10 contract:

- ``svrl:failed-assert`` AND ``svrl:successful-report`` are active findings
  handled identically — element type never drives severity.
- Severity resolves ``@flag`` → ``@role`` → fail-closed ERROR, so nothing
  publisher-authored is silently downgraded.
- ``svrl:fired-rule`` counts rules/contexts evaluated, never assertions.
- The ``finding_rule_ids_by_severity`` map is the pinned CEL contract
  ({rule_id: severity}, most severe wins).
- Truncation keeps ERROR findings first and is always explicit, while the
  aggregate counts still reflect the FULL totals.

Different Schematron compilers emit slightly different SVRL dialects, so the
parser must be defensive — the un-namespaced-SVRL test guards that.
"""

from __future__ import annotations

import pytest

from validibot_shared.schematron.svrl import (
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    SvrlParseError,
    parse_svrl,
)

# Named test values (avoid magic literals in assertions).
TRUNCATION_CAP = 2
TOTAL_FINDINGS_FOR_TRUNCATION = 5
EXPECTED_SUPPRESSED = TOTAL_FINDINGS_FOR_TRUNCATION - TRUNCATION_CAP
EXPECTED_FIRED_RULES = 2
ERRORS_IN_TRUNCATION_BODY = 2
WARNINGS_IN_TRUNCATION_BODY = 2


def _svrl(body: str) -> str:
    """Wrap finding elements in a minimal schematron-output document."""
    return (
        '<svrl:schematron-output xmlns:svrl="http://purl.oclc.org/dsdl/svrl">'
        f"{body}"
        "</svrl:schematron-output>"
    )


def _failed_assert(
    *,
    rule_id: str = "VB-X",
    flag: str = "",
    role: str = "",
    location: str = "/Invoice",
    text: str = "Something failed.",
) -> str:
    attrs = f' id="{rule_id}" location="{location}"'
    if flag:
        attrs += f' flag="{flag}"'
    if role:
        attrs += f' role="{role}"'
    return (
        f"<svrl:failed-assert{attrs}>"
        f"<svrl:text>{text}</svrl:text>"
        "</svrl:failed-assert>"
    )


# ── Severity resolution: @flag → @role → fail-closed ERROR ──────────────────


def test_failed_assert_flag_fatal_maps_to_error():
    """flag="fatal" resolves to ERROR and id/location survive the mapping.

    The rule id and location are the whole value proposition (D10): they make
    findings actionable and cross-referenceable against the published rules.
    """
    summary = parse_svrl(
        _svrl(
            _failed_assert(
                rule_id="VB-CO-15",
                flag="fatal",
                location="/Invoice/LegalMonetaryTotal",
            ),
        ),
    )

    assert summary.error_count == 1
    assert not summary.passed
    finding = summary.findings[0]
    assert finding.rule_id == "VB-CO-15"
    assert finding.severity == SEVERITY_ERROR
    assert finding.location == "/Invoice/LegalMonetaryTotal"
    assert finding.flag == "fatal"


def test_successful_report_is_an_active_finding_handled_identically():
    """A svrl:successful-report with flag="fatal" is an ERROR finding.

    This is the D3 rule the naive implementation gets wrong: a ``<report>``
    can carry a publisher-authored *error*, so the element type must never
    drive severity — only @flag/@role do.
    """
    summary = parse_svrl(
        _svrl(
            '<svrl:successful-report id="VB-R-01" flag="fatal" location="/a">'
            "<svrl:text>Reported error.</svrl:text>"
            "</svrl:successful-report>",
        ),
    )

    assert summary.error_count == 1
    assert summary.findings[0].severity == SEVERITY_ERROR
    assert summary.findings[0].element == "successful-report"


def test_role_is_the_fallback_when_flag_is_absent():
    """@role maps warning→WARNING and information→INFO when @flag is missing.

    The official packs use both spellings families (warn/warning,
    info/information); the resolver accepts them all.
    """
    summary = parse_svrl(
        _svrl(
            _failed_assert(rule_id="VB-W", role="warning")
            + _failed_assert(rule_id="VB-I", role="information"),
        ),
    )

    by_id = {f.rule_id: f for f in summary.findings}
    assert by_id["VB-W"].severity == SEVERITY_WARNING
    assert by_id["VB-I"].severity == SEVERITY_INFO
    assert summary.warning_count == 1
    assert summary.info_count == 1
    # Warnings/info alone never fail a Schematron step (D3).
    assert summary.passed


def test_flag_wins_over_role():
    """When both attributes exist, @flag is authoritative (D3 resolution order)."""
    summary = parse_svrl(
        _svrl(_failed_assert(rule_id="VB-B", flag="fatal", role="warning")),
    )
    assert summary.findings[0].severity == SEVERITY_ERROR


def test_fail_closed_to_error_when_neither_flag_nor_role_present():
    """A finding with no severity attributes fail-closes to ERROR.

    Fail-open (defaulting to INFO) would silently downgrade publisher-authored
    rules whose pack relies on a default phase severity — the exact bug class
    D3 forbids.
    """
    summary = parse_svrl(_svrl(_failed_assert(rule_id="VB-N")))
    assert summary.findings[0].severity == SEVERITY_ERROR
    assert summary.error_count == 1


# ── Message text extraction ──────────────────────────────────────────────────


def test_message_text_collapses_whitespace_and_inline_markup():
    """svrl:text content survives inline markup and layout whitespace.

    Publisher messages contain inline elements (emph/span) and authored
    newlines; the human-readable message must come out flat and readable.
    """
    summary = parse_svrl(
        _svrl(
            '<svrl:failed-assert id="VB-T" flag="fatal" location="/a">'
            "<svrl:text>Total \n   must <emph>equal</emph>\n sum.</svrl:text>"
            "</svrl:failed-assert>",
        ),
    )
    assert summary.findings[0].message == "Total must equal sum."


# ── fired-rule counting ──────────────────────────────────────────────────────


def test_fired_rule_count_counts_rules_not_assertions():
    """svrl:fired-rule elements count evaluated rules/contexts — nothing else.

    The review explicitly renamed this signal away from "assertion count":
    a fired rule is a context the engine evaluated, not an assertion that
    failed. Two fired rules + one failed assert must yield 2 / 1.
    """
    summary = parse_svrl(
        _svrl(
            '<svrl:fired-rule context="/Invoice"/>'
            '<svrl:fired-rule context="/Invoice/Total"/>'
            + _failed_assert(rule_id="VB-1", flag="fatal"),
        ),
    )
    assert summary.fired_rule_count == EXPECTED_FIRED_RULES
    assert summary.error_count == 1


# ── The finding_rule_ids_by_severity map (CEL contract) ─────────────────────


def test_rule_id_map_shape_and_most_severe_wins():
    """The map is {rule_id: severity} and the most severe occurrence wins.

    This is the pinned D2 CEL contract: key membership tests
    (``"VB-D" in o.finding_rule_ids_by_severity``) and severity-aware gates
    both depend on this exact shape. A rule firing at WARNING in one context
    and ERROR in another must surface as ERROR.
    """
    summary = parse_svrl(
        _svrl(
            _failed_assert(rule_id="VB-D", role="warning")
            + _failed_assert(rule_id="VB-D", flag="fatal")
            + _failed_assert(rule_id="VB-W", role="warning"),
        ),
    )
    assert summary.finding_rule_ids_by_severity == {
        "VB-D": SEVERITY_ERROR,
        "VB-W": SEVERITY_WARNING,
    }


# ── Truncation (D10: capped, never silent) ───────────────────────────────────


def test_truncation_keeps_errors_first_and_counts_stay_full():
    """Capping keeps ERROR findings first and records the suppressed count.

    Two invariants: (1) the kept findings are ordered ERROR → WARNING → INFO
    so the most actionable rows survive; (2) the aggregate counts reflect the
    FULL document, so "clean-ish" and "thousands of errors, capped" can never
    look the same to a CEL gate.
    """
    body = (
        _failed_assert(rule_id="VB-I1", role="info")
        + _failed_assert(rule_id="VB-W1", role="warning")
        + _failed_assert(rule_id="VB-E1", flag="fatal")
        + _failed_assert(rule_id="VB-E2", flag="error")
        + _failed_assert(rule_id="VB-W2", role="warning")
    )
    summary = parse_svrl(_svrl(body), max_findings=TRUNCATION_CAP)

    assert summary.findings_truncated
    assert summary.findings_suppressed_count == EXPECTED_SUPPRESSED
    assert len(summary.findings) == TRUNCATION_CAP
    # ERROR findings survive the cap ahead of warnings/info.
    assert {f.rule_id for f in summary.findings} == {"VB-E1", "VB-E2"}
    # Aggregates are computed pre-cap.
    assert summary.error_count == ERRORS_IN_TRUNCATION_BODY
    assert summary.warning_count == WARNINGS_IN_TRUNCATION_BODY
    assert summary.info_count == 1
    assert len(summary.finding_rule_ids_by_severity) == TOTAL_FINDINGS_FOR_TRUNCATION


# ── Dialect tolerance + input guards ─────────────────────────────────────────


def test_unnamespaced_svrl_is_tolerated():
    """SVRL without the namespace still parses (compiler-dialect defensiveness).

    Some Schematron toolchains emit un-namespaced SVRL; the parser matches on
    local names so those reports still map to findings.
    """
    summary = parse_svrl(
        "<schematron-output>"
        '<fired-rule context="/a"/>'
        '<failed-assert id="VB-U" flag="fatal" location="/a">'
        "<text>Unnamespaced.</text>"
        "</failed-assert>"
        "</schematron-output>",
    )
    assert summary.fired_rule_count == 1
    assert summary.findings[0].rule_id == "VB-U"


def test_empty_and_malformed_svrl_raise():
    """Empty or non-XML input raises SvrlParseError rather than passing.

    Silently returning an empty summary for garbage input would read as
    "zero findings" — i.e. a pass — which is exactly the fail-open behaviour
    the D9 taxonomy exists to prevent.
    """
    with pytest.raises(SvrlParseError):
        parse_svrl("")
    with pytest.raises(SvrlParseError):
        parse_svrl("this is not XML <")
