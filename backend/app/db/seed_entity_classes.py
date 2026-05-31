"""Canonical entity-class seed data (§1.1 ``EntityClassId`` + color scheme).

[LOAD-BEARING] ``ENTITY_CLASS_SEED_DATA`` is the source-of-truth list of the 8
entity classes. The ``0001_initial_schema`` migration INSERTs these rows; S2-G
and integration fixtures import this list. Colors are the canonical color-coded
overlay scheme read by the downstream canvas renderer via ``entity_class.color_hex``.

Color spec:
  * ``pipe``         -> ``#1f77b4``
  * ``valve_*``      -> ``#d62728`` (the whole valve family shares one color)
  * ``instrument``   -> ``#2ca02c``

``parent_class`` is ``'valve'`` for every ``valve_*`` row and ``NULL`` for
``pipe`` / ``instrument``.
"""
from __future__ import annotations

_PIPE_COLOR = "#1f77b4"
_VALVE_COLOR = "#d62728"
_INSTRUMENT_COLOR = "#2ca02c"

ENTITY_CLASS_SEED_DATA: list[dict] = [
    {"id": "pipe", "name": "Pipe", "parent_class": None, "color_hex": _PIPE_COLOR},
    {"id": "valve_gate", "name": "Gate Valve", "parent_class": "valve", "color_hex": _VALVE_COLOR},
    {"id": "valve_globe", "name": "Globe Valve", "parent_class": "valve", "color_hex": _VALVE_COLOR},
    {"id": "valve_ball", "name": "Ball Valve", "parent_class": "valve", "color_hex": _VALVE_COLOR},
    {"id": "valve_butterfly", "name": "Butterfly Valve", "parent_class": "valve", "color_hex": _VALVE_COLOR},
    {"id": "valve_check", "name": "Check Valve", "parent_class": "valve", "color_hex": _VALVE_COLOR},
    {"id": "valve_control", "name": "Control Valve", "parent_class": "valve", "color_hex": _VALVE_COLOR},
    {"id": "instrument", "name": "Instrument", "parent_class": None, "color_hex": _INSTRUMENT_COLOR},
]

__all__ = ["ENTITY_CLASS_SEED_DATA"]
