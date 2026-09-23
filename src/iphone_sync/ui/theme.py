"""Modern colorful macOS theme and UI styles for iPhone Sync.

Supports 4 selectable visual palettes:
1. Apple Dark Obsidian (Default)
2. Midnight Slate & Deep Navy
3. macOS Cupertino Light
4. Titanium & Warm Amber
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Assets
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
CHECKMARK_PATH = str(ASSETS_DIR / "checkmark.svg").replace("\\", "/")


@dataclass(frozen=True)
class ThemePalette:
    id: str
    display_name: str
    description: str
    bg: str
    card_bg: str
    card_border: str
    card_hover: str
    text_primary: str
    text_secondary: str
    text_muted: str
    blue_accent: str
    green_accent: str
    purple_accent: str
    orange_accent: str
    coral_accent: str
    red_accent: str
    cyan_accent: str
    menu_bg: str
    menu_selected_bg: str
    statusbar_bg: str
    button_bg: str
    button_border: str
    button_hover_bg: str
    input_bg: str
    input_border: str
    log_bg: str
    log_text: str
    tooltip_bg: str
    tooltip_text: str
    scrollbar_handle: str
    scrollbar_handle_hover: str
    is_dark: bool = True


THEMES: dict[str, ThemePalette] = {
    "obsidian_dark": ThemePalette(
        id="obsidian_dark",
        display_name="Apple Dark Obsidian",
        description="Deep OLED obsidian background with luminous Apple accent glows",
        bg="#121316",
        card_bg="#1a1d24",
        card_border="rgba(255, 255, 255, 0.08)",
        card_hover="#20242e",
        text_primary="#FFFFFF",
        text_secondary="#9898A0",
        text_muted="#636366",
        blue_accent="#0A84FF",
        green_accent="#30D158",
        purple_accent="#BF5AF2",
        orange_accent="#FF9F0A",
        coral_accent="#FF375F",
        red_accent="#FF453A",
        cyan_accent="#64D2FF",
        menu_bg="#1c1f26",
        menu_selected_bg="#0A84FF",
        statusbar_bg="#15171d",
        button_bg="rgba(255, 255, 255, 0.08)",
        button_border="rgba(255, 255, 255, 0.12)",
        button_hover_bg="rgba(255, 255, 255, 0.14)",
        input_bg="rgba(255, 255, 255, 0.07)",
        input_border="rgba(255, 255, 255, 0.12)",
        log_bg="#0d0f13",
        log_text="#D1D5DB",
        tooltip_bg="#242833",
        tooltip_text="#FFFFFF",
        scrollbar_handle="rgba(255, 255, 255, 0.22)",
        scrollbar_handle_hover="rgba(255, 255, 255, 0.38)",
        is_dark=True,
    ),
    "midnight_navy": ThemePalette(
        id="midnight_navy",
        display_name="Midnight Slate & Deep Navy",
        description="Studio dark mode inspired by Xcode & Final Cut Pro",
        bg="#0D1424",
        card_bg="#152036",
        card_border="rgba(64, 130, 240, 0.16)",
        card_hover="#1c2b47",
        text_primary="#F0F4FC",
        text_secondary="#8E9EB8",
        text_muted="#52637D",
        blue_accent="#2F81F7",
        green_accent="#38D9A9",
        purple_accent="#6366F1",
        orange_accent="#F59E0B",
        coral_accent="#F43F5E",
        red_accent="#EF4444",
        cyan_accent="#38BDF8",
        menu_bg="#152238",
        menu_selected_bg="#2F81F7",
        statusbar_bg="#0A101C",
        button_bg="rgba(47, 129, 247, 0.12)",
        button_border="rgba(47, 129, 247, 0.25)",
        button_hover_bg="rgba(47, 129, 247, 0.22)",
        input_bg="rgba(255, 255, 255, 0.06)",
        input_border="rgba(47, 129, 247, 0.28)",
        log_bg="#080c17",
        log_text="#CBD5E1",
        tooltip_bg="#1c2b47",
        tooltip_text="#F0F4FC",
        scrollbar_handle="rgba(56, 189, 248, 0.25)",
        scrollbar_handle_hover="rgba(56, 189, 248, 0.45)",
        is_dark=True,
    ),
    "cupertino_light": ThemePalette(
        id="cupertino_light",
        display_name="macOS Cupertino Light",
        description="Clean, daylight interface matching native macOS Finder & System Settings",
        bg="#F5F5F7",
        card_bg="#FFFFFF",
        card_border="rgba(0, 0, 0, 0.08)",
        card_hover="#F0F0F3",
        text_primary="#1D1D1F",
        text_secondary="#6E6E73",
        text_muted="#86868B",
        blue_accent="#007AFF",
        green_accent="#34C759",
        purple_accent="#AF52DE",
        orange_accent="#FF9500",
        coral_accent="#FF2D55",
        red_accent="#FF3B30",
        cyan_accent="#32ADE6",
        menu_bg="#FFFFFF",
        menu_selected_bg="#007AFF",
        statusbar_bg="#EBEBED",
        button_bg="rgba(0, 0, 0, 0.05)",
        button_border="rgba(0, 0, 0, 0.12)",
        button_hover_bg="rgba(0, 0, 0, 0.09)",
        input_bg="#FFFFFF",
        input_border="rgba(0, 0, 0, 0.15)",
        log_bg="#FAFAFA",
        log_text="#1D1D1F",
        tooltip_bg="#333336",
        tooltip_text="#FFFFFF",
        scrollbar_handle="rgba(0, 0, 0, 0.22)",
        scrollbar_handle_hover="rgba(0, 0, 0, 0.38)",
        is_dark=False,
    ),
    "titanium_amber": ThemePalette(
        id="titanium_amber",
        display_name="Titanium & Warm Amber",
        description="Natural Titanium and warm amber highlights inspired by Apple Watch Ultra",
        bg="#1E1E1E",
        card_bg="#2A2826",
        card_border="rgba(255, 159, 10, 0.16)",
        card_hover="#35322E",
        text_primary="#F5F5F7",
        text_secondary="#A8A29E",
        text_muted="#78716C",
        blue_accent="#FF6B00",
        green_accent="#EAB308",
        purple_accent="#F97316",
        orange_accent="#FF9F0A",
        coral_accent="#F43F5E",
        red_accent="#EF4444",
        cyan_accent="#FBBF24",
        menu_bg="#282624",
        menu_selected_bg="#FF9F0A",
        statusbar_bg="#191817",
        button_bg="rgba(255, 159, 10, 0.12)",
        button_border="rgba(255, 159, 10, 0.26)",
        button_hover_bg="rgba(255, 159, 10, 0.22)",
        input_bg="rgba(255, 255, 255, 0.06)",
        input_border="rgba(255, 159, 10, 0.30)",
        log_bg="#161514",
        log_text="#E7E5E4",
        tooltip_bg="#383430",
        tooltip_text="#F5F5F7",
        scrollbar_handle="rgba(255, 159, 10, 0.25)",
        scrollbar_handle_hover="rgba(255, 159, 10, 0.45)",
        is_dark=True,
    ),
}

# Backward compatibility defaults (pointing to Obsidian Dark)
_DEFAULT_PALETTE = THEMES["obsidian_dark"]
COLOR_BG = _DEFAULT_PALETTE.bg
COLOR_CARD_BG = _DEFAULT_PALETTE.card_bg
COLOR_CARD_BORDER = _DEFAULT_PALETTE.card_border
COLOR_CARD_HOVER = _DEFAULT_PALETTE.card_hover

BLUE_ACCENT = _DEFAULT_PALETTE.blue_accent
GREEN_ACCENT = _DEFAULT_PALETTE.green_accent
PURPLE_ACCENT = _DEFAULT_PALETTE.purple_accent
ORANGE_ACCENT = _DEFAULT_PALETTE.orange_accent
CORAL_ACCENT = _DEFAULT_PALETTE.coral_accent
RED_ACCENT = _DEFAULT_PALETTE.red_accent
CYAN_ACCENT = _DEFAULT_PALETTE.cyan_accent

TEXT_PRIMARY = _DEFAULT_PALETTE.text_primary
TEXT_SECONDARY = _DEFAULT_PALETTE.text_secondary
TEXT_MUTED = _DEFAULT_PALETTE.text_muted


def get_theme(theme_id: str | None = None) -> ThemePalette:
    """Return the ThemePalette for the requested id, defaulting to obsidian_dark."""
    if not theme_id or theme_id not in THEMES:
        return THEMES["obsidian_dark"]
    return THEMES[theme_id]


def list_themes() -> list[tuple[str, str, str]]:
    """Return a list of (id, display_name, description) tuples."""
    return [(t.id, t.display_name, t.description) for t in THEMES.values()]


def generate_stylesheet(p: ThemePalette) -> str:
    """Generate dynamic Qt stylesheet for the given ThemePalette."""
    header_action_text = p.text_primary if p.is_dark else "#1D1D1F"

    return f"""
QMainWindow {{
    background-color: {p.bg};
}}

QWidget {{
    font-family: ".AppleSystemUIFont", "Helvetica Neue", Arial, sans-serif;
    color: {p.text_primary};
    font-size: 13px;
}}

/* Typography roles */
QLabel[heading="true"] {{
    color: {p.text_primary};
    font-size: 13px;
    font-weight: 700;
}}

QLabel[subheading="true"] {{
    color: {p.text_secondary};
    font-size: 11px;
}}

QLabel[muted="true"] {{
    color: {p.text_muted};
    font-size: 11px;
}}

/* Scroll Area */
QScrollArea {{
    border: none;
    background-color: transparent;
}}
QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}

/* Scrollbars */
QScrollBar:vertical {{
    border: none;
    background: transparent;
    width: 7px;
    margin: 4px 0 4px 0;
}}
QScrollBar::handle:vertical {{
    background: {p.scrollbar_handle};
    min-height: 28px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: {p.scrollbar_handle_hover};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    border: none;
    background: none;
    height: 0px;
}}
QScrollBar:horizontal {{
    border: none;
    background: transparent;
    height: 7px;
    margin: 0 4px 0 4px;
}}
QScrollBar::handle:horizontal {{
    background: {p.scrollbar_handle};
    min-width: 28px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {p.scrollbar_handle_hover};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    border: none;
    background: none;
    width: 0px;
}}

/* Cards (QFrame with card="true") */
QFrame[card="true"] {{
    background-color: {p.card_bg};
    border: 1px solid {p.card_border};
    border-radius: 10px;
}}
QFrame[card="true"]:hover {{
    background-color: {p.card_hover};
}}

/* Menu Bar */
QMenuBar {{
    background-color: {p.bg};
    color: {p.text_primary};
    border-bottom: 1px solid {p.card_border};
    padding: 2px 6px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 5px 10px;
    border-radius: 5px;
}}
QMenuBar::item:selected {{
    background: {p.button_hover_bg};
}}
QMenu {{
    background-color: {p.menu_bg};
    border: 1px solid {p.card_border};
    border-radius: 8px;
    padding: 5px;
    color: {p.text_primary};
}}
QMenu::item {{
    padding: 6px 20px 6px 12px;
    border-radius: 5px;
}}
QMenu::item:selected {{
    background-color: {p.menu_selected_bg};
    color: #FFFFFF;
}}
QMenu::separator {{
    height: 1px;
    background: {p.card_border};
    margin: 4px 6px;
}}

/* Status Bar */
QStatusBar {{
    background-color: {p.statusbar_bg};
    color: {p.text_secondary};
    border-top: 1px solid {p.card_border};
    font-size: 11px;
    padding: 2px 8px;
}}
QStatusBar QLabel {{
    color: {p.text_secondary};
    font-size: 11px;
}}

/* Default Buttons */
QPushButton {{
    background-color: {p.button_bg};
    color: {p.text_primary};
    border: 1px solid {p.button_border};
    border-radius: 6px;
    padding: 5px 12px;
    font-weight: 500;
    font-size: 12px;
}}
QPushButton:hover {{
    background-color: {p.button_hover_bg};
}}
QPushButton:pressed {{
    background-color: {p.button_bg};
}}
QPushButton:disabled {{
    background-color: {p.button_bg};
    color: {p.text_muted};
    border-color: {p.card_border};
}}
QPushButton::menu-indicator {{
    image: none;
    width: 0px;
}}

/* Vibrant Primary Action Buttons */
QPushButton[btnStyle="primary-blue"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {p.blue_accent}, stop:1 {p.cyan_accent});
    color: #FFFFFF;
    font-weight: 600;
    font-size: 12px;
    border: 1px solid rgba(255, 255, 255, 0.25);
    border-radius: 6px;
    padding: 6px 14px;
}}
QPushButton[btnStyle="primary-blue"]:hover {{
    opacity: 0.9;
    border-color: rgba(255, 255, 255, 0.4);
}}
QPushButton[btnStyle="primary-blue"]:disabled {{
    background: {p.button_bg};
    color: {p.text_muted};
    border: 1px solid {p.card_border};
}}

QPushButton[btnStyle="primary-green"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {p.cyan_accent}, stop:1 {p.green_accent});
    color: {"#05260f" if p.is_dark else "#FFFFFF"};
    font-weight: 700;
    font-size: 12px;
    border: 1px solid rgba(255, 255, 255, 0.25);
    border-radius: 6px;
    padding: 6px 14px;
}}
QPushButton[btnStyle="primary-green"]:hover {{
    opacity: 0.9;
    border-color: rgba(255, 255, 255, 0.4);
}}
QPushButton[btnStyle="primary-green"]:disabled {{
    background: {p.button_bg};
    color: {p.text_muted};
    border: 1px solid {p.card_border};
}}

QPushButton[btnStyle="primary-purple"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {p.purple_accent}, stop:1 {p.blue_accent});
    color: #FFFFFF;
    font-weight: 600;
    font-size: 12px;
    border: 1px solid rgba(255, 255, 255, 0.25);
    border-radius: 6px;
    padding: 6px 14px;
}}
QPushButton[btnStyle="primary-purple"]:hover {{
    opacity: 0.9;
    border-color: rgba(255, 255, 255, 0.4);
}}
QPushButton[btnStyle="primary-purple"]:disabled {{
    background: {p.button_bg};
    color: {p.text_muted};
    border: 1px solid {p.card_border};
}}

QPushButton[btnStyle="danger"] {{
    background-color: rgba(255, 69, 58, 0.12);
    color: {p.red_accent};
    border: 1px solid rgba(255, 69, 58, 0.25);
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 11px;
}}
QPushButton[btnStyle="danger"]:hover {{
    background-color: rgba(255, 69, 58, 0.22);
    border-color: rgba(255, 69, 58, 0.45);
}}
QPushButton[btnStyle="danger"]:disabled {{
    background-color: {p.button_bg};
    color: {p.text_muted};
    border-color: {p.card_border};
}}

QPushButton[btnStyle="header-action"] {{
    background-color: {p.button_bg};
    color: {header_action_text};
    border: 1px solid {p.button_border};
    border-radius: 6px;
    padding: 5px 11px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton[btnStyle="header-action"]:hover {{
    background-color: {p.button_hover_bg};
}}

/* Progress Bars */
QProgressBar {{
    background-color: {p.button_bg};
    border: 1px solid {p.card_border};
    border-radius: 3px;
    text-align: center;
    color: transparent;
    max-height: 5px;
    min-height: 5px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p.cyan_accent}, stop:1 {p.blue_accent});
    border-radius: 2px;
}}

QProgressBar[barStyle="green"]::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p.cyan_accent}, stop:1 {p.green_accent});
}}

QProgressBar[barStyle="purple"]::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p.purple_accent}, stop:1 {p.blue_accent});
}}

QProgressBar[barStyle="coral"]::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p.coral_accent}, stop:1 {p.orange_accent});
}}

QProgressBar[barStyle="blue"]::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p.cyan_accent}, stop:1 {p.blue_accent});
}}

/* Input Fields & Combos */
QLineEdit {{
    background-color: {p.input_bg};
    border: 1px solid {p.input_border};
    border-radius: 8px;
    padding: 7px 12px;
    color: {p.text_primary};
    selection-background-color: {p.blue_accent};
}}
QLineEdit:focus {{
    border: 1px solid {p.blue_accent};
}}

QComboBox {{
    background-color: {p.input_bg};
    border: 1px solid {p.input_border};
    border-radius: 6px;
    padding: 5px 10px;
    color: {p.text_primary};
    font-size: 12px;
}}
QComboBox:hover {{
    border-color: {p.blue_accent};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {p.menu_bg};
    color: {p.text_primary};
    border: 1px solid {p.card_border};
    selection-background-color: {p.blue_accent};
    selection-color: #FFFFFF;
}}

/* Checkboxes */
QCheckBox {{
    color: {p.text_primary};
    spacing: 9px;
    font-size: 13px;
}}
QCheckBox::indicator {{
    width: 17px;
    height: 17px;
    border-radius: 5px;
    border: 1px solid {p.button_border};
    background-color: {p.input_bg};
}}
QCheckBox::indicator:hover {{
    border-color: {p.blue_accent};
}}
QCheckBox::indicator:checked {{
    background-color: {p.blue_accent};
    border-color: {p.blue_accent};
    image: url("{CHECKMARK_PATH}");
}}

/* List Widgets */
QListWidget {{
    background-color: {p.card_bg};
    border: 1px solid {p.card_border};
    border-radius: 8px;
    padding: 6px;
    color: {p.text_primary};
}}
QListWidget::item {{
    border-radius: 6px;
    padding: 8px 10px;
    margin: 2px 0;
}}
QListWidget::item:selected {{
    background: {p.button_hover_bg};
    border: 1px solid {p.blue_accent};
    color: {p.text_primary};
}}

/* Dialogs */
QDialog {{
    background-color: {p.bg};
    color: {p.text_primary};
}}

/* Log Area */
QTextEdit {{
    background-color: {p.log_bg};
    border: 1px solid {p.card_border};
    border-radius: 10px;
    padding: 10px;
    color: {p.log_text};
    font-family: Menlo, Monaco, Consolas, "Courier New", monospace;
    font-size: 12px;
    line-height: 1.4;
}}

/* Tooltip */
QToolTip {{
    background-color: {p.tooltip_bg};
    color: {p.tooltip_text};
    border: 1px solid {p.card_border};
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 12px;
}}
"""


def get_theme_stylesheet(theme_id: str | None = None) -> str:
    """Return the generated stylesheet string for a theme id."""
    return generate_stylesheet(get_theme(theme_id))


# Static export matching default for existing imports
APP_STYLESHEET = get_theme_stylesheet("obsidian_dark")
