"""
Security and Input Validation Module
Provides sanitization, validation routines, and protection against XSS and injection attacks.
"""

import re
import html

# Allowed SKU pattern: Alphanumeric, underscores, hyphens (length 3 to 40)
SKU_PATTERN = re.compile(r'^[A-Za-z0-9_-]{3,40}$')

# Allowed Barcode pattern: Alphanumeric, digits (length 4 to 48)
BARCODE_PATTERN = re.compile(r'^[A-Za-z0-9]{4,48}$')

# HTML/Script tag detection regex
HTML_TAG_PATTERN = re.compile(r'<[^>]*>')

def sanitize_text(text: str, max_length: int = 150) -> str:
    """
    Sanitizes user string inputs by stripping HTML tags, trimming,
    and escaping dangerous characters to neutralize XSS vulnerabilities.
    """
    if text is None:
        return ""
    # Strip HTML tags
    clean_text = HTML_TAG_PATTERN.sub('', str(text))
    # Escape remaining entities
    clean_text = html.escape(clean_text)
    # Trim and clamp length
    clean_text = clean_text.strip()[:max_length]
    return clean_text

def validate_sku(sku: str) -> tuple[bool, str]:
    """
    Validates that a SKU conforms to strict alphanumeric/hyphen conventions.
    """
    if not sku:
        return False, "SKU cannot be blank."
    clean_sku = str(sku).strip().upper()
    if not SKU_PATTERN.match(clean_sku):
        return False, "SKU must be 3-40 characters containing only letters, numbers, hyphens (-), and underscores (_)."
    return True, clean_sku

def validate_barcode(barcode: str) -> tuple[bool, str]:
    """
    Validates barcode format.
    """
    if not barcode:
        return True, ""  # Optional barcode
    clean_bc = str(barcode).strip()
    if not BARCODE_PATTERN.match(clean_bc):
        return False, "Barcode must be 4-48 alphanumeric characters."
    return True, clean_bc

def validate_numeric(value, field_name: str, min_val: float = 0.0, max_val: float = 1e9, is_integer: bool = False) -> tuple[bool, str, float]:
    """
    Validates numeric values to prevent negative stock, prices, or lead times.
    """
    try:
        if is_integer:
            num = int(value)
        else:
            num = float(value)
    except (ValueError, TypeError):
        return False, f"'{field_name}' must be a valid {'integer' if is_integer else 'number'}.", 0.0

    if num < min_val:
        return False, f"'{field_name}' cannot be less than {min_val}.", 0.0
    if num > max_val:
        return False, f"'{field_name}' exceeds maximum allowed threshold ({max_val:,}).", 0.0

    return True, "", num
