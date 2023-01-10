from typing import Self
from BoardUtils import AlphanumericGrid, Range


class Car:
    def __init__(self, range: Range | str) -> None:

        # Convert location information to an internally compatible range
        if type(range) == str:
            range = AlphanumericGrid.parse_range(range)

        # Check the car's orientation
        if range.width > range.height:
            # Horizontal car
            self.is_horizontal = True
            self.is_vertical = False
        elif range.height > range.width:
            # Vertical car
            self.is_vertical = True
            self.is_horizontal = False
        else:
            # Square Car
            raise ValueError(f"unable to determine car orientation: '{range}'")

        # Define the car's boundary box
        self._range = range
        self.top = range.start.row
        self.bottom = range.end.row
        self.left = range.start.column
        self.right = range.end.column

    def does_intersect(self, other: Self) -> bool:
        return self._does_intersect(other) or other._does_intersect(self)

    def _does_intersect(self, other: Self) -> bool:
        left_intersection = (self.left <= other.right and self.right >= other.right)
        right_intersection = (self.right >= other.left and self.left <= other.left)
        top_intersection = (self.top <= other.bottom and self.bottom >= other.bottom)
        bottom_intersection = (self.bottom >= other.top and self.top <= other.top)

        return (left_intersection or right_intersection) and (top_intersection or bottom_intersection)

    def __repr__(self) -> str:
        return f"Car({self._range})"


class ParkingLot:
    # Type annotations
    cars: list[Car]

    def __init__(self, width: int, height: int, exit_location: str) -> None:
        self.width = width
        self.height = height
        self.exit_location = AlphanumericGrid.parse_alphanumeric_coordinate(exit_location)
        self.cars = []

    def add_car(self, new_car: Car, goal=True):
        # for each car, check that the new car does not collide
        for parked_car in self.cars:
            if new_car.does_intersect(parked_car):
                pass
