from functools import total_ordering
from typing import Self

from StringUtils import Is, categorize

INT_PAIR = tuple[int, int]


@total_ordering
class Location:
    def __init__(self, column: int, row: int) -> None:
        assert type(column) == int and type(row) == int

        self.column = column
        self.row = row

    def __eq__(self, other: Self | INT_PAIR) -> bool:
        if not self._is_valid_operand(other):
            return NotImplemented

        if type(other) == tuple:
            return (self.column, self.row) == other
        return (self.column, self.row) == (other.column, other.row)

    def __lt__(self, other: Self | INT_PAIR) -> bool:
        if not self._is_valid_operand(other):
            return NotImplemented

        if type(other) == tuple:
            return (self.column, self.row) < other
        return (self.column, self.row) < (other.column, other.row)

    def _is_valid_operand(self, other: any):
        if type(other) == tuple and len(other) == 2:
            column, row = other
            return (type(column) == int and type(row) == int)

        return type(other) == type(self)

    def __repr__(self) -> str:
        return f"Point{(self.column, self.row)}"


class Range:
    def __init__(self, p1: Location | INT_PAIR, p2: Location | INT_PAIR):
        p1 = self._parse_input(p1)
        p2 = self._parse_input(p2)

        self.start, self.end = sorted((p1, p2))
        self.width = self.end.column - self.start.column
        self.height = self.end.row - self.start.row

    def _parse_input(self, input: Location | INT_PAIR) -> Location:
        if type(input) == tuple and len(input) == 2:
            column, row = input
            return Location(column, row)
        elif type(input) == Location:
            return input
        else:
            raise TypeError(f"argument must be a Location or tuple, not {type(input)}")

    def __eq__(self, other: Self | tuple[INT_PAIR, INT_PAIR]) -> bool:
        if not self._is_valid_operand(other):
            return NotImplemented

        if type(other) == tuple:
            start, end = other
            other = Range(start, end)

        return (self.start, self.end) == (other.start, other.end)

    def _is_valid_operand(self, other):
        if type(other) == tuple and len(other) == 2:
            start, end = other
            return (
                type(start) == tuple and len(start) == 2 and
                type(end) == tuple and len(end) == 2 and
                all([type(item) == int for item in start + end])
            )

        return type(other) == type(self)

    def __repr__(self) -> str:
        return f"Range{(self.start, self.end)}"


class AlphanumericGrid:
    @classmethod
    def parse_range(cls, range: str, sep='-') -> Range:
        """
        This function translates an alphanumeric range into a pair of points on
        a zero-based grid. It accepts longform (e.g. 'A3-A4') and shortform
        (e.g. 'A3-4') notation, as well as single points (e.g. 'A3').

        For example:
            A3    -> (0, 3), (0, 3)
            B3-4  -> (1, 2), (1, 3)
            B-C4  -> (1, 3), (2, 3)
            A4-B6 -> (0, 3), (1, 5)
        """

        match range.split(sep):
            case [coord]:  # e.g. A3
                match categorize(coord):
                    case Is.ALPHANUMERIC:
                        coord = cls.parse_alphanumeric_coordinate(coord)
                        return Range(coord, coord)
                    case _:
                        raise ValueError(f"invalid single coordinate range: '{range}'")
            case [start, end]:
                match categorize(start), categorize(end):
                    case Is.ALPHANUMERIC, Is.NUMERIC:  # e.g. A1-2
                        start = cls.parse_alphanumeric_coordinate(start)
                        end_row = int(end) - 1
                        end = Location(start.column, end_row)
                    case Is.ALPHA, Is.ALPHANUMERIC:  # e.g. A-B1
                        end = cls.parse_alphanumeric_coordinate(end)
                        start_col = cls.translate_lettering(start) - 1
                        start = Location(start_col, end.row)
                    case Is.ALPHANUMERIC, Is.ALPHANUMERIC:  # e.g. A1-B2
                        start = cls.parse_alphanumeric_coordinate(start)
                        end = cls.parse_alphanumeric_coordinate(end)
                    case _:
                        raise ValueError("invalid alphanumeric range")
                return Range(start, end)
            case []:
                raise ValueError("recieved empty string")
            case _:
                raise ValueError(f"expected at most 1 separator ({sep}), "
                                 f"received {range.count(sep)}: {range}")

    @classmethod
    def parse_alphanumeric_coordinate(cls, coordinate: str) -> Location:
        numeric_section_length = 0
        for char in reversed(coordinate):
            if char.isnumeric():
                numeric_section_length += 1
            elif char.isalpha():
                break

        alphabetical_section = coordinate[:-numeric_section_length]
        numeric_section = coordinate[-numeric_section_length:]

        column = cls.translate_lettering(alphabetical_section)
        row = int(numeric_section)

        return Location(column - 1, row - 1)

    @staticmethod
    def translate_lettering(lettering: str) -> int:
        numerical_equivalent = 1
        for i, char in enumerate(reversed(lettering)):
            char = char.capitalize()
            if char < 'A' or char > 'Z':
                raise ValueError(f"invalid letter: '{char}' in '{lettering}'")

            numerical_equivalent += (26 ** i) * (ord(char) - ord('A'))
        return numerical_equivalent
