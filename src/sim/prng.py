"""Cross-platform deterministic 64-bit PRNG (SplitMix64 + Xorshift64*)."""

from __future__ import annotations

MASK_64 = (1 << 64) - 1


def _splitmix64(x: int) -> int:
    x = (x + 0x9E3779B97F4A7C15) & MASK_64
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK_64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK_64
    return (z ^ (z >> 31)) & MASK_64


class SeededRNG:
    """Deterministic PRNG isolated from Python's global random state."""

    def __init__(self, seed: int) -> None:
        state = _splitmix64(int(seed) & MASK_64)
        self._state = state if state != 0 else 0xA0761D6478BD642F

    def next_u64(self) -> int:
        x = self._state
        x ^= (x >> 12) & MASK_64
        x ^= (x << 25) & MASK_64
        x ^= (x >> 27) & MASK_64
        self._state = x if x != 0 else 0xA0761D6478BD642F
        return (self._state * 0x2545F4914F6CDD1D) & MASK_64

    def random(self) -> float:
        """Return float uniformly distributed in [0.0, 1.0)."""
        return (self.next_u64() >> 11) * (1.0 / (1 << 53))

    def uniform(self, low: float, high: float) -> float:
        """Return float in [low, high)."""
        return low + (high - low) * self.random()

    def randint(self, low: int, high: int) -> int:
        """Return integer N such that low <= N <= high."""
        span = high - low + 1
        return low + (self.next_u64() % span)
