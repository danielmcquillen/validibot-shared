"""Schematron Advanced validator envelopes and models."""

from validibot_shared.schematron.envelopes import (
    ENGINE_ERROR_ARTIFACT_MISMATCH,
    ENGINE_ERROR_BACKEND_UNAVAILABLE,
    ENGINE_STATUS_ERROR,
    ENGINE_STATUS_OK,
    ENGINE_STATUS_TIMEOUT,
    QUERY_BINDING_XSLT1,
    QUERY_BINDING_XSLT2,
    SchematronFinding,
    SchematronInputEnvelope,
    SchematronInputs,
    SchematronOutputEnvelope,
    SchematronOutputs,
    build_schematron_input_envelope,
)
from validibot_shared.schematron.svrl import (
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    SvrlFinding,
    SvrlParseError,
    SvrlSummary,
    parse_svrl,
)

__all__ = [
    "ENGINE_ERROR_ARTIFACT_MISMATCH",
    "ENGINE_ERROR_BACKEND_UNAVAILABLE",
    "ENGINE_STATUS_ERROR",
    "ENGINE_STATUS_OK",
    "ENGINE_STATUS_TIMEOUT",
    "QUERY_BINDING_XSLT1",
    "QUERY_BINDING_XSLT2",
    "SEVERITY_ERROR",
    "SEVERITY_INFO",
    "SEVERITY_WARNING",
    "SchematronFinding",
    "SchematronInputEnvelope",
    "SchematronInputs",
    "SchematronOutputEnvelope",
    "SchematronOutputs",
    "SvrlFinding",
    "SvrlParseError",
    "SvrlSummary",
    "build_schematron_input_envelope",
    "parse_svrl",
]
