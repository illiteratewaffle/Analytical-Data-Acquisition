from __future__ import annotations
"""User‑friendly, GUI‑ready runtime settings for the GC‑DAQ app.

🔧 **How to use (non‑coders welcome!)**
--------------------------------------------------
1. Open *this* file.
2. Change the numbers or text after the `=` signs to what you need.
3. Save – the rest of the program picks the new values up automatically.

A future settings dialog can simply import this class and read / write the
attributes directly. No JSON, INI, or command‑line flags are required.
"""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class Settings:
    # Acquisition parameters
    channel: int = 0                 # DAQ analog channel wired to detector
    sampling_frequency: int = 10_000 # Hz, e.g. 10_000 for 10 kHz
    block_size: int = 1_000          # samples grabbed per driver call
    run_duration: float = 30.0       # seconds, total length of a run

    # Valve timing map  { valve_name : seconds_from_start }
    valve_schedule: Dict[str, float] = field(default_factory=lambda: {
        # "ValveLabel" : time_in_seconds   (edit as needed)
        "SampleInject": 0.0,     # open right at t = 0 s
        "BackFlush"   : 15.0,    # swap after 15 seconds
    })

    # Misc / operator info
    operator_initials: str = "NULL"   # appears in data‑file names

    # Helpers
    def validate(self) -> None:
        """Raise ValueError if any field is outside a sane range."""
        if not (0 <= self.channel <= 15):
            raise ValueError("channel must be between 0 and 15 (inclusive)")
        if self.sampling_frequency <= 0:
            raise ValueError("sampling_frequency must be positive")
        if self.block_size <= 0:
            raise ValueError("block_size must be positive")
        if self.run_duration <= 0:
            raise ValueError("run_duration must be positive")
        for name, t in self.valve_schedule.items():
            if t < 0:
                raise ValueError(f"valve '{name}' time cannot be negative")

    # Easy‑to‑read dump (handy for logging)
    def as_dict(self) -> Dict[str, Any]:
        """Return a plain dict of the current settings."""
        return {
            "channel"           : self.channel,
            "sampling_frequency": self.sampling_frequency,
            "block_size"        : self.block_size,
            "run_duration"      : self.run_duration,
            "valve_schedule"    : dict(self.valve_schedule),
            "operator_initials" : self.operator_initials,
        }

    def __str__(self) -> str:
        items = [f"{k}: {v}" for k, v in self.as_dict().items()]
        return "\n".join(items)


# Global singleton – import once, everywhere
settings = Settings()

# Validate immediately so typos are caught on launch
settings.validate()
