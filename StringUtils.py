from enum import Enum


class Is(Enum):
    NONE = 0
    ALPHA = 1
    NUMERIC = 2
    ALPHANUMERIC = 3

def categorize(string:str) -> Is:
    if string.isalpha():
        return Is.ALPHA
    if string.isnumeric():
        return Is.NUMERIC
    if string.isalnum():
        return Is.ALPHANUMERIC
    return Is.NONE