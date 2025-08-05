from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Tuple
import os

@dataclass
class Settings:
    # Board configuration
    ai_board_number: int =0 # Analog input board number
    dio_board_number: int =0 # Digital I/O board number (for valves)
    ai_channel: int =0 # Analog input channel

    # Acquisition parameters
    sampling_frequency: int = 10_000  # Hz, e.g. 10_000 for 10 kHz
    block_size: int = 1_000  # samples grabbed per driver call
    run_duration: float = 595.0  # seconds, total length of a run (595 for 10 min interval)

    # Misc / operator info
    operator_initials: str = "NULL"  # appears in data‑file names
    save_directory: str = field(default=os.getcwd())

    # Auto-run parameters
    auto_run: bool = False  # Enable auto-run feature
    auto_run_interval: int = 600  # Seconds between runs (default 10 minutes)

    # Valve scheduling - now a list of (time, valve) pairs
    valve_schedule: List[Tuple[float, str]] = field(default_factory=lambda: [
        (15.0, "B")  # Default: swap to B at 15s
    ])

    # Properties for synchronization
    @property
    def effective_run_duration(self) -> float:
        """Run duration minus 5s buffer"""
        return max(0, self.run_duration - 5.0)

    # Helpers
    def validate(self) -> None:
        """Raise ValueError if any field is outside a sane range."""
        if not (0 <= self.ai_board_number <= 15):
            raise ValueError("AI board number must be between 0 and 15 (inclusive)")
        if not (0 <= self.dio_board_number <= 15):
            raise ValueError("DIO board number must be between 0 and 15 (inclusive)")
        if not (0 <= self.ai_channel <= 15):
            raise ValueError("AI channel must be between 0 and 15 (inclusive)")
        if self.sampling_frequency <= 0:
            raise ValueError("sampling_frequency must be positive")
        if self.block_size <= 0:
            raise ValueError("block_size must be positive")
        if self.run_duration <= 0:
            raise ValueError("run_duration must be positive")
        for time, valve in self.valve_schedule:
            if time < 0:
                raise ValueError(f"valve time cannot be negative")
            if valve not in ("A", "B"):
                raise ValueError(f"valve must be 'A' or 'B'")
        if self.auto_run_interval <= 0:
            raise ValueError("auto_run_interval must be positive")

    # Easy‑to‑read dump (handy for logging)
    def as_dict(self) -> Dict[str, Any]:
        """Return a plain dict of the current settings."""
        return {
            "ai_board_number": self.ai_board_number,
            "dio_board_number": self.dio_board_number,
            "ai_channel": self.ai_channel,
            "sampling_frequency": self.sampling_frequency,
            "block_size": self.block_size,
            "run_duration": self.run_duration,
            "operator_initials": self.operator_initials,
            "auto_run": self.auto_run,
            "auto_run_interval": self.auto_run_interval,
            "valve_schedule": list(self.valve_schedule),
        }

    def __str__(self) -> str:
        items = [f"{k}: {v}" for k, v in self.as_dict().items()]
        return "\n".join(items)


# Global singleton – import once, everywhere
settings = Settings()

# Validate immediately so typos are caught on launch
settings.validate()