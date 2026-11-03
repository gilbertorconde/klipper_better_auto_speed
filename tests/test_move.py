"""Endpoint geometry regression tests; no Klipper or hardware required."""
import math
import unittest

from better_auto_speed.move import MoveX, MoveY, MoveZ, MoveDiagX, MoveDiagY


def make_limits():
    # Nonzero origins and unequal spans catch offset and diagonal mistakes.
    return {a: {'min': lo, 'max': hi, 'dist': hi - lo, 'home': lo}
            for a, lo, hi in [('x', -10.0, 290.0), ('y', 20.0, 260.0), ('z', 5.0, 205.0)]}


class MoveTests(unittest.TestCase):
    classes = (MoveX, MoveY, MoveZ, MoveDiagX, MoveDiagY)

    def check_endpoints(self, move, limits, margin):
        distance = 0.0
        for axis, positions in move.pos.items():
            if positions[0] is None:
                self.assertEqual(positions, [None, None])
                continue
            for position in positions:
                self.assertGreaterEqual(position + 1e-10, limits[axis]['min'] + margin)
                self.assertLessEqual(position - 1e-10, limits[axis]['max'] - margin)
            distance += (positions[1] - positions[0]) ** 2
        self.assertAlmostEqual(move.dist, math.sqrt(distance))

    def test_stop_to_stop_distance(self):
        for cls in self.classes:
            with self.subTest(move=cls.__name__):
                move, limits = cls(), make_limits()
                move.Init(limits, 20, True)
                move.Calc(limits, 200, 1000, 20)
                self.assertAlmostEqual(move.dist, 40.0)
                self.check_endpoints(move, limits, 20)
                if cls in (MoveDiagX, MoveDiagY):
                    self.assertAlmostEqual(abs(move.pos['x'][1] - move.pos['x'][0]), 40 / math.sqrt(2))

    def test_full_travel(self):
        for cls in self.classes:
            with self.subTest(move=cls.__name__):
                move, limits = cls(), make_limits()
                move.Init(limits, 20, False)
                expected = min(limits[a]['max'] - limits[a]['min'] - 40 for a in move.axes) * math.sqrt(len(move.axes))
                self.assertAlmostEqual(move.max_dist, expected)
                move.Calc(limits, 100, 1000, 20, move.max_dist)
                self.assertAlmostEqual(move.dist, expected)
                self.check_endpoints(move, limits, 20)
                # At least one moving axis must use both margin boundaries.
                self.assertTrue(any(math.isclose(min(move.pos[a]), limits[a]['min'] + 20)
                                    and math.isclose(max(move.pos[a]), limits[a]['max'] - 20)
                                    for a in move.axes))

    def test_reject_unreachable_or_invalid_distance(self):
        for cls in self.classes:
            move, limits = cls(), make_limits()
            move.Init(limits, 20, False)
            for velocity, distance in [(1000, None), (200, 20), (100, move.max_dist + 1), (100, 0), (100, float('nan'))]:
                with self.subTest(move=cls.__name__, velocity=velocity, distance=distance):
                    with self.assertRaises(ValueError):
                        move.Calc(limits, velocity, 1000, 20, distance)

    def test_minimum_distance_and_lazy_init(self):
        move = MoveX()
        move.Calc(make_limits(), 10, 1000, 20)
        self.assertAlmostEqual(move.dist, 5)
        limits = make_limits()
        limits['x']['max'] = limits['x']['min'] + 3
        move.Calc(limits, 1, 1000, 0)
        self.assertAlmostEqual(move.dist, 3)

    def test_invalid_margin_and_limits(self):
        for margin in (-1, 150, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                MoveX().Init(make_limits(), margin)
        limits = make_limits()
        limits['x']['max'] = float('inf')
        with self.assertRaises(ValueError):
            MoveX().Init(limits, 0)

    def test_homing_and_direction(self):
        limits = make_limits()
        for cls, home in [(MoveX, [True, False, False]), (MoveY, [False, True, False]), (MoveZ, [False, False, True])]:
            move = cls()
            move.Init(limits, 20, True)
            move.Calc(limits, 100, 1000, 20)
            self.assertEqual(move.home, home)
        for home in (limits['z']['min'], limits['z']['max']):
            limits['z']['home'] = home
            move = MoveZ()
            move.Calc(limits, 100, 1000, 20)
            self.assertEqual(move.pos['z'][0] > move.pos['z'][1], home == limits['z']['min'])
        move = MoveDiagY()
        move.Calc(limits, 100, 1000, 20)
        self.assertGreater(move.pos['x'][0], move.pos['x'][1])
        self.assertLess(move.pos['y'][0], move.pos['y'][1])


if __name__ == '__main__':
    unittest.main()
