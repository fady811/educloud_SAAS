"""Shared validators (§18.6, INV-119) — phone, subdomain, color, Arabic text, HTML sanitizer."""
from __future__ import annotations

import re

import nh3
from django.core.exceptions import ValidationError

# ---------------------------------------------------------------------------
# SANITIZER_POLICY — the one allowlist (INV-119, §18.6)
# ---------------------------------------------------------------------------

ALLOWED_TAGS = {
    "a", "b", "blockquote", "br", "code", "em", "h1", "h2", "h3",
    "h4", "h5", "h6", "hr", "i", "img", "li", "ol", "p", "pre",
    "s", "strong", "sub", "sup", "table", "tbody", "td", "th", "thead",
    "tr", "u", "ul",
}

ALLOWED_ATTRIBUTES = {
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "width", "height"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
    "*": {"class", "dir"},  # dir for RTL Arabic support
}

SANITIZER_POLICY = {"tags": ALLOWED_TAGS, "attributes": ALLOWED_ATTRIBUTES}


def sanitize_html(html: str) -> str:
    """Sanitize HTML using nh3/ammonia (INV-119). Always called before storing rich text."""
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
    )


# ---------------------------------------------------------------------------
# Phone validation (E.164, Egyptian numbers as +20…)
# ---------------------------------------------------------------------------

_PHONE_RE = re.compile(r"^\+\d{7,15}$")
_EGYPTIAN_PHONE_RE = re.compile(r"^\+201[0-9]{9}$")


def normalize_phone(phone: str) -> str:
    """Normalize Egyptian phone numbers to E.164."""
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("01") and len(phone) == 11:
        phone = "+2" + phone
    elif phone.startswith("201") and not phone.startswith("+"):
        phone = "+" + phone
    return phone


def validate_phone(value: str) -> None:
    if not _PHONE_RE.match(value):
        raise ValidationError("Phone must be in E.164 format, e.g. +201012345678.")


# ---------------------------------------------------------------------------
# Subdomain validation (REQ-WS-13)
# ---------------------------------------------------------------------------

_SUBDOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{1,30}[a-z0-9])$")

RESERVED_SUBDOMAINS = frozenset({
    "www", "api", "admin", "app", "static", "mail", "smtp", "ftp",
    "educloud", "support", "help", "status", "blog", "cdn",
})


def validate_subdomain(value: str) -> None:
    if not _SUBDOMAIN_RE.match(value):
        raise ValidationError(
            "Subdomain must be 3–32 lowercase alphanumeric characters or hyphens, "
            "starting and ending with a letter or digit."
        )
    if value in RESERVED_SUBDOMAINS:
        raise ValidationError(f"'{value}' is a reserved subdomain.")


# ---------------------------------------------------------------------------
# Color validation (#RRGGBB)
# ---------------------------------------------------------------------------

_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def validate_hex_color(value: str) -> None:
    if not _COLOR_RE.match(value):
        raise ValidationError("Color must be in #RRGGBB format.")
