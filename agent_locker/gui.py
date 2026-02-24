from __future__ import annotations

import json
import shlex
from pathlib import Path
from tkinter import (
    END,
    Entry,
    Frame,
    Label,
    Listbox,
    OptionMenu,
    Scrollbar,
    StringVar,
    TclError,
    Text,
    Tk,
    filedialog,
    messagebox,
)
from tkinter import font as tkfont

from .audit import iso_utc_now, write_audit_log
from .config import write_default_policy
from .launch_command import build_launcher_command_line
from .policy import Policy, PolicyError, is_subpath, load_policy, normalize_path, save_policy
from .runner import CommandRunner, RunRequest


class ActionButton(Label):
    def __init__(
        self,
        master,
        text: str,
        command,
        bg: str,
        fg: str,
        hover_bg: str,
        active_bg: str,
        border: str,
    ):
        super().__init__(
            master,
            text=text,
            bg=bg,
            fg=fg,
            padx=7,
            pady=4,
            cursor="hand2",
            font=("Helvetica", 10, "bold"),
            highlightthickness=1,
            highlightbackground=border,
            highlightcolor=border,
        )
        self._command = command
        self._default_bg = bg
        self._hover_bg = hover_bg
        self._active_bg = active_bg
        self._border = border
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def set_colors(self, bg: str, fg: str, hover_bg: str, active_bg: str, border: str) -> None:
        self._default_bg = bg
        self._hover_bg = hover_bg
        self._active_bg = active_bg
        self._border = border
        self.config(bg=bg, fg=fg, highlightbackground=border, highlightcolor=border)

    def _on_enter(self, _event) -> None:
        self.config(bg=self._hover_bg)

    def _on_leave(self, _event) -> None:
        self.config(bg=self._default_bg)

    def _on_press(self, _event) -> None:
        self.config(bg=self._active_bg)

    def _on_release(self, _event) -> None:
        self.config(bg=self._hover_bg)
        self._command()



from .gui_data import (
    CANDIDATE_PATHS,
    CATEGORY_ORDER,
    COMPACT_BUTTON_WRAP,
    DISABLED,
    FONT_BODY,
    FONT_META,
    FONT_SECTION,
    FONT_TITLE,
    GOLDEN_MAJOR,
    GOLDEN_MINOR,
    ONBOARDING_STATE_PATH,
    PHI,
    SIDE_CONTROL_MIN_WIDTH,
    SPACE_LG,
    SPACE_MD,
    SPACE_XS,
    TEXTS,
    THEME,
)
from .gui_geometry import recenter_position_if_offscreen, resolve_min_window_size

MAX_UI_LOG_RECORDS = 200


class AgentLockerWindow:
    def __init__(self, policy_path: Path, audit_log_path: Path):
        self.policy_path = policy_path
        self.audit_log_path = audit_log_path
        self.language = "ja"
        self.command_generated = False
        self._generated_signature: tuple[str, str] | None = None
        self._log_records: list[tuple[str, str]] = []
        self.font_scale = 1.0
        self._base_fonts: dict[object, dict[str, object]] = {}
        self._candidate_paths_view: list[str] = []
        self._fixed_window_size = True
        self._base_min_width = 960
        self._base_min_height = 760
        self._wrap_sync_after_id: str | None = None
        write_default_policy(policy_path, overwrite=False)
        self.policy = self._load_policy()
        if not self.policy.enabled:
            self.policy = Policy(enabled=True, deny_paths=self.policy.deny_paths)
            save_policy(self.policy_path, self.policy)
        self.runner = CommandRunner()
        self.root = Tk()
        self.root.configure(bg=THEME["bg"])
        self.root.tk_setPalette(
            background=THEME["bg"],
            foreground=THEME["text"],
            activeBackground=THEME["button_bg"],
            activeForeground=THEME["text"],
        )
        self._disable_fullscreen_mode()
        self._set_golden_geometry()
        self._build_ui()
        self._apply_typography()
        self._apply_texts()
        self._refresh_deny_list()
        self._update_save_state_ui()
        self._show_onboarding_if_needed()
        self.root.bind("<Configure>", self._on_resize)
        self.root.after(0, self._sync_wraplengths)
        self.root.after(0, lambda: self.command_entry.focus_set())

    def _load_policy(self) -> Policy:
        try:
            return load_policy(self.policy_path)
        except PolicyError:
            write_default_policy(self.policy_path, overwrite=True)
            return load_policy(self.policy_path)

    def _t(self, key: str) -> str:
        return TEXTS[self.language][key]

    def _set_golden_geometry(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        max_width = max(int(screen_w * 0.90), 1)
        max_height = max(int(screen_h * 0.90), 1)
        width = min(1500, max_width)
        height = int(round(width / PHI))
        if height > max_height:
            height = max_height
            width = int(round(height * PHI))
        if width > max_width:
            width = max_width
            height = int(round(width / PHI))

        x = max((screen_w - width) // 2, 0)
        y = max((screen_h - height) // 2, 0)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self._base_min_width = width
        self._base_min_height = height
        self.root.minsize(width, height)
        self.root.maxsize(width, height)
        self.root.resizable(False, False)

    def _build_ui(self) -> None:
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=0)
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_rowconfigure(3, weight=0)

        header = Frame(self.root, bg=THEME["bg"])
        header.grid(row=0, column=0, sticky="ew", padx=SPACE_LG, pady=(SPACE_XS, SPACE_XS))
        header.grid_columnconfigure(0, weight=GOLDEN_MAJOR)
        header.grid_columnconfigure(1, weight=GOLDEN_MINOR)

        title_box = Frame(header, bg=THEME["bg"])
        title_box.grid(row=0, column=0, sticky="w")
        self.app_title_label = Label(
            title_box,
            bg=THEME["bg"],
            fg=THEME["text"],
            font=("Helvetica", 24, "bold"),
        )
        self.app_title_label.grid(row=0, column=0, sticky="w")

        self.status_bar = Frame(self.root, bg=THEME["bg"])
        self.status_bar.grid(row=3, column=0, sticky="ew", padx=SPACE_LG, pady=(0, SPACE_MD))
        self.status_bar.grid_columnconfigure(0, weight=1)
        self.status_bar.grid_columnconfigure(1, weight=0)
        self.policy_location_label = Label(
            self.status_bar,
            bg=THEME["bg"],
            fg=THEME["muted"],
            font=("Helvetica", 9),
            justify="left",
            anchor="w",
        )
        self.policy_location_label.grid(row=0, column=0, sticky="w")

        language_box = Frame(self.status_bar, bg=THEME["bg"])
        language_box.grid(row=0, column=1, sticky="e")
        self.language_label = Label(
            language_box,
            bg=THEME["bg"],
            fg=THEME["muted"],
            font=("Helvetica", 10, "bold"),
        )
        self.language_label.grid(row=0, column=0, sticky="e", pady=(SPACE_MD, 0))
        lang_buttons = Frame(language_box, bg=THEME["bg"])
        lang_buttons.grid(row=1, column=0, sticky="e", pady=(SPACE_XS, 0))
        self.en_button = ActionButton(
            lang_buttons,
            text="",
            command=lambda: self.set_language("en"),
            bg=THEME["button_bg"],
            fg=THEME["button_text"],
            hover_bg=THEME["button_hover"],
            active_bg=THEME["button_active"],
            border=THEME["button_border"],
        )
        self.en_button.grid(row=0, column=0, padx=(0, SPACE_XS))
        self.ja_button = ActionButton(
            lang_buttons,
            text="",
            command=lambda: self.set_language("ja"),
            bg=THEME["button_bg"],
            fg=THEME["button_text"],
            hover_bg=THEME["button_hover"],
            active_bg=THEME["button_active"],
            border=THEME["button_border"],
        )
        self.ja_button.grid(row=0, column=1)
        self.font_label = Label(
            language_box,
            bg=THEME["bg"],
            fg=THEME["muted"],
            font=("Helvetica", 10, "bold"),
        )
        self.font_label.grid(row=2, column=0, sticky="e", pady=(SPACE_MD, 0))
        font_buttons = Frame(language_box, bg=THEME["bg"])
        self.font_buttons = font_buttons
        font_buttons.grid(row=3, column=0, sticky="e", pady=(SPACE_XS, 0))
        self.font_smaller_button = ActionButton(
            font_buttons,
            text="",
            command=lambda: self.adjust_font_scale(-0.1),
            bg=THEME["button_bg"],
            fg=THEME["button_text"],
            hover_bg=THEME["button_hover"],
            active_bg=THEME["button_active"],
            border=THEME["button_border"],
        )
        self.font_smaller_button.grid(row=0, column=0, padx=(0, SPACE_XS))
        self.font_larger_button = ActionButton(
            font_buttons,
            text="",
            command=lambda: self.adjust_font_scale(0.1),
            bg=THEME["button_bg"],
            fg=THEME["button_text"],
            hover_bg=THEME["button_hover"],
            active_bg=THEME["button_active"],
            border=THEME["button_border"],
        )
        self.font_larger_button.grid(row=0, column=1)
        self.font_label.grid_remove()
        self.font_buttons.grid_remove()

        self.protection_banner = Label(
            self.root,
            bg=THEME["red"],
            fg="#FFFFFF",
            font=("Helvetica", 12, "bold"),
            padx=SPACE_MD,
            pady=SPACE_XS,
        )
        self.protection_banner.grid(row=1, column=0, sticky="ew", padx=SPACE_LG, pady=(0, SPACE_MD))
        self.protection_banner.grid_remove()

        top = Frame(self.root, bg=THEME["bg"])
        top.grid(row=2, column=0, sticky="nsew", padx=SPACE_LG, pady=(0, SPACE_LG))
        top.grid_columnconfigure(0, weight=GOLDEN_MAJOR, uniform="main_columns")
        top.grid_columnconfigure(1, weight=GOLDEN_MINOR, uniform="main_columns")
        top.grid_rowconfigure(0, weight=1)

        left = Frame(
            top,
            bg=THEME["panel"],
            highlightthickness=1,
            highlightbackground=THEME["panel_border"],
            highlightcolor=THEME["panel_border"],
        )
        self.left_panel = left
        left.grid(row=0, column=0, sticky="nsew", padx=(0, SPACE_MD))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=38)
        left.grid_rowconfigure(1, weight=62)

        candidate_box = Frame(
            left,
            bg=THEME["card"],
            highlightthickness=2,
            highlightbackground=THEME["panel_border"],
            highlightcolor=THEME["panel_border"],
        )
        self.candidate_box = candidate_box
        candidate_box.grid(row=1, column=0, sticky="nsew", padx=SPACE_MD, pady=(0, SPACE_MD))
        candidate_box.grid_columnconfigure(0, weight=1)
        candidate_box.grid_columnconfigure(1, weight=0, minsize=SIDE_CONTROL_MIN_WIDTH)
        candidate_box.grid_rowconfigure(2, weight=1)
        self.candidate_title_label = Label(
            candidate_box,
            bg=THEME["card"],
            fg=THEME["teal"],
            font=("Helvetica", 11, "bold"),
        )
        self.candidate_title_label.grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            padx=SPACE_XS,
            pady=(SPACE_XS, 2),
        )
        self.candidate_desc_label = Label(
            candidate_box,
            bg=THEME["card"],
            fg=THEME["muted"],
            font=("Helvetica", 9),
            justify="left",
            anchor="w",
        )
        self.candidate_desc_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=SPACE_XS)
        self.candidate_desc_label.grid_remove()
        candidate_list_frame = Frame(candidate_box, bg=THEME["card"])
        self.candidate_list_frame = candidate_list_frame
        candidate_list_frame.grid(row=2, column=0, rowspan=3, sticky="nsew", padx=SPACE_XS, pady=(SPACE_XS, SPACE_XS))
        candidate_list_frame.grid_columnconfigure(0, weight=1)
        candidate_list_frame.grid_rowconfigure(0, weight=1)
        self.candidate_list = Listbox(
            candidate_list_frame,
            bg=THEME["card"],
            fg=THEME["text"],
            selectbackground=THEME["blue"],
            selectforeground="#FFFFFF",
            highlightthickness=1,
            highlightbackground=THEME["focus_ring"],
            highlightcolor=THEME["focus_ring"],
            relief="flat",
        )
        self.candidate_list.grid(row=0, column=0, sticky="nsew")
        candidate_scroll = Scrollbar(candidate_list_frame, command=self.candidate_list.yview)
        self.candidate_scroll = candidate_scroll
        candidate_scroll.grid(row=0, column=1, sticky="ns")
        self.candidate_list.config(yscrollcommand=candidate_scroll.set)
        self.candidate_list.bind("<<ListboxSelect>>", self._on_candidate_selected)

        candidate_filter_row = Frame(candidate_box, bg=THEME["card"])
        self.candidate_filter_row = candidate_filter_row
        candidate_filter_row.grid(row=2, column=1, sticky="new", padx=SPACE_XS, pady=(SPACE_XS, SPACE_XS))
        candidate_filter_row.grid_columnconfigure(0, weight=1)
        self.candidate_search_label = Label(
            candidate_filter_row,
            bg=THEME["card"],
            fg=THEME["muted"],
            font=("Helvetica", 9, "bold"),
        )
        self.candidate_search_label.grid(row=0, column=0, sticky="w")
        self.candidate_search_entry = Entry(
            candidate_filter_row,
            bg=THEME["card"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
            highlightthickness=1,
            highlightbackground=THEME["focus_ring"],
            highlightcolor=THEME["focus_ring"],
            relief="flat",
        )
        self.candidate_search_entry.grid(row=1, column=0, sticky="ew", pady=(2, SPACE_XS))
        self.candidate_search_entry.bind("<KeyRelease>", self._on_candidate_filter_changed)
        self.candidate_category_label = Label(
            candidate_filter_row,
            bg=THEME["card"],
            fg=THEME["muted"],
            font=("Helvetica", 9, "bold"),
        )
        self.candidate_category_label.grid(row=2, column=0, sticky="w")
        self.candidate_category_label.grid_remove()
        self.candidate_category_key = "all"
        self.candidate_category_var = StringVar(value="")
        self.candidate_category_menu = OptionMenu(candidate_filter_row, self.candidate_category_var, "")
        self.candidate_category_menu.config(
            bg=THEME["button_bg"],
            fg=THEME["button_text"],
            activebackground=THEME["button_hover"],
            activeforeground=THEME["button_text"],
            highlightthickness=1,
            highlightbackground=THEME["button_border"],
            highlightcolor=THEME["button_border"],
            relief="flat",
        )
        self.candidate_category_menu.grid(row=2, column=0, sticky="ew", pady=(2, 0))

        self.candidate_detail_label = Label(
            candidate_box,
            bg=THEME["card"],
            fg=THEME["text"],
            font=("Helvetica", 10),
            justify="left",
            anchor="w",
            wraplength=SIDE_CONTROL_MIN_WIDTH - (SPACE_XS * 2),
        )
        self.candidate_detail_label.grid(
            row=5,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=SPACE_XS,
            pady=(0, SPACE_XS),
        )

        candidate_button_row = Frame(candidate_box, bg=THEME["card"])
        self.candidate_button_row = candidate_button_row
        candidate_button_row.grid(row=4, column=1, sticky="new", padx=SPACE_XS, pady=(SPACE_XS, SPACE_XS))
        candidate_button_row.grid_columnconfigure(0, weight=1)
        self.candidate_add_button = ActionButton(
            candidate_button_row,
            text="",
            command=self.add_selected_candidate,
            bg=THEME["button_bg"],
            fg=THEME["button_text"],
            hover_bg=THEME["button_hover"],
            active_bg=THEME["button_active"],
            border=THEME["button_border"],
        )
        self.candidate_add_button.config(wraplength=COMPACT_BUTTON_WRAP, justify="center")
        self.candidate_add_button.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_XS))
        self.candidate_add_all_button = ActionButton(
            candidate_button_row,
            text="",
            command=self.add_all_candidates,
            bg=THEME["button_bg"],
            fg=THEME["button_text"],
            hover_bg=THEME["button_hover"],
            active_bg=THEME["button_active"],
            border=THEME["button_border"],
        )
        self.candidate_add_all_button.config(wraplength=COMPACT_BUTTON_WRAP, justify="center")
        self.candidate_add_all_button.grid(row=1, column=0, sticky="ew", pady=(0, SPACE_XS))
        self.candidate_remove_all_button = ActionButton(
            candidate_button_row,
            text="",
            command=self.remove_all_candidates,
            bg=THEME["button_bg"],
            fg=THEME["button_text"],
            hover_bg=THEME["button_hover"],
            active_bg=THEME["button_active"],
            border=THEME["button_border"],
        )
        self.candidate_remove_all_button.config(wraplength=COMPACT_BUTTON_WRAP, justify="center")
        self.candidate_remove_all_button.grid(row=2, column=0, sticky="ew")

        blocked_box = Frame(
            left,
            bg=THEME["card"],
            highlightthickness=2,
            highlightbackground=THEME["green"],
            highlightcolor=THEME["green"],
        )
        self.blocked_box = blocked_box
        blocked_box.grid(row=0, column=0, sticky="nsew", padx=SPACE_MD, pady=(SPACE_MD, SPACE_XS))
        blocked_box.grid_columnconfigure(0, weight=1)
        blocked_box.grid_columnconfigure(1, weight=0, minsize=SIDE_CONTROL_MIN_WIDTH)
        blocked_box.grid_rowconfigure(2, weight=1)

        self.blocked_title_label = Label(
            blocked_box,
            bg=THEME["card"],
            fg=THEME["green"],
            font=("Helvetica", 13, "bold"),
        )
        self.blocked_title_label.grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            padx=SPACE_XS,
            pady=(SPACE_XS, 2),
        )
        self.blocked_desc_label = Label(
            blocked_box,
            bg=THEME["card"],
            fg=THEME["muted"],
            font=("Helvetica", 10),
            justify="left",
            anchor="w",
        )
        self.blocked_desc_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=SPACE_XS)

        list_frame = Frame(blocked_box, bg=THEME["card"])
        self.list_frame = list_frame
        list_frame.grid(row=2, column=0, rowspan=3, sticky="nsew", padx=SPACE_XS, pady=(SPACE_XS, SPACE_XS))
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)
        self.deny_list = Listbox(
            list_frame,
            bg=THEME["danger_bg"],
            fg=THEME["green"],
            selectbackground=THEME["green"],
            selectforeground="#ffffff",
            highlightthickness=1,
            highlightbackground=THEME["green"],
            highlightcolor=THEME["green"],
            relief="flat",
        )
        self.deny_list.grid(row=0, column=0, sticky="nsew")
        scroll = Scrollbar(list_frame, command=self.deny_list.yview)
        self.deny_scroll = scroll
        scroll.grid(row=0, column=1, sticky="ns")
        self.deny_list.config(yscrollcommand=scroll.set)

        button_row = Frame(blocked_box, bg=THEME["card"])
        self.blocked_button_row = button_row
        button_row.grid(row=2, column=1, sticky="new", padx=SPACE_XS, pady=(SPACE_XS, SPACE_XS))
        button_row.grid_columnconfigure(0, weight=1)
        button_row.grid_columnconfigure(1, weight=1)

        quick_add_box = Frame(
            button_row,
            bg=THEME["card"],
            highlightthickness=1,
            highlightbackground=THEME["panel_border"],
            highlightcolor=THEME["panel_border"],
        )
        self.quick_add_box = quick_add_box
        quick_add_box.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_XS))
        quick_add_box.grid_columnconfigure(0, weight=1)

        self.quick_add_title_label = Label(
            quick_add_box,
            bg=THEME["card"],
            fg=THEME["text"],
            font=("Helvetica", 10, "bold"),
            justify="left",
            anchor="w",
        )
        self.quick_add_title_label.grid(row=0, column=0, sticky="w", padx=SPACE_XS, pady=(SPACE_XS, 2))
        self.quick_add_hint_label = Label(
            quick_add_box,
            bg=THEME["card"],
            fg=THEME["muted"],
            font=("Helvetica", 9),
            justify="left",
            anchor="w",
            wraplength=SIDE_CONTROL_MIN_WIDTH - (SPACE_XS * 2),
        )
        self.quick_add_hint_label.grid(row=1, column=0, sticky="w", padx=SPACE_XS)
        self.quick_add_hint_label.grid_remove()
        self.quick_add_entry = Entry(
            quick_add_box,
            bg=THEME["card"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
            highlightthickness=1,
            highlightbackground=THEME["focus_ring"],
            highlightcolor=THEME["focus_ring"],
            relief="flat",
        )
        self.quick_add_entry.grid(row=2, column=0, sticky="ew", padx=SPACE_XS, pady=(SPACE_XS, SPACE_XS))
        self.quick_add_entry.bind("<Return>", self._on_quick_add_enter)

        quick_add_actions = Frame(quick_add_box, bg=THEME["card"])
        self.quick_add_actions = quick_add_actions
        quick_add_actions.grid(row=3, column=0, sticky="ew", padx=SPACE_XS, pady=(0, SPACE_XS))
        quick_add_actions.grid_columnconfigure(0, weight=1)
        quick_add_actions.grid_columnconfigure(1, weight=1)

        self.quick_add_button = ActionButton(
            quick_add_actions,
            text="",
            command=self.add_path,
            bg=THEME["accent"],
            fg=THEME["accent_text"],
            hover_bg=THEME["accent_hover"],
            active_bg=THEME["accent_active"],
            border=THEME["accent_hover"],
        )
        self.quick_add_button.config(wraplength=98, justify="center")
        self.quick_add_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.quick_add_pick_button = ActionButton(
            quick_add_actions,
            text="",
            command=self.pick_path_for_quick_add,
            bg=THEME["button_bg"],
            fg=THEME["button_text"],
            hover_bg=THEME["button_hover"],
            active_bg=THEME["button_active"],
            border=THEME["button_border"],
        )
        self.quick_add_pick_button.config(wraplength=98, justify="center")
        self.quick_add_pick_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.remove_button = ActionButton(
            button_row,
            text="",
            command=self.remove_selected,
            bg=THEME["button_bg"],
            fg=THEME["button_text"],
            hover_bg=THEME["button_hover"],
            active_bg=THEME["button_active"],
            border=THEME["button_border"],
        )
        self.remove_button.config(wraplength=120, justify="center")
        self.remove_button.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, SPACE_XS))
        self.clear_all_button = ActionButton(
            button_row,
            text="",
            command=self.clear_all_denies,
            bg=THEME["button_bg"],
            fg=THEME["button_text"],
            hover_bg=THEME["button_hover"],
            active_bg=THEME["button_active"],
            border=THEME["button_border"],
        )
        self.clear_all_button.config(wraplength=120, justify="center")
        self.clear_all_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, SPACE_XS))

        checker_box = Frame(
            blocked_box,
            bg=THEME["card"],
            highlightthickness=1,
            highlightbackground=THEME["panel_border"],
            highlightcolor=THEME["panel_border"],
        )
        self.checker_box = checker_box
        checker_box.grid(row=3, column=1, sticky="nsew", padx=SPACE_XS, pady=(0, SPACE_XS))
        checker_box.grid_columnconfigure(0, weight=1)
        self.check_title_label = Label(
            checker_box,
            bg=THEME["card"],
            fg=THEME["text"],
            font=("Helvetica", 11, "bold"),
        )
        self.check_title_label.grid(row=0, column=0, sticky="w", padx=SPACE_XS, pady=(SPACE_XS, 2))
        self.check_desc_label = Label(
            checker_box,
            bg=THEME["card"],
            fg=THEME["muted"],
            font=("Helvetica", 10),
            justify="left",
            anchor="w",
            wraplength=SIDE_CONTROL_MIN_WIDTH - (SPACE_XS * 2),
        )
        self.check_desc_label.grid(row=1, column=0, sticky="w", padx=SPACE_XS)
        self.check_desc_label.grid_remove()
        check_row = Frame(checker_box, bg=THEME["card"])
        self.check_row = check_row
        check_row.grid(row=2, column=0, sticky="ew", padx=SPACE_XS, pady=(SPACE_XS, SPACE_XS))
        check_row.grid_columnconfigure(0, weight=1)
        check_row.grid_columnconfigure(1, weight=0)
        self.path_check_entry = Entry(
            check_row,
            bg=THEME["card"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
            highlightthickness=1,
            highlightbackground=THEME["focus_ring"],
            highlightcolor=THEME["focus_ring"],
            relief="flat",
        )
        self.path_check_entry.grid(row=0, column=0, sticky="ew")
        self.check_button = ActionButton(
            check_row,
            text="",
            command=self.check_path_access,
            bg=THEME["button_bg"],
            fg=THEME["button_text"],
            hover_bg=THEME["button_hover"],
            active_bg=THEME["button_active"],
            border=THEME["button_border"],
        )
        self.check_button.grid(row=0, column=1, sticky="ew", padx=(SPACE_XS, 0))
        self.path_check_result = Label(
            checker_box,
            text="",
            bg=THEME["card"],
            fg=THEME["muted"],
            font=("Helvetica", 10, "bold"),
            justify="left",
            anchor="w",
            wraplength=SIDE_CONTROL_MIN_WIDTH - (SPACE_XS * 2),
        )
        self.path_check_result.grid(row=3, column=0, sticky="w", padx=SPACE_XS, pady=(0, SPACE_XS))

        right = Frame(
            top,
            bg=THEME["panel"],
            highlightthickness=1,
            highlightbackground=THEME["panel_border"],
            highlightcolor=THEME["panel_border"],
        )
        self.right_panel = right
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=0)

        controls = Frame(right, bg=THEME["panel"])
        self.controls_frame = controls
        controls.grid(row=0, column=0, sticky="nsew", padx=SPACE_MD, pady=(SPACE_MD, SPACE_XS))
        controls.grid_columnconfigure(0, weight=1)

        mechanism_box = Frame(
            controls,
            bg=THEME["card"],
            highlightthickness=1,
            highlightbackground=THEME["blue"],
            highlightcolor=THEME["blue"],
        )
        self.mechanism_box = mechanism_box
        mechanism_box.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_MD))
        mechanism_box.grid_columnconfigure(0, weight=1)
        self.mechanism_title_label = Label(
            mechanism_box,
            bg=THEME["card"],
            fg=THEME["teal"],
            font=("Helvetica", 11, "bold"),
        )
        self.mechanism_title_label.grid(row=0, column=0, sticky="w", padx=SPACE_XS, pady=(SPACE_XS, 2))
        self.mechanism_body_label = Label(
            mechanism_box,
            bg=THEME["card"],
            fg=THEME["text"],
            font=("Helvetica", 10),
            justify="left",
            anchor="w",
            wraplength=420,
        )
        self.mechanism_body_label.grid(row=1, column=0, sticky="w", padx=SPACE_XS)
        self.mechanism_note_label = Label(
            mechanism_box,
            bg=THEME["card"],
            fg=THEME["muted"],
            font=("Helvetica", 9, "bold"),
            justify="left",
            anchor="w",
            wraplength=420,
        )
        self.mechanism_note_label.grid(row=2, column=0, sticky="w", padx=SPACE_XS, pady=(SPACE_XS, SPACE_XS))
        self.mechanism_box.grid_remove()

        guide_box = Frame(
            controls,
            bg=THEME["card"],
            highlightthickness=1,
            highlightbackground=THEME["indigo"],
            highlightcolor=THEME["indigo"],
        )
        self.guide_box = guide_box
        guide_box.grid(row=1, column=0, sticky="ew", pady=(0, SPACE_MD))
        guide_box.grid_columnconfigure(0, weight=1)
        self.guide_title_label = Label(
            guide_box,
            bg=THEME["card"],
            fg=THEME["purple"],
            font=("Helvetica", 11, "bold"),
        )
        self.guide_title_label.grid(row=0, column=0, sticky="w", padx=SPACE_XS, pady=(SPACE_XS, 2))
        self.guide_body_label = Label(
            guide_box,
            bg=THEME["card"],
            fg=THEME["text"],
            font=("Helvetica", 10),
            justify="left",
            anchor="w",
            wraplength=420,
        )
        self.guide_body_label.grid(row=1, column=0, sticky="w", padx=SPACE_XS, pady=(0, SPACE_XS))
        self.guide_box.grid_remove()

        execution_box = Frame(
            controls,
            bg=THEME["card"],
            highlightthickness=2,
            highlightbackground=THEME["blue"],
            highlightcolor=THEME["blue"],
        )
        self.execution_box = execution_box
        execution_box.grid(row=2, column=0, sticky="ew", pady=(0, SPACE_MD))
        execution_box.grid_columnconfigure(0, weight=1)

        self.execution_title_label = Label(
            execution_box,
            bg=THEME["card"],
            fg=THEME["blue"],
            font=("Helvetica", 13, "bold"),
        )
        self.execution_title_label.grid(row=0, column=0, sticky="w", padx=SPACE_XS, pady=(SPACE_XS, 2))

        self.command_label = Label(
            execution_box,
            bg=THEME["card"],
            fg=THEME["text"],
            font=("Helvetica", 12, "bold"),
        )
        self.command_label.grid(row=1, column=0, sticky="w", padx=SPACE_XS)
        self.command_hint_label = Label(
            execution_box,
            bg=THEME["card"],
            fg=THEME["muted"],
            font=("Helvetica", 9),
        )
        self.command_hint_label.grid(row=2, column=0, sticky="w", padx=SPACE_XS, pady=(2, 0))
        self.command_entry = Entry(
            execution_box,
            bg=THEME["card"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
            highlightthickness=1,
            highlightbackground=THEME["focus_ring"],
            highlightcolor=THEME["focus_ring"],
            relief="flat",
        )
        self.command_entry.grid(row=3, column=0, sticky="ew", padx=SPACE_XS, pady=(3, SPACE_XS))

        self.cwd_label = Label(
            execution_box,
            bg=THEME["card"],
            fg=THEME["text"],
            font=("Helvetica", 12, "bold"),
        )
        self.cwd_label.grid(row=4, column=0, sticky="w", padx=SPACE_XS)
        self.cwd_hint_label = Label(
            execution_box,
            bg=THEME["card"],
            fg=THEME["muted"],
            font=("Helvetica", 9),
        )
        self.cwd_hint_label.grid(row=5, column=0, sticky="w", padx=SPACE_XS, pady=(2, 0))
        self.cwd_hint_label.grid_remove()
        cwd_row = Frame(execution_box, bg=THEME["card"])
        self.cwd_row = cwd_row
        cwd_row.grid(row=6, column=0, sticky="ew", padx=SPACE_XS, pady=(3, SPACE_XS))
        cwd_row.grid_columnconfigure(0, weight=1)
        self.cwd_entry = Entry(
            cwd_row,
            bg=THEME["card"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
            highlightthickness=1,
            highlightbackground=THEME["focus_ring"],
            highlightcolor=THEME["focus_ring"],
            relief="flat",
        )
        self.cwd_entry.insert(0, str(Path.cwd()))
        self.cwd_entry.grid(row=0, column=0, sticky="ew")
        self.cwd_pick_button = ActionButton(
            cwd_row,
            text="",
            command=self.pick_cwd,
            bg=THEME["button_bg"],
            fg=THEME["button_text"],
            hover_bg=THEME["button_hover"],
            active_bg=THEME["button_active"],
            border=THEME["button_border"],
        )
        self.cwd_pick_button.grid(row=0, column=1, padx=(SPACE_XS, 0))
        self.command_entry.bind("<KeyRelease>", self._on_target_input_change)
        self.cwd_entry.bind("<KeyRelease>", self._on_target_input_change)

        target_box = Frame(
            execution_box,
            bg=THEME["card"],
            highlightthickness=1,
            highlightbackground=THEME["teal"],
            highlightcolor=THEME["teal"],
        )
        self.target_box = target_box
        target_box.grid(row=7, column=0, sticky="ew", padx=SPACE_XS, pady=(0, SPACE_XS))
        target_box.grid_columnconfigure(0, weight=1)
        self.target_title_label = Label(
            target_box,
            bg=THEME["card"],
            fg=THEME["teal"],
            font=("Helvetica", 11, "bold"),
        )
        self.target_title_label.grid(row=0, column=0, sticky="w", padx=SPACE_XS, pady=(SPACE_XS, 2))
        self.target_body_label = Label(
            target_box,
            bg=THEME["card"],
            fg=THEME["text"],
            font=("Helvetica", 10),
            justify="left",
            anchor="w",
            wraplength=420,
        )
        self.target_body_label.grid(row=1, column=0, sticky="w", padx=SPACE_XS, pady=(0, SPACE_XS))
        self.target_box.grid_remove()

        self.run_action_button = ActionButton(
            execution_box,
            text="",
            command=self.run_action,
            bg=THEME["blue"],
            fg="#ffffff",
            hover_bg=THEME["indigo"],
            active_bg=THEME["blue"],
            border=THEME["blue"],
        )
        self.run_action_button.grid(row=11, column=0, sticky="ew", padx=SPACE_XS, pady=(0, SPACE_XS))

        self.timeline_title_label = Label(
            execution_box,
            bg=THEME["card"],
            fg=THEME["text"],
            font=("Helvetica", 11, "bold"),
            anchor="w",
            justify="left",
        )
        self.timeline_title_label.grid(row=12, column=0, sticky="w", padx=SPACE_XS)
        self.timeline_body_label = Label(
            execution_box,
            bg=THEME["card"],
            fg=THEME["muted"],
            font=("Helvetica", 9),
            justify="left",
            anchor="w",
            wraplength=420,
        )
        self.timeline_body_label.grid(row=13, column=0, sticky="w", padx=SPACE_XS, pady=(2, SPACE_XS))

        self.generated_command_label = Label(
            execution_box,
            bg=THEME["card"],
            fg=THEME["teal"],
            font=("Helvetica", 11, "bold"),
            anchor="w",
            justify="left",
        )
        self.generated_command_label.grid(row=14, column=0, sticky="w", padx=SPACE_XS)
        self.generated_command_hint_label = Label(
            execution_box,
            bg=THEME["card"],
            fg=THEME["muted"],
            font=("Helvetica", 9),
            justify="left",
            anchor="w",
        )
        self.generated_command_hint_label.grid(row=15, column=0, sticky="w", padx=SPACE_XS, pady=(2, 0))
        generated_row = Frame(execution_box, bg=THEME["card"])
        self.generated_row = generated_row
        generated_row.grid(row=16, column=0, sticky="ew", padx=SPACE_XS, pady=(3, SPACE_XS))
        generated_row.grid_columnconfigure(0, weight=1)
        self.generated_command_entry = Entry(
            generated_row,
            bg=THEME["card"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
            highlightthickness=1,
            highlightbackground=THEME["focus_ring"],
            highlightcolor=THEME["focus_ring"],
            relief="flat",
            state="readonly",
            readonlybackground=THEME["card"],
        )
        self.generated_command_entry.grid(row=0, column=0, sticky="ew")
        self.generated_copy_button = ActionButton(
            generated_row,
            text="",
            command=self._copy_generated_command,
            bg=THEME["button_bg"],
            fg=THEME["button_text"],
            hover_bg=THEME["button_hover"],
            active_bg=THEME["button_active"],
            border=THEME["button_border"],
        )
        self.generated_copy_button.grid(row=0, column=1, padx=(SPACE_XS, 0))

        output_wrap = Frame(right, bg=THEME["panel"])
        self.output_wrap = output_wrap
        output_wrap.grid(row=1, column=0, sticky="nsew", padx=SPACE_MD, pady=(SPACE_XS, SPACE_MD))
        output_wrap.grid_columnconfigure(0, weight=1)
        output_wrap.grid_rowconfigure(2, weight=1)

        output_header = Frame(output_wrap, bg=THEME["panel"])
        self.output_header = output_header
        output_header.grid(row=0, column=0, sticky="ew")
        output_header.grid_columnconfigure(0, weight=1)
        self.output_label = Label(
            output_header,
            bg=THEME["panel"],
            fg=THEME["text"],
            font=("Helvetica", 12, "bold"),
        )
        self.output_label.grid(row=0, column=0, sticky="w")
        self.output = Text(
            output_wrap,
            height=10,
            bg=THEME["output_bg"],
            fg=THEME["output_text"],
            insertbackground=THEME["output_text"],
            highlightthickness=1,
            highlightbackground=THEME["panel_border"],
            highlightcolor=THEME["panel_border"],
            relief="flat",
        )
        self.output.grid(row=2, column=0, sticky="nsew", pady=(SPACE_XS, 0))
        self.output.tag_configure("info", foreground=THEME["output_text"])
        self.output.tag_configure("warn", foreground=THEME["yellow"])
        self.output.tag_configure("block", foreground=THEME["red"])
        self.output.tag_configure("error", foreground=THEME["pink"])
        self.output.tag_configure("exec", foreground=THEME["green"])
        self.output_wrap.grid_remove()

    def _apply_texts(self) -> None:
        self.root.title(self._t("window_title"))
        self.app_title_label.config(text=self._t("app_title"))
        self.protection_banner.config(text=self._t("protection_off_banner"))
        self.language_label.config(text=self._t("language_label"))
        self.en_button.config(text=self._t("lang_en"))
        self.ja_button.config(text=self._t("lang_ja"))
        self.font_label.config(text=self._t("font_label"))
        self.font_smaller_button.config(text=self._t("font_smaller"))
        self.font_larger_button.config(text=self._t("font_larger"))
        self._apply_language_button_colors()

        self.blocked_title_label.config(text=self._t("blocked_title"))
        self.blocked_desc_label.config(text=self._t("blocked_desc"))
        self.quick_add_title_label.config(text=self._t("quick_add_title"))
        self.quick_add_hint_label.config(text=self._t("quick_add_hint"))
        self.quick_add_button.config(text=self._t("quick_add_button"))
        self.quick_add_pick_button.config(text=self._t("quick_add_pick_button"))
        self.remove_button.config(text=self._t("remove_button"))
        self.clear_all_button.config(text=self._t("clear_all_button"))
        self.candidate_title_label.config(text=self._t("candidate_title"))
        self.candidate_desc_label.config(text=self._t("candidate_desc"))
        self.candidate_search_label.config(text=self._t("candidate_search_label"))
        self.candidate_category_label.config(text=self._t("candidate_category_label"))
        self._rebuild_candidate_category_menu()
        self.candidate_add_button.config(text=self._t("candidate_add_button"))
        self.candidate_add_all_button.config(text=self._t("candidate_add_all_button"))
        self.candidate_remove_all_button.config(text=self._t("candidate_remove_all_button"))
        self._update_candidate_description()
        self.check_title_label.config(text=self._t("check_title"))
        self.check_desc_label.config(text=self._t("check_desc"))
        self.check_button.config(text=self._t("check_button"))
        self.mechanism_title_label.config(text=self._t("mechanism_title"))
        self.mechanism_body_label.config(text=self._t("mechanism_body"))
        self.mechanism_note_label.config(text=self._t("mechanism_note"))
        self.guide_title_label.config(text=self._t("guide_title"))
        self.guide_body_label.config(text=self._t("guide_body"))
        self.execution_title_label.config(text=self._t("execution_title"))
        self.command_label.config(text=self._t("command_label"))
        self.command_hint_label.config(text=self._t("command_hint"))
        self.cwd_label.config(text=self._t("cwd_label"))
        self.cwd_hint_label.config(text=self._t("cwd_hint"))
        self.cwd_pick_button.config(text=self._t("cwd_pick_button"))
        self.target_title_label.config(text=self._t("target_title"))
        self._update_target_preview()
        self._update_run_action_button_text()
        self.timeline_title_label.config(text=self._t("timeline_title"))
        self.timeline_body_label.config(text=self._t("timeline_body"))
        self.generated_command_label.config(text=self._t("generated_command_label"))
        self.generated_command_hint_label.config(text=self._t("generated_command_hint"))
        self.generated_copy_button.config(text=self._t("generated_command_copy_button"))
        if not self.command_generated:
            self._set_generated_command_text(self._t("generated_command_placeholder"))
        self.output_label.config(text=self._t("output_label"))
        self.policy_location_label.config(
            text=self._t("policy_location").format(policy=self.policy_path, audit=self.audit_log_path)
        )
        self._update_save_state_ui()
        self._update_protection_ui()

    def _apply_typography(self) -> None:
        self.app_title_label.config(font=("Helvetica", FONT_TITLE, "bold"))
        self.language_label.config(font=("Helvetica", FONT_META, "bold"))

        self.blocked_title_label.config(font=("Helvetica", FONT_SECTION, "bold"))
        self.blocked_desc_label.config(font=("Helvetica", FONT_BODY))
        self.quick_add_title_label.config(font=("Helvetica", FONT_BODY, "bold"))
        self.quick_add_hint_label.config(font=("Helvetica", FONT_META))
        self.candidate_title_label.config(font=("Helvetica", FONT_SECTION, "bold"))
        self.candidate_desc_label.config(font=("Helvetica", FONT_META))
        self.candidate_search_label.config(font=("Helvetica", FONT_META, "bold"))
        self.candidate_category_label.config(font=("Helvetica", FONT_META, "bold"))
        self.candidate_detail_label.config(font=("Helvetica", FONT_BODY))
        self.check_title_label.config(font=("Helvetica", FONT_BODY, "bold"))
        self.check_desc_label.config(font=("Helvetica", FONT_BODY))
        self.path_check_result.config(font=("Helvetica", FONT_BODY, "bold"))

        self.execution_title_label.config(font=("Helvetica", FONT_SECTION, "bold"))
        self.command_label.config(font=("Helvetica", FONT_SECTION, "bold"))
        self.command_hint_label.config(font=("Helvetica", FONT_META))
        self.cwd_label.config(font=("Helvetica", FONT_SECTION, "bold"))
        self.cwd_hint_label.config(font=("Helvetica", FONT_META))
        self.generated_command_label.config(font=("Helvetica", FONT_BODY, "bold"))
        self.generated_command_hint_label.config(font=("Helvetica", FONT_META))
        self.timeline_title_label.config(font=("Helvetica", FONT_BODY, "bold"))
        self.timeline_body_label.config(font=("Helvetica", FONT_META))
        self.target_title_label.config(font=("Helvetica", FONT_BODY, "bold"))
        self.target_body_label.config(font=("Helvetica", FONT_BODY))
        self.output_label.config(font=("Helvetica", FONT_SECTION, "bold"))
        self.policy_location_label.config(font=("Helvetica", FONT_META))
        self.deny_list.config(font=("Helvetica", FONT_BODY))
        self.candidate_list.config(font=("Helvetica", FONT_BODY))
        self.command_entry.config(font=("Helvetica", FONT_BODY))
        self.cwd_entry.config(font=("Helvetica", FONT_BODY))
        self.candidate_search_entry.config(font=("Helvetica", FONT_BODY))
        self.path_check_entry.config(font=("Helvetica", FONT_BODY))
        self.quick_add_entry.config(font=("Helvetica", FONT_BODY))
        self.generated_command_entry.config(font=("Helvetica", FONT_BODY))
        self.output.config(font=("Helvetica", FONT_BODY))

    def _category_for_candidate(self, candidate: dict[str, str]) -> str:
        path = candidate["path"].lower()
        if any(
            token in path
            for token in (
                "/etc",
                "/var/db",
                "/system",
                "launchdaemons",
                "systemconfiguration",
                "com.apple.tcc",
            )
        ):
            return "system"
        if any(token in path for token in ("chrome", "cookies", "login data", "safari", "firefox")):
            return "browser"
        if "history" in path:
            return "history"
        if any(token in path for token in ("kube", "gcloud", ".aws", ".azure", "docker")):
            return "cloud"
        if any(token in path for token in ("code/user", "globalstorage", ".vscode", ".idea")):
            return "dev"
        if any(
            token in path
            for token in (
                ".ssh",
                ".gnupg",
                "keychain",
                ".netrc",
                ".npmrc",
                "git-credentials",
                ".pypirc",
                "hosts.yml",
            )
        ):
            return "credentials"
        return "other"

    def _category_label(self, category_key: str) -> str:
        return self._t(f"category_{category_key}")

    def _rebuild_candidate_category_menu(self) -> None:
        menu = self.candidate_category_menu["menu"]
        menu.delete(0, "end")
        for key in CATEGORY_ORDER:
            label = self._category_label(key)
            menu.add_command(
                label=label,
                command=lambda selected=key: self._set_candidate_category(selected),
            )
        if self.candidate_category_key not in CATEGORY_ORDER:
            self.candidate_category_key = "all"
        self.candidate_category_var.set(self._category_label(self.candidate_category_key))

    def _set_candidate_category(self, category_key: str) -> None:
        self.candidate_category_key = category_key
        self.candidate_category_var.set(self._category_label(category_key))
        self._refresh_candidate_list()

    def _on_candidate_filter_changed(self, _event=None) -> None:
        self._refresh_candidate_list()

    def _update_save_state_ui(self) -> None:
        return

    def _mark_policy_dirty(self) -> None:
        self._save_policy()

    def _save_policy(self) -> None:
        save_policy(self.policy_path, self.policy)
        self._update_save_state_ui()
        self._append_output(self._t("log_autosaved").format(path=self.policy_path), level="info")

    def _capture_base_fonts(self) -> None:
        self._base_fonts = {}

        def walk(widget) -> None:
            try:
                current = widget.cget("font")
            except (AttributeError, TclError):
                current = None
            if current:
                font_obj = tkfont.Font(font=current)
                self._base_fonts[widget] = {
                    "family": font_obj.actual("family"),
                    "size": int(font_obj.actual("size")),
                    "weight": font_obj.actual("weight"),
                }
            for child in widget.winfo_children():
                walk(child)

        walk(self.root)

    def _apply_font_scale(self) -> None:
        for widget, meta in self._base_fonts.items():
            if not hasattr(widget, "winfo_exists") or not widget.winfo_exists():
                continue
            size = int(meta["size"])
            if size <= 0:
                continue
            scaled = max(8, int(round(size * self.font_scale)))
            try:
                widget.config(font=(meta["family"], scaled, meta["weight"]))
            except TclError:
                continue
        self._sync_wraplengths()

    def adjust_font_scale(self, delta: float) -> None:
        self.font_scale = min(1.6, max(0.8, round(self.font_scale + delta, 2)))
        self._apply_font_scale()
        self._apply_minimum_window_size_from_content()

    def _show_onboarding_if_needed(self) -> None:
        state: dict[str, object] = {}
        try:
            if ONBOARDING_STATE_PATH.exists():
                state = json.loads(ONBOARDING_STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}
        if state.get("onboarding_seen") is True:
            return
        self._show_info_dialog(self._t("onboarding_title"), self._t("onboarding_body"))
        try:
            ONBOARDING_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            ONBOARDING_STATE_PATH.write_text(
                json.dumps({"onboarding_seen": True}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            return

    def _show_info_dialog(self, title: str, body: str) -> None:
        messagebox.showinfo(title, body, parent=self.root)

    def _show_error_dialog(self, title: str, body: str) -> None:
        messagebox.showerror(title, body, parent=self.root)

    def _ask_yes_no_dialog(self, title: str, body: str) -> bool:
        return bool(messagebox.askyesno(title, body, parent=self.root))

    def _ask_directory_dialog(self, **kwargs) -> str:
        return str(filedialog.askdirectory(parent=self.root, **kwargs))

    def _ask_file_dialog(self, **kwargs) -> str:
        return str(filedialog.askopenfilename(parent=self.root, **kwargs))

    def pick_cwd(self) -> None:
        selected = self._ask_directory_dialog(initialdir=self.cwd_entry.get().strip() or str(Path.cwd()))
        if not selected:
            return
        self.cwd_entry.delete(0, END)
        self.cwd_entry.insert(0, selected)
        self._update_target_preview()

    def _update_run_action_button_text(self) -> None:
        self.run_action_button.config(text=self._t("run_action_button_execute"))

    def run_action(self) -> None:
        self._run_command(execute=True)

    def _on_resize(self, _event) -> None:
        self._enforce_window_mode()
        self._schedule_wrap_sync()

    def _disable_fullscreen_mode(self) -> None:
        self.root.bind("<F11>", lambda _event: "break")
        self.root.bind("<Control-Command-f>", lambda _event: "break")
        self.root.bind("<Command-Control-f>", lambda _event: "break")
        self.root.bind("<Alt-Return>", lambda _event: "break")
        self.root.bind("<Option-Return>", lambda _event: "break")
        self._enforce_window_mode()
        try:
            self.root.tk.call(
                "::tk::unsupported::MacWindowStyle",
                "style",
                self.root._w,
                "document",
                "closeBox collapseBox resizable inWindowMenu liveResize",
            )
        except TclError:
            return

    def _enforce_window_mode(self) -> None:
        try:
            state = self.root.attributes("-fullscreen")
            if str(state).lower() in {"1", "true"}:
                self.root.attributes("-fullscreen", False)
            if self.root.state() == "zoomed":
                self.root.state("normal")
        except TclError:
            return

    def _schedule_wrap_sync(self) -> None:
        if not hasattr(self, "root"):
            return
        if self._wrap_sync_after_id is not None:
            try:
                self.root.after_cancel(self._wrap_sync_after_id)
            except TclError:
                pass
            finally:
                self._wrap_sync_after_id = None
        try:
            self._wrap_sync_after_id = self.root.after(70, self._run_wrap_sync)
        except TclError:
            self._wrap_sync_after_id = None

    def _run_wrap_sync(self) -> None:
        self._wrap_sync_after_id = None
        self._sync_wraplengths()

    def _on_target_input_change(self, _event=None) -> None:
        self._invalidate_generated_command()
        self._update_target_preview()

    def _current_command_signature(self) -> tuple[str, str]:
        command = self.command_entry.get().strip()
        cwd = str(normalize_path(self.cwd_entry.get().strip() or str(Path.cwd())))
        return (command, cwd)

    def _set_generated_command_text(self, text: str) -> None:
        self.generated_command_entry.config(state="normal")
        self.generated_command_entry.delete(0, END)
        self.generated_command_entry.insert(0, text)
        self.generated_command_entry.config(state="readonly")

    def _invalidate_generated_command(self, force: bool = False) -> None:
        if not self.command_generated:
            return
        if not force and self._generated_signature == self._current_command_signature():
            return
        self.command_generated = False
        self._generated_signature = None
        self._set_generated_command_text(self._t("generated_command_placeholder"))
        self._apply_generated_command_visual_state()

    def _apply_generated_command_visual_state(self) -> None:
        if not hasattr(self, "generated_command_entry"):
            return
        enabled = self.policy.enabled
        if enabled:
            ready_entry_bg = THEME["card"]
            pending_entry_bg = THEME["panel_border"]
            ready_label_fg = THEME["text"]
            pending_label_fg = THEME["muted"]
            ready_generated_fg = THEME["teal"]
            pending_generated_fg = THEME["muted"]
            entry_fg = THEME["text"]
        else:
            ready_entry_bg = DISABLED["surface_alt"]
            pending_entry_bg = DISABLED["surface"]
            ready_label_fg = DISABLED["text"]
            pending_label_fg = DISABLED["muted"]
            ready_generated_fg = DISABLED["text"]
            pending_generated_fg = DISABLED["muted"]
            entry_fg = DISABLED["text"]

        if self.command_generated:
            self.command_label.config(fg=ready_label_fg)
            self.generated_command_label.config(fg=ready_generated_fg)
            self.command_entry.config(bg=ready_entry_bg, fg=entry_fg, insertbackground=entry_fg)
            self.generated_command_entry.config(
                fg=entry_fg,
                readonlybackground=ready_entry_bg,
                disabledforeground=entry_fg,
            )
            if enabled:
                self.generated_copy_button.set_colors(
                    bg=THEME["green"],
                    fg="#FFFFFF",
                    hover_bg=THEME["teal"],
                    active_bg=THEME["green"],
                    border=THEME["green"],
                )
            else:
                self.generated_copy_button.set_colors(
                    bg=DISABLED["button_bg"],
                    fg=DISABLED["button_text"],
                    hover_bg=DISABLED["button_hover"],
                    active_bg=DISABLED["button_active"],
                    border=DISABLED["border"],
                )
            return

        self.command_label.config(fg=pending_label_fg)
        self.generated_command_label.config(fg=pending_generated_fg)
        self.command_entry.config(bg=pending_entry_bg, fg=entry_fg, insertbackground=entry_fg)
        self.generated_command_entry.config(
            fg=entry_fg,
            readonlybackground=pending_entry_bg,
            disabledforeground=entry_fg,
        )
        if enabled:
            self.generated_copy_button.set_colors(
                bg=THEME["button_bg"],
                fg=THEME["button_text"],
                hover_bg=THEME["button_hover"],
                active_bg=THEME["button_active"],
                border=THEME["button_border"],
            )
        else:
            self.generated_copy_button.set_colors(
                bg=DISABLED["button_bg"],
                fg=DISABLED["button_text"],
                hover_bg=DISABLED["button_hover"],
                active_bg=DISABLED["button_active"],
                border=DISABLED["border"],
            )

    def _update_target_preview(self) -> None:
        command = self.command_entry.get().strip()
        cwd_value = self.cwd_entry.get().strip() or str(Path.cwd())
        cwd = str(normalize_path(cwd_value))
        if not command:
            self.target_body_label.config(text=self._t("target_empty"))
            return
        shell_line = f"cd {shlex.quote(cwd)} && {command.replace(chr(10), ' ')}"
        self.target_body_label.config(
            text=self._t("target_body").format(command=command, cwd=cwd, shell=shell_line),
        )

    def _sync_wraplengths(self) -> None:
        if not hasattr(self, "controls_frame"):
            return
        try:
            right_width = self.controls_frame.winfo_width()
            if right_width > 0:
                right_wrap = max(right_width - (SPACE_XS * 4), 240)
                self.mechanism_body_label.config(wraplength=right_wrap)
                self.mechanism_note_label.config(wraplength=right_wrap)
                self.guide_body_label.config(wraplength=right_wrap)
                self.target_body_label.config(wraplength=right_wrap)
                self.timeline_body_label.config(wraplength=right_wrap)

            left_width = self.left_panel.winfo_width()
            if left_width > 0:
                left_wrap = max(left_width - (SPACE_XS * 4), 220)
                self.blocked_desc_label.config(wraplength=left_wrap)
                self.candidate_desc_label.config(wraplength=left_wrap)
                candidate_box_width = self.candidate_box.winfo_width()
                candidate_wrap = max(candidate_box_width - (SPACE_XS * 4), 260)
                self.candidate_detail_label.config(wraplength=candidate_wrap)
                checker_width = self.checker_box.winfo_width()
                checker_wrap = max(checker_width - (SPACE_XS * 2), 180)
                self.check_desc_label.config(wraplength=checker_wrap)
                self.path_check_result.config(wraplength=checker_wrap)
                self.quick_add_hint_label.config(wraplength=checker_wrap)
        except TclError:
            return

    def _apply_language_button_colors(self) -> None:
        if not self.policy.enabled:
            self.ja_button.set_colors(
                bg=DISABLED["button_bg"],
                fg=DISABLED["button_text"],
                hover_bg=DISABLED["button_hover"],
                active_bg=DISABLED["button_active"],
                border=DISABLED["border"],
            )
            self.en_button.set_colors(
                bg=DISABLED["button_bg"],
                fg=DISABLED["button_text"],
                hover_bg=DISABLED["button_hover"],
                active_bg=DISABLED["button_active"],
                border=DISABLED["border"],
            )
            self.font_smaller_button.set_colors(
                bg=DISABLED["button_bg"],
                fg=DISABLED["button_text"],
                hover_bg=DISABLED["button_hover"],
                active_bg=DISABLED["button_active"],
                border=DISABLED["border"],
            )
            self.font_larger_button.set_colors(
                bg=DISABLED["button_bg"],
                fg=DISABLED["button_text"],
                hover_bg=DISABLED["button_hover"],
                active_bg=DISABLED["button_active"],
                border=DISABLED["border"],
            )
            return

        if self.language == "ja":
            self.ja_button.set_colors(
                bg=THEME["accent"],
                fg=THEME["accent_text"],
                hover_bg=THEME["accent_hover"],
                active_bg=THEME["accent_active"],
                border=THEME["accent_hover"],
            )
            self.en_button.set_colors(
                bg=THEME["button_bg"],
                fg=THEME["button_text"],
                hover_bg=THEME["button_hover"],
                active_bg=THEME["button_active"],
                border=THEME["button_border"],
            )
            self.font_smaller_button.set_colors(
                bg=THEME["button_bg"],
                fg=THEME["button_text"],
                hover_bg=THEME["button_hover"],
                active_bg=THEME["button_active"],
                border=THEME["button_border"],
            )
            self.font_larger_button.set_colors(
                bg=THEME["button_bg"],
                fg=THEME["button_text"],
                hover_bg=THEME["button_hover"],
                active_bg=THEME["button_active"],
                border=THEME["button_border"],
            )
            return

        self.ja_button.set_colors(
            bg=THEME["button_bg"],
            fg=THEME["button_text"],
            hover_bg=THEME["button_hover"],
            active_bg=THEME["button_active"],
            border=THEME["button_border"],
        )
        self.en_button.set_colors(
            bg=THEME["accent"],
            fg=THEME["accent_text"],
            hover_bg=THEME["accent_hover"],
            active_bg=THEME["accent_active"],
            border=THEME["accent_hover"],
        )
        self.font_smaller_button.set_colors(
            bg=THEME["button_bg"],
            fg=THEME["button_text"],
            hover_bg=THEME["button_hover"],
            active_bg=THEME["button_active"],
            border=THEME["button_border"],
        )
        self.font_larger_button.set_colors(
            bg=THEME["button_bg"],
            fg=THEME["button_text"],
            hover_bg=THEME["button_hover"],
            active_bg=THEME["button_active"],
            border=THEME["button_border"],
        )

    def _apply_protection_visual_state(self) -> None:
        if self.policy.enabled:
            self.font_label.config(bg=THEME["bg"], fg=THEME["muted"])
            self.policy_location_label.config(bg=THEME["bg"], fg=THEME["muted"])
            self.protection_banner.config(bg=THEME["red"], fg="#FFFFFF")

            self.left_panel.config(
                bg=THEME["panel"],
                highlightbackground=THEME["panel_border"],
                highlightcolor=THEME["panel_border"],
            )
            self.right_panel.config(
                bg=THEME["panel"],
                highlightbackground=THEME["panel_border"],
                highlightcolor=THEME["panel_border"],
            )
            self.blocked_box.config(
                bg=THEME["card"],
                highlightbackground=THEME["green"],
                highlightcolor=THEME["green"],
            )
            self.list_frame.config(bg=THEME["card"])
            self.blocked_button_row.config(bg=THEME["card"])
            self.quick_add_box.config(
                bg=THEME["card"],
                highlightbackground=THEME["panel_border"],
                highlightcolor=THEME["panel_border"],
            )
            self.quick_add_actions.config(bg=THEME["card"])
            self.candidate_box.config(
                bg=THEME["card"],
                highlightbackground=THEME["panel_border"],
                highlightcolor=THEME["panel_border"],
            )
            self.candidate_filter_row.config(bg=THEME["card"])
            self.candidate_list_frame.config(bg=THEME["card"])
            self.candidate_button_row.config(bg=THEME["card"])
            self.checker_box.config(
                bg=THEME["card"],
                highlightbackground=THEME["panel_border"],
                highlightcolor=THEME["panel_border"],
            )
            self.check_row.config(bg=THEME["card"])
            self.mechanism_box.config(
                bg=THEME["card"],
                highlightbackground=THEME["blue"],
                highlightcolor=THEME["blue"],
            )
            self.guide_box.config(
                bg=THEME["card"],
                highlightbackground=THEME["indigo"],
                highlightcolor=THEME["indigo"],
            )
            self.execution_box.config(
                bg=THEME["card"],
                highlightbackground=THEME["blue"],
                highlightcolor=THEME["blue"],
            )
            self.cwd_row.config(bg=THEME["card"])
            self.target_box.config(
                bg=THEME["card"],
                highlightbackground=THEME["teal"],
                highlightcolor=THEME["teal"],
            )
            self.output_wrap.config(bg=THEME["panel"])
            self.output_header.config(bg=THEME["panel"])
            self.generated_row.config(bg=THEME["card"])

            self.blocked_title_label.config(bg=THEME["card"], fg=THEME["green"])
            self.blocked_desc_label.config(bg=THEME["card"], fg=THEME["muted"])
            self.quick_add_title_label.config(bg=THEME["card"], fg=THEME["text"])
            self.quick_add_hint_label.config(bg=THEME["card"], fg=THEME["muted"])
            self.candidate_title_label.config(bg=THEME["card"], fg=THEME["teal"])
            self.candidate_desc_label.config(bg=THEME["card"], fg=THEME["muted"])
            self.candidate_search_label.config(bg=THEME["card"], fg=THEME["muted"])
            self.candidate_category_label.config(bg=THEME["card"], fg=THEME["muted"])
            self.candidate_detail_label.config(bg=THEME["card"], fg=THEME["text"])
            self.check_title_label.config(bg=THEME["card"], fg=THEME["text"])
            self.check_desc_label.config(bg=THEME["card"], fg=THEME["muted"])
            self.path_check_result.config(bg=THEME["card"], fg=THEME["muted"])

            self.mechanism_title_label.config(bg=THEME["card"], fg=THEME["teal"])
            self.mechanism_body_label.config(bg=THEME["card"], fg=THEME["text"])
            self.mechanism_note_label.config(bg=THEME["card"], fg=THEME["muted"])
            self.guide_title_label.config(bg=THEME["card"], fg=THEME["purple"])
            self.guide_body_label.config(bg=THEME["card"], fg=THEME["text"])
            self.execution_title_label.config(bg=THEME["card"], fg=THEME["blue"])
            self.generated_command_label.config(bg=THEME["card"], fg=THEME["teal"])
            self.generated_command_hint_label.config(bg=THEME["card"], fg=THEME["muted"])
            self.timeline_title_label.config(bg=THEME["card"], fg=THEME["text"])
            self.timeline_body_label.config(bg=THEME["card"], fg=THEME["muted"])
            self.target_title_label.config(bg=THEME["card"], fg=THEME["teal"])
            self.target_body_label.config(bg=THEME["card"], fg=THEME["text"])

            self.command_label.config(bg=THEME["card"], fg=THEME["text"])
            self.command_hint_label.config(bg=THEME["card"], fg=THEME["muted"])
            self.cwd_label.config(bg=THEME["card"], fg=THEME["text"])
            self.cwd_hint_label.config(bg=THEME["card"], fg=THEME["muted"])
            self.generated_command_entry.config(
                bg=THEME["card"],
                fg=THEME["text"],
                insertbackground=THEME["text"],
                highlightbackground=THEME["focus_ring"],
                highlightcolor=THEME["focus_ring"],
            )
            self.output_label.config(bg=THEME["panel"], fg=THEME["text"])

            self.command_entry.config(
                bg=THEME["card"],
                fg=THEME["text"],
                insertbackground=THEME["text"],
                highlightbackground=THEME["focus_ring"],
                highlightcolor=THEME["focus_ring"],
            )
            self.cwd_entry.config(
                bg=THEME["card"],
                fg=THEME["text"],
                insertbackground=THEME["text"],
                highlightbackground=THEME["focus_ring"],
                highlightcolor=THEME["focus_ring"],
            )
            self.candidate_search_entry.config(
                bg=THEME["card"],
                fg=THEME["text"],
                insertbackground=THEME["text"],
                highlightbackground=THEME["focus_ring"],
                highlightcolor=THEME["focus_ring"],
            )
            self.path_check_entry.config(
                bg=THEME["card"],
                fg=THEME["text"],
                insertbackground=THEME["text"],
                highlightbackground=THEME["focus_ring"],
                highlightcolor=THEME["focus_ring"],
            )
            self.quick_add_entry.config(
                bg=THEME["card"],
                fg=THEME["text"],
                insertbackground=THEME["text"],
                highlightbackground=THEME["focus_ring"],
                highlightcolor=THEME["focus_ring"],
            )
            self.candidate_category_menu.config(
                bg=THEME["button_bg"],
                fg=THEME["button_text"],
                activebackground=THEME["button_hover"],
                activeforeground=THEME["button_text"],
                highlightbackground=THEME["button_border"],
                highlightcolor=THEME["button_border"],
            )

            self.deny_list.config(
                bg=THEME["danger_bg"],
                fg=THEME["green"],
                selectbackground=THEME["green"],
                selectforeground="#FFFFFF",
                highlightbackground=THEME["green"],
                highlightcolor=THEME["green"],
            )
            self.candidate_list.config(
                bg=THEME["card"],
                fg=THEME["text"],
                selectbackground=THEME["blue"],
                selectforeground="#FFFFFF",
                highlightbackground=THEME["focus_ring"],
                highlightcolor=THEME["focus_ring"],
            )
            self.output.config(
                bg=THEME["output_bg"],
                fg=THEME["output_text"],
                insertbackground=THEME["output_text"],
                highlightbackground=THEME["panel_border"],
                highlightcolor=THEME["panel_border"],
            )

            self.quick_add_button.set_colors(
                bg=THEME["accent"],
                fg=THEME["accent_text"],
                hover_bg=THEME["accent_hover"],
                active_bg=THEME["accent_active"],
                border=THEME["accent_hover"],
            )
            self.quick_add_pick_button.set_colors(
                bg=THEME["button_bg"],
                fg=THEME["button_text"],
                hover_bg=THEME["button_hover"],
                active_bg=THEME["button_active"],
                border=THEME["button_border"],
            )
            self.remove_button.set_colors(
                bg=THEME["button_bg"],
                fg=THEME["button_text"],
                hover_bg=THEME["button_hover"],
                active_bg=THEME["button_active"],
                border=THEME["button_border"],
            )
            self.clear_all_button.set_colors(
                bg=THEME["button_bg"],
                fg=THEME["button_text"],
                hover_bg=THEME["button_hover"],
                active_bg=THEME["button_active"],
                border=THEME["button_border"],
            )
            self.candidate_add_button.set_colors(
                bg=THEME["button_bg"],
                fg=THEME["button_text"],
                hover_bg=THEME["button_hover"],
                active_bg=THEME["button_active"],
                border=THEME["button_border"],
            )
            self.candidate_add_all_button.set_colors(
                bg=THEME["button_bg"],
                fg=THEME["button_text"],
                hover_bg=THEME["button_hover"],
                active_bg=THEME["button_active"],
                border=THEME["button_border"],
            )
            self.candidate_remove_all_button.set_colors(
                bg=THEME["button_bg"],
                fg=THEME["button_text"],
                hover_bg=THEME["button_hover"],
                active_bg=THEME["button_active"],
                border=THEME["button_border"],
            )
            self.cwd_pick_button.set_colors(
                bg=THEME["button_bg"],
                fg=THEME["button_text"],
                hover_bg=THEME["button_hover"],
                active_bg=THEME["button_active"],
                border=THEME["button_border"],
            )
            self.check_button.set_colors(
                bg=THEME["button_bg"],
                fg=THEME["button_text"],
                hover_bg=THEME["button_hover"],
                active_bg=THEME["button_active"],
                border=THEME["button_border"],
            )
            self.run_action_button.set_colors(
                bg=THEME["blue"],
                fg="#FFFFFF",
                hover_bg=THEME["indigo"],
                active_bg=THEME["blue"],
                border=THEME["blue"],
            )
            self.generated_copy_button.set_colors(
                bg=THEME["button_bg"],
                fg=THEME["button_text"],
                hover_bg=THEME["button_hover"],
                active_bg=THEME["button_active"],
                border=THEME["button_border"],
            )
            self._apply_generated_command_visual_state()
            return

        self.font_label.config(bg=THEME["bg"], fg=DISABLED["muted"])
        self.policy_location_label.config(bg=THEME["bg"], fg=DISABLED["muted"])
        self.protection_banner.config(bg=DISABLED["surface_alt"], fg=DISABLED["text"])

        self.left_panel.config(
            bg=DISABLED["surface"],
            highlightbackground=DISABLED["border"],
            highlightcolor=DISABLED["border"],
        )
        self.right_panel.config(
            bg=DISABLED["surface"],
            highlightbackground=DISABLED["border"],
            highlightcolor=DISABLED["border"],
        )
        self.blocked_box.config(
            bg=DISABLED["surface_alt"],
            highlightbackground=DISABLED["list_border"],
            highlightcolor=DISABLED["list_border"],
        )
        self.list_frame.config(bg=DISABLED["surface_alt"])
        self.blocked_button_row.config(bg=DISABLED["surface_alt"])
        self.quick_add_box.config(
            bg=DISABLED["surface_alt"],
            highlightbackground=DISABLED["border"],
            highlightcolor=DISABLED["border"],
        )
        self.quick_add_actions.config(bg=DISABLED["surface_alt"])
        self.candidate_box.config(
            bg=DISABLED["surface_alt"],
            highlightbackground=DISABLED["border"],
            highlightcolor=DISABLED["border"],
        )
        self.candidate_filter_row.config(bg=DISABLED["surface_alt"])
        self.candidate_list_frame.config(bg=DISABLED["surface_alt"])
        self.candidate_button_row.config(bg=DISABLED["surface_alt"])
        self.checker_box.config(
            bg=DISABLED["surface_alt"],
            highlightbackground=DISABLED["border"],
            highlightcolor=DISABLED["border"],
        )
        self.check_row.config(bg=DISABLED["surface_alt"])
        self.mechanism_box.config(
            bg=DISABLED["surface_alt"],
            highlightbackground=DISABLED["border"],
            highlightcolor=DISABLED["border"],
        )
        self.guide_box.config(
            bg=DISABLED["surface_alt"],
            highlightbackground=DISABLED["border"],
            highlightcolor=DISABLED["border"],
        )
        self.execution_box.config(
            bg=DISABLED["surface_alt"],
            highlightbackground=DISABLED["border"],
            highlightcolor=DISABLED["border"],
        )
        self.cwd_row.config(bg=DISABLED["surface_alt"])
        self.target_box.config(
            bg=DISABLED["surface_alt"],
            highlightbackground=DISABLED["border"],
            highlightcolor=DISABLED["border"],
        )
        self.output_wrap.config(bg=DISABLED["surface"])
        self.output_header.config(bg=DISABLED["surface"])
        self.generated_row.config(bg=DISABLED["surface_alt"])

        self.blocked_title_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["text"])
        self.blocked_desc_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["muted"])
        self.quick_add_title_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["text"])
        self.quick_add_hint_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["muted"])
        self.candidate_title_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["text"])
        self.candidate_desc_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["muted"])
        self.candidate_search_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["muted"])
        self.candidate_category_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["muted"])
        self.candidate_detail_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["text"])
        self.check_title_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["text"])
        self.check_desc_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["muted"])
        self.path_check_result.config(bg=DISABLED["surface_alt"], fg=DISABLED["muted"])

        self.mechanism_title_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["text"])
        self.mechanism_body_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["muted"])
        self.mechanism_note_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["muted"])
        self.guide_title_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["text"])
        self.guide_body_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["muted"])
        self.execution_title_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["text"])
        self.generated_command_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["text"])
        self.generated_command_hint_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["muted"])
        self.timeline_title_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["text"])
        self.timeline_body_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["muted"])
        self.target_title_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["text"])
        self.target_body_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["muted"])

        self.command_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["text"])
        self.command_hint_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["muted"])
        self.cwd_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["text"])
        self.cwd_hint_label.config(bg=DISABLED["surface_alt"], fg=DISABLED["muted"])
        self.generated_command_entry.config(
            bg=DISABLED["surface_alt"],
            fg=DISABLED["text"],
            insertbackground=DISABLED["text"],
            highlightbackground=DISABLED["border"],
            highlightcolor=DISABLED["border"],
        )
        self.output_label.config(bg=DISABLED["surface"], fg=DISABLED["text"])

        self.command_entry.config(
            bg=DISABLED["surface_alt"],
            fg=DISABLED["text"],
            insertbackground=DISABLED["text"],
            highlightbackground=DISABLED["border"],
            highlightcolor=DISABLED["border"],
        )
        self.cwd_entry.config(
            bg=DISABLED["surface_alt"],
            fg=DISABLED["text"],
            insertbackground=DISABLED["text"],
            highlightbackground=DISABLED["border"],
            highlightcolor=DISABLED["border"],
        )
        self.candidate_search_entry.config(
            bg=DISABLED["surface_alt"],
            fg=DISABLED["text"],
            insertbackground=DISABLED["text"],
            highlightbackground=DISABLED["border"],
            highlightcolor=DISABLED["border"],
        )
        self.path_check_entry.config(
            bg=DISABLED["surface_alt"],
            fg=DISABLED["text"],
            insertbackground=DISABLED["text"],
            highlightbackground=DISABLED["border"],
            highlightcolor=DISABLED["border"],
        )
        self.quick_add_entry.config(
            bg=DISABLED["surface_alt"],
            fg=DISABLED["text"],
            insertbackground=DISABLED["text"],
            highlightbackground=DISABLED["border"],
            highlightcolor=DISABLED["border"],
        )
        self.candidate_category_menu.config(
            bg=DISABLED["button_bg"],
            fg=DISABLED["button_text"],
            activebackground=DISABLED["button_hover"],
            activeforeground=DISABLED["button_text"],
            highlightbackground=DISABLED["border"],
            highlightcolor=DISABLED["border"],
        )

        self.deny_list.config(
            bg=DISABLED["list_bg"],
            fg=DISABLED["list_text"],
            selectbackground=DISABLED["surface_alt"],
            selectforeground=DISABLED["text"],
            highlightbackground=DISABLED["list_border"],
            highlightcolor=DISABLED["list_border"],
        )
        self.candidate_list.config(
            bg=DISABLED["list_bg"],
            fg=DISABLED["list_text"],
            selectbackground=DISABLED["surface_alt"],
            selectforeground=DISABLED["text"],
            highlightbackground=DISABLED["list_border"],
            highlightcolor=DISABLED["list_border"],
        )
        self.output.config(
            bg=DISABLED["surface_alt"],
            fg=DISABLED["text"],
            insertbackground=DISABLED["text"],
            highlightbackground=DISABLED["border"],
            highlightcolor=DISABLED["border"],
        )

        self.quick_add_button.set_colors(
            bg=DISABLED["button_bg"],
            fg=DISABLED["button_text"],
            hover_bg=DISABLED["button_hover"],
            active_bg=DISABLED["button_active"],
            border=DISABLED["border"],
        )
        self.quick_add_pick_button.set_colors(
            bg=DISABLED["button_bg"],
            fg=DISABLED["button_text"],
            hover_bg=DISABLED["button_hover"],
            active_bg=DISABLED["button_active"],
            border=DISABLED["border"],
        )
        self.remove_button.set_colors(
            bg=DISABLED["button_bg"],
            fg=DISABLED["button_text"],
            hover_bg=DISABLED["button_hover"],
            active_bg=DISABLED["button_active"],
            border=DISABLED["border"],
        )
        self.clear_all_button.set_colors(
            bg=DISABLED["button_bg"],
            fg=DISABLED["button_text"],
            hover_bg=DISABLED["button_hover"],
            active_bg=DISABLED["button_active"],
            border=DISABLED["border"],
        )
        self.candidate_add_button.set_colors(
            bg=DISABLED["button_bg"],
            fg=DISABLED["button_text"],
            hover_bg=DISABLED["button_hover"],
            active_bg=DISABLED["button_active"],
            border=DISABLED["border"],
        )
        self.candidate_add_all_button.set_colors(
            bg=DISABLED["button_bg"],
            fg=DISABLED["button_text"],
            hover_bg=DISABLED["button_hover"],
            active_bg=DISABLED["button_active"],
            border=DISABLED["border"],
        )
        self.candidate_remove_all_button.set_colors(
            bg=DISABLED["button_bg"],
            fg=DISABLED["button_text"],
            hover_bg=DISABLED["button_hover"],
            active_bg=DISABLED["button_active"],
            border=DISABLED["border"],
        )
        self.cwd_pick_button.set_colors(
            bg=DISABLED["button_bg"],
            fg=DISABLED["button_text"],
            hover_bg=DISABLED["button_hover"],
            active_bg=DISABLED["button_active"],
            border=DISABLED["border"],
        )
        self.check_button.set_colors(
            bg=DISABLED["button_bg"],
            fg=DISABLED["button_text"],
            hover_bg=DISABLED["button_hover"],
            active_bg=DISABLED["button_active"],
            border=DISABLED["border"],
        )
        self.run_action_button.set_colors(
            bg=DISABLED["button_bg"],
            fg=DISABLED["button_text"],
            hover_bg=DISABLED["button_hover"],
            active_bg=DISABLED["button_active"],
            border=DISABLED["border"],
        )
        self.generated_copy_button.set_colors(
            bg=DISABLED["button_bg"],
            fg=DISABLED["button_text"],
            hover_bg=DISABLED["button_hover"],
            active_bg=DISABLED["button_active"],
            border=DISABLED["border"],
        )
        self._apply_generated_command_visual_state()

    def _update_protection_ui(self) -> None:
        if not self.policy.enabled:
            self.policy = Policy(enabled=True, deny_paths=self.policy.deny_paths)
            save_policy(self.policy_path, self.policy)
        self._apply_protection_visual_state()
        self._apply_language_button_colors()
        self.protection_banner.grid_remove()
        self._update_save_state_ui()

    def set_language(self, language: str) -> None:
        if language not in TEXTS:
            return
        self.language = language
        self._apply_texts()
        self._refresh_deny_list()
        self._sync_wraplengths()
        self._apply_minimum_window_size_from_content()
        if self.path_check_entry.get().strip():
            self.check_path_access()

    def _apply_minimum_window_size_from_content(self) -> None:
        if self._fixed_window_size:
            return
        try:
            if not hasattr(self, "root") or not self.root.winfo_exists():
                return
            self.root.update_idletasks()
            min_w, min_h = resolve_min_window_size(
                base_min_w=self._base_min_width,
                base_min_h=self._base_min_height,
                req_w=max(self.root.winfo_reqwidth(), 1),
                req_h=max(self.root.winfo_reqheight(), 1),
                screen_w=self.root.winfo_screenwidth(),
                screen_h=self.root.winfo_screenheight(),
                padding=SPACE_MD * 2,
            )
            self.root.minsize(min_w, min_h)

            cur_w = max(self.root.winfo_width(), 1)
            cur_h = max(self.root.winfo_height(), 1)
            if cur_w >= min_w and cur_h >= min_h:
                return
            new_w = max(cur_w, min_w)
            new_h = max(cur_h, min_h)
            self.root.geometry(f"{new_w}x{new_h}")
        except TclError:
            return

    def _candidate_by_path(self, path_text: str) -> dict | None:
        for candidate in CANDIDATE_PATHS:
            if candidate["path"] == path_text:
                return candidate
        return None

    def _selected_candidate(self) -> dict | None:
        selected = self.candidate_list.curselection()
        if not selected:
            return None
        index = selected[0]
        if index >= len(self._candidate_paths_view):
            return None
        path_text = self._candidate_paths_view[index]
        return self._candidate_by_path(path_text)

    def _update_candidate_description(self) -> None:
        candidate = self._selected_candidate()
        if not candidate:
            self.candidate_detail_label.config(text=self._t("candidate_empty"))
            return
        reason = candidate.get(self.language) or candidate["en"]
        category = self._category_label(self._category_for_candidate(candidate))
        resolved = str(normalize_path(candidate["path"]))
        existing = set(str(path) for path in self.policy.deny_paths)
        status = (
            self._t("candidate_status_added")
            if resolved in existing
            else self._t("candidate_status_pending")
        )
        self.candidate_detail_label.config(
            text=self._t("candidate_detail").format(
                path=candidate["path"],
                category=category,
                status=status,
                resolved=resolved,
                reason=reason,
            )
        )

    def _on_candidate_selected(self, _event=None) -> None:
        self._update_candidate_description()

    def _refresh_candidate_list(self) -> None:
        previous_path = None
        selected = self.candidate_list.curselection()
        if selected:
            index = selected[0]
            if index < len(self._candidate_paths_view):
                previous_path = self._candidate_paths_view[index]

        self.candidate_list.delete(0, END)
        self._candidate_paths_view = []
        existing = set(str(path) for path in self.policy.deny_paths)
        search_query = self.candidate_search_entry.get().strip().lower()
        category_filter = self.candidate_category_key
        for candidate in CANDIDATE_PATHS:
            path_text = candidate["path"]
            category_key = self._category_for_candidate(candidate)
            category_label = self._category_label(category_key)
            reason = (candidate.get(self.language) or candidate["en"]).lower()
            if category_filter != "all" and category_key != category_filter:
                continue
            if search_query:
                haystack = f"{path_text.lower()} {category_label.lower()} {reason}"
                if search_query not in haystack:
                    continue
            resolved = str(normalize_path(path_text))
            is_added = resolved in existing
            status = (
                self._t("candidate_status_added")
                if is_added
                else self._t("candidate_status_pending")
            )
            self.candidate_list.insert(
                END,
                self._t("candidate_item").format(status=status, path=path_text),
            )
            index = self.candidate_list.size() - 1
            if self.policy.enabled:
                color = THEME["green"] if is_added else THEME["muted"]
            else:
                color = DISABLED["list_text"]
            self.candidate_list.itemconfig(index, fg=color)
            self._candidate_paths_view.append(path_text)

        if not self._candidate_paths_view:
            self._update_candidate_description()
            return

        target_index = 0
        if previous_path is not None:
            for idx, path in enumerate(self._candidate_paths_view):
                if path == previous_path:
                    target_index = idx
                    break

        self.candidate_list.selection_clear(0, END)
        self.candidate_list.selection_set(target_index)
        self.candidate_list.activate(target_index)
        self.candidate_list.see(target_index)
        self._update_candidate_description()

    def _select_deny_path(self, target_path: str) -> None:
        self.deny_list.selection_clear(0, END)
        for idx in range(self.deny_list.size()):
            if self.deny_list.get(idx) == target_path:
                self.deny_list.selection_set(idx)
                self.deny_list.activate(idx)
                self.deny_list.see(idx)
                return

    def _candidate_normalized_paths(self) -> list[str]:
        normalized: list[str] = []
        for candidate in CANDIDATE_PATHS:
            normalized.append(str(normalize_path(candidate["path"])))
        return normalized

    def _visible_candidate_normalized_paths(self) -> list[str]:
        normalized: list[str] = []
        for path_text in self._candidate_paths_view:
            normalized.append(str(normalize_path(path_text)))
        return normalized

    def _refresh_deny_list(self) -> None:
        self.deny_list.delete(0, END)
        deny_paths = sorted(str(path) for path in self.policy.deny_paths)
        for deny in deny_paths:
            self.deny_list.insert(END, deny)
        self._invalidate_generated_command(force=True)
        self._update_save_state_ui()
        self._refresh_candidate_list()

    def _on_quick_add_enter(self, _event=None) -> None:
        self.add_path()

    def pick_path_for_quick_add(self) -> None:
        selected = self._ask_directory_dialog(title=self._t("quick_add_pick_button"))
        if not selected:
            selected = self._ask_file_dialog(title=self._t("quick_add_pick_button"))
        if not selected:
            return
        self.quick_add_entry.delete(0, END)
        self.quick_add_entry.insert(0, selected)
        self.quick_add_entry.focus_set()

    def add_path(self) -> None:
        raw = self.quick_add_entry.get().strip()
        if not raw:
            self._append_output(self._t("quick_add_empty"), level="warn")
            self.quick_add_entry.focus_set()
            return
        normalized = str(normalize_path(raw))
        existing = set(str(path) for path in self.policy.deny_paths)
        existing.add(normalized)
        self.policy = Policy.from_dict(
            {
                "enabled": self.policy.enabled,
                "deny_paths": sorted(existing),
            }
        )
        self._refresh_deny_list()
        self._mark_policy_dirty()
        self.quick_add_entry.delete(0, END)

    def add_selected_candidate(self) -> None:
        candidate = self._selected_candidate()
        if not candidate:
            self._append_output(self._t("candidate_empty"), level="warn")
            return

        normalized = str(normalize_path(candidate["path"]))
        existing = set(str(path) for path in self.policy.deny_paths)
        if normalized in existing:
            self._append_output(self._t("log_candidate_exists").format(path=normalized), level="warn")
            self._select_deny_path(normalized)
            self._refresh_candidate_list()
            return

        existing.add(normalized)
        self.policy = Policy.from_dict(
            {
                "enabled": self.policy.enabled,
                "deny_paths": sorted(existing),
            }
        )
        self._refresh_deny_list()
        self._select_deny_path(normalized)
        self._mark_policy_dirty()
        self._append_output(self._t("log_candidate_added").format(path=normalized), level="info")

    def add_all_candidates(self) -> None:
        existing = set(str(path) for path in self.policy.deny_paths)
        pending: list[str] = []
        for candidate_path in self._visible_candidate_normalized_paths():
            if candidate_path not in existing:
                pending.append(candidate_path)

        if not pending:
            self._append_output(self._t("log_candidates_add_nothing"), level="warn")
            self._refresh_candidate_list()
            return
        approved = self._ask_yes_no_dialog(
            self._t("candidate_confirm_add_all_title"),
            self._t("candidate_confirm_add_all_body").format(count=len(pending)),
        )
        if not approved:
            self._append_output(self._t("log_canceled"), level="warn")
            return

        existing.update(pending)
        self.policy = Policy.from_dict(
            {
                "enabled": self.policy.enabled,
                "deny_paths": sorted(existing),
            }
        )
        self._refresh_deny_list()
        self._select_deny_path(pending[0])
        self._mark_policy_dirty()
        self._append_output(self._t("log_candidates_added_all").format(count=len(pending)), level="info")

    def remove_all_candidates(self) -> None:
        current = [str(path) for path in self.policy.deny_paths]
        candidate_paths = set(self._candidate_normalized_paths())
        remaining = [path for path in current if path not in candidate_paths]
        removed_count = len(current) - len(remaining)

        if removed_count == 0:
            self._append_output(self._t("log_candidates_remove_nothing"), level="warn")
            self._refresh_candidate_list()
            return
        approved = self._ask_yes_no_dialog(
            self._t("candidate_confirm_remove_all_title"),
            self._t("candidate_confirm_remove_all_body").format(count=removed_count),
        )
        if not approved:
            self._append_output(self._t("log_canceled"), level="warn")
            return

        self.policy = Policy.from_dict(
            {
                "enabled": self.policy.enabled,
                "deny_paths": sorted(remaining),
            }
        )
        self._refresh_deny_list()
        self._mark_policy_dirty()
        self._append_output(self._t("log_candidates_removed_all").format(count=removed_count), level="info")

    def clear_all_denies(self) -> None:
        current = [str(path) for path in self.policy.deny_paths]
        if not current:
            self._append_output(self._t("log_clear_all_nothing"), level="warn")
            return

        approved = self._ask_yes_no_dialog(
            self._t("clear_all_confirm_title"),
            self._t("clear_all_confirm_body").format(count=len(current)),
        )
        if not approved:
            self._append_output(self._t("log_canceled"), level="warn")
            return

        self.policy = Policy.from_dict(
            {
                "enabled": self.policy.enabled,
                "deny_paths": [],
            }
        )
        self._refresh_deny_list()
        self._mark_policy_dirty()
        self._append_output(self._t("log_clear_all_done").format(count=len(current)), level="info")

    def remove_selected(self) -> None:
        selected = self.deny_list.curselection()
        if not selected:
            return
        target = self.deny_list.get(selected[0])
        remaining = [str(path) for path in self.policy.deny_paths if str(path) != target]
        self.policy = Policy.from_dict(
            {
                "enabled": self.policy.enabled,
                "deny_paths": sorted(remaining),
            }
        )
        self._refresh_deny_list()
        self._mark_policy_dirty()

    def _matching_deny_path(self, path: Path) -> Path | None:
        for deny in self.policy.deny_paths:
            if is_subpath(path, deny):
                return deny
        return None

    def _show_generated_command(self, command_line: str) -> None:
        self._set_generated_command_text(command_line)
        self.command_generated = True
        self._generated_signature = self._current_command_signature()
        self._apply_generated_command_visual_state()
        self.generated_command_entry.selection_range(0, END)
        self.generated_command_entry.focus_set()

    def _copy_to_clipboard(self, text: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update_idletasks()

    def _copy_generated_command(self) -> None:
        text = self.generated_command_entry.get().strip()
        if not text or text == self._t("generated_command_placeholder"):
            return
        self._copy_to_clipboard(text)

    def check_path_access(self) -> None:
        raw = self.path_check_entry.get().strip()
        if not raw:
            self.path_check_result.config(text=self._t("check_empty"), fg=THEME["muted"])
            return
        cwd = normalize_path(self.cwd_entry.get().strip() or str(Path.cwd()))
        normalized = normalize_path(raw, base_dir=cwd)
        matched = self._matching_deny_path(normalized)
        if matched is not None:
            self.path_check_result.config(
                text=self._t("check_match").format(path=normalized, deny=matched),
                fg=THEME["red"],
            )
            self._select_deny_path(str(matched))
            return
        self.path_check_result.config(
            text=self._t("check_no_match").format(path=normalized),
            fg=THEME["green"],
        )

    def _reason_message(self, reason: str, fallback: str) -> str:
        key = f"reason_{reason}"
        if key in TEXTS[self.language]:
            return self._t(key)
        return fallback

    def _reason_label(self, reason: str) -> str:
        key = f"reason_label_{reason}"
        if key in TEXTS[self.language]:
            return self._t(key)
        return reason

    def _reason_level(self, reason: str) -> str:
        if reason == "executed":
            return "exec"
        if reason == "executed_external_terminal":
            return "exec"
        if reason in {"blocked_by_policy"}:
            return "block"
        if reason in {"command_not_found", "timeout", "invalid_request", "external_terminal_failed"}:
            return "error"
        if reason in {"test_mode_block"}:
            return "warn"
        return "info"

    def _run_command(self, execute: bool) -> None:
        cmd_text = self.command_entry.get().strip()
        if not cmd_text:
            self._show_error_dialog(self._t("error_title"), self._t("error_command_required"))
            return

        cwd = normalize_path(self.cwd_entry.get().strip() or str(Path.cwd()))
        if not cwd.exists():
            self._append_output(self._t("error_invalid_cwd").format(path=cwd), level="error")
            return
        if not cwd.is_dir():
            self._append_output(self._t("error_cwd_not_directory").format(path=cwd), level="error")
            return
        try:
            command = shlex.split(cmd_text)
        except ValueError as exc:
            self._append_output(self._t("error_parse_command").format(message=str(exc)), level="error")
            return

        if execute:
            if not self.policy.enabled:
                self.policy = Policy(enabled=True, deny_paths=self.policy.deny_paths)
                save_policy(self.policy_path, self.policy)
            preflight_request = RunRequest(
                command=command,
                cwd=cwd,
                execute=False,
                timeout_sec=None,
            )
            preflight = self.runner.run(preflight_request, self.policy)
            if preflight.reason == "blocked_by_policy":
                write_audit_log(
                    self.audit_log_path,
                    {
                        "timestamp": iso_utc_now(),
                        "command": command,
                        "command_text": shlex.join(command),
                        "cwd": str(cwd),
                        "executed": preflight.executed,
                        "reason": preflight.reason,
                        "exit_code": preflight.exit_code,
                        "blocked_paths": list(preflight.blocked_paths),
                    },
                )
                localized = self._reason_message(preflight.reason, preflight.message)
                self._append_output(
                    self._t("log_result").format(reason=self._reason_label(preflight.reason), message=localized),
                    level=self._reason_level(preflight.reason),
                )
                for blocked in preflight.blocked_paths:
                    self._append_output(self._t("log_blocked_path").format(path=blocked), level="block")
                return

            shell_line = build_launcher_command_line(
                policy_path=self.policy_path,
                audit_log_path=self.audit_log_path,
                cwd=cwd,
                command=command,
            )
            write_audit_log(
                self.audit_log_path,
                {
                    "timestamp": iso_utc_now(),
                    "command": command,
                    "command_text": shlex.join(command),
                    "cwd": str(cwd),
                    "executed": False,
                    "reason": "manual_command_generated",
                    "exit_code": 0,
                    "blocked_paths": [],
                },
            )
            message = self._t("log_manual_command").format(command=shell_line)
            self._append_output(message, level="info")
            self._show_generated_command(shell_line)
            return

        request = RunRequest(
            command=command,
            cwd=cwd,
            execute=execute,
            timeout_sec=None,
        )
        result = self.runner.run(request, self.policy)

        write_audit_log(
            self.audit_log_path,
            {
                "timestamp": iso_utc_now(),
                "command": command,
                "command_text": shlex.join(command),
                "cwd": str(cwd),
                "executed": result.executed,
                "reason": result.reason,
                "exit_code": result.exit_code,
                "blocked_paths": list(result.blocked_paths),
            },
        )

        localized = self._reason_message(result.reason, result.message)
        self._append_output(
            self._t("log_result").format(reason=self._reason_label(result.reason), message=localized),
            level=self._reason_level(result.reason),
        )
        if result.blocked_paths:
            for blocked in result.blocked_paths:
                self._append_output(self._t("log_blocked_path").format(path=blocked), level="block")
        if result.stdout:
            self._append_output(result.stdout.rstrip("\n"), level="exec")
        if result.stderr:
            self._append_output(result.stderr.rstrip("\n"), level="error")

    def _render_output_logs(self) -> None:
        if not self._log_records:
            self.output.delete("1.0", END)
            return
        level, text = self._log_records[-1]
        self.output.delete("1.0", END)
        self.output.insert(END, text + "\n", level)
        self.output.see(END)

    def _append_output(self, text: str, level: str = "info") -> None:
        self._log_records.append((level, text))
        if len(self._log_records) > MAX_UI_LOG_RECORDS:
            self._log_records = self._log_records[-MAX_UI_LOG_RECORDS:]
        self._render_output_logs()

    def run(self) -> None:
        self.root.mainloop()


def launch_gui(policy_path: Path, audit_log_path: Path) -> None:
    window = AgentLockerWindow(policy_path, audit_log_path)
    window.run()
