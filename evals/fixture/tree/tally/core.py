def total(items):
    return sum(items)


def average(items):
    return sum(items) / len(items)


def top(items, n):
    return sorted(items, reverse=True)[:n]
