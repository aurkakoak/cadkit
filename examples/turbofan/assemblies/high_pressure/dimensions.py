"""Fixed sleeve and rotor drawing stations; shared fit inputs live with the engine."""

from ...parts.rotor import RotorStage

SLEEVE_START = 108.0
SLEEVE_LENGTH = 129.0

ROTOR_STAGES = (
    RotorStage(
        name="hp-compressor-1",
        station=122,
        tip_radius=29,
        blade_count=24,
        chord=8,
        stagger=31,
        sweep=2,
        hub_radius=13,
    ),
    RotorStage(
        name="hp-compressor-2",
        station=141,
        tip_radius=26,
        blade_count=26,
        chord=7,
        stagger=29,
        sweep=2,
        hub_radius=13,
    ),
    RotorStage(
        name="hp-compressor-3",
        station=159,
        tip_radius=23,
        blade_count=28,
        chord=6,
        stagger=27,
        sweep=2,
        hub_radius=13,
    ),
    RotorStage(
        name="hp-turbine",
        station=222,
        tip_radius=29,
        blade_count=24,
        chord=8,
        stagger=-27,
        sweep=2,
        hub_radius=13,
    ),
)
