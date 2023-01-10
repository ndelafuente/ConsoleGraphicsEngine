from main import Car


def both_intersect(car1: Car, car2: Car) -> bool:
    return car1.does_intersect(car2) and car2.does_intersect(car1)


def neither_intersect(car1: Car, car2: Car) -> bool:
    return not (car1.does_intersect(car2) or car2.does_intersect(car1))


class TestCar:
    def test_construction(self):
        pass  # TODO

    def test_should_intersect(self):
        vertical_car = Car("C3-D5")
        horizontal_car = Car("C3-E4")

        # Intersecting self
        assert both_intersect(vertical_car, vertical_car)
        assert both_intersect(horizontal_car, horizontal_car)

        # Left Boundary
        assert both_intersect(vertical_car, Car("B-C3"))
        assert both_intersect(vertical_car, Car("B-C4"))
        assert both_intersect(vertical_car, Car("B-C5"))
        assert both_intersect(vertical_car, Car("A2-C3"))
        assert both_intersect(vertical_car, Car("A3-C4"))
        assert both_intersect(vertical_car, Car("A4-C5"))
        assert both_intersect(vertical_car, Car("A5-C6"))

        # Right Boundary
        assert both_intersect(vertical_car, Car("D-E3"))
        assert both_intersect(vertical_car, Car("D-E4"))
        assert both_intersect(vertical_car, Car("D-E5"))
        assert both_intersect(vertical_car, Car("D2-F3"))
        assert both_intersect(vertical_car, Car("D3-F4"))
        assert both_intersect(vertical_car, Car("D4-F5"))
        assert both_intersect(vertical_car, Car("D5-F6"))

        # Top Boundary
        assert both_intersect(horizontal_car, Car("C2-3"))
        assert both_intersect(horizontal_car, Car("D2-3"))
        assert both_intersect(horizontal_car, Car("E2-3"))
        assert both_intersect(horizontal_car, Car("B1-C3"))
        assert both_intersect(horizontal_car, Car("C1-D3"))
        assert both_intersect(horizontal_car, Car("D1-E3"))
        assert both_intersect(horizontal_car, Car("E1-F3"))

        # Bottom Boundary
        assert both_intersect(horizontal_car, Car("C4-5"))
        assert both_intersect(horizontal_car, Car("D4-5"))
        assert both_intersect(horizontal_car, Car("E4-5"))
        assert both_intersect(horizontal_car, Car("B4-C6"))
        assert both_intersect(horizontal_car, Car("C4-D6"))
        assert both_intersect(horizontal_car, Car("D4-E6"))
        assert both_intersect(horizontal_car, Car("E4-F6"))

        big_car = Car("B2-E7")

        # Vertical internal
        assert both_intersect(big_car, Car("B4-5"))
        assert both_intersect(big_car, Car("C2-3"))
        assert both_intersect(big_car, Car("C4-5"))
        assert both_intersect(big_car, Car("C6-7"))
        assert both_intersect(big_car, Car("E4-5"))

        # Horizontal internal
        assert both_intersect(big_car, Car("B-C4"))
        assert both_intersect(big_car, Car("C-D2"))
        assert both_intersect(big_car, Car("C-D4"))
        assert both_intersect(big_car, Car("C-D7"))
        assert both_intersect(big_car, Car("D-E4"))

    def test_should_not_intersect(self):
        car = Car("C3-D5")

        assert neither_intersect(car, Car("A3-4"))
        assert neither_intersect(car, Car("B3-4"))
        assert neither_intersect(car, Car("E3-4"))
        assert neither_intersect(car, Car("F3-4"))

        assert neither_intersect(car, Car("C-D1"))
        assert neither_intersect(car, Car("C-D2"))
        assert neither_intersect(car, Car("C-D6"))
        assert neither_intersect(car, Car("C-D7"))

        assert neither_intersect(car, Car("B2-6"))
        assert neither_intersect(car, Car("E2-6"))

        assert neither_intersect(car, Car("B-E2"))
        assert neither_intersect(car, Car("B-E6"))
