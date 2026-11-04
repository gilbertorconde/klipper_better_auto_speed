# Find your printers max speed before losing steps
#
# Copyright (C) 2026 gilbertorconde (https://github.com/gilbertorconde) - Better Auto Speed fork
#
# This file may be distributed under the terms of the MIT license.
#
# Decide whether a [printer] option can be queued for SAVE_CONFIG.
#
# SAVE_CONFIG refuses the whole save when an autosave option is also set in an
# included file ("conflicts with included value"), which then blocks every
# later SAVE_CONFIG until Klipper restarts. Options set in printer.cfg's main
# body are fine: SAVE_CONFIG comments those lines out itself.

import configparser
import glob
import os
import sys


def _klipper_parser(configfile):
    """Return Klipper's own (read, split_autosave, build_with_includes)."""
    module = sys.modules.get(type(configfile).__module__)
    reader_cls = getattr(module, 'ConfigFileReader', None)
    if reader_cls is not None and hasattr(configfile, 'autosave'):
        # Klipper since 2024-09: parsing lives in ConfigFileReader.
        reader = reader_cls()
        return (reader.read_config_file, configfile.autosave._find_autosave_data,
                reader.build_fileconfig_with_includes)
    # Older Klipper and Kalico keep the same helpers on PrinterConfig itself.
    return (configfile._read_config_file, configfile._find_autosave_data,
            lambda data, filename: configfile._build_config_wrapper(data, filename).fileconfig)


def _plain_fileconfig(data):
    # Same parser settings as Klipper; '#' comments are stripped first like Klipper.
    fileconfig = configparser.RawConfigParser(strict=False, inline_comment_prefixes=(';', '#'))
    fileconfig.read_string('\n'.join(line.split('#', 1)[0] for line in data.split('\n')))
    return fileconfig


def _includes_only(data):
    """Keep only [include ...] directives (and any lines up to the next section).

    Parsing this with Klipper's reader yields exactly the options the includes
    set, i.e. what SAVE_CONFIG checks after it comments out main-body values.
    The lines after an include header are kept for Kalico's include variables.
    """
    kept, keep = [], False
    for line in data.split('\n'):
        mo = configparser.RawConfigParser.SECTCRE.match(line.split('#', 1)[0])
        if mo:
            keep = mo.group('header').startswith('include ')
        if keep:
            kept.append(line)
    return '\n'.join(kept)


def _locate(filename, data, section, option, visited):
    """Best-effort list of files setting section/option (for the message only)."""
    path = os.path.abspath(filename)
    if path in visited:
        return []
    visited.add(path)
    try:
        fileconfig = _plain_fileconfig(data)
    except configparser.Error:
        return []
    found = [path] if fileconfig.has_option(section, option) else []
    for name in fileconfig.sections():
        if not name.startswith('include '):
            continue
        pattern = os.path.join(os.path.dirname(path), name[8:].strip())
        for include in sorted(glob.glob(pattern)):
            try:
                with open(include) as f:
                    include_data = f.read()
            except OSError:
                continue
            found += [p for p in _locate(include, include_data, section, option, visited)
                      if p not in found]
    return found


def find_included_definitions(printer, configfile, section, options):
    """Return {option: [files]} for options set by an included config file.

    Whether an include sets an option is decided by Klipper's own parser (same
    include resolution SAVE_CONFIG uses). Values set only in printer.cfg's main
    body or its SAVE_CONFIG block are not reported. The file list is best effort
    and may be empty when the defining include could not be located. Raises if
    the config can't be read, so callers can refuse to queue rather than guess.
    """
    read, split_autosave, build_with_includes = _klipper_parser(configfile)
    filename = printer.get_start_args()['config_file']
    regular_data, _autosave = split_autosave(read(filename))
    regular = build_with_includes(_includes_only(regular_data), filename)
    main = os.path.abspath(filename)
    return {option: [path for path in _locate(filename, regular_data, section, option, set())
                     if path != main]
            for option in options if regular.has_option(section, option)}
