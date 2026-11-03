# Find your printers max speed before losing steps
#
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
# Copyright (C) 2026 gilbertorconde (https://github.com/gilbertorconde) - Better Auto Speed fork
#
# This file may be distributed under the terms of the MIT license.
#
# Matplotlib isolation: render the max-accel-vs-velocity graph to a PNG and
# return its path. Importing matplotlib is deferred so the addon loads without it.

import os
import datetime as dt


def render_graph(results_dir, axis, accel_accu, velocs, accels, accel_mins, accel_maxs, derate):
    import matplotlib          # this may fail if matplotlib isn't installed
    matplotlib.use('Agg')      # headless: render straight to a file, no display
    import matplotlib.pyplot as plt

    # An infeasible velocity is a gap, never a zero or interpolated success.
    accels = [float('nan') if a is None else a for a in accels]
    plt.figure()
    plt.plot(velocs, accels, 'go-', label='measured')
    plt.plot(velocs, [a*derate for a in accels], 'g-', label='derated')
    plt.plot(velocs, accel_mins, 'b--', label='min')
    plt.plot(velocs, accel_maxs, 'r--', label='max')
    plt.legend(loc='upper right')
    plt.title(f"Max accel at velocity on {axis} to {int(accel_accu*100)}% accuracy")
    plt.xlabel("Velocity")
    plt.ylabel("Acceleration")
    # Colons in the timestamp break file transfers to Windows/CIFS/exFAT.
    filepath = os.path.join(
        results_dir,
        f"BETTER_AUTO_SPEED_GRAPH_{dt.datetime.now():%Y-%m-%d_%H-%M-%S}_{axis}.png"
    )
    os.makedirs(results_dir, exist_ok=True)
    plt.savefig(filepath, bbox_inches='tight')
    plt.close()
    return filepath
