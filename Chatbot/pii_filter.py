"""
pii_filter.py
=============
Detects personally-identifiable information (PII) in chat messages so the
chat_send view can reject them before they are stored.

Patterns covered
----------------
  - Email addresses          (e.g.  user@example.com)
  - Phone numbers            (various North-American and international formats)
  - Bank / account numbers   (6–17 consecutive digits, optionally space/dash separated)
"""

import re
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# Standard email  (RFC-5321 simplified)
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

# Phone numbers
#   Matches formats like:
#     416-555-0100   (416) 555-0100   +1 416 555 0100
#     +44 20 7946 0958   0044-20-7946-0958
#     1-800-555-0100   555.0100  etc.
_PHONE_RE = re.compile(
    r"""
    (?:
        # Optional country code  +1  or  001  or  0044
        (?:\+?\d{1,3}[\s.\-]?)?
        # Optional area code in parens or bare
        (?:\(?\d{2,4}\)?[\s.\-]?)?
        # 3-4 digit prefix
        \d{3,4}
        [\s.\-]
        # 4 digit suffix (allow 1 optional separator inside)
        \d{4}
        (?:[\s.\-]?\d{1,5})?  # optional extension
    )
    """,
    re.VERBOSE,
)

# Account / bank numbers
#   Six or more digits that appear as a contiguous block (optionally split by
#   spaces or hyphens every few digits — the pattern used by most account and
#   card number formats).
#   We require a word-boundary on each side so we don't fire on things like
#   plain years ("2024").
_ACCOUNT_RE = re.compile(
    r"""
    (?<!\d)            # no digit before
    \d{4,}             # first group: 4+ digits
    (?:[\s\-]\d{2,})+  # one or more separated groups (catches  1234 5678  or  1234-56789)
    (?!\d)             # no digit after
    |
    (?<!\d)
    \d{6,17}           # plain run of 6-17 digits  (6 = shortest account #)
    (?!\d)
    """,
    re.VERBOSE,
)

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class PIIMatch:
    kind: str          # 'email' | 'phone' | 'account_number'
    value: str         # the matched text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_pii(text: str) -> list[PIIMatch]:
    """
    Return a list of all PII found in *text*.
    An empty list means the message is clean.
    """
    found: list[PIIMatch] = []

    for m in _EMAIL_RE.finditer(text):
        found.append(PIIMatch(kind='email', value=m.group()))

    for m in _PHONE_RE.finditer(text):
        raw = m.group().strip()
        # Skip very short matches (lone 4-digit numbers are not phone numbers)
        digits_only = re.sub(r'\D', '', raw)
        if len(digits_only) >= 7:
            found.append(PIIMatch(kind='phone', value=raw))

    for m in _ACCOUNT_RE.finditer(text):
        raw = m.group().strip()
        digits_only = re.sub(r'\D', '', raw)
        # Only flag if not already covered by a phone match
        already = any(
            re.sub(r'\D', '', p.value) == digits_only
            for p in found if p.kind == 'phone'
        )
        if not already:
            found.append(PIIMatch(kind='account_number', value=raw))

    return found


def contains_pii(text: str) -> bool:
    """Convenience wrapper — returns True if any PII is found."""
    return bool(find_pii(text))


def pii_error_message(matches: list[PIIMatch]) -> str:
    """
    Build a human-readable error string listing the types of PII detected,
    without echoing the actual values back to the sender.
    """
    kinds = {m.kind for m in matches}
    labels = {
        'email':          'email address',
        'phone':          'phone number',
        'account_number': 'account / bank number',
    }
    found_labels = [labels[k] for k in ('email', 'phone', 'account_number') if k in kinds]

    if len(found_labels) == 1:
        detail = found_labels[0]
    elif len(found_labels) == 2:
        detail = f"{found_labels[0]} and {found_labels[1]}"
    else:
        detail = ", ".join(found_labels[:-1]) + f", and {found_labels[-1]}"

    return (
        f"Your message contains a {detail}. "
        "For your security, sharing personal contact or financial details "
        "through chat is not allowed on this platform."
    )
