from __future__ import annotations
from email.mime import base

import json
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from statuses import StatusEffect, get_status_factory
from typeData import get_stab_multiplier, get_type_multiplier
from weather import WeatherState


def has_status(target: "PokemonInstance", status_name: str) -> bool:
    """Return True if the target currently has the named status."""
    return any(status.name == status_name for status in target.status_effects)


def try_block_with_protect(
    target: "PokemonInstance",
    log: List[str],
    context: Dict[str, object],
) -> bool:
    """Return True if Protect blocks the incoming effect."""
    if not has_status(target, "Protect"):
        return False

    if not context.get("protect_triggered", False):
        log.append(f"{target.name} protected itself!")
        context["protect_triggered"] = True

    context["damage_dealt"] = 0
    context.setdefault("hits", 0)
    context["move_disrupted"] = True
    context["move_disruption_reason"] = "blocked"
    return True


@dataclass
class Move:
    """Represents a move definition and its effect list."""

    name: str
    move_type: str
    accuracy: int = 100
    max_pp: int = 1
    priority: int = 0
    effects: List["Effect"] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate and normalize fields after initialization."""
        if not self.name.strip():
            raise ValueError("Move name cannot be empty.")
        if not self.move_type.strip():
            raise ValueError("Move type cannot be empty.")
        if not 0 <= self.accuracy <= 100:
            raise ValueError("Move accuracy must be between 0 and 100.")
        if self.max_pp < 1:
            raise ValueError("Move max_pp must be at least 1.")

    def check_hit(self, user: "PokemonInstance", target: "PokemonInstance") -> bool:
        """Handle check hit."""
        acc = user.get_effective_stat("accuracy")
        eva = target.get_effective_stat("evasion")
        chance = max(1.0, min(100.0, self.accuracy * (float(acc) / float(eva))))
        return random.uniform(0.0, 100.0) < chance


class Effect:
    """Base class for move effects."""

    def apply(
        self,
        user: "PokemonInstance",
        target: "PokemonInstance",
        move_type: str,
        move_name: str,
        log: List[str],
        context: Dict[str, object],
    ) -> None:
        """Handle apply."""
        raise NotImplementedError("Effect subclasses must implement apply().")


@dataclass
class SetWeatherEffect(Effect):
    weather_kind: str
    duration: int = 5

    def __post_init__(self) -> None:
        """Validate and normalize fields after initialization."""
        valid = {"clear", "sun", "rain", "sandstorm", "hail"}
        if self.weather_kind not in valid:
            raise ValueError(f"Unknown weather kind '{self.weather_kind}'.")
        if self.duration < 0:
            raise ValueError("Weather duration cannot be negative.")

    def apply(self, user, target, move_type, move_name, log, context) -> None:
        """Handle apply."""
        battle_manager = context.get("battle_manager")
        if battle_manager is None:
            raise ValueError("Battle manager missing from move context.")
        battle_manager.set_weather(self.weather_kind, self.duration, log)


@dataclass
class DamageEffect(Effect):
    power: int
    category: str
    crit_stage: int = 0
    crit_multiplier: float = 1.5

    def __post_init__(self) -> None:
        """Validate and normalize fields after initialization."""
        if self.power < 0:
            raise ValueError("Damage power cannot be negative.")
        if self.category not in {"physical", "special"}:
            raise ValueError("Damage category must be physical or special.")
        if self.crit_stage < 0:
            raise ValueError("crit_stage cannot be negative.")
        if self.crit_multiplier < 1.0:
            raise ValueError("crit_multiplier must be at least 1.0.")

    def get_crit_chance(self) -> float:
        """Return crit chance."""
        crit_stage_table = {0: 1.0 / 24.0, 1: 1.0 / 8.0, 2: 1.0 / 2.0}
        if self.crit_stage >= 3:
            return 1.0
        return crit_stage_table.get(self.crit_stage, 1.0 / 24.0)

    def is_critical_hit(self) -> bool:
        """Return whether critical hit."""
        return random.random() < self.get_crit_chance()

    def get_damage_stats(
        self,
        user: "PokemonInstance",
        target: "PokemonInstance",
        is_crit: bool,
    ) -> Tuple[int, int]:
        """Return damage stats."""
        if self.category == "physical":
            attack_name = "attack"
            defense_name = "defense"
        else:
            attack_name = "special_attack"
            defense_name = "special_defense"

        if is_crit:
            attack_stat = user.get_effective_stat(attack_name, stage_rule="ignore_negative")
            defense_stat = target.get_effective_defensive_stat(defense_name, stage_rule="ignore_positive")
        else:
            attack_stat = user.get_effective_stat(attack_name)
            defense_stat = target.get_effective_defensive_stat(defense_name)

        return attack_stat, defense_stat

    def calculate_damage(
        self,
        user: "PokemonInstance",
        target: "PokemonInstance",
        move_type: str,
        is_crit: bool,
        weather: Optional[WeatherState] = None,
    ) -> Tuple[int, float, float]:
        """Handle calculate damage."""
        attack_stat, defense_stat = self.get_damage_stats(user, target, is_crit)
        level = user.level
        levelPart = 2 * level / 5 + 2
        statPart = self.power * attack_stat/defense_stat
        base_damage = max(0,levelPart * statPart / 50 + 2 )
        #print(levelPart)
        #print(statPart)
        #print(base_damage)
        stab_multiplier = get_stab_multiplier(user.types, move_type)
        type_multiplier = get_type_multiplier(move_type, target.types)
        print(type_multiplier)
        weather_multiplier = 1.0 if weather is None else weather.damage_multiplier_for_move(move_type)
        burnMulti = 0.5 if (any(isinstance(status,get_status_factory("Burn")) for status in user.status_effects)) and self.category == "physical" else 1

        final_damage = base_damage * stab_multiplier * type_multiplier * weather_multiplier * random.uniform(0.85,1.0)
        
        
        if is_crit:
            final_damage *= self.crit_multiplier
        return max(0, int(final_damage)), type_multiplier, stab_multiplier

    def apply(self, user, target, move_type, move_name, log, context) -> None:
        """Handle apply."""
        if try_block_with_protect(target, log, context):
            return

        is_crit = self.is_critical_hit()
        weather = context.get("weather")
        damage, type_multiplier, stab_multiplier = self.calculate_damage(user, target, move_type, is_crit, weather)
        before_hp = target.current_hp
        target.take_damage(damage)
        actual_damage = before_hp - target.current_hp
        context["damage_dealt"] = context.get("damage_dealt", 0) + actual_damage
        log.append(f"{target.name} took {actual_damage} damage.")

        if is_crit:
            log.append("A critical hit!")
        if stab_multiplier > 1.0:
            log.append("STAB boosted the attack!")
        if type_multiplier > 1.0:
            log.append("It's super effective!")
        elif type_multiplier == 0.0:
            log.append("It had no effect!")
        elif type_multiplier < 1.0:
            log.append("It's not very effective...")
        if target.is_fainted:
            log.append(f"{target.name} fainted!")


@dataclass
class MultiHitDamageEffect(Effect):
    power: int
    category: str
    min_hits: int
    max_hits: int
    crit_stage: int = 0
    crit_multiplier: float = 1.5

    def __post_init__(self) -> None:
        """Validate and normalize fields after initialization."""
        if self.power < 0:
            raise ValueError("Damage power cannot be negative.")
        if self.category not in {"physical", "special"}:
            raise ValueError("Invalid category.")
        if self.min_hits < 1:
            raise ValueError("min_hits must be at least 1.")
        if self.max_hits < self.min_hits:
            raise ValueError("max_hits must be at least min_hits.")
        if self.crit_stage < 0:
            raise ValueError("crit_stage cannot be negative.")
        if self.crit_multiplier < 1.0:
            raise ValueError("crit_multiplier must be at least 1.0.")

    def roll_hits(self) -> int:
        """Handle roll hits."""
        return random.randint(self.min_hits, self.max_hits)

    def apply(self, user, target, move_type, move_name, log, context) -> None:
        """Handle apply."""
        if try_block_with_protect(target, log, context):
            return

        hits = self.roll_hits()
        total_damage = 0
        actual_hits = 0

        for hit_index in range(hits):
            if target.is_fainted:
                break

            damage_effect = DamageEffect(
                power=self.power,
                category=self.category,
                crit_stage=self.crit_stage,
                crit_multiplier=self.crit_multiplier,
            )
            is_crit = damage_effect.is_critical_hit()
            weather = context.get("weather")
            damage, type_multiplier, stab_multiplier = damage_effect.calculate_damage(user, target, move_type, is_crit, weather)
            before_hp = target.current_hp
            target.take_damage(damage)
            actual_damage = before_hp - target.current_hp
            total_damage += actual_damage
            actual_hits += 1

            log.append(f"Hit {hit_index + 1}! {target.name} took {actual_damage} damage.")
            if is_crit:
                log.append("A critical hit!")
            if stab_multiplier > 1.0:
                log.append("STAB boosted the attack!")
            if type_multiplier > 1.0:
                log.append("It's super effective!")
            elif type_multiplier == 0.0:
                log.append("It had no effect!")
            elif type_multiplier < 1.0:
                log.append("It's not very effective...")
            if target.is_fainted:
                log.append(f"{target.name} fainted!")
                break

        log.append(f"It hit {actual_hits} time(s)!")
        context["damage_dealt"] = context.get("damage_dealt", 0) + total_damage
        context["hits"] = actual_hits


@dataclass
class FixedDamageEffect(Effect):
    damage: int

    def __post_init__(self) -> None:
        """Validate and normalize fields after initialization."""
        if self.damage < 0:
            raise ValueError("damage cannot be negative.")

    def apply(self, user, target, move_type, move_name, log, context) -> None:
        """Handle apply."""
        if try_block_with_protect(target, log, context):
            return
        before_hp = target.current_hp
        target.take_damage(self.damage)
        actual_damage = before_hp - target.current_hp
        context["damage_dealt"] = context.get("damage_dealt", 0) + actual_damage
        log.append(f"{target.name} took {actual_damage} damage.")
        if target.is_fainted:
            log.append(f"{target.name} fainted!")


@dataclass
class CurrentHpFractionDamageEffect(Effect):
    ratio: float

    def __post_init__(self) -> None:
        """Validate and normalize fields after initialization."""
        if not (0.0 < self.ratio <= 1.0):
            raise ValueError("ratio must be between 0.0 and 1.0.")

    def apply(self, user, target, move_type, move_name, log, context) -> None:
        """Handle apply."""
        if try_block_with_protect(target, log, context):
            return
        damage = max(1, int(target.current_hp * self.ratio))
        before_hp = target.current_hp
        target.take_damage(damage)
        actual_damage = before_hp - target.current_hp
        context["damage_dealt"] = context.get("damage_dealt", 0) + actual_damage
        log.append(f"{target.name} took {actual_damage} damage.")
        if target.is_fainted:
            log.append(f"{target.name} fainted!")


@dataclass
class UserLevelDamageEffect(Effect):
    def apply(self, user, target, move_type, move_name, log, context) -> None:
        """Handle apply."""
        if try_block_with_protect(target, log, context):
            return
        before_hp = target.current_hp
        target.take_damage(user.level)
        actual_damage = before_hp - target.current_hp
        context["damage_dealt"] = context.get("damage_dealt", 0) + actual_damage
        log.append(f"{target.name} took {actual_damage} damage.")
        if target.is_fainted:
            log.append(f"{target.name} fainted!")


@dataclass
class HealPercentEffect(Effect):
    ratio: float

    def __post_init__(self) -> None:
        """Validate and normalize fields after initialization."""
        if not (0.0 < self.ratio <= 1.0):
            raise ValueError("ratio must be between 0.0 and 1.0.")

    def apply(self, user, target, move_type, move_name, log, context) -> None:
        """Handle apply."""
        heal_amount = max(1, int(user.max_hp * self.ratio))
        before_hp = user.current_hp
        user.heal(heal_amount)
        actual_healed = user.current_hp - before_hp
        if actual_healed > 0:
            log.append(f"{user.name} restored {actual_healed} HP!")
        else:
            log.append(f"{user.name}'s HP is already full!")


@dataclass
class DrainEffect(Effect):
    ratio: float

    def __post_init__(self) -> None:
        """Validate and normalize fields after initialization."""
        if not (0.0 < self.ratio <= 1.0):
            raise ValueError("ratio must be between 0.0 and 1.0.")

    def apply(self, user, target, move_type, move_name, log, context) -> None:
        """Handle apply."""
        damage_dealt = int(context.get("damage_dealt", 0))
        if damage_dealt <= 0:
            log.append(f"{user.name} could not drain any HP!")
            return
        heal_amount = max(1, int(damage_dealt * self.ratio))
        before_hp = user.current_hp
        user.heal(heal_amount)
        actual_healed = user.current_hp - before_hp
        if actual_healed > 0:
            log.append(f"{user.name} drained {actual_healed} HP!")
        else:
            log.append(f"{user.name}'s HP is already full!")


@dataclass
class RecoilEffect(Effect):
    ratio: float

    def __post_init__(self) -> None:
        """Validate and normalize fields after initialization."""
        if not (0.0 < self.ratio <= 1.0):
            raise ValueError("ratio must be between 0.0 and 1.0.")

    def apply(self, user, target, move_type, move_name, log, context) -> None:
        """Handle apply."""
        damage_dealt = int(context.get("damage_dealt", 0))
        if damage_dealt <= 0:
            return
        recoil_damage = max(1, int(damage_dealt * self.ratio))
        before_hp = user.current_hp
        user.take_damage(recoil_damage)
        actual_recoil = before_hp - user.current_hp
        log.append(f"{user.name} took {actual_recoil} recoil damage!")
        if user.is_fainted:
            log.append(f"{user.name} fainted!")


@dataclass
class ModifyStatStageEffect(Effect):
    stat_name: str
    amount: int
    target_side: str

    def __post_init__(self) -> None:
        """Validate and normalize fields after initialization."""
        valid_stats = {"attack", "defense", "special_attack", "special_defense", "speed", "accuracy", "evasion"}
        valid_targets = {"user", "target"}
        if self.stat_name not in valid_stats:
            raise ValueError(f"Unknown stat '{self.stat_name}'.")
        if self.amount == 0:
            raise ValueError("amount cannot be 0.")
        if self.target_side not in valid_targets:
            raise ValueError(f"target_side must be one of {valid_targets}.")

    def apply(self, user, target, move_type, move_name, log, context) -> None:
        """Handle apply."""
        if self.target_side == "target" and try_block_with_protect(target, log, context):
            return
        battler = user if self.target_side == "user" else target
        new_stage = battler.stat_stages.change_stage(self.stat_name, self.amount)
        if self.amount > 0:
            log.append(f"{battler.name}'s {self.stat_name} rose to {new_stage}.")
        else:
            log.append(f"{battler.name}'s {self.stat_name} fell to {new_stage}.")


@dataclass
class ApplyStatusEffect(Effect):
    status_factory: Callable[[], StatusEffect]
    target_side: str
    chance: float = 1.0

    def __post_init__(self) -> None:
        """Validate and normalize fields after initialization."""
        valid_targets = {"user", "target"}
        if self.target_side not in valid_targets:
            raise ValueError(f"target_side must be one of {valid_targets}.")
        if self.chance < 0.0 or self.chance > 1.0:
            raise ValueError("chance must be between 0.0 and 1.0.")

    def roll_application(self) -> bool:
        """Handle roll application."""
        return random.random() < self.chance

    def apply(self, user, target, move_type, move_name, log, context) -> None:
        """Handle apply."""
        if not self.roll_application():
            return
        battler = user if self.target_side == "user" else target
        status = self.status_factory()
        if status.name == "Flinch" and bool(context.get("target_already_acted", False)):
            return
        if self.target_side == "target" and try_block_with_protect(target, log, context):
            return
        battler.add_status_effect(status, log)


@dataclass
class LockMoveEffect(Effect):
    min_turns: int
    max_turns: int

    def __post_init__(self) -> None:
        """Validate and normalize fields after initialization."""
        if self.min_turns < 2:
            raise ValueError("min_turns must be at least 2.")
        if self.max_turns < self.min_turns:
            raise ValueError("max_turns must be at least min_turns.")

    def apply(self, user, target, move_type, move_name, log, context) -> None:
        """Handle apply."""
        if context.get("move_disrupted", False):
            return
        if getattr(user, "is_locked_into_move", False):
            return
        total_turns = random.randint(self.min_turns, self.max_turns)
        user.start_move_lock(move_name, total_turns)


@dataclass
class ChargeMoveEffect(Effect):
    charge_turns: int
    start_message: Optional[str] = None
    semi_invulnerable_state: Optional[str] = None
    vulnerable_to_moves: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate and normalize fields after initialization."""
        if self.charge_turns < 1:
            raise ValueError("charge_turns must be at least 1.")

    def apply(self, user, target, move_type, move_name, log, context) -> None:
        """Handle apply."""
        if context.get("is_charge_release_turn", False):
            return
        if user.is_charging_move:
            return

        user.start_charge(
            move_name=move_name,
            charge_turns=self.charge_turns,
            semi_invulnerable_state=self.semi_invulnerable_state,
            exceptions=self.vulnerable_to_moves,
        )

        if self.start_message:
            log.append(self.start_message.format(user_name=user.name, move_name=move_name))
        else:
            log.append(f"{user.name} began charging {move_name}!")

        context["charge_started"] = True
        context["skip_remaining_effects"] = True


def build_effect(effect_data: Dict[str, object]) -> Effect:
    """Build effect."""
    kind = effect_data["kind"]
    if kind == "damage":
        return DamageEffect(power=effect_data["power"], category=effect_data["category"], crit_stage=effect_data.get("crit_stage", 0))
    if kind == "multi_hit":
        return MultiHitDamageEffect(
            power=effect_data["power"],
            category=effect_data["category"],
            min_hits=effect_data["min_hits"],
            max_hits=effect_data["max_hits"],
            crit_stage=effect_data.get("crit_stage", 0),
        )
    if kind == "fixed_damage":
        return FixedDamageEffect(damage=effect_data["damage"])
    if kind == "current_hp_fraction_damage":
        return CurrentHpFractionDamageEffect(ratio=effect_data["ratio"])
    if kind == "user_level_damage":
        return UserLevelDamageEffect()
    if kind == "heal_percent":
        return HealPercentEffect(ratio=effect_data["ratio"])
    if kind == "drain":
        return DrainEffect(ratio=effect_data["ratio"])
    if kind == "recoil":
        return RecoilEffect(ratio=effect_data["ratio"])
    if kind == "modify_stat_stage":
        return ModifyStatStageEffect(stat_name=effect_data["stat_name"], amount=effect_data["amount"], target_side=effect_data["target_side"])
    if kind == "apply_status":
        return ApplyStatusEffect(
            status_factory=get_status_factory(effect_data["status_name"]),
            target_side=effect_data["target_side"],
            chance=effect_data.get("chance", 1.0),
        )
    if kind == "lock_move":
        return LockMoveEffect(min_turns=effect_data["min_turns"], max_turns=effect_data["max_turns"])
    if kind == "charge_move":
        return ChargeMoveEffect(
            charge_turns=effect_data["charge_turns"],
            start_message=effect_data.get("start_message"),
            semi_invulnerable_state=effect_data.get("semi_invulnerable_state"),
            vulnerable_to_moves=effect_data.get("vulnerable_to_moves", []),
        )
    if kind == "set_weather":
        return SetWeatherEffect(
            weather_kind=effect_data["weather_kind"],
            duration=effect_data.get("duration", 5),
        )
    raise ValueError(f"Unknown effect kind '{kind}'.")


def load_moves(path: str) -> Dict[str, Move]:
    """Load moves from disk."""
    with open(path, "r", encoding="utf-8") as file:
        raw_data = json.load(file)

    moves = {}
    for entry in raw_data["moves"]:
        move = Move(
            name=entry["name"],
            move_type=entry["move_type"],
            accuracy=entry["accuracy"],
            max_pp=entry["max_pp"],
            priority=entry.get("priority", 0),
            effects=[build_effect(effect) for effect in entry["effects"]],
        )
        moves[move.name] = move
        print(move)
    return moves
