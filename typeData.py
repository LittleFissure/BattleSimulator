from typing import Iterable, List


ALL_TYPES = {
    "Normal",
    "Fire",
    "Water",
    "Electric",
    "Grass",
    "Ice",
    "Fighting",
    "Poison",
    "Ground",
    "Flying",
    "Psychic",
    "Bug",
    "Rock",
    "Ghost",
    "Dragon",
    "Dark",
    "Steel",
    "Fairy",
}

STAB_MULTIPLIER = 1.5

TYPE_ALIASES = {
    "Basic": "Normal",
}


TYPE_CHART = {
    "Normal": {
        "Rock": 0.5,
        "Ghost": 0.0,
        "Steel": 0.5,
    },
    "Fire": {
        "Fire": 0.5,
        "Water": 0.5,
        "Grass": 2.0,
        "Ice": 2.0,
        "Bug": 2.0,
        "Rock": 0.5,
        "Dragon": 0.5,
        "Steel": 2.0,
    },
    "Water": {
        "Fire": 2.0,
        "Water": 0.5,
        "Grass": 0.5,
        "Ground": 2.0,
        "Rock": 2.0,
        "Dragon": 0.5,
    },
    "Electric": {
        "Water": 2.0,
        "Electric": 0.5,
        "Grass": 0.5,
        "Ground": 0.0,
        "Flying": 2.0,
        "Dragon": 0.5,
    },
    "Grass": {
        "Fire": 0.5,
        "Water": 2.0,
        "Grass": 0.5,
        "Poison": 0.5,
        "Ground": 2.0,
        "Flying": 0.5,
        "Bug": 0.5,
        "Rock": 2.0,
        "Dragon": 0.5,
        "Steel": 0.5,
    },
    "Ice": {
        "Fire": 0.5,
        "Water": 0.5,
        "Grass": 2.0,
        "Ice": 0.5,
        "Ground": 2.0,
        "Flying": 2.0,
        "Dragon": 2.0,
        "Steel": 0.5,
    },
    "Fighting": {
        "Normal": 2.0,
        "Ice": 2.0,
        "Poison": 0.5,
        "Flying": 0.5,
        "Psychic": 0.5,
        "Bug": 0.5,
        "Rock": 2.0,
        "Ghost": 0.0,
        "Dark": 2.0,
        "Steel": 2.0,
        "Fairy": 0.5,
    },
    "Poison": {
        "Grass": 2.0,
        "Poison": 0.5,
        "Ground": 0.5,
        "Rock": 0.5,
        "Ghost": 0.5,
        "Steel": 0.0,
        "Fairy": 2.0,
    },
    "Ground": {
        "Fire": 2.0,
        "Electric": 2.0,
        "Grass": 0.5,
        "Poison": 2.0,
        "Flying": 0.0,
        "Bug": 0.5,
        "Rock": 2.0,
        "Steel": 2.0,
    },
    "Flying": {
        "Electric": 0.5,
        "Grass": 2.0,
        "Fighting": 2.0,
        "Bug": 2.0,
        "Rock": 0.5,
        "Steel": 0.5,
    },
    "Psychic": {
        "Fighting": 2.0,
        "Poison": 2.0,
        "Psychic": 0.5,
        "Dark": 0.0,
        "Steel": 0.5,
    },
    "Bug": {
        "Fire": 0.5,
        "Grass": 2.0,
        "Fighting": 0.5,
        "Poison": 0.5,
        "Flying": 0.5,
        "Psychic": 2.0,
        "Ghost": 0.5,
        "Dark": 2.0,
        "Steel": 0.5,
        "Fairy": 0.5,
    },
    "Rock": {
        "Fire": 2.0,
        "Ice": 2.0,
        "Fighting": 0.5,
        "Ground": 0.5,
        "Flying": 2.0,
        "Bug": 2.0,
        "Steel": 0.5,
    },
    "Ghost": {
        "Normal": 0.0,
        "Psychic": 2.0,
        "Ghost": 2.0,
        "Dark": 0.5,
    },
    "Dragon": {
        "Dragon": 2.0,
        "Steel": 0.5,
        "Fairy": 0.0,
    },
    "Dark": {
        "Fighting": 0.5,
        "Psychic": 2.0,
        "Ghost": 2.0,
        "Dark": 0.5,
        "Fairy": 0.5,
    },
    "Steel": {
        "Fire": 0.5,
        "Water": 0.5,
        "Electric": 0.5,
        "Ice": 2.0,
        "Rock": 2.0,
        "Steel": 0.5,
        "Fairy": 2.0,
    },
    "Fairy": {
        "Fire": 0.5,
        "Fighting": 2.0,
        "Poison": 0.5,
        "Dragon": 2.0,
        "Dark": 2.0,
        "Steel": 0.5,
    },
}


def normalize_type_name(type_name: str) -> str:
    """
    Normalizes a type name.

    This allows legacy/custom names like "Basic" to be treated as
    standard Gen 6 types such as "Normal".

    Args:
        type_name: Raw type name.

    Returns:
        Normalized type name.
    """
    return TYPE_ALIASES.get(type_name, type_name)


def normalize_type_list(type_names: Iterable[str]) -> List[str]:
    """
    Normalizes a sequence of type names.

    Args:
        type_names: Iterable of raw type names.

    Returns:
        List of normalized type names.
    """
    return [normalize_type_name(type_name) for type_name in type_names]


def get_type_multiplier(move_type: str, target_types: List[str]) -> float:
    """
    Calculates the total type effectiveness multiplier for a move
    against one or two defending types.

    Args:
        move_type: The attacking move's type.
        target_types: The defender's type list.

    Returns:
        Combined effectiveness multiplier.
    """
    attacking_type = normalize_type_name(move_type)
    defending_types = normalize_type_list(target_types)

    multiplier = 1.0

    for defending_type in defending_types:
        multiplier *= TYPE_CHART.get(attacking_type, {}).get(defending_type, 1.0)

    return multiplier


def get_stab_multiplier(user_types: List[str], move_type: str) -> float:
    """
    Calculates the Same-Type Attack Bonus multiplier.

    Args:
        user_types: The attacker's type list.
        move_type: The move's type.

    Returns:
        1.5 if the move type matches one of the user's types,
        otherwise 1.0.
    """
    normalized_user_types = normalize_type_list(user_types)
    normalized_move_type = normalize_type_name(move_type)

    if normalized_move_type in normalized_user_types:
        return STAB_MULTIPLIER

    return 1.0