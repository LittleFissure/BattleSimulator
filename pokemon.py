from __future__ import annotations

import json
from dataclasses import dataclass, field
from pyexpat import native_encoding
import re
import stat
from typing import Dict, List, Literal, Optional
import math

from moves import Move
from statuses import StatusEffect, get_status_factory


StageRule = Literal["normal", "ignore_negative", "ignore_positive", "ignore_all"]
MAJOR_STATUS_NAMES = {"Burn", "Poison", "Paralysis", "Sleep", "Freeze"}



@dataclass(frozen=True)
class Nature:
    '''Defines natures along with the stat they increase/decrease'''
    
    name: str
    boostedStat: str
    nerfedStat: str
    
    def __post_init(self) -> None:
        """Validate and normalize fields after initialization."""
        pass
        
    def getMulti(self, stat: str) -> int:
        '''Returns the multplier for the sclaed stat'''
        
        if self.boostedStat == self.nerfedStat:
            return 1
        if self.boostedStat == stat:
            return 1.1
        if self.nerfedStat == stat:
            return 0.9
        return 1
            
NatureList = {
    "Adamant" : Nature("Adamant","attack","special_attack"),
    "Bashful" : Nature("Bashful","special_attack","special_attack"),
    "Bold" : Nature("Bold","defense","attack"),
    "Brave" : Nature("Brave","attack","speed"),
    "Calm" : Nature("Calm","special_defense","attack"),
    "Careful" : Nature("Careful","special_defense","special_defense"),
    "Docile" : Nature("Docile","defense","defence"),
    "Gentle" : Nature("Gentle","special_defence","defence"),
    "Hardy" : Nature("Hardy","attack","attack"),
    "Hasty" : Nature("Hasty","speed","defence"),
    "Impish" : Nature("Impish","defence","special_attack"),
    "Jolly" : Nature("Jolly","speed","special_attack"),
    "Lax" : Nature("Lax","defence","special_defense"),
    "Lonely" : Nature("Lonely","attack ","defense"),
    "Mild" : Nature("Mild","special_attack ","defense"),
    "Modest" : Nature("Modest","special_attack ","attack"),
    "Naive" : Nature("Naive","speed ","special_defense"),
    "Naughty" : Nature("Naughty","attack ","special_defense"),
    "Quiet" : Nature("Quiet","special_defense ","speed"),
    "Quirky" : Nature("Quirky","special_defense ","special_defense"),
    "Rash" : Nature("Rash","special_attack ","special_defense"),
    "Relaxed" : Nature("Relaxed","defense ","speed"),
    "Sassy" : Nature("Relaxed","special_defense ","speed"),
    "Serious" : Nature("Serious","speed ","speed"),
    "Timid" : Nature("Timid","speed ","attack")
}


@dataclass(frozen=True)
class Stats:
    """Base or scaled stats for a Pokemon."""

    hp: int
    attack: int
    defense: int
    special_attack: int
    special_defense: int
    speed: int
    accuracy: int = 100
    evasion: int = 100
    

    def __post_init__(self) -> None:
        """Reject bad stat data as soon as it is loaded."""
        for stat_name, value in self.__dict__.items():
            if value < 0:
                raise ValueError(f"{stat_name} cannot be negative.")


@dataclass(frozen=True)
class Evolution:
    """A simple level-up evolution rule."""

    target_name: str
    level_requirement: int

    def __post_init__(self) -> None:
        """Validate evolution data."""
        if not self.target_name.strip():
            raise ValueError("target_name cannot be empty.")
        if self.level_requirement < 1:
            raise ValueError("level_requirement must be at least 1.")


@dataclass
class PokemonTemplate:
    """A species definition loaded from the Pokemon data file."""

    name: str
    types: List[str]
    base_stats: Stats
    evolutions: List[Evolution] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Clean and validate species data."""
        if not self.name.strip():
            raise ValueError("Pokemon name cannot be empty.")

        cleaned_types = [pokemon_type.strip() for pokemon_type in self.types if pokemon_type.strip()]
        if not cleaned_types:
            raise ValueError("Pokemon must have at least one type.")

        self.types = cleaned_types


@dataclass
class StatStages:
    """Temporary stage modifiers used during battle."""

    attack: int = 0
    defense: int = 0
    special_attack: int = 0
    special_defense: int = 0
    speed: int = 0
    accuracy: int = 0
    evasion: int = 0

    MIN_STAGE: int = -6
    MAX_STAGE: int = 6

    def _clamp(self, value: int) -> int:
        """Keep a stage inside the normal Pokemon range."""
        return max(self.MIN_STAGE, min(self.MAX_STAGE, value))

    def change_stage(self, stat_name: str, amount: int) -> int:
        """Apply a stage change and return the new value."""
        current = getattr(self, stat_name)
        new = self._clamp(current + amount)
        setattr(self, stat_name, new)
        return new

    def get_stage(self, stat_name: str) -> int:
        """Return the current stage for a stat."""
        return getattr(self, stat_name)


@dataclass
class KnownMove:
    """A move plus its remaining PP for one Pokemon."""

    move: Move
    current_pp: int = field(init=False)

    def __post_init__(self) -> None:
        """Start at full PP."""
        self.current_pp = self.move.max_pp

    @property
    def is_usable(self) -> bool:
        """Return True when this move still has PP left."""
        return self.current_pp > 0

    def spend_pp(self) -> None:
        """Spend one PP or fail if the move is empty."""
        if self.current_pp <= 0:
            raise ValueError("No PP left.")
        self.current_pp -= 1


@dataclass
class PokemonInstance:
    """A battle-ready Pokemon with its own HP, PP, and statuses."""

    template: PokemonTemplate
    level: int
    known_moves: List[KnownMove] = field(default_factory=list)
    current_hp: int = field(init=False)
    stats: Stats = field(init=False)
    stat_stages: StatStages = field(default_factory=StatStages)
    status_effects: List[StatusEffect] = field(default_factory=list)
    nature: Nature = NatureList["Docile"]

    locked_move_name: Optional[str] = None
    locked_turns_remaining: int = 0
    locked_move_pending_confusion: bool = False

    charging_move_name: Optional[str] = None
    charging_turns_remaining: int = 0
    semi_invulnerable_state: Optional[str] = None
    semi_invulnerable_exceptions: List[str] = field(default_factory=list)
    charge_interrupted_this_round: bool = False

    def __post_init__(self) -> None:
        """Scale stats and start at full HP."""
        if self.level < 1:
            raise ValueError("Level must be at least 1.")

        self.stats = self.calculate_scaled_stats()
        self.current_hp = self.stats.hp

    def calculate_scaled_stats(self) -> Stats:
        """Scale the species stats using the project's simple level formula."""
        base = self.template.base_stats
        level_offset = self.level - 1

        return  Stats(
            hp = math.floor(base.hp/50 * self.level )+ self.level + 10,
            
            attack = math.floor((math.floor(base.attack/50 * self.level ) + 5 ) * self.nature.getMulti("attack")),
            defense = math.floor((math.floor(base.defense/50 * self.level ) + 5) * self.nature.getMulti("defense")),
            special_attack = math.floor((math.floor(base.special_attack/50 * self.level ) + 5) * self.nature.getMulti("special_attack")),
            special_defense = math.floor((math.floor(base.special_defense/50 * self.level ) + 5) * self.nature.getMulti("special_defense")),
            speed = math.floor((math.floor(base.speed/50 * self.level ) + 5) * self.nature.getMulti("speed")),
            
            accuracy= base.accuracy,
            evasion=base.evasion,
        )


    def get_stage_multiplier(self, stage: int) -> float:
        """Convert a stat stage into its battle multiplier."""
        return (2 + stage) / 2 if stage >= 0 else 2 / (2 - stage)

    def _resolve_stage(self, stage: int, stage_rule: StageRule) -> int:
        """Apply special stage rules, such as critical-hit handling."""
        if stage_rule == "ignore_negative" and stage < 0:
            return 0
        if stage_rule == "ignore_positive" and stage > 0:
            return 0
        if stage_rule == "ignore_all":
            return 0
        return stage

    def _apply_status_modifiers(self, stat_name: str, value: int, defensive: bool) -> int:
        """Apply outgoing or incoming status hooks to a stat value."""
        for status in self.status_effects:
            if defensive:
                value = status.modify_incoming_stat(self, stat_name, value)
            else:
                value = status.modify_outgoing_stat(self, stat_name, value)
        return max(1, value)

    def get_effective_stat(self, stat_name: str, stage_rule: StageRule = "normal") -> int:
        """Return the current effective value for an attacking-side stat."""
        base = getattr(self.stats, stat_name)
        stage = self._resolve_stage(self.stat_stages.get_stage(stat_name), stage_rule)
        staged_value = int(base * self.get_stage_multiplier(stage))
        return self._apply_status_modifiers(stat_name, staged_value, defensive=False)

    def get_effective_defensive_stat(
        self,
        stat_name: str,
        stage_rule: StageRule = "normal",
    ) -> int:
        """Return the current effective value for a defending-side stat."""
        base = getattr(self.stats, stat_name)
        stage = self._resolve_stage(self.stat_stages.get_stage(stat_name), stage_rule)
        staged_value = int(base * self.get_stage_multiplier(stage))
        return self._apply_status_modifiers(stat_name, staged_value, defensive=True)

    @property
    def name(self) -> str:
        """Return the species name."""
        return self.template.name

    @property
    def types(self) -> List[str]:
        """Return the species typing."""
        return self.template.types

    @property
    def max_hp(self) -> int:
        """Return this Pokemon's maximum HP."""
        return self.stats.hp

    @property
    def is_fainted(self) -> bool:
        """Return True when HP has reached zero."""
        return self.current_hp <= 0

    @property
    def has_major_status(self) -> bool:
        """Return True when a major non-volatile status is already present."""
        return any(status.name in MAJOR_STATUS_NAMES for status in self.status_effects)

    @property
    def is_locked_into_move(self) -> bool:
        """Return True when this Pokemon is forced to keep using one move."""
        return self.locked_move_name is not None and self.locked_turns_remaining > 0

    @property
    def is_charging_move(self) -> bool:
        """Return True when this Pokemon is preparing a delayed move."""
        return self.charging_move_name is not None

    @property
    def is_semi_invulnerable(self) -> bool:
        """Return True when this Pokemon is in a protected charge state."""
        return self.semi_invulnerable_state is not None

    def add_known_move(self, move: Move) -> None:
        """Teach this Pokemon a move."""
        self.known_moves.append(KnownMove(move))

    def get_known_move(self, name: str) -> KnownMove:
        """Return a known move by name."""
        for known_move in self.known_moves:
            if known_move.move.name == name:
                return known_move
        raise ValueError(f"Unknown move {name}")

    def has_status(self, status_name: str) -> bool:
        """Return True when the named status is active."""
        return any(status.name == status_name for status in self.status_effects)

    def can_receive_status(self, status: StatusEffect) -> bool:
        """Apply simple Pokemon-style status slot rules."""
        if self.has_status(status.name):
            return False
        if not status.is_volatile and self.has_major_status:
            return False
        return True

    def add_status_effect(self, status: StatusEffect, log: List[str]) -> bool:
        """Add a status when it is allowed and report whether it stuck."""
        if not self.can_receive_status(status):
            log.append(f"{self.name} was unaffected.")
            return False

        self.status_effects.append(status)
        status.on_apply(self, log)
        return True

    def remove_status_effect(self, status_name: str) -> bool:
        """Remove the first matching status by name."""
        for index, status in enumerate(self.status_effects):
            if status.name == status_name:
                del self.status_effects[index]
                return True
        return False

    def process_turn_start_statuses(self, log: List[str]) -> None:
        """Run start-of-turn hooks for active statuses."""
        for status in list(self.status_effects):
            status.on_turn_start(self, log)

    def process_turn_end_statuses(self, log: List[str]) -> None:
        """Run end-of-turn hooks for the active Pokemon and clean up expired effects."""
        expired_statuses: List[StatusEffect] = []

        for status in list(self.status_effects):
            if self.is_fainted:
                break

            status.on_turn_end(self, log)
            if status.tick_duration():
                expired_statuses.append(status)

        for status in expired_statuses:
            if self.remove_status_effect(status.name):
                log.append(f"{self.name}'s {status.name} wore off.")

    def process_benched_round_end_statuses(self, log: List[str]) -> None:
        """Advance timers for statuses that keep ticking while benched."""
        expired_statuses: List[StatusEffect] = []

        for status in list(self.status_effects):
            if not status.ticks_while_benched:
                continue

            if status.on_benched_round_end(self, log):
                expired_statuses.append(status)
                continue

            if status.tick_duration():
                expired_statuses.append(status)

        for status in expired_statuses:
            if self.remove_status_effect(status.name):
                log.append(f"{self.name}'s {status.name} wore off.")

    def can_act(self, log: List[str]) -> bool:
        """Return False when a current status blocks this Pokemon's action."""
        for status in list(self.status_effects):
            if status.prevents_action(self, log):
                return False
        return True

    def start_move_lock(self, move_name: str, total_turns: int) -> None:
        """Begin a forced-move lock that lasts a fixed total number of uses."""
        if total_turns < 2:
            raise ValueError("Locked moves must last at least 2 turns.")
        self.locked_move_name = move_name
        self.locked_turns_remaining = total_turns - 1
        self.locked_move_pending_confusion = True

    def clear_move_lock(self) -> None:
        """Clear any active forced-move lock without side effects."""
        self.locked_move_name = None
        self.locked_turns_remaining = 0
        self.locked_move_pending_confusion = False

    def finish_move_lock(self, log: List[str], apply_confusion: bool) -> None:
        """End the lock and optionally apply confusion."""
        should_confuse = self.locked_move_pending_confusion and apply_confusion
        self.locked_move_name = None
        self.locked_turns_remaining = 0
        self.locked_move_pending_confusion = False

        if should_confuse:
            confusion_factory = get_status_factory("Confusion")
            self.add_status_effect(confusion_factory(), log)

    def start_charge(
        self,
        move_name: str,
        charge_turns: int,
        semi_invulnerable_state: Optional[str] = None,
        exceptions: Optional[List[str]] = None,
    ) -> None:
        """Begin charging a delayed move."""
        if charge_turns < 1:
            raise ValueError("charge_turns must be at least 1.")

        self.charging_move_name = move_name
        self.charging_turns_remaining = charge_turns
        self.semi_invulnerable_state = semi_invulnerable_state
        self.semi_invulnerable_exceptions = list(exceptions or [])
        self.charge_interrupted_this_round = False

    def clear_charge(self) -> None:
        """Clear any active charge state without side effects."""
        self.charging_move_name = None
        self.charging_turns_remaining = 0
        self.semi_invulnerable_state = None
        self.semi_invulnerable_exceptions = []

    def advance_charge_turn(self) -> bool:
        """Advance a charge turn and return True when the move should be released now."""
        if not self.is_charging_move:
            return False

        if self.charging_turns_remaining > 0:
            self.charging_turns_remaining -= 1

        return self.charging_turns_remaining <= 0

    def can_be_hit_while_semi_invulnerable(self, move_name: str) -> bool:
        """Return True when the given move can hit through the active charge state."""
        if not self.is_semi_invulnerable:
            return True
        return move_name in self.semi_invulnerable_exceptions

    def cancel_charge(self, log: List[str], reason: Optional[str] = None) -> None:
        """End a charge state and optionally explain why."""
        move_name = self.charging_move_name
        self.clear_charge()
        self.charge_interrupted_this_round = True

        if reason and move_name is not None:
            log.append(f"{self.name}'s {move_name} was interrupted by {reason}")
        elif move_name is not None:
            log.append(f"{self.name}'s {move_name} was interrupted!")

    def take_damage(self, amount: int) -> None:
        """Deal damage without dropping below zero HP."""
        self.current_hp = max(0, self.current_hp - max(0, amount))
        if self.current_hp <= 0:
            self.clear_move_lock()
            self.clear_charge()
            self.charge_interrupted_this_round = False

    def heal(self, amount: int) -> None:
        """Restore HP without going above max HP."""
        self.current_hp = min(self.max_hp, self.current_hp + max(0, amount))

    def on_switch_out(self) -> None:
        """Clear battle-only state when this Pokemon leaves the field."""
        self.stat_stages = StatStages()
        self.status_effects = [status for status in self.status_effects if not status.is_volatile]
        self.clear_move_lock()
        self.clear_charge()
        self.charge_interrupted_this_round = False

    def on_switch_in(self) -> None:
        """Hook for future switch-in behavior."""
        return None


def load_pokemon_templates(path: str) -> Dict[str, PokemonTemplate]:
    """Load Pokemon species templates from a JSON file."""
    with open(path, "r", encoding="utf-8") as file:
        raw_data = json.load(file)

    templates: Dict[str, PokemonTemplate] = {}

    for entry in raw_data["pokemon"]:
        template = PokemonTemplate(
            name=entry["name"],
            types=entry["types"],
            base_stats=Stats(**entry["base_stats"]),
            evolutions=[Evolution(**evolution) for evolution in entry["evolutions"]],
        )
        templates[template.name] = template

    return templates
