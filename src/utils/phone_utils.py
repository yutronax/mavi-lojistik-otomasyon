import re
from typing import List

def normalize_phone(phone_str: str) -> str:
    """
    Normalizes a phone number to 0XXXXXXXXXX format (11 digits).
    """
    if not phone_str:
        return ""
    
    # Remove all non-digits
    digits = re.sub(r'\D', '', str(phone_str))
    
    if not digits:
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

def is_phone_in_list(phone: str, phone_list: List[str]) -> bool:
    """
    Checks if a phone (in any variant) exists in a list of phones (also in any variant).
    """
    if not phone or not phone_list:
        return False
        
    variants = get_phone_variants(phone)
    # Convert list to a set of all possible variants for efficiency
    # But for a small blacklist, we can just check
    for v in variants:
        if v in phone_list:
            return True
            
    # Also check if any variant of the list items matches our variants
    # Actually, if we store the base format in the list, it's easier.
    # But if the list has mixed formats, we check the variants of the input.
    return False
