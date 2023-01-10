from main import Car, ParkingLot


class TestMain:
    def test_parking_lot(self):
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
        sample_goal_car = Car('B-C3')
        sample_car_list = [
            Car('A1-2'),
            Car('A3-4'),
            Car('A5-6'),
            Car('B1-2'),
            Car('B5-6'),
            Car('C4-5'),
            Car('C-D1'),
            Car('C-D2'),
            Car('C-D6'),
            Car('D3-4'),
            Car('D-E5'),
            Car('E2-3'),
            Car('E-F1'),
            Car('E-F4'),
            Car('E-F6'),
            Car('F2-3'),
        ]

        sample_board = ParkingLot(sample_width, sample_height, sample_exit_location)
        sample_board.add_car(sample_goal_car, goal=True)
