def panic_probability(features):
    count = features["count"]
    intensity = features["weak_signal_sum"]

    if count < 3:
        return 0.0

    score = 0.4 * min(count / 10, 1.0) + 0.6 * min(intensity / count, 1.0)
    return min(score, 1.0)
