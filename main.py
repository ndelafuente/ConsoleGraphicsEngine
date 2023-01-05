
def translate_lettering(lettering: str):
    numerical_equivalent = 1
    for i, char in enumerate(reversed(lettering)):
        char = char.upper()
        if char < 'A' or char > 'Z':
            raise ValueError(f"invalid letter: '{char}' in '{lettering}'")

        numerical_equivalent += (26 ** i) * (ord(char) - ord('A'))
    return numerical_equivalent


def translate_alphanumeric_coordinate(coordinate: str):
    numeric_section_length = 0
    for char in reversed(coordinate):
        if char.isnumeric():
            numeric_section_length += 1
        elif char.isalpha():
            break

    alphabetical_section = coordinate[:-numeric_section_length]
    numeric_section = coordinate[-numeric_section_length:]

    column = translate_lettering(alphabetical_section)
    row = int(numeric_section)

    return column, row

class Car:
    def __init__(self, location: str) -> None:
        col_info, row_info = [info.split('-') for info in location.split(',')]

        if len(col_info) not in (1, 2) or len(row_info) not in (1, 2):
            raise ValueError(f"invalid car location: '{location}'")

        # Convert location information to an internally compatible range
        col_start, col_end = self.convert_range(col_info, key=translate_lettering)
        row_start, row_end = self.convert_range(row_info)

        # Calculate the car's dimentions
        x_length = col_end - col_start
        y_length = row_end - row_start

        # Check the car's orientation
        if x_length > y_length:
            # Horizontal car
            self.is_horizontal = True
            self.is_vertical = False
        elif y_length > x_length:
            # Vertical car
            self.is_vertical = True
            self.is_horizontal = False
        else:
            # Square Car
            raise ValueError(f"unable to determine car orientation: '{location}'")

        self.p1 = (col_start, row_start)
        self.p2 = (col_end, row_end)

    def convert_range(self, range, key=int):
        # Map the range using the key
        range = list(map(key, range))

        # Convert single number ranges, e.g. [3] -> [3, 3]
        if len(range) == 1:
            range *= 2

        # Sort range in ascending order
        start, end = sorted(range)

        # Translate to zero-based indexing, e.g. [3,3] -> [2,2]
        return start - 1, end - 1

    def __repr__(self):
        return f"[{self.p1}, {self.p2}]"


class ParkingLot:
    def __init__(self, width: int, height: int, exit_location: str) -> None:
        self.width = width
        self.height = height
        self.exit_location = translate_alphanumeric_coordinate(exit_location)
        self.board = []

    def add_car(self, car: Car):
        pass


"""
Sample 6x6 Board
Regular Car: ←→
Goal Car: ⇇⇉
Border: | _
    A̲ B̲ C̲ D̲ E̲ F̲
 1 |↑ ↑ ← → ← →|
 2 |↓ ↓ ← → ↑ ↑|
 3 |↑ ⇇ ⇉ ↑ ↓ ↓
 4 |↓   ↑ ↓ ← →|
 5 |↑ ↑ ↓ ← →  |
 6 |↓ ↓ ← → ← →|
    ‾ ‾ ‾ ‾ ‾ ‾
"""

# Sample board definition
sample_width, sample_height = (6, 6)
sample_exit_location = 'F3'
sample_goal_car = Car('B-C, 3')
sample_car_list = [
    Car('A, 1-2'),
    Car('A, 3-4'),
    Car('A, 5-6'),
    Car('B, 1-2'),
    Car('B, 5-6'),
    Car('C, 4-5'),
    Car('C-D, 1'),
    Car('C-D, 2'),
    Car('C-D, 6'),
    Car('D, 3-4'),
    Car('D-E, 5'),
    Car('E, 2-3'),
    Car('E-F, 1'),
    Car('E-F, 4'),
    Car('E-F, 6'),
    Car('F, 2-3'),
]

sample_board = ParkingLot(sample_width, sample_height, sample_exit_location)
