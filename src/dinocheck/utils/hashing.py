"""Hash utilities for cache key generation."""

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class CacheKey:
    """Immutable cache key for analysis results."""

    file_hash: str
    rules_hash: str

    def __str__(self) -> str:
        """Return combined key for display."""
        return f"{self.file_hash}:{self.rules_hash}"


class ContentHasher:
    """Generates stable hashes for content and rule sets.

    Used to create cache keys that invalidate when:
    - File content changes
    - Active rules change
    """

    HASH_LENGTH = 32  # 128 bits - good collision resistance

    @classmethod
    def hash_content(cls, content: str) -> str:
        """Compute stable hash of file content.

        Normalizes whitespace to ensure consistent hashing:
        - Strips trailing whitespace from each line
        - Removes trailing blank lines
        - Ensures single newline at end
        """
        # Normalize: strip trailing whitespace per line, remove trailing blank lines
        lines = [line.rstrip() for line in content.splitlines()]
        normalized = "\n".join(lines).rstrip() + "\n"
        return hashlib.sha256(normalized.encode()).hexdigest()[: cls.HASH_LENGTH]

    @classmethod
    def hash_rules(cls, rule_ids: list[str]) -> str:
        """Compute hash of rule IDs.

        Order-independent to ensure same rules = same hash.
        Empty list returns hash of empty string (consistent sentinel value).
        """
        content = ",".join(sorted(rule_ids))
        return hashlib.sha256(content.encode()).hexdigest()[: cls.HASH_LENGTH]

    @classmethod
    def create_cache_key(cls, content: str, rule_ids: list[str]) -> CacheKey:
        """Create a complete cache key from content and rules."""
        return CacheKey(
            file_hash=cls.hash_content(content),
            rules_hash=cls.hash_rules(rule_ids),
        )
