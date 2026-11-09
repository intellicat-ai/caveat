"""Small statistics shared by the authoring stages."""
import math

TYPICAL_MIN_K = 5
TYPICAL_MIN_SHARE = 0.25

# Precision of a term's sampled matches against the draft definition, and
# the lexicon level it supports. Below the lowest bound a term is not
# offered as a standalone engagement term.
LEVEL_BOUNDS = [(0.9, "domain_defining"), (0.7, "domain_characteristic")]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for k successes in n trials (95% by default)."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def wilson_text(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{lo:.2f}-{hi:.2f}"


def lift(k_topic: int, k_total: int, topic_size: int, corpus_size: int) -> float:
    """How much more often the query's works fall in a topic than works at large."""
    if not (k_total and topic_size and corpus_size):
        return 0.0
    return (k_topic / k_total) / (topic_size / corpus_size)


def typical_candidate(k: int, n: int) -> bool:
    """A co-occurring mode qualifies for typicallyExhibits at >= 5 works and >= 25%."""
    return n > 0 and k >= TYPICAL_MIN_K and k / n >= TYPICAL_MIN_SHARE


def level_for(precision: float) -> str | None:
    for bound, level in LEVEL_BOUNDS:
        if precision >= bound:
            return level
    return None
