# Find your printers max speed before losing steps
#
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
# Copyright (C) 2026 gilbertorconde (https://github.com/gilbertorconde) - Better Auto Speed fork
#
# This file may be distributed under the terms of the MIT license.

import math

def calculate_velocity(accel: float, travel: float):
    return math.sqrt(travel/accel)*accel

def calculate_accel(veloc: float, travel: float):
    return veloc**2/travel

def calculate_distance(veloc: float, accel: float):
    return veloc**2/accel

def calculate_diagonal(x: float, y: float):
    return math.sqrt(x**2 + y**2)

def calculate_graph(velocity: float, slope: int):
    return (10000/(velocity/slope))

def calculate_move_time(accel: float, veloc: float, dist: float):
    # Time for a point-to-point move of `dist` under trapezoidal motion limits.
    # Lower time means higher throughput for a representative move of that size.
    if dist <= 0 or accel <= 0 or veloc <= 0:
        return float('inf')
    accel_dist = veloc**2 / accel          # distance to ramp up to veloc and back down
    if dist >= accel_dist:
        return veloc/accel + dist/veloc    # trapezoid (reaches cruise velocity)
    return 2.0 * math.sqrt(dist/accel)     # triangle (never reaches veloc)