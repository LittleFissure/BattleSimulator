from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional

from weather import WeatherState


@dataclass
class BattleAction:
    """One action chosen for the turn."""

    action_type: str
    move_name: Optional[str] = None
    switch_index: Optional[int] = None

    @classmethod
    def move(cls, move_name: str) -> "BattleAction":
        """Build a move action."""
        return cls(action_type="move", move_name=move_name)

    @classmethod
    def switch(cls, switch_index: int) -> "BattleAction":
        """Build a switch action."""
        return cls(action_type="switch", switch_index=switch_index)


@dataclass
class PendingAction:
    """An action tied to the exact Pokemon that selected it."""

    team: "Team"
    user: "PokemonInstance"
    action: BattleAction


class BattleManager:
    """Manage a standard 1v1 battle with teams of up to 6 Pokemon."""

    def __init__(self, player_team: "Team", enemy_team: "Team") -> None:
        """Initialize battlemanager state."""
        self.player_team = player_team
        self.enemy_team = enemy_team
        self.round_number = 1
        self.last_round_log: List[str] = []
        self.weather_cycle_length = 5
        self.weather = WeatherState.clear(turns_remaining=self.weather_cycle_length)

    @property
    def player(self) -> "PokemonInstance":
        """Return the current player."""
        return self.player_team.active

    @property
    def enemy(self) -> "PokemonInstance":
        """Return the current enemy."""
        return self.enemy_team.active

    def is_battle_over(self) -> bool:
        """Return whether battle over."""
        return (not self.player_team.has_usable_pokemon()) or (
            not self.enemy_team.has_usable_pokemon()
        )

    def get_winner(self) -> Optional["Team"]:
        """Return winner."""
        player_has_pokemon = self.player_team.has_usable_pokemon()
        enemy_has_pokemon = self.enemy_team.has_usable_pokemon()
        if player_has_pokemon and enemy_has_pokemon:
            return None
        if player_has_pokemon and not enemy_has_pokemon:
            return self.player_team
        if enemy_has_pokemon and not player_has_pokemon:
            return self.enemy_team
        return None

    def get_opposing_team(self, team: "Team") -> "Team":
        """Return opposing team."""
        return self.enemy_team if team is self.player_team else self.player_team

    def needs_player_replacement(self) -> bool:
        """Handle needs player replacement."""
        return self.player.is_fainted and self.player_team.has_usable_benched_pokemon()

    def needs_enemy_replacement(self) -> bool:
        """Handle needs enemy replacement."""
        return self.enemy.is_fainted and self.enemy_team.has_usable_benched_pokemon()

    def replace_fainted_player(self, index: int, log: List[str]) -> None:
        """Handle replace fainted player."""
        old_name = self.player.name
        self.player_team.force_replace(index)
        log.append(f"{old_name} fainted!")
        log.append(f"{self.player_team.name} sent out {self.player.name}!")

    def auto_replace_fainted_enemy(self, log: List[str]) -> None:
        """Handle auto replace fainted enemy."""
        old_name = self.enemy.name
        index = self.enemy_team.choose_first_benched_available()
        self.enemy_team.force_replace(index)
        log.append(f"{old_name} fainted!")
        log.append(f"{self.enemy_team.name} sent out {self.enemy.name}!")

    def set_weather(self, weather_kind: str, duration: int, log: List[str]) -> None:
        """Set weather."""
        turns = max(1, duration)
        previous_kind = self.weather.kind
        self.weather = WeatherState(kind=weather_kind, turns_remaining=turns)
        log.append(self.weather.change_message(previous_kind))

    def clear_weather(self, log: Optional[List[str]] = None, turns_remaining: Optional[int] = None) -> None:
        """Clear weather."""
        turns = self.weather_cycle_length if turns_remaining is None else max(1, turns_remaining)
        previous_kind = self.weather.kind
        self.weather = WeatherState.clear(turns_remaining=turns)
        if log is not None:
            log.append(self.weather.change_message(previous_kind))

    def apply_weather_end_of_round(self, log: List[str]) -> None:
        """Apply weather end of round."""
        if not self.weather.is_active:
            return
        battlers = []
        if not self.player.is_fainted:
            battlers.append(self.player)
        if not self.enemy.is_fainted:
            battlers.append(self.enemy)

        for battler in self.weather.weather_damage_targets(battlers):
            damage = max(1, battler.max_hp // 16)
            before_hp = battler.current_hp
            battler.take_damage(damage)
            actual_damage = before_hp - battler.current_hp
            if actual_damage <= 0:
                continue
            if self.weather.kind == "sandstorm":
                log.append(f"{battler.name} is buffeted by the sandstorm for {actual_damage} damage.")
            elif self.weather.kind == "hail":
                log.append(f"{battler.name} is pelted by hail for {actual_damage} damage.")
            if battler.is_fainted:
                log.append(f"{battler.name} fainted!")

    def tick_weather(self, log: List[str]) -> None:
        """Handle tick weather."""
        if self.weather.turns_remaining > 0:
            self.weather.turns_remaining -= 1

        if self.weather.turns_remaining > 0:
            return

        previous_kind = self.weather.kind
        next_kind = WeatherState.random_kind()
        self.weather = WeatherState(kind=next_kind, turns_remaining=self.weather_cycle_length)
        log.append(self.weather.change_message(previous_kind))

    def process_start_of_round(self, log: List[str]) -> None:
        """Process start of round."""
        if self.weather.is_active:
            upkeep = self.weather.upkeep_message()
            if upkeep:
                log.append(upkeep)

        if not self.player.is_fainted:
            if self.player.is_locked_into_move:
                log.append(f"{self.player.name} is locked into {self.player.locked_move_name}!")
            if self.player.is_charging_move:
                log.append(f"{self.player.name} is preparing {self.player.charging_move_name}!")
            self.player.process_turn_start_statuses(log)

        if not self.enemy.is_fainted:
            if self.enemy.is_locked_into_move:
                log.append(f"{self.enemy.name} is locked into {self.enemy.locked_move_name}!")
            if self.enemy.is_charging_move:
                log.append(f"{self.enemy.name} is preparing {self.enemy.charging_move_name}!")
            self.enemy.process_turn_start_statuses(log)

    def process_end_of_round(self, log: List[str]) -> None:
        """Process end of round."""
        if not self.player.is_fainted:
            self.player.process_turn_end_statuses(log)
        if not self.enemy.is_fainted:
            self.enemy.process_turn_end_statuses(log)

    def process_benched_round_end_statuses(self, log: List[str]) -> None:
        """Process benched round end statuses."""
        self.player_team.process_benched_round_end_statuses(log)
        self.enemy_team.process_benched_round_end_statuses(log)

    def build_pending_actions(self, player_action: BattleAction, enemy_action: BattleAction) -> List[PendingAction]:
        """Build pending actions."""
        return [
            PendingAction(team=self.player_team, user=self.player_team.active, action=player_action),
            PendingAction(team=self.enemy_team, user=self.enemy_team.active, action=enemy_action),
        ]

    def get_effective_action(self, pending: PendingAction) -> BattleAction:
        """Return effective action."""
        if pending.user.is_charging_move and pending.user.charging_move_name is not None:
            return BattleAction.move(pending.user.charging_move_name)
        if pending.user.is_locked_into_move and pending.user.locked_move_name is not None:
            return BattleAction.move(pending.user.locked_move_name)
        return pending.action

    def get_action_priority(self, pending: PendingAction) -> int:
        """Return action priority."""
        action = self.get_effective_action(pending)
        if action.action_type == "switch":
            return 10_000
        if action.action_type == "move":
            if action.move_name is None:
                return -10_000
            known_move = pending.user.get_known_move(action.move_name)
            return known_move.move.priority
        return -10_000

    def sort_actions(self, actions: List[PendingAction]) -> List[PendingAction]:
        """Handle sort actions."""
        decorated: List[tuple[int, int, float, PendingAction]] = []
        for pending in actions:
            priority = self.get_action_priority(pending)
            speed = pending.user.get_effective_stat("speed")
            tie_breaker = random.random()
            decorated.append((priority, speed, tie_breaker, pending))
        decorated.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        return [item[3] for item in decorated]

    def process_switch_action(self, acting_team: "Team", switch_index: int, log: List[str]) -> bool:
        """Process switch action."""
        if not acting_team.can_switch_to(switch_index):
            log.append(f"{acting_team.active.name} could not switch.")
            return False
        old_name = acting_team.active.name
        acting_team.switch_to(switch_index)
        new_name = acting_team.active.name
        log.append(f"{acting_team.name} withdrew {old_name}!")
        log.append(f"{acting_team.name} sent out {new_name}!")
        return True

    def finalize_locked_move_after_resolution(
        self,
        user: "PokemonInstance",
        was_locked_turn: bool,
        was_final_locked_turn: bool,
        context: Dict[str, object],
        log: List[str],
    ) -> None:
        """Finalize locked move after resolution."""
        if not was_locked_turn:
            return
        if context.get("move_disrupted", False):
            user.finish_move_lock(log, apply_confusion=was_final_locked_turn)
            return
        if user.locked_turns_remaining > 0:
            user.locked_turns_remaining -= 1
        if user.locked_turns_remaining <= 0:
            user.finish_move_lock(log, apply_confusion=True)

    def finalize_charge_after_resolution(self, user: "PokemonInstance", was_release_turn: bool) -> None:
        """Finalize charge after resolution."""
        if was_release_turn and user.is_charging_move:
            user.clear_charge()

    def handle_semi_invulnerable_interruption(
        self,
        target: "PokemonInstance",
        move_name: str,
        context: Dict[str, object],
        log: List[str],
    ) -> None:
        """Handle semi invulnerable interruption."""
        if not context.get("hit_semi_invulnerable_target", False):
            return
        if int(context.get("damage_dealt", 0)) <= 0:
            return
        if not target.is_charging_move:
            return
        if target.is_fainted:
            return
        target.cancel_charge(log, reason=f"{move_name}!")

    def process_move_action(
        self,
        acting_team: "Team",
        pending_user: "PokemonInstance",
        move_name: str,
        log: List[str],
        target_already_acted: bool,
    ) -> bool:
        """Process move action."""
        opposing_team = self.get_opposing_team(acting_team)

        if self.is_battle_over() or pending_user.is_fainted:
            return False
        if acting_team.active is not pending_user:
            return False
        if opposing_team.active.is_fainted:
            return False

        was_locked_turn = pending_user.is_locked_into_move
        was_final_locked_turn = was_locked_turn and pending_user.locked_turns_remaining == 1

        actual_move_name = move_name
        if pending_user.is_charging_move and pending_user.charging_move_name is not None:
            actual_move_name = pending_user.charging_move_name
        elif was_locked_turn and pending_user.locked_move_name is not None:
            actual_move_name = pending_user.locked_move_name
            log.append(f"{pending_user.name} is locked into {actual_move_name}!")

        if pending_user.charge_interrupted_this_round:
            pending_user.charge_interrupted_this_round = False
            return False

        if not pending_user.can_act(log):
            log.append(f"{pending_user.name} could not act.")
            return False

        known_move = pending_user.get_known_move(actual_move_name)
        target = opposing_team.active
        context: Dict[str, object] = {
            "target_already_acted": target_already_acted,
            "move_disrupted": False,
            "move_disruption_reason": None,
            "damage_dealt": 0,
            "is_charge_release_turn": False,
            "charge_started": False,
            "skip_remaining_effects": False,
            "hit_semi_invulnerable_target": False,
            "weather": self.weather,
            "battle_manager": self,
        }

        is_charge_release_turn = False
        if pending_user.is_charging_move and pending_user.charging_move_name == actual_move_name:
            is_charge_release_turn = pending_user.advance_charge_turn()
            context["is_charge_release_turn"] = is_charge_release_turn
            if not is_charge_release_turn:
                log.append(f"{pending_user.name} is still charging {actual_move_name}.")
                return False

        has_charge_effect = any(effect.__class__.__name__ == "ChargeMoveEffect" for effect in known_move.move.effects)

        if not known_move.is_usable:
            log.append(f"{pending_user.name} tried to use {actual_move_name}, but it has no PP left!")
            context["move_disrupted"] = True
            context["move_disruption_reason"] = "no_pp"
            self.finalize_locked_move_after_resolution(pending_user, was_locked_turn, was_final_locked_turn, context, log)
            if is_charge_release_turn:
                pending_user.clear_charge()
            return False

        should_spend_pp = is_charge_release_turn or not has_charge_effect
        if should_spend_pp:
            known_move.spend_pp()
            log.append(f"{pending_user.name} used {actual_move_name}! (PP {known_move.current_pp}/{known_move.move.max_pp})")
        else:
            log.append(f"{pending_user.name} used {actual_move_name}!")

        if target.is_semi_invulnerable and not target.can_be_hit_while_semi_invulnerable(actual_move_name):
            state_label = target.semi_invulnerable_state or "out of reach"
            log.append(f"{target.name} avoided the attack while {state_label}!")
            context["move_disrupted"] = True
            context["move_disruption_reason"] = "semi_invulnerable"
            self.finalize_locked_move_after_resolution(pending_user, was_locked_turn, was_final_locked_turn, context, log)
            self.finalize_charge_after_resolution(pending_user, is_charge_release_turn)
            return False

        if target.is_semi_invulnerable and target.can_be_hit_while_semi_invulnerable(actual_move_name):
            context["hit_semi_invulnerable_target"] = True

        should_roll_accuracy = is_charge_release_turn or not has_charge_effect
        if should_roll_accuracy and not known_move.move.check_hit(pending_user, target):
            log.append(f"{pending_user.name}'s attack missed!")
            context["move_disrupted"] = True
            context["move_disruption_reason"] = "miss"
            self.finalize_locked_move_after_resolution(pending_user, was_locked_turn, was_final_locked_turn, context, log)
            self.finalize_charge_after_resolution(pending_user, is_charge_release_turn)
            return False

        for effect in known_move.move.effects:
            effect.apply(
                pending_user,
                opposing_team.active,
                known_move.move.move_type,
                known_move.move.name,
                log,
                context,
            )
            if context.get("skip_remaining_effects", False):
                break
            if self.is_battle_over() or pending_user.is_fainted or opposing_team.active.is_fainted:
                break

        self.handle_semi_invulnerable_interruption(target, actual_move_name, context, log)
        self.finalize_locked_move_after_resolution(pending_user, was_locked_turn, was_final_locked_turn, context, log)
        self.finalize_charge_after_resolution(pending_user, is_charge_release_turn)
        return True

    def play_round(self, player_action: BattleAction, enemy_action: BattleAction) -> List[str]:
        """Handle play round."""
        log: List[str] = [f"=== Round {self.round_number} ==="]

        if self.is_battle_over():
            log.append("The battle is already over.")
            self.last_round_log = log
            return log

        self.process_start_of_round(log)

        if not self.is_battle_over():
            pending_actions = self.build_pending_actions(player_action, enemy_action)
            ordered_actions = self.sort_actions(pending_actions)
            acted_this_round: Dict[int, bool] = {id(pending.user): False for pending in ordered_actions}

            for pending in ordered_actions:
                if self.is_battle_over():
                    break
                if pending.user.is_fainted:
                    continue

                effective_action = self.get_effective_action(pending)
                if effective_action.action_type == "switch":
                    if effective_action.switch_index is not None:
                        self.process_switch_action(pending.team, effective_action.switch_index, log)
                    acted_this_round[id(pending.user)] = True
                    continue

                if effective_action.action_type == "move" and effective_action.move_name is not None:
                    opposing_team = self.get_opposing_team(pending.team)
                    target_already_acted = acted_this_round.get(id(opposing_team.active), False)
                    self.process_move_action(
                        pending.team,
                        pending.user,
                        effective_action.move_name,
                        log,
                        target_already_acted=target_already_acted,
                    )
                    acted_this_round[id(pending.user)] = True

        if not self.is_battle_over():
            self.process_end_of_round(log)
        if not self.is_battle_over():
            self.apply_weather_end_of_round(log)
        if not self.is_battle_over():
            self.process_benched_round_end_statuses(log)
        self.tick_weather(log)
        self.player.charge_interrupted_this_round = False
        self.enemy.charge_interrupted_this_round = False

        if self.is_battle_over():
            winner = self.get_winner()
            if winner is None:
                log.append("The battle ended in a draw!")
            else:
                log.append(f"{winner.name} wins the battle!")

        self.round_number += 1
        self.last_round_log = log
        return log
