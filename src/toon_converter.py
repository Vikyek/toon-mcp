"""
TOON (Token-Optimized Object Notation) Converter
Converts verbose JSON structures to compact TOON format for reduced token consumption.
"""

import json
from typing import Any, Dict, List, Optional, Union
from collections import Counter

from .config import KEY_ABBREV, CHARS_PER_TOKEN


class TOONConverter:
    """
    Converts JSON to TOON format and vice versa.

    TOON Format Rules:
    1. Common keys are abbreviated (id->i, name->n, type->t, value->v, data->d)
    2. Repeated structures use references (@ref)
    3. Arrays of similar objects are compacted with schema encoding (_sch/_dat)
    4. Null values are represented as ~
    5. Boolean values: true=T, false=F
    6. In aggressive mode, domain-specific keys are auto-abbreviated and stored in _custom_keys
    """

    KEY_ABBREV: Dict[str, str] = KEY_ABBREV
    ABBREV_KEY: Dict[str, str] = {v: k for k, v in KEY_ABBREV.items()}

    def __init__(self, aggressive: bool = False):
        """
        Initialize TOON converter.

        Args:
            aggressive: If True, auto-abbreviate domain-specific keys beyond KEY_ABBREV.
                        Custom abbreviations are stored in _custom_keys for lossless round-trip.
        """
        self.aggressive = aggressive
        self.ref_cache: Dict[str, Any] = {}
        self.ref_counter = 0
        self.key_freq: Counter = Counter()
        self.custom_abbrev: Dict[str, str] = {}  # key -> short form, populated in aggressive mode

    def json_to_toon(self, data: Union[Dict, List, str]) -> str:
        """
        Convert JSON to TOON format.

        Args:
            data: JSON data (dict, list, or JSON string)

        Returns:
            TOON formatted string
        """
        if isinstance(data, str):
            data = json.loads(data)

        self.ref_cache = {}
        self.ref_counter = 0
        self.key_freq = Counter()
        self.custom_abbrev = {}

        # Collect key frequencies for compression analysis
        self._build_ref_cache(data)

        # In aggressive mode, auto-abbreviate frequent domain-specific keys
        if self.aggressive:
            self.custom_abbrev = self._build_custom_abbrev()

        toon_data = self._convert_to_toon(data)

        result: Dict[str, Any] = {
            '_toon': '1.0',
            'd': toon_data,
        }

        if self.ref_cache:
            result['_refs'] = self.ref_cache

        # Emit custom key map so decompression can reverse abbreviations
        if self.custom_abbrev:
            result['_custom_keys'] = self.custom_abbrev

        return json.dumps(result, separators=(',', ':'))

    def toon_to_json(self, toon_str: str) -> str:
        """
        Convert TOON format back to JSON.

        Args:
            toon_str: TOON formatted string

        Returns:
            Standard JSON string
        """
        toon_data = json.loads(toon_str)

        if '_toon' not in toon_data:
            raise ValueError("Invalid TOON format: missing _toon version")

        refs = toon_data.get('_refs', {})

        # Merge standard abbreviations with any custom ones from this TOON payload
        custom_keys = toon_data.get('_custom_keys', {})
        abbrev_key = {**self.ABBREV_KEY, **{v: k for k, v in custom_keys.items()}}

        json_data = self._convert_from_toon(toon_data['d'], refs, abbrev_key)
        return json.dumps(json_data, indent=2)

    def _build_ref_cache(self, data: Any) -> None:
        """Traverse data and collect key frequencies for aggressive-mode abbreviation."""
        if isinstance(data, dict):
            for key, value in data.items():
                self.key_freq[key] += 1
                self._build_ref_cache(value)
        elif isinstance(data, list):
            for item in data:
                self._build_ref_cache(item)

    def _build_custom_abbrev(self) -> Dict[str, str]:
        """
        Build custom abbreviations for frequent domain-specific keys.
        Only targets keys that appear 2+ times, are absent from KEY_ABBREV,
        and are longer than 3 characters.
        """
        custom: Dict[str, str] = {}
        existing_abbrevs = set(self.KEY_ABBREV.values())

        for key, count in self.key_freq.most_common():
            if count < 2 or key in self.KEY_ABBREV or len(key) <= 3:
                continue
            abbrev = self._generate_abbreviation(key, existing_abbrevs)
            custom[key] = abbrev
            existing_abbrevs.add(abbrev)

        return custom

    def _generate_abbreviation(self, key: str, existing: set) -> str:
        """Generate a short, collision-free abbreviation for a key."""
        # Strip interior vowels and underscores, keep first char
        consonants = key[0] + ''.join(c for c in key[1:] if c not in 'aeiouAEIOU_')
        abbrev = consonants[:4].lower()
        if abbrev not in existing:
            return abbrev
        # Fallback 1: first 2 chars + last char
        abbrev = (key[:2] + key[-1]).lower()
        if abbrev not in existing:
            return abbrev
        # Fallback 2: first 3 chars + collision-count digit
        abbrev = key[:3].lower() + str(len(existing) % 10)
        return abbrev

    def _convert_to_toon(self, data: Any) -> Any:
        """Recursively convert data to TOON format."""
        if data is None:
            return '~'
        if isinstance(data, bool):
            return 'T' if data else 'F'
        if isinstance(data, (int, float)):
            return data
        if isinstance(data, str):
            return self._compress_string(data)
        if isinstance(data, list):
            return self._compress_array(data)
        if isinstance(data, dict):
            return self._compress_object(data)
        return data

    def _compress_string(self, s: str) -> str:
        """Compress string values (extensible hook for future strategies)."""
        return s

    def _compress_array(self, arr: List) -> Any:
        """
        Compress arrays. When all items share identical keys, use schema encoding:
            {"_sch": [<keys>], "_dat": [[<values>], ...]}
        This is the most impactful compression for API responses and database results.
        """
        if not arr:
            return []

        if all(isinstance(item, dict) for item in arr):
            key_sets = [set(item.keys()) for item in arr]
            if len({tuple(sorted(ks)) for ks in key_sets}) == 1:
                # All objects have identical keys — encode as schema + value rows
                keys = sorted(arr[0].keys())
                compressed_keys = [self._abbrev_key(k) for k in keys]
                return {
                    '_sch': compressed_keys,
                    '_dat': [
                        [self._convert_to_toon(item[k]) for k in keys]
                        for item in arr
                    ],
                }

        return [self._convert_to_toon(item) for item in arr]

    def _compress_object(self, obj: Dict) -> Dict:
        """Compress object by abbreviating keys."""
        return {self._abbrev_key(k): self._convert_to_toon(v) for k, v in obj.items()}

    def _abbrev_key(self, key: str) -> str:
        """Return the shortest known abbreviation for a key."""
        if key in self.KEY_ABBREV:
            return self.KEY_ABBREV[key]
        if self.aggressive and key in self.custom_abbrev:
            return self.custom_abbrev[key]
        return key

    def _convert_from_toon(self, data: Any, refs: Dict, abbrev_key: Dict[str, str]) -> Any:
        """Recursively convert TOON format back to standard JSON."""
        if data == '~':
            return None
        if data == 'T':
            return True
        if data == 'F':
            return False
        if isinstance(data, (int, float)):
            return data
        if isinstance(data, str):
            if data.startswith('@'):
                return refs.get(data[1:], data)
            return data
        if isinstance(data, list):
            return [self._convert_from_toon(item, refs, abbrev_key) for item in data]
        if isinstance(data, dict):
            if '_sch' in data and '_dat' in data:
                return self._decompress_schema_array(data, refs, abbrev_key)
            return self._decompress_object(data, refs, abbrev_key)
        return data

    def _decompress_schema_array(self, data: Dict, refs: Dict, abbrev_key: Dict[str, str]) -> List:
        """Decompress schema-encoded array back to list of objects."""
        expanded_keys = [abbrev_key.get(k, k) for k in data['_sch']]
        return [
            {expanded_keys[i]: self._convert_from_toon(v, refs, abbrev_key) for i, v in enumerate(row)}
            for row in data['_dat']
        ]

    def _decompress_object(self, obj: Dict, refs: Dict, abbrev_key: Dict[str, str]) -> Dict:
        """Decompress object by expanding abbreviated keys."""
        return {
            abbrev_key.get(k, k): self._convert_from_toon(v, refs, abbrev_key)
            for k, v in obj.items()
        }

    def calculate_savings(self, original_json: str, toon_str: str) -> Dict[str, Any]:
        """
        Calculate token savings from TOON conversion.

        Token counts are estimated at CHARS_PER_TOKEN characters per token.
        Both character counts and estimated token counts are returned.

        Args:
            original_json: Original JSON string
            toon_str: TOON formatted string

        Returns:
            Dictionary with savings statistics
        """
        original_chars = len(original_json)
        toon_chars = len(toon_str)
        original_tokens = max(1, original_chars // CHARS_PER_TOKEN)
        toon_tokens = max(1, toon_chars // CHARS_PER_TOKEN)
        tokens_saved = original_tokens - toon_tokens
        savings_percent = (tokens_saved / original_tokens * 100) if original_tokens > 0 else 0

        return {
            'original_chars': original_chars,
            'toon_chars': toon_chars,
            'original_tokens': original_tokens,
            'toon_tokens': toon_tokens,
            'tokens_saved': tokens_saved,
            'savings_percent': round(savings_percent, 2),
            'compression_ratio': round(toon_chars / original_chars, 3) if original_chars > 0 else 0,
        }


def convert_json_to_toon(json_data: Union[Dict, List, str], aggressive: bool = False) -> str:
    """
    Convenience function to convert JSON to TOON.

    Args:
        json_data: JSON data to convert
        aggressive: Use aggressive compression (auto-abbreviates domain-specific keys)

    Returns:
        TOON formatted string
    """
    converter = TOONConverter(aggressive=aggressive)
    return converter.json_to_toon(json_data)


def convert_toon_to_json(toon_str: str) -> str:
    """
    Convenience function to convert TOON to JSON.

    Args:
        toon_str: TOON formatted string

    Returns:
        Standard JSON string
    """
    converter = TOONConverter()
    return converter.toon_to_json(toon_str)
