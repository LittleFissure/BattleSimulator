from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Dict, List, Optional

from battle_manager import BattleAction, BattleManager
from moves import load_moves
from pokemon import NatureList, PokemonInstance, load_pokemon_templates
from team import Team
import AI

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
POKEMON_JSON_PATH = DATA_DIR / "pokemon.json"
MOVES_JSON_PATH = DATA_DIR / "moves.json"
TEAM_SAVE_PATH = BASE_DIR / "saved_team.json"
MAX_TEAM_SIZE = 6
MAX_MOVES_PER_POKEMON = 4
MIN_LEVEL = 1
MAX_LEVEL = 100

STATUS_COLOURS = {
    "Burn": "#cc5500",
    "Poison": "#7a3db8",
    "Paralysis": "#b59b00",
    "Sleep": "#4a6fa5",
    "Freeze": "#4aa3d8",
    "Confusion": "#8b5a2b",
    "Flinch": "#666666",
    "Protect": "#2e8b57",
}

TYPE_COLOURS = {
    "Normal": "#A8A77A",
    "Fire": "#EE8130",
    "Water": "#6390F0",
    "Electric": "#F7D02C",
    "Grass": "#7AC74C",
    "Ice": "#96D9D6",
    "Fighting": "#C22E28",
    "Poison": "#A33EA1",
    "Ground": "#E2BF65",
    "Flying": "#A98FF3",
    "Psychic": "#F95587",
    "Bug": "#A6B91A",
    "Rock": "#B6A136",
    "Ghost": "#735797",
    "Dragon": "#6F35FC",
    "Dark": "#705746",
    "Steel": "#B7B7CE",
    "Fairy": "#D685AD",
}

MOVE_BUTTON_BG = TYPE_COLOURS.copy()

WEATHER_COLOURS = {
    "clear": "black",
    "sun": "#EE8130",
    "rain": "#6390F0",
    "sandstorm": "#B6A136",
    "hail": "#96D9D6",
}


@dataclass
class SlotConfig:
    species: str = ""
    level: int = 5
    nature: str = "Docile"
    moves: List[str] | None = None

    def __post_init__(self) -> None:
        """Validate and normalize fields after initialization."""
        if self.moves is None:
            self.moves = [""] * MAX_MOVES_PER_POKEMON


class PokemonSlotEditor(ttk.LabelFrame):
    """UI block for configuring one Pokemon team slot."""

    def __init__(
        self,
        master: tk.Widget,
        slot_number: int,
        species_names: List[str],
        move_names: List[str],
        nature_names: List[str],
        templates: Dict[str, object],
    ) -> None:
        """Initialize pokemonsloteditor state."""
        super().__init__(master, text=f"Slot {slot_number}", padding=10)
        self.templates = templates
        self.species_names = species_names
        self.move_names = move_names
        self.nature_names = nature_names

        self.species_var = tk.StringVar()
        self.level_var = tk.IntVar(value=5)
        self.nature_var = tk.StringVar(value="Docile")
        self.move_vars = [tk.StringVar() for _ in range(MAX_MOVES_PER_POKEMON)]
        self.stats_var = tk.StringVar(value="Select a Pokemon to preview its stats.")

        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="Pokemon").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        self.species_box = ttk.Combobox(
            self,
            textvariable=self.species_var,
            values=[""] + species_names,
            state="normal",
            height=20,
        )
        self.species_box.grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(self, text="Level").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Spinbox(
            self,
            from_=MIN_LEVEL,
            to=MAX_LEVEL,
            textvariable=self.level_var,
            width=8,
        ).grid(row=1, column=1, sticky="w", pady=2)

        ttk.Label(self, text="Nature").grid(row=2, column=0, sticky="w", padx=(0, 6), pady=2)
        self.nature_box = ttk.Combobox(
            self,
            textvariable=self.nature_var,
            values=nature_names,
            state="normal",
            height=20,
        )
        self.nature_box.grid(row=2, column=1, sticky="ew", pady=2)

        self.move_boxes: List[ttk.Combobox] = []
        for move_index, move_var in enumerate(self.move_vars, start=1):
            ttk.Label(self, text=f"Move {move_index}").grid(
                row=2 + move_index,
                column=0,
                sticky="w",
                padx=(0, 6),
                pady=2,
            )
            move_box = ttk.Combobox(
                self,
                textvariable=move_var,
                values=[""] + move_names,
                state="normal",
                height=20,
            )
            move_box.grid(row=2 + move_index, column=1, sticky="ew", pady=2)
            self.move_boxes.append(move_box)

        self.type_text = tk.Text(
            self,
            height=1,
            width=28,
            borderwidth=0,
            highlightthickness=0,
            wrap="none",
            font=("Segoe UI", 9, "bold"),
        )
        self.type_text.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.type_text.configure(state="disabled", bg="SystemButtonFace")

        for type_name, colour in TYPE_COLOURS.items():
            self.type_text.tag_configure(type_name, foreground=colour)
        self.type_text.tag_configure("label", foreground="black")

        ttk.Label(
            self,
            textvariable=self.stats_var,
            justify="left",
            wraplength=250,
        ).grid(row=8, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        self.species_var.trace_add("write", self._on_field_change)
        self.level_var.trace_add("write", self._on_field_change)
        self.nature_var.trace_add("write", self._on_field_change)

        self._bind_filtering()

    def _bind_filtering(self) -> None:
        """Internal helper to bind filtering."""
        self.species_box.bind(
            "<KeyRelease>",
            lambda event: self._filter_combobox(self.species_box, self.species_names),
        )
        self.nature_box.bind(
            "<KeyRelease>",
            lambda event: self._filter_combobox(self.nature_box, self.nature_names),
        )

        for move_box in self.move_boxes:
            move_box.bind(
                "<KeyRelease>",
                lambda event, box=move_box: self._filter_combobox(box, self.move_names),
            )

    def _filter_combobox(self, combobox: ttk.Combobox, full_values: List[str]) -> None:
        """Internal helper to filter combobox."""
        typed = combobox.get()
        cursor_index = combobox.index(tk.INSERT)

        if not typed.strip():
            filtered = [""] + full_values
        else:
            typed_lower = typed.lower()
            starts_with = [value for value in full_values if value.lower().startswith(typed_lower)]
            contains = [
                value for value in full_values
                if typed_lower in value.lower() and value not in starts_with
            ]
            filtered = starts_with + contains

        combobox["values"] = filtered
        combobox.focus_set()
        combobox.icursor(cursor_index)

    def _on_field_change(self, *_args: object) -> None:
        """Internal helper to on field change."""
        self.refresh_preview()

    def _set_type_text(self, types: Optional[List[str]]) -> None:
        """Internal helper to set type text."""
        self.type_text.configure(state="normal")
        self.type_text.delete("1.0", tk.END)

        self.type_text.insert(tk.END, "Type: ", "label")

        if types is None:
            self.type_text.insert(tk.END, "?", "label")
        elif not types:
            self.type_text.insert(tk.END, "-", "label")
        else:
            for index, type_name in enumerate(types):
                if index > 0:
                    self.type_text.insert(tk.END, "/", "label")
                self.type_text.insert(tk.END, type_name, type_name)

        self.type_text.configure(state="disabled")

    def refresh_preview(self) -> None:
        """Refresh preview."""
        species_name = self.species_var.get().strip()
        if not species_name:
            self._set_type_text([])
            self.stats_var.set("Empty slot.")
            return

        if species_name not in self.templates:
            self._set_type_text(None)
            self.stats_var.set("Type a valid Pokemon name.")
            return

        template = self.templates[species_name]
        level = max(MIN_LEVEL, min(MAX_LEVEL, int(self.level_var.get() or 1)))
        nature_name = self.nature_var.get().strip() or "Docile"
        nature = NatureList.get(nature_name, NatureList["Docile"])
        preview = PokemonInstance(template=template, level=level, nature=nature)

        self._set_type_text(preview.types)

        stats = preview.stats
        self.stats_var.set(
            f"HP {stats.hp} | Atk {stats.attack} | Def {stats.defense}\n"
            f"SpA {stats.special_attack} | SpD {stats.special_defense} | Spe {stats.speed}"
        )

    def get_config(self) -> SlotConfig:
        """Return config."""
        return SlotConfig(
            species=self.species_var.get().strip(),
            level=int(self.level_var.get() or 1),
            nature=self.nature_var.get().strip() or "Docile",
            moves=[move_var.get().strip() for move_var in self.move_vars],
        )

    def set_config(self, config: SlotConfig) -> None:
        """Set config."""
        self.species_var.set(config.species)
        self.level_var.set(config.level)
        self.nature_var.set(config.nature)

        moves = list(config.moves or [])
        moves += [""] * (MAX_MOVES_PER_POKEMON - len(moves))
        for move_var, move_name in zip(self.move_vars, moves):
            move_var.set(move_name)

        self.refresh_preview()

    def clear(self) -> None:
        """Handle clear."""
        self.set_config(SlotConfig())


class TeamBuilderBattleApp:
    """Desktop UI for building a player team and running battles."""

    def __init__(self, root: tk.Tk) -> None:
        """Initialize teambuilderbattleapp state."""
        self.root = root
        self.root.title("Pokemon Team Builder")
        self.root.geometry("1500x980")

        random.seed()
        self.templates = load_pokemon_templates(str(POKEMON_JSON_PATH))
        self.moves = load_moves(str(MOVES_JSON_PATH))
        self.species_names = sorted(self.templates.keys())
        self.move_names = sorted(self.moves.keys())
        self.nature_names = sorted(NatureList.keys())

        self.player_team_name_var = tk.StringVar(value="Player")
        self.enemy_team_name_var = tk.StringVar(value="Enemy")
        self.enemy_mode_var = tk.StringVar(value="random")
        self.status_var = tk.StringVar(value="Build a team, then start a battle.")
        self.random_level_base_var = tk.IntVar(value=25)
        self.random_level_range_var = tk.IntVar(value=10)

        self.player_team: Optional[Team] = None
        self.enemy_team: Optional[Team] = None
        self.battle: Optional[BattleManager] = None
        self.player_slots: List[PokemonSlotEditor] = []
        self.enemy_slots: List[PokemonSlotEditor] = []
        self.action_buttons: List[tk.Button] = []
        self.switch_buttons: List[ttk.Button] = []

        self._build_layout()
        self._refresh_enemy_editor_visibility()

    def _build_layout(self) -> None:
        """Internal helper to build layout."""
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        header = ttk.Frame(self.root, padding=10)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        ttk.Label(
            header,
            text="Pokemon Team Builder and Battle UI",
            font=("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(header, textvariable=self.status_var).grid(row=1, column=0, sticky="w", pady=(4, 0))

        content = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        content.grid(row=1, column=0, sticky="nsew")

        left_panel = ttk.Frame(content, padding=10)
        right_panel = ttk.Frame(content, padding=10)
        content.add(left_panel, weight=3)
        content.add(right_panel, weight=2)

        self._build_team_builder(left_panel)
        self._build_battle_panel(right_panel)

    def _build_team_builder(self, parent: ttk.Frame) -> None:
        """Internal helper to build team builder."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)

        control_bar = ttk.Frame(parent)
        control_bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        for col in range(8):
            control_bar.columnconfigure(col, weight=0)
        control_bar.columnconfigure(7, weight=1)

        ttk.Label(control_bar, text="Player team name").grid(row=0, column=0, sticky="w")
        ttk.Entry(control_bar, textvariable=self.player_team_name_var, width=18).grid(row=0, column=1, padx=(6, 12))

        ttk.Label(control_bar, text="Enemy team name").grid(row=0, column=2, sticky="w")
        ttk.Entry(control_bar, textvariable=self.enemy_team_name_var, width=18).grid(row=0, column=3, padx=(6, 12))

        ttk.Radiobutton(
            control_bar,
            text="Random enemy",
            variable=self.enemy_mode_var,
            value="random",
            command=self._refresh_enemy_editor_visibility,
        ).grid(row=0, column=4, padx=(0, 8))

        ttk.Radiobutton(
            control_bar,
            text="Custom enemy",
            variable=self.enemy_mode_var,
            value="custom",
            command=self._refresh_enemy_editor_visibility,
        ).grid(row=0, column=5, padx=(0, 12))

        ttk.Button(control_bar, text="Load saved team", command=self.load_saved_team).grid(row=0, column=6, padx=(0, 6))
        ttk.Button(control_bar, text="Save player team", command=self.save_player_team).grid(row=0, column=7, sticky="e")

        ttk.Label(control_bar, text="Random level").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Spinbox(
            control_bar,
            from_=MIN_LEVEL,
            to=MAX_LEVEL,
            textvariable=self.random_level_base_var,
            width=8,
        ).grid(row=1, column=1, sticky="w", pady=(8, 0))

        ttk.Label(control_bar, text="Range ±").grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Spinbox(
            control_bar,
            from_=0,
            to=MAX_LEVEL - MIN_LEVEL,
            textvariable=self.random_level_range_var,
            width=8,
        ).grid(row=1, column=3, sticky="w", pady=(8, 0))

        action_bar = ttk.Frame(parent)
        action_bar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(action_bar, text="Clear player team", command=self.clear_player_team).pack(side=tk.LEFT)
        ttk.Button(action_bar, text="Randomize player team", command=self.randomize_player_team).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(action_bar, text="Randomize enemy team", command=self.randomize_enemy_team).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(action_bar, text="Randomize levels", command=self.randomize_levels_only).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(action_bar, text="Start battle", command=self.start_battle).pack(side=tk.RIGHT)

        builder_notebook = ttk.Notebook(parent)
        builder_notebook.grid(row=3, column=0, sticky="nsew")

        player_tab = ttk.Frame(builder_notebook, padding=10)
        enemy_tab = ttk.Frame(builder_notebook, padding=10)
        builder_notebook.add(player_tab, text="Player Team")
        builder_notebook.add(enemy_tab, text="Enemy Team")

        self._build_slot_grid(player_tab, self.player_slots)
        self.enemy_tab = enemy_tab
        self._build_slot_grid(enemy_tab, self.enemy_slots)

    def _build_slot_grid(self, parent: ttk.Frame, slot_store: List[PokemonSlotEditor]) -> None:
        """Internal helper to build slot grid."""
        for column in range(3):
            parent.columnconfigure(column, weight=1)
        for row in range(2):
            parent.rowconfigure(row, weight=1)

        for slot_index in range(MAX_TEAM_SIZE):
            editor = PokemonSlotEditor(
                parent,
                slot_number=slot_index + 1,
                species_names=self.species_names,
                move_names=self.move_names,
                nature_names=self.nature_names,
                templates=self.templates,
            )
            editor.grid(row=slot_index // 3, column=slot_index % 3, sticky="nsew", padx=6, pady=6)
            slot_store.append(editor)

    def _build_battle_panel(self, parent: ttk.Frame) -> None:
        """Internal helper to build battle panel."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=0)
        parent.rowconfigure(1, weight=0)
        parent.rowconfigure(2, weight=1)
        parent.rowconfigure(3, weight=0)
        parent.rowconfigure(4, weight=0)

        enemy_frame = ttk.LabelFrame(parent, text="Enemy Active", padding=10)
        enemy_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        enemy_frame.columnconfigure(0, weight=1)

        self.enemy_name_var = tk.StringVar(value="No battle")
        self.enemy_hp_text_var = tk.StringVar(value="-")
        self.enemy_status_var = tk.StringVar(value="Status: None")

        ttk.Label(enemy_frame, textvariable=self.enemy_name_var, font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        self.enemy_status_label = tk.Label(enemy_frame, textvariable=self.enemy_status_var, anchor="w")
        self.enemy_status_label.grid(row=1, column=0, sticky="w", pady=(2, 4))
        self.enemy_hp_bar = ttk.Progressbar(enemy_frame, orient="horizontal", mode="determinate", maximum=100)
        self.enemy_hp_bar.grid(row=2, column=0, sticky="ew")
        ttk.Label(enemy_frame, textvariable=self.enemy_hp_text_var).grid(row=3, column=0, sticky="w", pady=(4, 0))

        weather_frame = ttk.LabelFrame(parent, text="Weather", padding=10)
        weather_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        weather_frame.columnconfigure(0, weight=1)

        self.weather_name_var = tk.StringVar(value="Clear")
        self.weather_turns_var = tk.StringVar(value="Turns remaining: -")
        self.weather_name_label = tk.Label(
            weather_frame,
            textvariable=self.weather_name_var,
            anchor="w",
            font=("Segoe UI", 11, "bold"),
        )
        self.weather_name_label.grid(row=0, column=0, sticky="w")
        ttk.Label(weather_frame, textvariable=self.weather_turns_var).grid(row=1, column=0, sticky="w", pady=(4, 0))

        middle_frame = ttk.Frame(parent)
        middle_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        middle_frame.columnconfigure(0, weight=1)
        middle_frame.columnconfigure(1, weight=1)
        middle_frame.rowconfigure(0, weight=1)

        team_state_frame = ttk.LabelFrame(middle_frame, text="Battle State", padding=10)
        team_state_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        team_state_frame.columnconfigure(0, weight=1)
        team_state_frame.rowconfigure(0, weight=1)

        self.battle_state_box = tk.Text(team_state_frame, height=16, wrap="word", state="disabled")
        self.battle_state_box.grid(row=0, column=0, sticky="nsew")
        self._configure_battle_state_tags()

        log_frame = ttk.LabelFrame(middle_frame, text="Battle Log", padding=10)
        log_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_box = ScrolledText(
            log_frame,
            height=16,
            wrap=tk.WORD,
            state="disabled",
            font=("Consolas", 9),
        )
        self.log_box.grid(row=0, column=0, sticky="nsew")
        self.log_box.configure(
            bg="#111111",
            fg="#eeeeee",
            insertbackground="white",
            padx=6,
            pady=6,
        )

        player_frame = ttk.LabelFrame(parent, text="Player Active", padding=10)
        player_frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        player_frame.columnconfigure(0, weight=1)

        self.player_name_var = tk.StringVar(value="No battle")
        self.player_hp_text_var = tk.StringVar(value="-")
        self.player_status_var = tk.StringVar(value="Status: None")

        ttk.Label(player_frame, textvariable=self.player_name_var, font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        self.player_status_label = tk.Label(player_frame, textvariable=self.player_status_var, anchor="w")
        self.player_status_label.grid(row=1, column=0, sticky="w", pady=(2, 4))
        self.player_hp_bar = ttk.Progressbar(player_frame, orient="horizontal", mode="determinate", maximum=100)
        self.player_hp_bar.grid(row=2, column=0, sticky="ew")
        ttk.Label(player_frame, textvariable=self.player_hp_text_var).grid(row=3, column=0, sticky="w", pady=(4, 0))

        controls = ttk.LabelFrame(parent, text="Actions", padding=10)
        controls.grid(row=4, column=0, sticky="ew")
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)

        moves_frame = ttk.Frame(controls)
        moves_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        switches_frame = ttk.Frame(controls)
        switches_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        ttk.Label(moves_frame, text="Moves").pack(anchor="w")
        ttk.Label(switches_frame, text="Switch").pack(anchor="w")

        for _ in range(MAX_MOVES_PER_POKEMON):
            button = tk.Button(
                moves_frame,
                text="-",
                state="disabled",
                relief="raised",
                bd=1,
                activeforeground="black",
            )
            button.pack(fill="x", pady=3)
            self.action_buttons.append(button)

        for _ in range(MAX_TEAM_SIZE):
            button = ttk.Button(switches_frame, text="-", state="disabled")
            button.pack(fill="x", pady=3)
            self.switch_buttons.append(button)

        extra_controls = ttk.Frame(controls)
        extra_controls.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(
            extra_controls,
            text="Auto resolve forced action",
            command=self.resolve_forced_action,
        ).pack(side=tk.LEFT)
        ttk.Button(extra_controls, text="Reset battle panel", command=self.reset_battle_panel).pack(side=tk.RIGHT)

    def _configure_battle_state_tags(self) -> None:
        """Internal helper to configure battle state tags."""
        self.battle_state_box.tag_configure("header", font=("Segoe UI", 10, "bold"))
        self.battle_state_box.tag_configure("active", foreground="#006400")
        self.battle_state_box.tag_configure("fainted", foreground="#b22222")
        self.battle_state_box.tag_configure("normal", foreground="black")

    def _style_move_button(self, button: tk.Button, move_name: str) -> None:
        """Internal helper to style move button."""
        move = self.moves.get(move_name)
        move_type = getattr(move, "move_type", None) if move is not None else None
        colour = MOVE_BUTTON_BG.get(move_type, "SystemButtonFace")

        button.configure(
            bg=colour,
            fg="black",
            activebackground=colour,
            activeforeground="black",
            disabledforeground="#666666",
        )

    def _refresh_enemy_editor_visibility(self) -> None:
        """Internal helper to refresh enemy editor visibility."""
        mode = self.enemy_mode_var.get()
        if mode == "custom":
            self.enemy_tab.state(["!disabled"])
            self.status_var.set("Custom enemy mode enabled.")
        else:
            self.enemy_tab.state(["disabled"])
            self.status_var.set("Random enemy mode enabled.")

    def append_log(self, lines: List[str] | str) -> None:
        """Append log."""
        if isinstance(lines, str):
            text = lines
        else:
            text = "\n".join(lines)
        if not text:
            return
        self.log_box.configure(state="normal")
        if self.log_box.index("end-1c") != "1.0":
            self.log_box.insert(tk.END, "\n")
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.see(tk.END)
        self.log_box.configure(state="disabled")

    def reset_battle_panel(self) -> None:
        """Handle reset battle panel."""
        self.player_team = None
        self.enemy_team = None
        self.battle = None
        self.status_var.set("Battle panel reset.")
        self._clear_active_panels()
        self._render_battle_state_box()
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", tk.END)
        self.log_box.configure(state="disabled")
        self.refresh_battle_controls()

    def _clear_active_panels(self) -> None:
        """Internal helper to clear active panels."""
        self.enemy_name_var.set("No battle")
        self.enemy_hp_text_var.set("-")
        self.enemy_status_var.set("Status: None")
        self.enemy_status_label.configure(fg="black")
        self.enemy_hp_bar["value"] = 0

        self.player_name_var.set("No battle")
        self.player_hp_text_var.set("-")
        self.player_status_var.set("Status: None")
        self.player_status_label.configure(fg="black")
        self.player_hp_bar["value"] = 0

        self.weather_name_var.set("Clear")
        self.weather_turns_var.set("Turns remaining: -")
        self.weather_name_label.configure(fg=WEATHER_COLOURS["clear"])

    def _update_weather_panel(self) -> None:
        """Internal helper to update weather panel."""
        if self.battle is None:
            self.weather_name_var.set("Clear")
            self.weather_turns_var.set("Turns remaining: -")
            self.weather_name_label.configure(fg=WEATHER_COLOURS["clear"])
            return

        weather = getattr(self.battle, "weather", None)
        kind = getattr(weather, "kind", "clear") if weather is not None else "clear"
        turns_remaining = getattr(weather, "turns_remaining", None) if weather is not None else None

        display_name = kind.replace("_", " ").title()
        self.weather_name_var.set(display_name)
        self.weather_turns_var.set(f"Turns remaining: {turns_remaining}")

        self.weather_name_label.configure(fg=WEATHER_COLOURS.get(kind, "black"))

    def _random_slot_config(self) -> SlotConfig:
        """Internal helper to random slot config."""
        species = random.choice(self.species_names)

        if len(self.move_names) >= MAX_MOVES_PER_POKEMON:
            selected_moves = random.sample(self.move_names, k=MAX_MOVES_PER_POKEMON)
        else:
            selected_moves = random.choices(self.move_names, k=MAX_MOVES_PER_POKEMON)

        base_level = int(self.random_level_base_var.get() or 1)
        level_range = abs(int(self.random_level_range_var.get() or 0))

        low = max(MIN_LEVEL, base_level - level_range)
        high = min(MAX_LEVEL, base_level + level_range)
        level = random.randint(low, high)

        return SlotConfig(
            species=species,
            level=level,
            nature=random.choice(self.nature_names),
            moves=selected_moves,
        )

    def clear_player_team(self) -> None:
        """Clear player team."""
        for slot in self.player_slots:
            slot.clear()
        self.status_var.set("Player team cleared.")

    def randomize_player_team(self) -> None:
        """Randomize player team."""
        for slot in self.player_slots:
            slot.set_config(self._random_slot_config())
        self.status_var.set("Player team randomized.")

    def randomize_enemy_team(self) -> None:
        """Randomize enemy team."""
        for slot in self.enemy_slots:
            slot.set_config(self._random_slot_config())
        self.status_var.set("Enemy team randomized.")

    def randomize_levels_only(self) -> None:
        """Randomize levels only."""
        base_level = int(self.random_level_base_var.get() or 1)
        level_range = int(self.random_level_range_var.get() or 0)

        low = max(MIN_LEVEL, base_level - level_range)
        high = min(MAX_LEVEL, base_level + level_range)

        changed = False

        for slot in self.player_slots:
            config = slot.get_config()
            if config.species:
                config.level = random.randint(low, high)
                slot.set_config(config)
                changed = True

        if changed:
            self.status_var.set(f"Player levels randomized in range {low}-{high}.")
        else:
            self.status_var.set("No player Pokemon to level.")

    def save_player_team(self) -> None:
        """Handle save player team."""
        data = {
            "team_name": self.player_team_name_var.get().strip() or "Player",
            "slots": [slot.get_config().__dict__ for slot in self.player_slots],
        }
        with open(TEAM_SAVE_PATH, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        self.status_var.set(f"Saved player team to {TEAM_SAVE_PATH.name}.")

    def load_saved_team(self) -> None:
        """Load saved team from disk."""
        if not TEAM_SAVE_PATH.exists():
            messagebox.showinfo("No saved team", f"{TEAM_SAVE_PATH.name} was not found.")
            return

        with open(TEAM_SAVE_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        self.player_team_name_var.set(data.get("team_name", "Player"))
        slots = data.get("slots", [])
        for index, slot in enumerate(self.player_slots):
            if index < len(slots):
                slot.set_config(SlotConfig(**slots[index]))
            else:
                slot.clear()
        self.status_var.set(f"Loaded player team from {TEAM_SAVE_PATH.name}.")

    def build_pokemon_from_config(self, config: SlotConfig) -> PokemonInstance:
        """Build pokemon from config."""
        if config.species not in self.templates:
            raise ValueError(f"Unknown Pokemon: {config.species}")
        if config.nature not in NatureList:
            raise ValueError(f"Unknown nature: {config.nature}")

        selected_moves = [move_name for move_name in (config.moves or []) if move_name]
        if not selected_moves:
            raise ValueError(f"{config.species} must have at least one move.")
        if len(selected_moves) > MAX_MOVES_PER_POKEMON:
            raise ValueError(f"{config.species} cannot know more than four moves.")
        if len(selected_moves) != len(set(selected_moves)):
            raise ValueError(f"{config.species} has duplicate moves.")
        for move_name in selected_moves:
            if move_name not in self.moves:
                raise ValueError(f"Unknown move: {move_name}")

        pokemon = PokemonInstance(
            template=self.templates[config.species],
            level=max(MIN_LEVEL, min(MAX_LEVEL, int(config.level))),
            nature=NatureList[config.nature],
        )
        for move_name in selected_moves:
            pokemon.add_known_move(self.moves[move_name])
        return pokemon

    def build_team_from_slots(self, name: str, slots: List[PokemonSlotEditor]) -> Team:
        """Build team from slots."""
        members: List[PokemonInstance] = []
        for slot in slots:
            config = slot.get_config()
            if not config.species:
                continue
            members.append(self.build_pokemon_from_config(config))

        if not members:
            raise ValueError(f"{name} team is empty.")
        return Team(name=name.strip() or "Trainer", members=members)

    def build_random_enemy_team(self, name: str) -> Team:
        """Build random enemy team."""
        members = [self.build_pokemon_from_config(self._random_slot_config()) for _ in range(MAX_TEAM_SIZE)]
        return Team(name=name.strip() or "Enemy", members=members)

    def start_battle(self) -> None:
        """Handle start battle."""
        try:
            self.player_team = self.build_team_from_slots(self.player_team_name_var.get(), self.player_slots)
            if self.enemy_mode_var.get() == "custom":
                self.enemy_team = self.build_team_from_slots(self.enemy_team_name_var.get(), self.enemy_slots)
            else:
                self.enemy_team = self.build_random_enemy_team(self.enemy_team_name_var.get())
        except ValueError as exc:
            messagebox.showerror("Invalid team", str(exc))
            return

        self.battle = BattleManager(self.player_team, self.enemy_team)
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", tk.END)
        self.log_box.configure(state="disabled")
        self.append_log(
            [
                f"{self.player_team.name} sent out {self.battle.player.name}!",
                f"{self.enemy_team.name} sent out {self.battle.enemy.name}!",
            ]
        )
        self.status_var.set("Battle started.")
        self.refresh_battle_state()
        self.refresh_battle_controls()

    def refresh_battle_state(self) -> None:
        """Refresh battle state."""
        if self.battle is None or self.player_team is None or self.enemy_team is None:
            self._clear_active_panels()
            self._render_battle_state_box()
            return

        self._update_weather_panel()

        self._update_active_panel(
            battler=self.battle.enemy,
            team_name=self.enemy_team.name,
            name_var=self.enemy_name_var,
            hp_text_var=self.enemy_hp_text_var,
            status_var=self.enemy_status_var,
            status_label=self.enemy_status_label,
            hp_bar=self.enemy_hp_bar,
        )
        self._update_active_panel(
            battler=self.battle.player,
            team_name=self.player_team.name,
            name_var=self.player_name_var,
            hp_text_var=self.player_hp_text_var,
            status_var=self.player_status_var,
            status_label=self.player_status_label,
            hp_bar=self.player_hp_bar,
        )

        self._render_battle_state_box()

    def _update_active_panel(
        self,
        battler: PokemonInstance,
        team_name: str,
        name_var: tk.StringVar,
        hp_text_var: tk.StringVar,
        status_var: tk.StringVar,
        status_label: tk.Label,
        hp_bar: ttk.Progressbar,
    ) -> None:
        """Internal helper to update active panel."""
        types_text = "/".join(battler.types)
        name_var.set(f"{team_name}: {battler.name} Lv{battler.level} ({types_text})")
        hp_text_var.set(f"HP {battler.current_hp}/{battler.max_hp}")

        hp_percent = 0 if battler.max_hp <= 0 else (battler.current_hp / battler.max_hp) * 100
        hp_bar["value"] = max(0, min(100, hp_percent))

        if battler.status_effects:
            names = [status.name for status in battler.status_effects]
            status_var.set(f"Status: {', '.join(names)}")
            status_label.configure(fg=STATUS_COLOURS.get(names[0], "black"))
        else:
            status_var.set("Status: None")
            status_label.configure(fg="black")

    def _render_battle_state_box(self) -> None:
        """Internal helper to render battle state box."""
        self.battle_state_box.configure(state="normal")
        self.battle_state_box.delete("1.0", tk.END)

        if self.player_team is None or self.enemy_team is None:
            self.battle_state_box.insert(tk.END, "No battle is running.\n", "normal")
            self.battle_state_box.configure(state="disabled")
            return

        self._insert_team_summary(self.player_team)
        self.battle_state_box.insert(tk.END, "\n")
        self._insert_team_summary(self.enemy_team)

        self.battle_state_box.configure(state="disabled")

    def _insert_team_summary(self, team: Team) -> None:
        """Internal helper to insert team summary."""
        self.battle_state_box.insert(tk.END, f"{team.name} team:\n", "header")
        for index, pokemon in enumerate(team.members, start=1):
            markers: List[str] = []
            tag = "normal"
            if index - 1 == team.active_index:
                markers.append("ACTIVE")
                tag = "active"
            if pokemon.is_fainted:
                markers.append("FNT")
                tag = "fainted"
            marker_text = f" [{' | '.join(markers)}]" if markers else ""
            line = f"{index}. {pokemon.name} Lv{pokemon.level} HP {pokemon.current_hp}/{pokemon.max_hp}{marker_text}\n"
            self.battle_state_box.insert(tk.END, line, tag)

    def refresh_battle_controls(self) -> None:
        """Refresh battle controls."""
        battle = self.battle
        player_team = self.player_team

        for button in self.action_buttons:
            button.configure(
                text="-",
                state="disabled",
                command=lambda: None,
                bg="SystemButtonFace",
                fg="black",
                activebackground="SystemButtonFace",
                activeforeground="black",
            )
        for button in self.switch_buttons:
            button.configure(text="-", state="disabled", command=lambda: None)

        if battle is None or player_team is None or battle.is_battle_over():
            if battle is not None and battle.is_battle_over():
                winner = battle.get_winner()
                self.status_var.set("Draw." if winner is None else f"{winner.name} won the battle.")
            return

        active = player_team.active
        if battle.needs_player_replacement():
            self.status_var.set("Choose a replacement Pokemon.")
            for index, pokemon in enumerate(player_team.members):
                if player_team.can_switch_to(index):
                    self.switch_buttons[index].configure(
                        text=f"{pokemon.name} Lv{pokemon.level}",
                        state="normal",
                        command=lambda idx=index: self.force_player_replacement(idx),
                    )
            return

        forced_move_name: Optional[str] = None
        if active.is_charging_move and active.charging_move_name:
            forced_move_name = active.charging_move_name
        elif active.is_locked_into_move and active.locked_move_name:
            forced_move_name = active.locked_move_name

        if forced_move_name:
            self.status_var.set(f"{active.name} is committed to {forced_move_name}.")
            self.action_buttons[0].configure(
                text=f"Use {forced_move_name}",
                state="normal",
                command=lambda name=forced_move_name: self.play_player_turn(BattleAction.move(name)),
            )
            self._style_move_button(self.action_buttons[0], forced_move_name)
            return

        self.status_var.set("Choose a move or switch.")
        for index, known_move in enumerate(active.known_moves):
            button = self.action_buttons[index]
            button.configure(
                text=f"{known_move.move.name} ({known_move.current_pp}/{known_move.move.max_pp})",
                state="normal" if known_move.is_usable else "disabled",
                command=lambda name=known_move.move.name: self.play_player_turn(BattleAction.move(name)),
            )
            self._style_move_button(button, known_move.move.name)

        for index, pokemon in enumerate(player_team.members):
            self.switch_buttons[index].configure(
                text=f"{pokemon.name} Lv{pokemon.level}",
                state="normal" if player_team.can_switch_to(index) else "disabled",
                command=lambda idx=index: self.play_player_turn(BattleAction.switch(idx)),
            )

    def choose_enemy_action(self) -> BattleAction:
        """Choose enemy action."""
        if self.enemy_team is None:
            raise ValueError("Enemy team is not loaded.")

        active = self.enemy_team.active
        if active.is_charging_move and active.charging_move_name is not None:
            return BattleAction.move(active.charging_move_name)
        if active.is_locked_into_move and active.locked_move_name is not None:
            return BattleAction.move(active.locked_move_name)

        usable_moves = [known_move for known_move in active.known_moves if known_move.is_usable]
        if usable_moves:
            return BattleAction.move(AI.find_best_move(active,self.enemy_team,self.battle.player, usable_moves))
        if self.enemy_team.has_usable_benched_pokemon():
            return BattleAction.switch(self.enemy_team.choose_first_benched_available())
        raise ValueError(f"{active.name} has no usable moves left.")

    def play_player_turn(self, player_action: BattleAction) -> None:
        """Handle play player turn."""
        if self.battle is None:
            return
        try:
            enemy_action = self.choose_enemy_action()
            round_log = self.battle.play_round(player_action, enemy_action)
        except ValueError as exc:
            messagebox.showerror("Battle error", str(exc))
            return

        self.append_log(round_log)
        self.handle_post_round_flow()

    def force_player_replacement(self, index: int) -> None:
        """Handle force player replacement."""
        if self.battle is None:
            return
        replacement_log: List[str] = []
        try:
            self.battle.replace_fainted_player(index, replacement_log)
        except ValueError as exc:
            messagebox.showerror("Invalid replacement", str(exc))
            return

        self.append_log(replacement_log)
        self.handle_post_round_flow(skip_enemy_replacement=False)

    def handle_post_round_flow(self, skip_enemy_replacement: bool = False) -> None:
        """Handle post round flow."""
        if self.battle is None:
            return

        if not skip_enemy_replacement:
            while self.battle.needs_enemy_replacement() and not self.battle.is_battle_over():
                replacement_log: List[str] = []
                self.battle.auto_replace_fainted_enemy(replacement_log)
                self.append_log(replacement_log)

        self.refresh_battle_state()
        self.refresh_battle_controls()

        if self.battle.is_battle_over():
            winner = self.battle.get_winner()
            self.append_log("The battle ended in a draw!" if winner is None else f"{winner.name} wins!")
            self.refresh_battle_controls()

    def resolve_forced_action(self) -> None:
        """Handle resolve forced action."""
        if self.battle is None or self.player_team is None:
            return

        if self.battle.needs_player_replacement():
            for index in range(len(self.player_team.members)):
                if self.player_team.can_switch_to(index):
                    self.force_player_replacement(index)
                    return
            return

        active = self.player_team.active
        if active.is_charging_move and active.charging_move_name:
            self.play_player_turn(BattleAction.move(active.charging_move_name))
            return
        if active.is_locked_into_move and active.locked_move_name:
            self.play_player_turn(BattleAction.move(active.locked_move_name))
            return

        self.status_var.set("No forced action is pending.")


def main() -> None:
    """Run the application entry point."""
    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    TeamBuilderBattleApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()