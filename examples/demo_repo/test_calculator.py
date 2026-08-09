import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from calculator import Calculator


class TestCalculator:
    def setup_method(self):
        self.calc = Calculator()

    def test_add(self):
        assert self.calc.add(2, 3) == 5

    def test_subtract(self):
        assert self.calc.subtract(5, 3) == 2

    def test_multiply(self):
        assert self.calc.multiply(3, 4) == 12

    def test_divide(self):
        assert self.calc.divide(10, 2) == 5.0

    def test_divide_by_zero_raises(self):
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            self.calc.divide(10, 0)
