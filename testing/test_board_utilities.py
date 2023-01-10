from BoardUtils import AlphanumericGrid


class TestAlphanumericGrid:
    def test_parse_range(self):
        expected = {
            "A3": ((0, 2), (0, 2)),
            "A3-A3": ((0, 2), (0, 2)),
            "A-A3": ((0, 2), (0, 2)),
            "A3-3": ((0, 2), (0, 2)),
            "B3-4": ((1, 2), (1, 3)),
            "B4-3": ((1, 2), (1, 3)),
            "B-C4": ((1, 3), (2, 3)),
            "C-B4": ((1, 3), (2, 3)),
            "A4-B6": ((0, 3), (1, 5)),
            "B6-A4": ((0, 3), (1, 5)),
        }
        for expected_input, expected_output in expected.items():
            output = AlphanumericGrid.parse_range(expected_input)
            assert output == expected_output, f"Incorrect value for '{expected_input}'"
