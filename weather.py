from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List

WEATHER_DISPLAY_NAMES = {
    "clear": "Clear",
    "sun": "Sun",
    "rain": "Rain",
    "sandstorm": "Sandstorm",
    "hail": "Hail",
}

RANDOM_WEATHER_KINDS = ["clear", "sun", "rain", "sandstorm", "hail"]


@dataclass
class WeatherState:
    """Battlefield weather shared by both sides."""

    kind: str = "clear"
    turns_remaining: int = 5

    def __post_init__(self) -> None:
        """Validate and normalize fields after initialization."""
        if self.kind not in WEATHER_DISPLAY_NAMES:
            raise ValueError(f"Unknown weather kind '{self.kind}'.")
        if self.turns_remaining < 0:
            raise ValueError("Weather turns_remaining cannot be negative.")

    @classmethod
    def clear(cls, turns_remaining: int = 5) -> "WeatherState":
        """Create a clear-weather state."""
        return cls(kind="clear", turns_remaining=turns_remaining)

    @classmethod
    def random_kind(cls) -> str:
        """Handle random kind."""
        return random.choice(RANDOM_WEATHER_KINDS)

    @property
    def is_active(self) -> bool:
        """Return the current is active."""
        return self.kind != "clear" and self.turns_remaining > 0

    @property
    def display_name(self) -> str:
        """Return the current display name."""
        return WEATHER_DISPLAY_NAMES[self.kind]

    def clone(self) -> "WeatherState":
        """Handle clone."""
        return WeatherState(kind=self.kind, turns_remaining=self.turns_remaining)

    def describe_for_ui(self) -> str:
        """Handle describe for ui."""
        return f"Weather: {self.display_name} ({self.turns_remaining} turn(s) left)"

    def start_message(self) -> str:
        """Handle start message."""
        if self.kind == "sun":
            return "The sunlight turned harsh!"
        if self.kind == "rain":
            return "It started to rain!"
        if self.kind == "sandstorm":
            return "A sandstorm kicked up!"
        if self.kind == "hail":
            return "It started to hail!"
        return "The weather cleared."

    def change_message(self, previous_kind: str) -> str:
        """Handle change message."""
        if self.kind == previous_kind:
            return f"The weather remained {self.display_name.lower()}."
        return self.start_message()

    def upkeep_message(self) -> str:
        """Handle upkeep message."""
        if self.kind == "sun":
            return "The sunlight is strong."
        if self.kind == "rain":
            return "Rain is falling."
        if self.kind == "sandstorm":
            return "The sandstorm rages."
        if self.kind == "hail":
            return "Hail continues to fall."
        return ""

    def ending_message(self) -> str:
        """Handle ending message."""
        if self.kind == "sun":
            return "The harsh sunlight faded."
        if self.kind == "rain":
            return "The rain stopped."
        if self.kind == "sandstorm":
            return "The sandstorm subsided."
        if self.kind == "hail":
            return "The hail stopped."
        return "The weather cleared."

    def damage_multiplier_for_move(self, move_type: str) -> float:
        """Handle damage multiplier for move."""
        if not self.is_active:
            return 1.0
        if self.kind == "sun":
            if move_type == "Fire":
                return 1.5
            if move_type == "Water":
                return 0.5
        if self.kind == "rain":
            if move_type == "Water":
                return 1.5
            if move_type == "Fire":
                return 0.5
        return 1.0

    def weather_damage_targets(self, battlers: List["PokemonInstance"]) -> List["PokemonInstance"]:
        """Handle weather damage targets."""
        if not self.is_active:
            return []
        if self.kind == "sandstorm":
            immune_types = {"Rock", "Ground", "Steel"}
            return [b for b in battlers if not set(b.types).intersection(immune_types)]
        if self.kind == "hail":
            return [b for b in battlers if "Ice" not in b.types]
        return []
