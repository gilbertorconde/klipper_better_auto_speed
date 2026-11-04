<p align="center">
  <img src="assets/logo.png" alt="Better Auto Speed" width="230">
</p>

# Better Auto Speed

Klipper module for automatically calculating your printer's maximum acceleration/velocity

_With one copy/paste and one line in your configuration, automatically optimize your printer's motion_

> **Disclaimer — improved, independently-maintained version**
>
> This is an enhanced version of Klipper Auto Speed, built on top of the original project created by [Anonoei](https://github.com/Anonoei/klipper_auto_speed). Full credit for the original idea and implementation belongs to the original author.
>
> This is a **separate, branched project — not a fork intended to upstream changes back** to the original repository. It is maintained independently at [gilbertorconde/klipper_better_auto_speed](https://github.com/gilbertorconde/klipper_better_auto_speed) and layers additional features and fixes on top of the original.
>
> Please direct installation and issues to **this** repository rather than the original.

This module automatically performs movements on the _x_, _y_, _x-diagonal_, _y-diagonal_, and _z_ axes, and measures your steppers missed steps at various accelerations/velocities.
With the default configuration, this may take _awhile_ (~10 minutes).
Most of the testing time is waiting for your printer to home.
On my printer with default settings (except MAX_MISSED), it takes ~3.5 minutes for acceleration, and ~5 minutes for velocity.

**Sensorless homing**: If you're using sensorless homing `MAX_MISSED=1.0` is probably too low.
Let the endstop variance check drive the value: it runs before every search (`VARIANCE=1`) and prints the most steps lost while homing (`Missed X:#.## steps, Y:#.## steps`), and the run stops if that reaches `MAX_MISSED`.
Set `MAX_MISSED` comfortably above the worst value it reports.
For instance, on my printer I lose around 0-4.2 steps each home.
I run `BETTER_AUTO_SPEED MAX_MISSED=10.0` to account for that variance, and occasional wildly different endstop results.

**This module is under development**, and has only been validated on CoreXY printers: You may run into issues or bugs, feel free to post an issue on this repository.

**Supervise every calibration run.** These tests deliberately approach missed-step limits. Re-homing and bounded movement do not guarantee collision-free operation after a stall, homing failure, or mechanical fault. Clear the build area and be ready to stop the printer.

Ellis' pattern (`BETTER_AUTO_SPEED_VALIDATE`) also requires supervision. Never leave a stress test unattended.

# Table of Contents

- [Overview](https://github.com/gilbertorconde/klipper_better_auto_speed#overview)
- [Credits](https://github.com/gilbertorconde/klipper_better_auto_speed#credits)
- [Example Usage](https://github.com/gilbertorconde/klipper_better_auto_speed#example-usage)
- [Roadmap](https://github.com/gilbertorconde/klipper_better_auto_speed#roadmap)
- [How does it work](https://github.com/gilbertorconde/klipper_better_auto_speed#how-does-it-work)
- [Using Better Auto Speed](https://github.com/gilbertorconde/klipper_better_auto_speed#using-better-auto-speed)
  - [Installation](https://github.com/gilbertorconde/klipper_better_auto_speed#installation)
    - [Moonraker Update Manager](https://github.com/gilbertorconde/klipper_better_auto_speed#moonraker-update-manager)
  - [Configuration](https://github.com/gilbertorconde/klipper_better_auto_speed#configuration)
  - [Macros](https://github.com/gilbertorconde/klipper_better_auto_speed#macro)
    - [BETTER_AUTO_SPEED](https://github.com/gilbertorconde/klipper_better_auto_speed#better_auto_speed)
    - [BETTER_AUTO_SPEED_ACCEL](https://github.com/gilbertorconde/klipper_better_auto_speed#better_auto_speed_accel)
    - [BETTER_AUTO_SPEED_VELOCITY](https://github.com/gilbertorconde/klipper_better_auto_speed#better_auto_speed_velocity)
    - [BETTER_AUTO_SPEED_VALIDATE](https://github.com/gilbertorconde/klipper_better_auto_speed#better_auto_speed_validate)
    - [BETTER_AUTO_SPEED_GRAPH](https://github.com/gilbertorconde/klipper_better_auto_speed#better_auto_speed_graph)
- [Console Output](https://github.com/gilbertorconde/klipper_better_auto_speed#console-output)

## Overview

- License: MIT

### Calibration safeguards

Search results use only actually tested, passing values. A search with no passing attempt does not produce a recommendation. Motion geometry uses stop-to-stop travel sufficient to reach the requested velocity; impossible bounds and margins must be corrected rather than silently clipped.

When `VALIDATE=1`, settings are queued for `SAVE_CONFIG` only after validation succeeds. Without validation, recommendations remain unvalidated. Temporary motion limits and motor overrides are restored on success and failure; firmware shutdown or communication loss may still require a restart and inspection.

### Development checks

Tests use fake Klipper objects and do not move hardware. No third-party test runner is required:

```sh
python -m unittest discover -s tests -v
bash -n install.sh uninstall.sh
git diff --check
```

CI runs these checks across multiple Python versions. Passing unit tests is not a substitute for supervised testing on supported printer hardware.

## Credits

This project is a branched, independently-maintained continuation of the original [Klipper Auto Speed](https://github.com/Anonoei/klipper_auto_speed) by [Anonoei](https://github.com/Anonoei). The original author designed and implemented the core module; this version builds on that foundation with additional features and fixes. The original copyright and MIT license are retained throughout the source and `LICENSE` file. Thank you to Anonoei and the original contributors for making this possible.

## Example Usage

- Default usage (couple sweep + save the recommended pair)
  - `BETTER_AUTO_SPEED`
- Legacy independent accel + velocity search (no coupling), without saving
  - `BETTER_AUTO_SPEED COUPLE=0 SAVE=0`
- Find maximum acceleration on y axis
  - `BETTER_AUTO_SPEED_ACCEL AXIS="y"`
- Find maximum velocity on y, then x axis
  - `BETTER_AUTO_SPEED_VELOCITY AXIS="y,x"`
- Validate your printer's current accel/velocity (Ellis' test pattern)
  - `BETTER_AUTO_SPEED_VALIDATE`
- Graph your printer's max velocity/accel
  - `BETTER_AUTO_SPEED_GRAPH`
- Graph your printer's max velocity/accel between v100 and v1000, over 9 steps
  - `BETTER_AUTO_SPEED_GRAPH VELOCITY_MIN=100 VELOCITY_MAX=1000 VELOCITY_DIV=9`
- Find what velocity is usable at a fixed acceleration
  - `BETTER_AUTO_SPEED ACCEL=10000`
- Find what acceleration is usable at a fixed velocity
  - `BETTER_AUTO_SPEED VELOC=500`
- Find the best combined accel/velocity pair for your printer (this is the default)
  - `BETTER_AUTO_SPEED COUPLE=1`

## How does it work?

1.  Home your printer
2.  If your print is enclosed, heat soak it. You want to run this module in the typical state your printer is in when you're printing.
3.  Run `BETTER_AUTO_SPEED`
    1. Prepare
       1. Make sure the printer is level
       2. Check endstop variance
          - Validate the endstops are accurate enough for `MAX_MISSED`
    2. Find the maximum acceleration
       - Perform a binary search between `ACCEL_MIN` and `ACCEL_MAX`
       1. Home, and save stepper start steps
       2. Perform the movement check on the specified axis
       3. Home, and save stepper stop steps
       4. If difference between start/stop steps is more than `max_missed`, go to next step
    3. Find maximum velocity
       - Perform a binary search between `VELOCITY_MIN` and `VELOCITY_MAX`
       1. Home, and save stepper start steps
       2. Perform the movement check on the specified axis
       3. Home, and save stepper stop steps
       4. If difference between start/stop steps is more than `max_missed`, go to next step
    4. Show results

## Using Better Auto Speed

### Moonraker Update Manager

```
[update_manager klipper_better_auto_speed]
type: git_repo
path: ~/klipper_better_auto_speed
origin: https://github.com/gilbertorconde/klipper_better_auto_speed.git
primary_branch: main
managed_services: klipper
```

Moonraker does not run an `install_script` when it updates a `git_repo` (it only scans that script for system packages), so none is configured. Updates still work without re-running `install.sh`: the installer links the whole `better_auto_speed` directory into Klipper, so files added by an update are picked up automatically. Klipper must restart to load them; `managed_services: klipper` makes Moonraker do that after an update.

### Installation

To install this module you need to clone the repository and run the `install.sh` script.
**Depending on when you installed klipper, you may also need to [update your klippy-env python version.](https://github.com/gilbertorconde/klipper_better_auto_speed#update-klippy-env)**

#### Automatic installation

```
cd ~
git clone https://github.com/gilbertorconde/klipper_better_auto_speed.git
cd klipper_better_auto_speed
./install.sh
```

The installer works from any working directory and does **not** restart services by default. Run it while the printer is idle. Custom installations can select their paths explicitly:

```sh
KLIPPER_PATH="$HOME/klipper" KLIPPY_ENV="$HOME/klippy-env" ./install.sh
```

The installer creates one directory link, `~/klipper/klippy/extras/better_auto_speed -> ~/klipper_better_auto_speed/better_auto_speed`. Earlier versions linked each `.py` file separately; re-running `./install.sh` once migrates that layout to the directory link (it refuses, and changes nothing, if that directory holds anything other than links into this checkout and `__pycache__`). With the directory link, updates that add new modules work without re-running `install.sh`; restart Klipper after any update so it loads them.

Plotting is optional: set `INSTALL_PLOTTING=1` to install matplotlib. To request a restart of exactly one service, set `KLIPPER_SERVICE=klipper.service`; this requires systemd authorization. Otherwise restart that service manually when safe. The uninstaller removes only links belonging to this checkout and never restarts services or recursively deletes the extras directory.

#### Manual installation

1.  Clone the repository
    1. `cd ~`
    2. `git clone https://github.com/gilbertorconde/klipper_better_auto_speed.git`
    3. `cd klipper_better_auto_speed`
2.  Link better_auto_speed to klipper
    1. `ln -s ~/klipper_better_auto_speed/better_auto_speed ~/klipper/klippy/extras/better_auto_speed`
3.  Install matplotlib
    1.  `~/klippy-env/bin/python -m pip install matplotlib`
4.  Restart klipper
    1. `sudo systemctl restart klipper`

#### Update klippy-env

The installer checks the Python used by Klipper's virtual environment (`~/klippy-env/bin/python`), not your system `python3`. If that env still uses Python 2, recreate/upgrade it:

1.  `sudo apt install python3`
2.  `sudo apt install python3-numpy`
3.  `sudo systemctl stop klipper`
4.  `python3 -m venv --upgrade ~/klippy-env`
5.  `~/klippy-env/bin/pip install -r "~/klipper/scripts/klippy-requirements.txt"`

Check the env's Python version with `~/klippy-env/bin/python --version`.

#### Uninstallation

Run the `uninstall.sh` script to remove the module from Klipper:

```
cd ~/klipper_better_auto_speed
./uninstall.sh
```

It removes the `better_auto_speed` directory link from `~/klipper/klippy/extras` (or, for an older per-file install, only the links that point into this checkout). It does **not** restart Klipper. Afterwards, delete the `[better_auto_speed]` section (and any `BETTER_AUTO_SPEED`-saved values) from your config, then restart Klipper manually when the printer is idle.

### Configuration

Place this in your printer.cfg

```
[better_auto_speed]
```

The values listed below are the defaults Better Auto Speed uses. You can include them if you wish to change their values or run into issues.

```
[better_auto_speed]
#axis: diag_x, diag_y  ; One or multiple of `x`, `y`, `diag_x`, `diag_y`, `z`

#margin: 20            ; How far away from your axes to perform movements

#settling_home: 1      ; Perform settling home before starting Better Auto Speed
#max_missed: 1.0       ; Maximum full steps that can be missed
#endstop_samples: 3    ; How many endstop samples to take for endstop variance

#accel_min: 1000.0     ; Minimum acceleration test may try
#accel_max: 50000.0    ; Maximum acceleration test may try
#accel_accu: 0.05      ; Keep binary searching until the result is within this percentage

#velocity_min: 50.0    ; Minimum velocity test may try
#velocity_max: 5000.0  ; Maximum velocity test may try
#velocity_accu: 0.05   ; Keep binary searching until the result is within this percentage

#derate: 0.8           ; Derate discovered results by this amount
#scv: 5                ; square_corner_velocity (mm/s) used during test and validation moves; must be >1 and <50. Your own value is restored afterwards

#z_position_speed: 25  ; Speed (mm/s) for positioning moves that change Z, e.g. centering/Z= move. Keeps belted/Trident Z from slamming after leveling
#motor_off: 0          ; Issue M84 (disable steppers) once the run finishes

#validate_margin: Unset      ; Margin for VALIDATE, Defaults to margin
#validate_inner_margin: 20.0 ; Margin for VALIDATE inner pattern
#validate_iterations: 50     ; Perform VALIDATE pattern this many times

#results_dir: ~/printer_data/config ; Destination directory for graphs
```

> [!WARNING]
> If your Z axis is homed with a probe / virtual endstop (e.g. Klipper Tap, or `endstop_pin: probe:z_virtual_endstop`), missed-step detection on Z is unreliable. Better Auto Speed will warn you, and any Z results may be over-optimistic — treat them with caution.

### Macro

Better Auto Speed is split into 5 separate macros. The default `BETTER_AUTO_SPEED` automatically calls the other three (`BETTER_AUTO_SPEED_ACCEL`, `BETTER_AUTO_SPEED_VELOCITY`, `BETTER_AUTO_SPEED_VALIDATE`). You can use any argument from those macros when you call `BETTER_AUTO_SPEED`.

You can also use `BETTER_AUTO_SPEED_GRAPH` to find your printers velocity-to-accel relationship.

#### BETTER_AUTO_SPEED

`BETTER_AUTO_SPEED` finds maximum acceleration, velocity, and validates results at the end.
Argument | Default | Description
----------------- | ------- | -----------
AXIS | Unset | Perform test on these axes, defaults to diag_x, diag_y
Z | 50 | Z position to run Better Auto Speed
MARGIN | 20 | How far away from your axis maximums to perform the test movement
SETTLING_HOME | 1 | Perform settling home before starting Better Auto Speed
MAX_MISSED | 1.0 | Maximum full steps that can be missed
ENDSTOP_SAMPLES | 3 | How many endstop samples to take for endstop variance
TEST_ATTEMPTS | 2 | Re-test this many times if test fails
ACCEL_MIN | auto | Minimum acceleration test may try (auto: from axis travel when a fixed VELOCITY is given, else 1000)
ACCEL_MAX | auto | Maximum acceleration test may try (auto: 100000)
ACCEL_ACCU | 0.05 | Keep binary searching until the result is within this percentage
VELOCITY_MIN | auto | Minimum velocity test may try (auto: 50)
VELOCITY_MAX | auto | Maximum velocity test may try (auto: `sqrt(accel_max * axis travel)`)
VELOCITY_ACCU | 0.05 | Keep binary searching until the result is within this percentage
ACCEL | Unset | Couple mode: hold this acceleration fixed and search for the velocity that works with it (skips the accel search)
VELOC | Unset | Couple mode: hold this velocity fixed and search for the acceleration that works with it (alias: `VELOCITY`)
COUPLE | 1 | Sweep velocities, measure max accel at each, and recommend the best combined accel/velocity pair for your printer. Set `COUPLE=0` for the legacy independent accel + velocity search. Ignored when `ACCEL` or `VELOC` is given
VELOCITY_DIV | 5 | Number of velocities to sweep when coupling
MOTOR_OFF | 0 | Disable steppers (`M84`) when the run finishes. Overrides the `motor_off` config value for a single run
LEVEL | 1 | Level the printer if it's not leveled
VARIANCE | 1 | Check endstop variance
SAVE | 1 | Queue recommended max_accel/max_velocity to `[printer]` (run `SAVE_CONFIG` to apply). Set `SAVE=0` to only print the results. See [Saving results](#saving-results-save) for configs that set these in an included file
SCV | 5 | `square_corner_velocity` (mm/s) used during test moves; overrides the `scv` config value for a single run
X_CURRENT | Unset | Motor run-current (A) applied to the X axis during the run, restored after (requires TMC drivers)
Y_CURRENT | Unset | Motor run-current (A) applied to the Y axis during the run, restored after (requires TMC drivers)
Z_CURRENT | Unset | Motor run-current (A) applied to the Z axis during the run, restored after (requires TMC drivers)
X_HOMING_SPEED | Unset | Homing speed (mm/s) applied to the X axis during the run, restored after
Y_HOMING_SPEED | Unset | Homing speed (mm/s) applied to the Y axis during the run, restored after
Z_HOMING_SPEED | Unset | Homing speed (mm/s) applied to the Z axis during the run, restored after

On CoreXY (`corexy`/`hybrid_corexy`/`markforged`) the A/B motors share current: a single `X_CURRENT` or `Y_CURRENT` is applied to both `stepper_x` and `stepper_y`; passing both with different values is allowed but warns. Current applies to every motor on an axis (e.g. dual/quad Z). Homing speed is always per-axis.

##### Saving results (SAVE)

With `SAVE=1` (the default for `BETTER_AUTO_SPEED`, `_ACCEL` and `_VELOCITY`; opt-in for `_VALIDATE`), Better Auto Speed queues `max_accel` / `max_velocity` under `[printer]` for `SAVE_CONFIG`. With `VALIDATE=1`, nothing is queued unless validation passes.

Before queueing, it checks whether an included file sets each option, using Klipper's own config parser and include resolution on the file Klipper was started with:

- **Not set, set in the main body of `printer.cfg`, or set in the `#*# SAVE_CONFIG` block**: the value is queued. Run `SAVE_CONFIG` to write it (this rewrites `printer.cfg` and restarts Klipper; Klipper comments out the old main-body line itself).
- **Set in an included file** (for example Klippain-style `config/kinematics.cfg`), even if `printer.cfg` also sets it: the value is **not** queued. Klipper refuses a whole `SAVE_CONFIG` when a saved option conflicts with an included value (`SAVE_CONFIG section 'printer' option 'max_accel' conflicts with included value`), and that would also block saving anything else (bed mesh, probe data...) until Klipper restarts. Instead the console shows the recommended values and the file(s) to edit:

  ```
  BETTER AUTO SPEED did NOT queue max_accel, max_velocity: already set in an included config file (...)
  Edit [printer] in /home/pi/printer_data/config/config/kinematics.cfg by hand:
    max_accel: 8000
    max_velocity: 400
  then restart Klipper.
  ```

  Put those lines under `[printer]` in that file, then restart Klipper.

The check is per option: if only `max_accel` is set in an include, `max_velocity` is still queued. If the config can't be read, nothing is queued and the values are printed for a manual edit.

##### Coupling acceleration and velocity

Acceleration and velocity are not independent: within a fixed travel distance, a higher acceleration leaves less room to reach a high cruise velocity and vice versa. `BETTER_AUTO_SPEED` can account for this in three ways:

- **`ACCEL=<value>`** holds that acceleration fixed and searches for the velocity that works with it (the acceleration search is skipped). Answers "what velocity can I use at this accel?"
- **`VELOC=<value>`** (alias `VELOCITY`) holds that velocity fixed and searches for the acceleration that works with it. Answers "what accel can I use at this velocity?"
- **`COUPLE=1`** (the default) sweeps `VELOCITY_DIV` cruise velocities between the (size-aware) velocity bounds, measures the maximum acceleration that passes at each (per axis), then recommends the single accel/velocity pair with the highest throughput. Pass `COUPLE=0` to fall back to the legacy independent accel + velocity search. `COUPLE` is ignored when you give a fixed `ACCEL` or `VELOC`.

The throughput metric is the time of a representative point-to-point move sized to your printer (the shortest tested axis travel), using the standard trapezoidal/triangular motion model (`t = v/a + D/v`, or `2*sqrt(D/a)` when the move never reaches cruise). The pair with the lowest move time wins. Each accel attempt runs over the axis' full usable travel so the toolhead truly reaches the cruise velocity; any velocity for which no acceleration passes is reported as *infeasible* and excluded. When multiple axes are tested, the acceleration at each velocity is the minimum measured across axes so the recommended pair is safe everywhere. `DERATE` is applied to the recommended values, and `SAVE`/`VALIDATE` work as usual (`SAVE` defaults to `1`). The sweep runs a full acceleration search at every velocity, so it takes considerably longer than the legacy `COUPLE=0` run.

#### BETTER_AUTO_SPEED_ACCEL

`BETTER_AUTO_SPEED_ACCEL` find maximum acceleration
Argument | Default | Description
---------- | ------- | -----------
AXIS | Unset | Perform test on these axes, defaults to diag_x, diag_y
MARGIN | 20.0 | How far away from your axis maximums to perform movements
DERATE | 0.8 | How much to derate maximum values for the recommended max
MAX_MISSED | 1.0 | Maximum fulls steps that can be missed
ACCEL_MIN | auto | Minimum acceleration test may try (auto: from axis travel when a fixed VELOCITY is given, else 1000)
ACCEL_MAX | auto | Maximum acceleration test may try (auto: 100000)
ACCEL_ACCU | 0.05 | Keep binary searching until the result is within this percentage
SAVE | 1 | Queue recommended max_accel to `[printer]` (run `SAVE_CONFIG` to apply). Set `SAVE=0` to only print the result. See [Saving results](#saving-results-save)
X_CURRENT | Unset | Motor run-current (A) applied to X during the run, restored after (requires TMC drivers)
Y_CURRENT | Unset | Motor run-current (A) applied to Y during the run, restored after (requires TMC drivers)
Z_CURRENT | Unset | Motor run-current (A) applied to Z during the run, restored after (requires TMC drivers)
X_HOMING_SPEED | Unset | Homing speed (mm/s) applied to X during the run, restored after
Y_HOMING_SPEED | Unset | Homing speed (mm/s) applied to Y during the run, restored after
Z_HOMING_SPEED | Unset | Homing speed (mm/s) applied to Z during the run, restored after

#### BETTER_AUTO_SPEED_VELOCITY

`BETTER_AUTO_SPEED_VELOCITY` finds maximum velocity
Argument | Default | Description
------------- | ------- | -----------
AXIS | Unset | Perform test on these axes, defaults to diag_x, diag_y
MARGIN | 20.0 | How far away from your axis maximums to perform movements
DERATE | 0.8 | How much to derate maximum values for the recommended max
MAX_MISSED | 1.0 | Maximum fulls steps that can be missed
VELOCITY_MIN | auto | Minimum velocity test may try (auto: 50)
VELOCITY_MAX | auto | Maximum velocity test may try (auto: `sqrt(accel_max * axis travel)`)
VELOCITY_ACCU | 0.05 | Keep binary searching until the result is within this percentage
SAVE | 1 | Queue recommended max_velocity to `[printer]` (run `SAVE_CONFIG` to apply). Set `SAVE=0` to only print the result. See [Saving results](#saving-results-save)
X_CURRENT | Unset | Motor run-current (A) applied to X during the run, restored after (requires TMC drivers)
Y_CURRENT | Unset | Motor run-current (A) applied to Y during the run, restored after (requires TMC drivers)
Z_CURRENT | Unset | Motor run-current (A) applied to Z during the run, restored after (requires TMC drivers)
X_HOMING_SPEED | Unset | Homing speed (mm/s) applied to X during the run, restored after
Y_HOMING_SPEED | Unset | Homing speed (mm/s) applied to Y during the run, restored after
Z_HOMING_SPEED | Unset | Homing speed (mm/s) applied to Z during the run, restored after

**Size-aware search bounds:** When you don't set them explicitly, the accel/velocity search bounds are derived per-axis from that axis's usable travel rather than fixed constants. The velocity ceiling is `sqrt(accel_max * travel)` (e.g. ~3464 mm/s on a 120 mm axis, ~7071 mm/s on a 500 mm axis), and the accel floor scales from travel when a fixed `VELOCITY` is supplied. `velocity_min` and `accel_max` are not travel-bounded and keep their defaults. Any value you set explicitly (config option or macro argument) always overrides the computed default. This is a behavior change from earlier fixed defaults (5000 mm/s, etc.); set `velocity_max`/`accel_min`/etc. explicitly to restore fixed values.

#### BETTER_AUTO_SPEED_VALIDATE

`BETTER_AUTO_SPEED_VALIDATE` validates a specified acceleration/velocity, using [Ellis' TEST_SPEED Pattern](https://github.com/AndrewEllis93/Print-Tuning-Guide/blob/main/macros/TEST_SPEED.cfg)
Argument | Default | Description
--------------------- | ------- | -----------
MAX_MISSED | 1.0 | Maximum fulls steps that can be missed
VALIDATE_MARGIN | 20.0 | Margin axes max/min pattern can move to
VALIDATE_INNER_MARGIN | 20.0 | Margin from axes center pattern can move to
VALIDATE_ITERATIONS | 50 | Repeat the pattern this many times
ACCEL | Unset | Defaults to current max accel
VELOCITY | Unset | Defaults to current max velocity
SAVE | 0 | Queue the validated accel/velocity to `[printer]` when validation passes. See [Saving results](#saving-results-save)
X_CURRENT | Unset | Motor run-current (A) applied to X during the run, restored after (requires TMC drivers)
Y_CURRENT | Unset | Motor run-current (A) applied to Y during the run, restored after (requires TMC drivers)
Z_CURRENT | Unset | Motor run-current (A) applied to Z during the run, restored after (requires TMC drivers)
X_HOMING_SPEED | Unset | Homing speed (mm/s) applied to X during the run, restored after
Y_HOMING_SPEED | Unset | Homing speed (mm/s) applied to Y during the run, restored after
Z_HOMING_SPEED | Unset | Homing speed (mm/s) applied to Z during the run, restored after

#### BETTER_AUTO_SPEED_GRAPH

`BETTER_AUTO_SPEED_GRAPH` graphs your printer's velocity-to-accel relationship on specified axes
You must specify `VELOCITY_MIN` and `VELOCITY_MAX`.

| Argument        | Default | Description                                                        |
| --------------- | ------- | ------------------------------------------------------------------ |
| AXIS            | Unset   | Perform test on these axes, defaults to diag_x, diag_y             |
| MARGIN          | 20.0    | How far away from axis to perform movements                        |
| DERATE          | 0.8     | How much to derate maximum values for the recommended max          |
| MAX_MISSED      | 1.0     | Maximum fulls steps that can be missed                             |
| VELOCITY_MIN    | Unset   | Minimum velocity test may try                                      |
| VELOCITY_MAX    | Unset   | Maximum velocity test may try                                      |
| VELOCITY_DIV    | 5       | How many velocities to test (minimum 2)                            |
| ACCEL_ACCU      | 0.05    | Keep binary searching until the result within this percent         |
| ACCEL_MIN_SLOPE | 100     | Calculated min slope value $\frac{10000}{velocity \div slope}$     |
| ACCEL_MAX_SLOPE | 1800    | Calculated max slope value $\frac{10000}{velocity \div slope}$     |

## Console Output

Console output is slightly different depending on whether testing acceleration/velocity, and which axis is being tested.

- `axis` is one of `x`, `y`, `diag_x`, `diag_y`, `z`
- The three times after `after` are (first home time)/(movement time)/(end home time)
- `#`s before decimals are variable, `#`s after decimals are static

### Acceleration tests

```
BETTER AUTO SPEED accel on `axis` try # (#.##s)
Moved #.##mm at a###/v### after #.##/#.##/#.##s
Missed X #.##, Y #.##
```

Example:

```
BETTER AUTO SPEED accel on diag_x try 1 (19.66s)
Moved 1.43mm at a17333/v241 after 8.92/0.30/9.93s
Missed X 0.31, Y 2.00
```

### Velocity tests

```
BETTER AUTO SPEED velocity on `axis` try # (#.##s)
Moved #.##mm at a###/v### after #.##/#.##/#.##s
Missed X #.##, Y #.##
```

Example:

```
BETTER AUTO SPEED velocity on diag_y try 1 (23.91s)
Moved 13.44mm at a91456/v1700 after 8.92/0.31/13.87s
Missed X 0.06, Y 132.00
```

### Acceleration results

```
BETTER AUTO SPEED found maximum acceleration after #.##s
| `AXIS 1` max: ###
| `AXIS 2` max: ###

Recommended values:
| `AXIS 1` max: ###
| `AXIS 2` max: ###
Recommended acceleration: ###
```

Example:

```
BETTER AUTO SPEED found maximum acceleration after 218.00s
| DIAG X max: 48979
| DIAG Y max: 48979

Recommended values:
| DIAG X max: 39183
| DIAG Y max: 39183
Recommended acceleration: 39183
```

### Velocity results

```
BETTER AUTO SPEED found maximum velocity after #.##s
| `AXIS 1` max: ###
| `AXIS 2` max: ###

Recommended values
| `AXIS 1` max: ###
| `AXIS 2` max: ###
Recommended velocity: ###
```

Example:

```
BETTER AUTO SPEED found maximum velocity after 307.60s
| DIAG X max: 577
| DIAG Y max: 552

Recommended values
| DIAG X max: 462
| DIAG Y max: 442
Recommended velocity: 442
```

### Recommended results

```
BETTER AUTO SPEED found recommended acceleration and velocity after #.##s
| `AXIS 1` max: a### v###
| `AXIS 2`: a### v###
Recommended accel: ###
Recommended velocity: ###
```

Example:

```
BETTER AUTO SPEED found recommended acceleration and velocity after 525.61s
| DIAG X max: a39183 v462
| DIAG Y max: a39183 v442
Recommended accel: 39183
Recommended velocity: 442
```
