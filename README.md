# Pokémon Battle Engine -- Comprehensive Technical Guide

## Overview

This system implements a modular, data-driven Pokémon-style battle
engine.

All gameplay content (Pokémon, moves, effects) is defined through JSON
and interpreted by the engine.

The design emphasizes: - composability (effects stack cleanly) - clarity
(each mechanic is explicit) - extensibility (new mechanics require
minimal engine changes)

------------------------------------------------------------------------

# Pokémon Definitions

## Structure

Pokémon are defined in `pokemon.json`.

### Example

``` json
{
  "name": "Blazion",
  "types": ["Fire"],
  "base_stats": {
    "hp": 70,
    "attack": 90,
    "defense": 60,
    "special_attack": 95,
    "special_defense": 60,
    "speed": 100
  },
  "evolutions": []
}
```

## Notes

-   Types must be valid Pokémon types
-   Stats must be non-negative
-   Evolution is optional

------------------------------------------------------------------------

# Move System

Each move is defined as a list of **effects** executed in order.

## Example

``` json
{
  "name": "Rage Burst",
  "move_type": "Normal",
  "accuracy": 100,
  "max_pp": 10,
  "priority": 0,
  "effects": [
    {
      "kind": "damage",
      "power": 10,
      "category": "physical",
      "crit_stage": 0
    },
    {
      "kind": "lock_move",
      "min_turns": 2,
      "max_turns": 3
    }
  ]
}
```

------------------------------------------------------------------------

# Effect Types 

## 1. Damage


``` json
{
  "kind": "damage",
  "power": 12,
  "category": "physical",
  "crit_stage": 0
}
```


------------------------------------------------------------------------

## 2. Multi Hit

``` json
{
  "kind": "multi_hit",
  "power": 5,
  "category": "physical",
  "min_hits": 2,
  "max_hits": 5
}
```

------------------------------------------------------------------------

## 3. Fixed Damage

``` json
{
  "kind": "fixed_damage",
  "damage": 40
}
```

Behavior: - ignores stats - ignores type effectiveness

------------------------------------------------------------------------

## 4. HP Fraction Damage

``` json
{
  "kind": "current_hp_fraction_damage",
  "ratio": 0.5
}
```

Example: - Super Fang → halves HP

------------------------------------------------------------------------

## 5. Level Damage

``` json
{
  "kind": "user_level_damage"
}
```

Damage = user level

------------------------------------------------------------------------

## 6. Healing

``` json
{
  "kind": "heal_percent",
  "ratio": 0.5
}
```

------------------------------------------------------------------------

## 7. Drain

``` json
{
  "kind": "drain",
  "ratio": 0.5
}
```

------------------------------------------------------------------------

## 8. Recoil

``` json
{
  "kind": "recoil",
  "ratio": 0.25
}
```

------------------------------------------------------------------------

## 9. Stat Changes

``` json
{
  "kind": "modify_stat_stage",
  "stat_name": "attack",
  "amount": 2,
  "target_side": "user"
}
```

------------------------------------------------------------------------

## 10. Status Effects

``` json
{
  "kind": "apply_status",
  "status_name": "Burn",
  "target_side": "target",
  "chance": 0.2
}
```

------------------------------------------------------------------------

## 11. Lock Moves

``` json
{
  "kind": "lock_move",
  "min_turns": 2,
  "max_turns": 3
}
```

Behavior: - repeats move automatically - ends early on miss/block -
confusion applied at end

------------------------------------------------------------------------

# Status Effects Explained

## Burn

-   damages each turn
-   reduces attack

## Poison

-   damages each turn

## Paralysis

-   chance to skip turn
-   reduces speed

## Sleep

-   cannot act for several turns

## Freeze

-   cannot act until thawed

## Confusion

-   chance to self-damage

## Flinch

-   skips current turn if applied before acting

## Protect

-   blocks incoming effects for one turn

------------------------------------------------------------------------

# Battle Flow

1.  Start-of-turn status processing
2.  Determine order (priority → speed)
3.  Execute actions
4.  Apply move effects
5.  End-of-turn status resolution

------------------------------------------------------------------------

# Creating Custom Moves

## Example: Hybrid Move

``` json
{
  "name": "Leech Strike",
  "move_type": "Grass",
  "accuracy": 100,
  "max_pp": 10,
  "priority": 0,
  "effects": [
    {
      "kind": "damage",
      "power": 8,
      "category": "physical",
      "crit_stage": 0
    },
    {
      "kind": "drain",
      "ratio": 0.5
    }
  ]
}
```

------------------------------------------------------------------------

## Example: Control Move

``` json
{
  "name": "Stunning Blow",
  "move_type": "Electric",
  "accuracy": 90,
  "max_pp": 15,
  "priority": 0,
  "effects": [
    {
      "kind": "damage",
      "power": 6,
      "category": "physical",
      "crit_stage": 0
    },
    {
      "kind": "apply_status",
      "status_name": "Flinch",
      "target_side": "target",
      "chance": 0.3
    }
  ]
}
```

------------------------------------------------------------------------

# Design Principles

-   Effects are independent and reusable
-   Order of effects matters 
-   Statuses handle long-term behavior
-   Battle manager handles turn logic

------------------------------------------------------------------------

# Summary

This engine supports: - complex move composition - accurate battle
sequencing - extensible mechanics - advanced interactions (lock moves,
flinch, protect)

New features can be added by introducing new effect types or statuses
without modifying existing systems.
