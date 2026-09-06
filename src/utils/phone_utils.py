import re
from typing import List

def normalize_phone(phone_str: str) -> str:
    """
    Normalizes a phone number to 0XXXXXXXXXX format (11 digits).
    Returns empty string if phone is invalid (< 7 digits or > 15 digits after normalization).
    """
    if not phone_str:
        return ""

    # Remove all non-digits
    digits = re.sub(r'\D', '', str(phone_str))

    if not digits:
        return ""

    # AC-5: Reject if too short (< 7 digits) or too long (> 15 digits)
    if len(digits) < 7 or len(digits) > 15:
        return ""

    # Handle Turkey prefixes
    if digits.startswith('90') and len(digits) == 12:
        return '0' + digits[2:]
    elif digits.startswith('0') and len(digits) == 11:
        return digits
    elif len(digits) == 10:
        return '0' + digits

    # If it starts with 5 and is 10 digits (already handled by len 10, but just in case)
    # or other cases, just return as is but we prefer the 0... format
    return digits

def get_phone_variants(phone: str) -> List[str]:
    """
    Generate 3 common phone variants: 0..., 5..., and 90...
    Used for matching against various system formats.
    """
    if not phone:
        return []
        
    # Clean digits
    digits = re.sub(r'\D', '', str(phone))
    
    # Determine the base 10-digit number (5xx xxx xxxx)
    base = ""
    if len(digits) == 10:
        base = digits
    elif len(digits) == 11 and digits.startswith('0'):
        base = digits[1:]
    elif len(digits) == 12 and digits.startswith('90'):
        base = digits[2:]
    else:
        # Fallback for non-standard lengths
        base = digits if len(digits) >= 10 else ""
        
    if not base:
        return [digits] if digits else []
        
    # Variants: 0..., base (5...), 90...
    return [f"0{base}", base, f"90{base}"]

def is_phone_in_list(phone: str, phone_list: List) -> bool:
    """
    Checks if a phone (in any variant) exists in a list of phones (also in any variant).
    AC-2, AC-6: Normalizes list items (handling dict entries with "phone" key and unnormalized strings).
    """
    if not phone or not phone_list:
        return False

    # Normalize the input phone
    input_variants = get_phone_variants(phone)

    # Build normalized list variants from phone_list
    # Handle dict entries ({"phone": "...", "reason": "..."}) and string entries
    list_variants_set = set()
    for entry in phone_list:
        phone_str = None

        # AC-6: Extract phone from dict if entry is a dict
        if isinstance(entry, dict):
            phone_str = entry.get('phone', '')
        else:
            # String entry (possibly with spaces/dashes)
            phone_str = entry

        if phone_str:
            # Normalize the list entry phone
            normalized = normalize_phone(str(phone_str))
            if normalized:
                # Add all variants of this normalized phone to the set
                variants = get_phone_variants(normalized)
                list_variants_set.update(variants)

    # Check if any input variant matches any list variant
    for v in input_variants:
        if v in list_variants_set:
            return True

    return False
