
def bound(number, min=0, max=None):
    if number < min:
        return min
    if max is not None and number > max:
        return max
    return number


def stable_round(number):
    integer_part = int(number)
    fractional_part = integer_part - number
    if fractional_part >= 0.5:
        return integer_part + 1
    else:
        return integer_part
