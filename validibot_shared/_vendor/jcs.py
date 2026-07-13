"""
Vendored RFC 8785 JSON Canonicalization Scheme (JCS) implementation.

Vendored from: jcs 0.2.1 (https://pypi.org/project/jcs/)
Original author: WebPKI.org (http://webpki.org)
License: Apache License, Version 2.0

Copyright 2006-2019 WebPKI.org (http://webpki.org).

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

This file combines _jcs.py and ntoj.py from the original package
into a single module for simplicity.  The public API is the single
``canonicalize(obj)`` function.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# ntoj: Convert Python float/int into an ES6/V8-compatible JSON string
# ---------------------------------------------------------------------------


def _convert_to_es6_format(value):
    """Convert a Python number to its ES6/V8 canonical string representation.

    This handles the tricky parts of RFC 8785 number serialization:
    no trailing zeros, no positive sign, specific exponent formatting,
    and special handling for zero and small/large values.
    """
    fvalue = float(value)

    # Zero is a special case.  Handles "-0" as well.
    if fvalue == 0:
        return "0"

    py_double = str(fvalue)

    # Catch "inf" and "nan" values
    if "n" in py_double:
        msg = f"Invalid JSON number: {py_double}"
        raise ValueError(msg)

    # Save sign separately
    py_sign = ""
    if py_double.startswith("-"):
        py_sign = "-"
        py_double = py_double[1:]

    # Extract exponent if present
    py_exp_str = ""
    py_exp_val = 0
    q = py_double.find("e")
    if q > 0:
        py_exp_str = py_double[q:]
        if py_exp_str[2:3] == "0":
            # Suppress leading zero on exponents
            py_exp_str = py_exp_str[:2] + py_exp_str[3:]
        py_double = py_double[:q]
        py_exp_val = int(py_exp_str[1:])

    # Split number into first + dot + last
    py_first = py_double
    py_dot = ""
    py_last = ""
    q = py_double.find(".")
    if q > 0:
        py_dot = "."
        py_first = py_double[:q]
        py_last = py_double[q + 1 :]

    # Always remove trailing .0
    if py_last == "0":
        py_dot = ""
        py_last = ""

    if 0 < py_exp_val < 21:
        # Integers shown as-is with up to 21 digits
        py_first += py_last
        py_last = ""
        py_dot = ""
        py_exp_str = ""
        q = py_exp_val - len(py_first)
        while q >= 0:
            q -= 1
            py_first += "0"
    elif -7 < py_exp_val < 0:
        # Small numbers shown as 0.etc with e-6 as lower limit
        py_last = py_first + py_last
        py_first = "0"
        py_dot = "."
        py_exp_str = ""
        q = py_exp_val
        while q < -1:
            q += 1
            py_last = "0" + py_last

    return py_sign + py_first + py_dot + py_last + py_exp_str


# ---------------------------------------------------------------------------
# _jcs: JCS-compatible JSON encoder
# ---------------------------------------------------------------------------

_ESCAPE = re.compile(r'[\x00-\x1f\\"\b\f\n\r\t]')
_ESCAPE_DCT = {
    "\\": "\\\\",
    '"': '\\"',
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}
for _i in range(0x20):
    _ESCAPE_DCT.setdefault(chr(_i), f"\\u{_i:04x}")


def _encode_basestring(s):
    """Return a JSON representation of a Python string (non-ASCII preserved)."""

    def replace(match):
        return _ESCAPE_DCT[match.group(0)]

    return '"' + _ESCAPE.sub(replace, s) + '"'


def _serialize(obj):
    """Recursively serialize a Python object to a JCS-canonical JSON string.

    Keys are sorted by UTF-16BE byte order per RFC 8785 §3.2.3.
    """
    if isinstance(obj, str):
        return _encode_basestring(obj)
    if obj is None:
        return "null"
    if obj is True:
        return "true"
    if obj is False:
        return "false"
    if isinstance(obj, int):
        # RFC 8785 §3.2.2.3 mandates that JSON integers be emitted as their
        # exact decimal literal.  We must NOT route ``int`` through the ES6
        # number formatter, because that helper begins ``float(value)`` which
        # loses precision for any integer whose magnitude exceeds 2**53
        # (the largest exactly-representable IEEE-754 double).  Corrupting the
        # value here would silently break cross-language canonical-hash
        # reproducibility (e.g. signature verification against a non-Python
        # signer).  ``str(int)`` already yields the canonical literal: no
        # leading zeros, a single optional ``-`` sign, and no ``+``/exponent.
        # ``bool`` is handled above (it is a subclass of ``int``) so it never
        # reaches this branch and still serializes as ``true``/``false``.
        return str(obj)
    if isinstance(obj, float):
        return _convert_to_es6_format(obj)
    if isinstance(obj, (list, tuple)):
        return "[" + ",".join(_serialize(v) for v in obj) + "]"
    if isinstance(obj, dict):
        items = sorted(obj.items(), key=lambda kv: kv[0].encode("utf-16-be"))
        return (
            "{"
            + ",".join(_encode_basestring(k) + ":" + _serialize(v) for k, v in items)
            + "}"
        )
    msg = f"Object of type '{type(obj).__name__}' is not JSON serializable"
    raise TypeError(msg)


def canonicalize(obj: object) -> bytes:
    """Serialize a Python object to RFC 8785 canonical JSON bytes.

    Args:
        obj: A JSON-serializable Python object (dict, list, str,
            int, float, bool, None).

    Returns:
        UTF-8 encoded canonical JSON bytes.
    """
    return _serialize(obj).encode("utf-8")
