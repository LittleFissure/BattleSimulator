from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


@dataclass
class StatusEffect:
    """Base class for persistent battle conditions."""

    name: str
    duration: Optional[int] = None
    is_volatile: bool = False
    ticks_while_benched: bool = False

    def __post_init__(self) -> None:
        """Validate the core status fields."""
        if not self.name.strip():
            raise ValueError("Status effect name cannot be empty.")
        if self.duration is not None and self.duration < 1:
            raise ValueError("Status effect duration must be at least 1.")

    def on_apply(self, target: "PokemonInstance", log: List[str]) -> None:
        """Run once when the status is first applied."""

    def on_turn_start(self, target: "PokemonInstance", log: List[str]) -> None:
        """Run at the start of the active Pokemon's turn."""

    def on_turn_end(self, target: "PokemonInstance", log: List[str]) -> None:
        """Run at the end of the active Pokemon's turn."""

    def on_benched_round_end(self, target: "PokemonInstance", log: List[str]) -> bool:
        """Run at round end while the Pokemon is benched.

        Return True when the status should be removed immediately, usually
        because it woke the Pokemon up or otherwise expired itself.
        """
        return False

    def modify_outgoing_stat(
        self,
        target: "PokemonInstance",
        stat_name: str,
        value: int,
    ) -> int:
        """Change a stat while this Pokemon is attacking or acting."""
        return value

    def modify_incoming_stat(
        self,
        target: "PokemonInstance",
        stat_name: str,
        value: int,
    ) -> int:
        """Change a stat while this Pokemon is defending."""
        return value

    def prevents_action(self, target: "PokemonInstance", log: List[str]) -> bool:
        """Return True when this status stops the Pokemon from acting."""
        return False

    def tick_duration(self) -> bool:
        """Advance the duration counter and report whether the status expired."""
        if self.duration is None:
            return False

        self.duration -= 1
        return self.duration <= 0


@dataclass
class Burn(StatusEffect):
    """Burn chips HP every turn and halves physical Attack."""

    def __init__(self, duration: Optional[int] = None) -> None:
        """Initialize burn state."""
        super().__init__("Burn", duration, False, False)

    def on_apply(self, target: "PokemonInstance", log: List[str]) -> None:
        """Handle on apply."""
        log.append(f"{target.name} was burned!")

    def on_turn_end(self, target: "PokemonInstance", log: List[str]) -> None:
        """Handle on turn end."""
        damage = max(1, target.max_hp // 8)
        before_hp = target.current_hp
        target.take_damage(damage)
        actual_damage = before_hp - target.current_hp
        log.append(f"{target.name} is hurt by its burn for {actual_damage} damage.")

    def modify_outgoing_stat(
        self,
        target: "PokemonInstance",
        stat_name: str,
        value: int,
    ) -> int:
        """Handle modify outgoing stat."""
        return value


@dataclass
class Poison(StatusEffect):
    """Poison chips HP at the end of each turn."""

    def __init__(self, duration: Optional[int] = None) -> None:
        """Initialize poison state."""
        super().__init__("Poison", duration, False, False)

    def on_apply(self, target: "PokemonInstance", log: List[str]) -> None:
        """Handle on apply."""
        log.append(f"{target.name} was poisoned!")

    def on_turn_end(self, target: "PokemonInstance", log: List[str]) -> None:
        """Handle on turn end."""
        damage = max(1, target.max_hp // 8)
        before_hp = target.current_hp
        target.take_damage(damage)
        actual_damage = before_hp - target.current_hp
        log.append(f"{target.name} is hurt by poison for {actual_damage} damage.")


@dataclass
class Paralysis(StatusEffect):
    """Paralysis halves Speed and may stop actions."""

    def __init__(self, duration: Optional[int] = None) -> None:
        """Initialize paralysis state."""
        super().__init__("Paralysis", duration, False, False)

    def on_apply(self, target: "PokemonInstance", log: List[str]) -> None:
        """Handle on apply."""
        log.append(f"{target.name} is paralyzed!")

    def modify_outgoing_stat(
        self,
        target: "PokemonInstance",
        stat_name: str,
        value: int,
    ) -> int:
        """Handle modify outgoing stat."""
        if stat_name == "speed":
            return max(1, int(value * 0.5))
        return value

    def prevents_action(self, target: "PokemonInstance", log: List[str]) -> bool:
        """Handle prevents action."""
        if random.random() < 0.25:
            log.append(f"{target.name} is paralyzed! It can't move!")
            return True
        return False


@dataclass
class Sleep(StatusEffect):
    """Sleep blocks actions and keeps counting down even on the bench."""

    def __init__(self, duration: Optional[int] = None) -> None:
        """Initialize sleep state."""
        if duration is None:
            duration = random.randint(1, 3)
        super().__init__("Sleep", duration, False, True)

    def on_apply(self, target: "PokemonInstance", log: List[str]) -> None:
        """Handle on apply."""
        log.append(f"{target.name} fell asleep!")

    def prevents_action(self, target: "PokemonInstance", log: List[str]) -> bool:
        """Handle prevents action."""
        log.append(f"{target.name} is fast asleep!")
        return True

    def on_benched_round_end(self, target: "PokemonInstance", log: List[str]) -> bool:
        """Handle on benched round end."""
        if self.duration is None:
            return False
        if self.duration == 1:
            log.append(f"{target.name} woke up while benched.")
            return True
        return False


@dataclass
class Confusion(StatusEffect):
    """Confusion is volatile and may cause self-hit damage."""

    def __init__(self, duration: Optional[int] = None) -> None:
        """Initialize confusion state."""
        if duration is None:
            duration = random.randint(2, 5)
        super().__init__("Confusion", duration, True, False)

    def on_apply(self, target: "PokemonInstance", log: List[str]) -> None:
        """Handle on apply."""
        log.append(f"{target.name} became confused!")

    def prevents_action(self, target: "PokemonInstance", log: List[str]) -> bool:
        """Handle prevents action."""
        log.append(f"{target.name} is confused!")

        if random.random() < 0.5:
            damage = self.calculate_self_hit_damage(target)
            before_hp = target.current_hp
            target.take_damage(damage)
            actual_damage = before_hp - target.current_hp
            log.append(f"{target.name} hurt itself in confusion for {actual_damage} damage!")

            if target.is_fainted:
                log.append(f"{target.name} fainted!")

            return True

        return False

    def calculate_self_hit_damage(self, target: "PokemonInstance") -> int:
        """Use a simple physical self-hit formula for confusion damage."""
        attack_stat = target.get_effective_stat("attack")
        defense_stat = target.get_effective_defensive_stat("defense")
        return max(1, int(8 + attack_stat - defense_stat))


@dataclass
class Freeze(StatusEffect):
    """Freeze blocks actions until the Pokemon thaws."""

    def __init__(self) -> None:
        """Initialize freeze state."""
        super().__init__("Freeze", None, False, False)

    def on_apply(self, target: "PokemonInstance", log: List[str]) -> None:
        """Handle on apply."""
        log.append(f"{target.name} was frozen solid!")

    def prevents_action(self, target: "PokemonInstance", log: List[str]) -> bool:
        """Handle prevents action."""
        if random.random() < 0.20:
            target.remove_status_effect(self.name)
            log.append(f"{target.name} thawed out!")
            return False

        log.append(f"{target.name} is frozen solid!")
        return True


@dataclass
class Flinch(StatusEffect):
    """Flinch is a volatile same-turn interrupt."""

    def __init__(self) -> None:
        """Initialize flinch state."""
        super().__init__("Flinch", 1, True, False)

    def on_apply(self, target: "PokemonInstance", log: List[str]) -> None:
        """Handle on apply."""
        log.append(f"{target.name} flinched!")

    def prevents_action(self, target: "PokemonInstance", log: List[str]) -> bool:
        """Handle prevents action."""
        log.append(f"{target.name} flinched and couldn't move!")
        return True


@dataclass
class Protect(StatusEffect):
    """Protect blocks incoming move effects for the current round."""

    def __init__(self) -> None:
        """Initialize protect state."""
        super().__init__("Protect", 1, True, False)

    def on_apply(self, target: "PokemonInstance", log: List[str]) -> None:
        """Handle on apply."""
        log.append(f"{target.name} protected itself!")


STATUS_REGISTRY: Dict[str, Callable[[], StatusEffect]] = {
    "Burn": Burn,
    "Poison": Poison,
    "Paralysis": Paralysis,
    "Sleep": Sleep,
    "Confusion": Confusion,
    "Freeze": Freeze,
    "Flinch": Flinch,
    "Protect": Protect,
}


def get_status_factory(status_name: str) -> Callable[[], StatusEffect]:
    """Return the constructor used to create a named status."""
    if status_name not in STATUS_REGISTRY:
        raise ValueError(f"Unknown status '{status_name}'.")
    return STATUS_REGISTRY[status_name]