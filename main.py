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
        return not (
            self.left > other.right or
            self.right < other.left or
            self.top > other.bottom or
            self.bottom < other.top
        )

    def __repr__(self) -> str:
        return f"Car({self._range})"


class ParkingLot:
    # Type annotations
    cars: list[Car]
    goal_car: Car

    def __init__(self, width: int, height: int, exit_location: str) -> None:
        self.width = width
        self.height = height
        self.exit_location = AlphanumericGrid.parse_alphanumeric_coord(exit_location)
        self.goal_car = None
        self.cars = []

    def add_car(self, new_car: Car, goal=True):
        # Check that the new car does not collide with any of the existing cars
        for parked_car in self.cars:
            if new_car.does_intersect(parked_car):
                raise ValueError(f"Car {new_car} cannot fit into the parking lot")

        if goal:
            if self.goal_car is not None:
                self.goal_car = new_car
            else:
                raise ValueError("Goal car has already been set")
        else:
            self.cars.append(new_car)
