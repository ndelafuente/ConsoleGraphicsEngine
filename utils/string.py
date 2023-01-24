from enum import Enum


class Is(Enum):
    NONE = 0
    ALPHA = 1
    NUMERIC = 2
    ALPHANUMERIC = 3


def categorize(string: str) -> Is:
    if string.isalpha():
        return Is.ALPHA
    if string.isnumeric():
        return Is.NUMERIC
    if string.isalnum():
        return Is.ALPHANUMERIC
    return Is.NONE


def str_delete(str: str, start: int, end: int = None) -> str:
    if end is None:
        end = start
    if start < len(str):
        return str[:start] + str[end + 1:]
    else:
        raise IndexError("string index out of range")


def str_insert(str: str, char: str, index: int) -> str:
    if index <= len(str):
        return str[:index] + char + str[index:]
    else:
        raise IndexError("string index out of range")


def find_next_word(str: str, start: int) -> int:
    """
    Find the start of the next word
    """
    if str[start] != ' ':
        while start < len(str) and str[start] != ' ':
            start += 1

    while start < len(str) and str[start] == ' ':
        start += 1

    return start


def find_next_word_end(str: str, start: int) -> int:
    """
    Find the end of the next word
    """
    if str[start] == ' ':
        while start < len(str) and str[start] == ' ':
            start += 1

    while start < len(str) and str[start] != ' ':
        start += 1

    return start


def find_prev_word(str: str, start: int) -> int:
    """
    Find the start of the previous word
    """
    return str[:start].rstrip().rfind(' ') + 1


def delete_next_word(str: str, start: int) -> tuple(str, int):
    """
    Delete from start to the end of the next word
    """
    del_end = find_next_word_end(str, start)
    return str[:start] + str[del_end:], del_end


def delete_prev_word(str: str, start: int) -> tuple(str, int):
    """
    Delete from start to the beginning of the previous word
    """
    del_start = find_prev_word(str, start)
    return str[:del_start] + str[start:], del_start
