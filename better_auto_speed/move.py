# Find your printers max speed before losing steps
#
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
# Copyright (C) 2026 gilbertorconde (https://github.com/gilbertorconde) - Better Auto Speed fork
#
# This file may be distributed under the terms of the MIT license.

import math

from .funcs import calculate_distance


class Move:
    home = [False, False, False]
    axes = ()

    def __init__(self):
        # Both distances are physical path lengths, not coordinate offsets.
        self.dist = 0.0
        self.pos = {}
        self.max_dist = 0.0
        self.isolate_xy = False

    def __str__(self):
        return f"dist/max {self.dist:.0f}/{self.max_dist:.0f}\nPos: {self.pos}"

    def Init(self, axis_limits, margin, isolate_xy=False):
        if not math.isfinite(margin) or margin < 0:
            raise ValueError("margin must be finite and nonnegative")
        self.isolate_xy = isolate_xy
        spans = []
        for axis in self.axes:
            limits = axis_limits[axis]
            low, high = limits['min'], limits['max']
            if not all(math.isfinite(v) for v in (low, high)):
                raise ValueError("axis endpoints must be finite")
            span = high - low - 2 * margin
            if not math.isfinite(span) or span <= 0:
                raise ValueError("margin leaves no usable axis travel")
            spans.append(span)
        if not spans:
            raise ValueError("move has no axes")
        self.max_dist = min(spans) * math.sqrt(len(self.axes))
        self.home = [axis in self.axes for axis in ('x', 'y', 'z')]
        if len(self.axes) == 1 and self.axes[0] in ('x', 'y') and not isolate_xy:
            self.home = [True, True, False]

    def Calc(self, axis_limits, veloc, accel, margin, dist=None):
        self.Init(axis_limits, margin, self.isolate_xy)
        required = calculate_distance(veloc, accel)
        # A stop-to-stop move needs v^2/a, including both acceleration ramps.
        length = max(min(5.0, self.max_dist), required) if dist is None else dist
        if not math.isfinite(length) or length <= 0:
            raise ValueError("move distance must be finite and positive")
        if length > self.max_dist and not math.isclose(length, self.max_dist, rel_tol=1e-12):
            raise ValueError("requested move exceeds usable travel")
        length = min(length, self.max_dist)  # roundoff only, never physical clipping
        if required > length and not math.isclose(required, length, rel_tol=1e-12):
            raise ValueError("velocity is unreachable at this acceleration and distance")
        self.pos = {axis: [None, None] for axis in ('x', 'y', 'z')}
        component = length / math.sqrt(len(self.axes))
        for axis in self.axes:
            limits = axis_limits[axis]
            toward_min = (isinstance(self, MoveDiagY) and axis == 'x') or (
                axis == 'z' and limits['home'] <= limits['min'])
            if toward_min:
                end = limits['min'] + margin
                self.pos[axis] = [end + component, end]
            else:
                end = limits['max'] - margin
                self.pos[axis] = [end - component, end]
        self.dist = math.sqrt(sum((self.pos[a][1] - self.pos[a][0]) ** 2 for a in self.axes))


class MoveX(Move):
    axes = ('x',)


class MoveY(Move):
    axes = ('y',)


class MoveZ(Move):
    axes = ('z',)


class MoveDiagX(Move):
    axes = ('x', 'y')


class MoveDiagY(Move):
    axes = ('x', 'y')
