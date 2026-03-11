import math


def word_count_factor(word_count: int, target: int = 150) -> float:
    """
    Returns a multiplier between 0 and 1.
    At target words: 1.0 (no penalty).
    Deviation gets penalized exponentially (Gaussian curve).

    Examples with k=3:
      150 words → 1.00  (perfect)
      120 words → 0.96  (minimal penalty)
      225 words → 0.78  (noticeable penalty, 50% over)
      300 words → 0.37  (heavy penalty, 100% over)
    """
    k = 3
    relative_deviation = (word_count - target) / target
    factor = math.exp(-k * relative_deviation ** 2)
    return round(factor, 4)


def calculate_final_score(empathy: int, professionalism: int,
                          concreteness: int, word_count: int) -> dict:
    """
    Calculates content average and applies word count penalty.
    Returns all scoring components for transparency.
    """
    content_score = (empathy + professionalism + concreteness) / 3
    wc_weight = word_count_factor(word_count)
    final = round(content_score * wc_weight, 2)

    return {
        "empathy": empathy,
        "professionalism": professionalism,
        "concreteness": concreteness,
        "content_score": round(content_score, 2),
        "word_count": word_count,
        "word_count_weight": round(wc_weight, 2),
        "total_score": final
    }