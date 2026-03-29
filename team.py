from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from pokemon import PokemonInstance


@dataclass
class Team:
    """A trainer's party for a standard 1v1 battle."""

    name: str
    members: List[PokemonInstance] = field(default_factory=list)
    active_index: int = 0

    def __post_init__(self) -> None:
        """Validate the team and choose the first healthy lead."""
        if not self.name.strip():
            raise ValueError("Team name cannot be empty.")
        if not 1 <= len(self.members) <= 6:
            raise ValueError("A team must have between 1 and 6 Pokemon.")

        if self.members[self.active_index].is_fainted:
            self.active_index = self.first_available_index()

    @property
    def active(self) -> PokemonInstance:
        """Return the Pokemon currently on the field."""
        return self.members[self.active_index]

    def first_available_index(self) -> int:
        """Return the first non-fainted team member index."""
        for index, pokemon in enumerate(self.members):
            if not pokemon.is_fainted:
                return index
        raise ValueError("This team has no usable Pokemon left.")

    def has_usable_pokemon(self) -> bool:
        """Return True when the team still has at least one healthy Pokemon."""
        return any(not pokemon.is_fainted for pokemon in self.members)

    def has_usable_benched_pokemon(self) -> bool:
        """Return True when the team can switch to someone on the bench."""
        return any(
            index != self.active_index and not pokemon.is_fainted
            for index, pokemon in enumerate(self.members)
        )

    def can_switch_to(self, index: int) -> bool:
        """Return True when the requested switch target is valid."""
        if index < 0 or index >= len(self.members):
            return False
        if index == self.active_index:
            return False
        if self.members[index].is_fainted:
            return False
        return True

    def switch_to(self, index: int) -> PokemonInstance:
        """Switch the active Pokemon and return the new battler."""
        if not self.can_switch_to(index):
            raise ValueError("Invalid switch target.")

        outgoing = self.active
        outgoing.on_switch_out()
        self.active_index = index
        incoming = self.active
        incoming.on_switch_in()
        return incoming

    def force_replace(self, index: int) -> PokemonInstance:
        """Send in a replacement after a faint, without switch-out cleanup."""
        if index < 0 or index >= len(self.members):
            raise ValueError("Invalid replacement target.")
        if index == self.active_index:
            raise ValueError("Cannot replace with the current active Pokemon.")
        if self.members[index].is_fainted:
            raise ValueError("Cannot replace with a fainted Pokemon.")

        self.active_index = index
        incoming = self.active
        incoming.on_switch_in()
        return incoming

    def choose_first_benched_available(self) -> int:
        """Return the first healthy non-active team member index."""
        for index, pokemon in enumerate(self.members):
            if index != self.active_index and not pokemon.is_fainted:
                return index
        raise ValueError("No benched Pokemon are available.")

    def process_benched_round_end_statuses(self, log: List[str]) -> None:
        """Advance bench-only timers, such as sleep turns while switched out."""
        for index, pokemon in enumerate(self.members):
            if index == self.active_index or pokemon.is_fainted:
                continue
            pokemon.process_benched_round_end_statuses(log)
