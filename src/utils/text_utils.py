import itertools
import re

def generate_keyword_variants(keyword: str):
    """
    Generates variations of a keyword based on logistic typo rules:
    1. Vowel Opposition (ı <-> i, u <-> ü, o <-> ö)
    2. Permutations & Joins for multi-word phrases
    3. Number to Word conversion
    """
    if not keyword:
        return []
        
    keyword = keyword.strip().upper()
    
    # helper for Number-Word
    num_map = {
        '1': 'BİR', '2': 'İKİ', '3': 'ÜÇ', '4': 'DÖRT', '5': 'BEŞ',
        '6': 'ALTI', '7': 'YEDİ', '8': 'SEKİZ', '9': 'DOKUZ', '10': 'ON',
        '0': 'SIFIR'
    }
    
    # Expanded character map for common typos and Turkish-English keyboard swaps
    char_map = {
        'İ': 'I', 'I': 'İ',
        'Ü': 'U', 'U': 'Ü',
        'Ö': 'O', 'O': 'Ö',
        'Ş': 'S', 'S': 'Ş',
        'Ç': 'C', 'C': 'Ç',
        'Ğ': 'G', 'G': 'Ğ'
    }

    def get_word_variations(word):
        # Rule 3: Number to word
        if word in num_map:
            return {word, num_map[word]}
            
        # combinatorial character swap
        chars = list(word)
        options = []
        for c in chars:
            if c in char_map:
                options.append([c, char_map[c]])
            else:
                options.append([c])
        
        # Limit combinations to prevent explosion (max 32 variants per word)
        # 2^5 = 32. If more than 5 swappable chars, we cap it.
        swappable_indices = [i for i, opt in enumerate(options) if len(opt) > 1]
        if len(swappable_indices) > 5:
            # Only swap first 5 to avoid 2^N explosion
            for idx in swappable_indices[5:]:
                options[idx] = [options[idx][0]]
        
        word_vars = set()
        for combo in itertools.product(*options):
            word_vars.add("".join(combo))
        
        return word_vars

    words = keyword.split()
    # word_options: list of sets, each set contains variants for that word
    word_options = [get_word_variations(w) for w in words]
    
    # Rule 2: Multi-word logic (Join variations)
    all_variants = set()
    
    # Basic combinations in original order
    for combo in itertools.product(*word_options):
        # Original order joined by space
        all_variants.add(" ".join(combo))
        # Original order joined (bitişik)
        all_variants.add("".join(combo))
        
        # Permutations if more than 1 word (e.g. "KAPALI KASA" -> "KASA KAPALI")
        if len(combo) > 1:
            for p in itertools.permutations(combo):
                all_variants.add(" ".join(p))
                all_variants.add("".join(p))
                
    # Final filter: remove empty or single spaces, sort by length
    result = sorted([v for v in all_variants if v.strip()], key=len)
    return result

if __name__ == "__main__":
    # Test
    test_cases = ["1", "BİR ÜÇ", "PALETLİ UN"]
    for tc in test_cases:
        print(f"Test case: {tc}")
        vars = generate_keyword_variants(tc)
        print(f"Variants: {vars}")
        print("-" * 20)
