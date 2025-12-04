# styles.py
from typing import Optional
from PyQt5.QtGui import QColor


# =========================
#  Цвета для спред-боксов
# =========================
SPREAD_PALETTES = {
    "green":  ("#006611", "#009919", "#00cc22"),
    "red":    ("#660000", "#990000", "#cc0000"),
    "yellow": ("#666100", "#999100", "#ccc200"),
    "orange": ("#663c00", "#995900", "#cc7700"),
    "blue":   ("#001b66", "#002999", "#0036cc"),
    "cyan":   ("#006666", "#009999", "#00cccc"),
    "violet": ("#3b0066", "#590099", "#7700cc"),
    "pink":   ("#660058", "#990085", "#cc00b1"),
    "teal":   ("#006658", "#009985", "#00ccb1"),
    "gray":   ("#666666", "#999999", "#c4c4c4"),
}

_DEFAULT_DIRECT_PALETTE = "green"
_DEFAULT_REVERSE_PALETTE = "red"

_current_direct_palette = _DEFAULT_DIRECT_PALETTE
_current_reverse_palette = _DEFAULT_REVERSE_PALETTE

# для главного окна храним именно КЛЮЧ палитры из SPREAD_PALETTES
_DEFAULT_POSITIVE_PALETTE = "green"
_DEFAULT_NEGATIVE_PALETTE = "red"

_main_positive_spread_color = _DEFAULT_POSITIVE_PALETTE
_main_negative_spread_color = _DEFAULT_NEGATIVE_PALETTE


def _normalize_main_palette(value: str, default_key: str) -> str:
    """
    Нормализуем значение из настроек для главного меню:
    - если это ключ палитры из SPREAD_PALETTES — оставляем его;
    - если это старый hex-цвет и т.п. — откатываемся к дефолту.
    """
    if not value:
        return default_key
    v = str(value).strip().lower()
    if v in SPREAD_PALETTES:
        return v
    # legacy: раньше могли храниться hex-цвета — в этом случае просто дефолт
    return default_key


def set_main_spread_colors(positive: str, negative: str) -> None:
    """
    Цвета коробочек спреда в ГЛАВНОМ МЕНЮ (плюс/минус).

    Здесь мы храним КЛЮЧ палитры из SPREAD_PALETTES
    и дальше выбираем оттенок по величине спреда.
    """
    global _main_positive_spread_color, _main_negative_spread_color
    if positive is not None:
        _main_positive_spread_color = _normalize_main_palette(
            positive, _DEFAULT_POSITIVE_PALETTE
        )
    if negative is not None:
        _main_negative_spread_color = _normalize_main_palette(
            negative, _DEFAULT_NEGATIVE_PALETTE
        )


def main_spread_bg(spread_value) -> QColor:
    """
    Цвет фона коробочек в главном меню.

    Берём палитру из настроек (плюсовую/минусовую) и оттенок по величине |s|:

        - |s| < 0.5         -> тёмный
        - 0.5 <= |s| < 1.0  -> обычный
        - |s| >= 1.0        -> светлый
    """
    base_bg = QColor("#111827")  # дефолтный фон

    try:
        v = float(spread_value)
    except Exception:
        return base_bg

    if v > 0:
        palette_key = _main_positive_spread_color
    elif v < 0:
        palette_key = _main_negative_spread_color
    else:
        # нулевой спред — просто базовый фон
        return base_bg

    # если это ключ палитры — используем общую логику _pick_color_from_palette
    if palette_key in SPREAD_PALETTES:
        return _pick_color_from_palette(palette_key, v)

    # fallback на случай каких-то неожиданных значений
    return QColor(str(palette_key))





def set_spread_palettes(direct_palette: str, reverse_palette: str) -> None:
    """
    Настроить базовые цвета для прямого / обратного спреда.
    direct_palette / reverse_palette — ключи из SPREAD_PALETTES.
    Если ключ неизвестен — старое значение сохраняется.
    """
    global _current_direct_palette, _current_reverse_palette

    if direct_palette in SPREAD_PALETTES:
        _current_direct_palette = direct_palette
    if reverse_palette in SPREAD_PALETTES:
        _current_reverse_palette = reverse_palette


def _pick_color_from_palette(palette_key: str, spread: Optional[float]) -> QColor:
    """
    Общая логика выбора оттенка по величине спреда:
    - |s| < 0.5         -> тёмный
    - 0.5 <= |s| < 1.0  -> обычный
    - |s| >= 1.0        -> светлый
    """
    if spread is None:
        return QColor("#1f2933")

    try:
        s = abs(float(spread))
    except Exception:
        return QColor("#1f2933")

    palette = SPREAD_PALETTES.get(palette_key) or SPREAD_PALETTES[_DEFAULT_DIRECT_PALETTE]
    dark, normal, light = palette

    if s >= 1.0:
        return QColor(light)
    if s >= 0.5:
        return QColor(normal)
    if s > 0:
        return QColor(dark)

    # ноль / всё остальное — нейтральный тёмный фон
    return QColor("#1f2933")



def color_direct(spread: Optional[float]) -> QColor:
    """
    Цвет для ПРЯМОГО спреда по его значению.
    Базовый цвет — из палитры `_current_direct_palette`,
    оттенок — по величине спреда (тёмный / обычный / светлый).
    """
    return _pick_color_from_palette(_current_direct_palette, spread)


def color_reverse(spread: Optional[float]) -> QColor:
    """
    Цвет для ОБРАТНОГО спреда по его значению.
    Базовый цвет — из палитры `_current_reverse_palette`,
    оттенок — по величине спреда (тёмный / обычный / светлый).
    """
    return _pick_color_from_palette(_current_reverse_palette, spread)

def get_direct_spread_mid_color() -> str:
    """
    Средний цвет (normal) для текущей палитры ПРЯМОГО спреда.
    Используется, например, для рамки уведомлений.
    """
    palette = SPREAD_PALETTES.get(_current_direct_palette) or SPREAD_PALETTES[_DEFAULT_DIRECT_PALETTE]
    # palette = (dark, normal, light)
    if len(palette) >= 2:
        return palette[1]
    return palette[0]


def get_reverse_spread_mid_color() -> str:
    """
    Средний цвет (normal) для текущей палитры ОБРАТНОГО спреда.
    Используется, например, для рамки уведомлений.
    """
    palette = SPREAD_PALETTES.get(_current_reverse_palette) or SPREAD_PALETTES[_DEFAULT_REVERSE_PALETTE]
    if len(palette) >= 2:
        return palette[1]
    return palette[0]

def text_color(spread: Optional[float]) -> QColor:
    if spread is None:
        return QColor("#9ca3af")
    return QColor("#f9fafb")


# =========================
#  Общие стили текста (увеличены)
# =========================

MAIN_WINDOW = """
QMainWindow {
    background-color: #020617;
    color: #f5f5f5;
}
QWidget:focus {
    outline: none;
}
"""




TITLEBAR_BG = """
QWidget#Titlebar {
    background-color: #020617;
}
"""

TITLEBAR_LABEL = """
QLabel#TitlebarLabel {
    font-size: 16px;
    color: #e5e7eb;
}
"""

TITLEBAR_DIVIDER = """
QFrame#TitlebarDivider {
    background-color: #1f2937;
}
"""
MAIN_BG_WIDGET = """
#MainBg {
    background-color: #050816;   /* чуть светлее/другое, чем фон окна */
    border-radius: 12px;
    color: #f5f5f5;
}
"""



LINEEDIT_SEARCH = """
QLineEdit {
    background-color: #0a0f1c;
    border: 1px solid #2d3748;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e5e7eb;
    font-size: 14px;
}
QLineEdit:focus {
    border: 1px solid #4c9aff;
}
"""



LABEL_TITLE = "font-size: 28px; font-weight: 600; color: #ffffff;"
LABEL_SUBTITLE = "font-size: 15px; color: #9ca3af;"
LABEL_SECTION = "font-size: 13px; color: #9ca3af;"
LABEL_ALERT = "font-size: 12px; color: #9ca3af;"

LABEL_DIALOG_TITLE = "font-size: 18px; font-weight: 600; color: #f9fafb;"
LABEL_FORM = "font-size: 14px; color: #e5e7eb;"
MESSAGE_TEXT_STYLE = "color:#cbd5e1; font-size:14px;"

LABEL_TOKEN_NAME = "font-size: 18px; font-weight: 600; color: #e5e7eb;"
LABEL_TOKEN_NAME_BIG = "font-size: 20px; font-weight: 600; color: #e5e7eb;"
LABEL_SMALL_MUTED = "font-size: 14px; color: #9ca3af;"
LABEL_DEX_NAME = "font-size: 13px; color: #9ca3af;"

LABEL_STAR_DEFAULT = "color: #4b5563; font-size: 16px;"
LABEL_STAR_FAVORITE = "color: #facc15; font-size: 16px;"


# =========================
#  Стили карточек и полей
# =========================

CARD_WIDGET = "background-color: #020617; border-radius: 6px;"

SPREAD_BOX_BASE = (
    "border-radius: 4px; background-color: #111827; "
    "font-size: 13px; font-weight: 500;"
)

TEXTEDIT_LOG = (
    "QTextEdit { background-color: #020617; color: #e5e7eb; "
    "border: 1px solid #1f2937; border-radius: 4px; font-size: 15px; }"
)

LINEEDIT_DARK = (
    "QLineEdit { background-color: #030712; color: #f9fafb;"
    "border-radius: 4px; border: 1px solid #27272a; padding: 8px 10px; font-size: 14px; }"
)

STATUS_LABEL_IDLE = (
    "font-size: 14px; color: #9ca3af; padding: 0 10px;"
    "border-radius: 4px; border: 1px solid #27272a; "
    "background-color: #020617;"
)

STATUS_LABEL_ONLINE = (
    "font-size: 14px; color: #22c55e; padding: 0 10px;"
    "border-radius: 4px; border: 1px solid #16a34a; "
    "background-color: #020617;"
)


# =========================
#  Кнопки
# =========================

# зелёная — как была, с зелёным hover
BUTTON_PRIMARY = (
    "QPushButton { background-color: #22c55e; color: #020617;"
    "border-radius: 4px; padding: 8px 22px; font-size: 14px; "
    "font-weight: 600; border: none; }"
    "QPushButton:hover { background-color: #16a34a; }"
)

# тёмные кнопки/иконки
BUTTON_SECONDARY = (
    "QPushButton { background-color: #111827; color: #e5e7eb;"
    "border-radius: 4px; padding: 8px 22px; font-size: 14px; "
    "border: none; }"
    "QPushButton:hover { background-color: #1f2937; color: #e5e7eb; }"
)

BUTTON_TOP_DARK = (
    "QPushButton { background-color: #0f172a; color: #e5e7eb;"
    "border-radius: 4px; border: 1px solid #1f2937; padding: 0 22px; "
    "font-size: 14px; }"
    "QPushButton:hover { background-color: #1f2937; color: #e5e7eb; }"
    "QPushButton::menu-indicator { image:none; width:0; height:0; }"
)

BUTTON_ROUND_ICON = (
    "QPushButton {"
    "background-color: #111827;"
    "color: #e5e7eb;"
    "border-radius: 4px;"
    "border: none;"  
    "font-size: 15px;"
    "}"
    "QPushButton:hover {"
    "background-color: #b91c1c;"
    "color: #f9fafb;"
    "}"
)

BUTTON_ICON_TOP = (
    "QPushButton {"
    "background-color: #111827;"
    "color: #e5e7eb;"
    "border-radius: 4px;"
    "border: none;"
    "font-size: 15px;"
    "}"
    "QPushButton:hover {"
    "background-color: #1f2937;"   # при наведении — аккуратный серый
    "color: #e5e7eb;"
    "}"
)
BUTTON_ICON_TOP_WARN = (
    "QPushButton {"
    "background-color: #111827;"
    "color: #e5e7eb;"
    "border-radius: 4px;"
    "border: none;"
    "font-size: 15px;"
    "}"
    "QPushButton:hover {"
    "background-color: #facc15;"
    "color: #111827;"
    "}"
)

BUTTON_ICON_TOP_BLUE = (
    "QPushButton {"
    "background-color: #111827;"
    "color: #e5e7eb;"
    "border-radius: 4px;"
    "border: none;"
    "font-size: 15px;"
    "}"
    "QPushButton:hover {"
    "background-color: #3b82f6;"   # синий при наведении
    "color: #111827;"
    "}"
)

BUTTON_ICON_TOP_PURPLE = (
    "QPushButton {"
    "background-color: #111827;"
    "color: #e5e7eb;"
    "border-radius: 4px;"
    "border: none;"
    "font-size: 15px;"
    "}"
    "QPushButton:hover {"
    "background-color: #8B00FF;"   # фиолетовый при наведении
    "color: #111827;"
    "}"
)

SPINBOX_WITH_ARROWS_STYLE = """
    QSpinBox, QDoubleSpinBox {
        background-color: #030712;
        color: #f9fafb;
        border: 1px solid #27272a;
        font-size: 14px;
        padding: 8px 10px;

        /* Скругление только слева */
        border-top-left-radius: 4px;
        border-bottom-left-radius: 4px;
        border-top-right-radius: 0px;
        border-bottom-right-radius: 0px;
    }

    /* Кнопки ↑ и ↓ */
    QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    background: #1f2937;
    border-left: none;       /* ← убрано */
    width: 16px;             /* ← уменьшено (можешь 16 сделать) */
    padding: 0;
    margin: 0;
    
}

    /* ВАЖНО: скругления на кнопках — через border */
    QSpinBox::up-button, QDoubleSpinBox::up-button {
        border-top-right-radius: 4px;
        border-top: 1px solid #27272a; /* ← без этого Qt игнорирует radius */
    }

    QSpinBox::down-button, QDoubleSpinBox::down-button {
        border-bottom-right-radius: 4px;
        border-bottom: 1px solid #27272a; /* ← тоже обязательно */
    }

    /* Hover */
    QSpinBox::up-button:hover,
    QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover,
    QDoubleSpinBox::down-button:hover {
        background: #374151;
    }

    /* PNG стрелки */
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
        image: url("Icon/arrow_up.png");
        width: 16px;
        height: 18px;
    }

    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
        image: url("Icon/arrow_down.png");
        width: 16px;
        height: 18px;
    }
"""


SPINBOX_MAX_NOTIF = SPINBOX_WITH_ARROWS_STYLE + """
QSpinBox {
    background-color: #050816;
    border-radius: 4px;
}
"""



BUTTON_ROUND_ICON_MIN = (
    "QPushButton {"
    "background-color: #111827;" 
    "color: #e5e7eb;"
    "border-radius: 4px;"
    "border: none;"
    "font-size: 18px;" 
    "font-weight: 550;" 
    "} "
    "QPushButton:hover {"
    "background-color: #1f2937;" 
    "color: #e5e7eb;"
    "} "
    "QPushButton:pressed {"
    "background-color: #374151;"
    "} "
)


BUTTON_CLEAR = (
    "QPushButton { background-color: #111827; color: #e5e7eb;"
    "border-radius: 4px; padding: 8px 22px; font-size: 14px; border: none; }"
    "QPushButton:hover { background-color: #b91c1c; color: #f9fafb; }"
)


# =========================
#  Диалоги
# =========================

# =========================
#  Диалоги
# =========================

# Один базовый стиль для ВСЕХ диалоговых окон
DIALOG_BASE_COLOR = "#020617"

DIALOG_FRAME = f"""
QWidget#dialogFrame {{
    background-color: {DIALOG_BASE_COLOR};
    color: #f5f5f5;
    border: 1px solid #1f2937;
    border-radius: 12px;
}}
"""

DIALOG_ADD = f"""
QDialog {{
    background-color: {DIALOG_BASE_COLOR};
    color: #f5f5f5;
    border: 1px solid #1f2937;
    border-radius: 12px;
}}
"""

DIALOG_LOG = DIALOG_ADD

MESSAGE_CARD_STYLE = f"""
QWidget#MsgCard {{
    background-color: {DIALOG_BASE_COLOR};
    color: #f5f5f5;
    border: 1px solid #1f2937;
    border-radius: 12px;
}}
"""

ACCENT_STRIP_LEFT = "border-top-left-radius:12px; border-bottom-left-radius:12px;"

MESSAGE_TEXT_STYLE = "color:#cbd5e1; font-size:14px;"




# =========================
#  Комбо-боксы
# =========================

COMBOBOX_TOP_DARK = """
QComboBox {
    background-color: #0f172a;
    color: #e5e7eb;
    border: 1px solid #1f2937;
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 14px;
}
QComboBox:hover {
    background-color: #111827;
}
QComboBox::drop-down {
    border: 0px;
}
QComboBox:focus {
    outline: 0;
}
QComboBox QAbstractItemView {
    background-color: #020617;
    color: #e5e7eb;
    border: 1px solid #27272a;
    selection-background-color: #1f2937;
    selection-color: #f9fafb;
    outline: 0;
    font-size: 14px;
}
QComboBox QAbstractItemView::item {
    padding: 4px 8px;
}
QComboBox QAbstractItemView::item:focus {
    outline: none;
}
"""

COMBOBOX_DIALOG_MAIN = """
QComboBox {
    background-color: #030712;
    color: #f9fafb;
    border-radius: 4px;
    border: 1px solid #27272a;
    padding: 8px 10px;
    font-size: 14px;
    outline: 0;
    min-width: 240px;
}
QComboBox:hover {
    background-color: #1f2937;
}
QComboBox::drop-down {
    border: 0px;
}
QComboBox:focus {
    outline: 0;
}
QComboBox QAbstractItemView {
    background-color: #020617;
    color: #e5e7eb;
    border: 1px solid #27272a;
    selection-background-color: #1f2937;
    selection-color: #f9fafb;
    outline: 0;
    font-size: 14px;
}
QComboBox QAbstractItemView::item {
    padding: 4px 8px;
}
QComboBox QAbstractItemView::item:focus {
    outline: none;
}
"""

COMBOBOX_DIALOG_MUTED = """
QComboBox {
    background-color: #030712;
    color: #9ca3af;
    border-radius: 4px;
    border: 1px solid #27272a;
    padding: 8px 10px;
    font-size: 14px;
    outline: 0;
}
QComboBox:hover {
    background-color: #1f2937;
}
QComboBox::drop-down {
    border: 0px;
}
QComboBox:focus {
    outline: 0;
}
QComboBox QAbstractItemView {
    background-color: #020617;
    color: #e5e7eb;
    border: 1px solid #27272a;
    selection-background-color: #1f2937;
    selection-color: #f9fafb;
    outline: 0;
    font-size: 14px;
}
QComboBox QAbstractItemView::item {
    padding: 4px 8px;
}
QComboBox QAbstractItemView::item:focus {
    outline: none;
}
"""


# =========================
#  Меню DEX (шрифт как на кнопках)
# =========================

DEX_MENU = """
QMenu {
    background-color: #020617;
    color: #e5e7eb;
    border: 1px solid #27272a;
    border-radius: 2px;      /* такая же небольшая округлость, как у кнопок */
    padding: 2px -2;          /* чтобы пункты не прилипали к верху/низу */
    margin-top: 0px;         /* маленький зазор между кнопкой DEXы и меню */
    font-size: 14px;
}
QMenu::item {
    padding: 6px 12px;
    margin: 2px 6px;         /* зазор между пунктами и от краёв, чтобы не сливались */
    border-radius: 4px;      /* лёгкая округлость у самих пунктов */
}
QMenu::item:selected {
    background-color: #1f2937;
}
QMenu::item:focus {
    outline: none;
}
QMenu::indicator {
    width: 12px;
    height: 12px;
    border: 1px solid #4b5563;
    background-color: transparent;
    border-radius: 2px;         /* округлые чекбоксы */
    margin-left: 6px;
    margin-right: 6px;
    transition: background-color 0.2s;
}

QMenu::indicator:checked {
    background-color: #22c55e;   /* зелёная галочка */
    border-color: #22c55e;
}

QMenu::indicator:unchecked:hover {
    border-color: #22c55e;       /* подсветка при наведении */
}
"""


CHECKBOX_SPREAD = """
QCheckBox {
    background: transparent;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #4b5563;
    background-color: transparent;
    border-radius: 2px;
}
QCheckBox::indicator:checked {
    background-color: #22c55e;
    border-color: #22c55e;
}
QCheckBox::indicator:unchecked:hover {
    border-color: #22c55e;
}
"""
CHECKBOX_SPREAD_INLINE = CHECKBOX_SPREAD + """
QCheckBox {
    padding: 0px;
    margin: 0px;
}
QCheckBox::indicator {
    margin-left: 0px;
}
"""



TOOLTIP_STYLE = """
QToolTip {
    background-color: #020617;        /* тёмный фон как у окна */
    color: #e5e7eb;                   /* светлый текст */
    border: 1px solid #22c55e;        /* зелёная рамка (цвет можно менять) */
    padding: 6px 10px;                /* отступы внутри окошка */
    border-radius: 6px;               /* скруглённые углы */
    font-size: 11px;
}
"""


SCROLLBAR_DARK = """
QScrollBar:vertical {
    background: #0f172a;
    width: 10px;
    margin: 2px 0 2px 0;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #1f2937;
    border-radius: 5px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #374151;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    background: none;
    height: 0px;
}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: none;
}
"""

SCROLLAREA_TOKENS = """
QScrollArea {
    border: none;
    background-color: #050816;
}
QScrollArea::viewport {
    background-color: #050816;
}
""" + SCROLLBAR_DARK

TOKENS_CONTAINER_BG = "background-color: #050816;"

TABS_STYLE = """
QTabWidget::pane {
    background-color: #020617;
    border: 1px solid #1f2937;
    border-radius: 6px;
    margin-top: 0px;
    margin-left: 0px;   /* 👈 сжимаем поле слева */
    margin-right: 6px;  /* 👈 и справа */
}

/* сами вкладки */
QTabBar::tab {
    background-color: #0f172a;
    color: #9ca3af;
    font-size: 14px;
    padding: 6px 14px 6px 12px;  /* снизу больше места, чем сверху */
    border: 1px solid transparent;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    min-width: 80px;
    min-height: 20px;             /* гарантируем достаточную высоту */
    text-align: center;
}

QTabBar::tab:hover {
    background-color: #1e293b;
}

QTabBar::tab:selected {
    background-color: #020617;
    color: #e5e7eb;
    border-color: #1f2937;
    border-bottom-color: transparent;
}

/* зона, где появляются стрелки для прокрутки вкладок */
QTabBar::scroller {
    background: #020617;   /* убираем белое пятно слева/справа */
}

/* сами кнопки со стрелками */
QTabBar QToolButton {
    background-color: #020617;
    border: none;
    padding: 0;
    margin: 0;
    width: 20px;
    height: 20px;
    color: #e5e7eb;
    border-radius: 4px; 
}

QTabBar QToolButton:hover {
    background-color: #1e293b;
}
"""

# =========================
#  Общие мелкие стили
# =========================

# Прозрачный фон для виджетов
TRANSPARENT_BG = "background: transparent;"

# Тёмная панель (фон контейнеров, списков и т.п.)
PANEL_DARK_BG = "background-color: #020617;"

# Кнопка top-dark без стрелочки меню
BUTTON_TOP_DARK_NO_ARROW = (
    BUTTON_TOP_DARK
    + "QPushButton::menu-indicator{image:none;width:0;height:0;}"
)



# Прозрачный QScrollArea (фон берётся из того, что под ним)
SCROLLAREA_TRANSPARENT = (
    "QScrollArea { border: none; background: transparent; }"
    "QScrollArea::viewport { background: transparent; }"
    + SCROLLBAR_DARK
)

# Тёмный QScrollArea с рамкой
SCROLLAREA_DARK = (
    "QScrollArea {"
    "    background-color: #020617;"
    "    border: 1px solid #1f2937;"
    "    border-radius: 4px;"
    "}"
    "QScrollArea::viewport {"
    "    background-color: #020617;"
    "}"
    + SCROLLBAR_DARK
)

# Маленький поп-ап "Скопировано"
POPUP_COPIED_STYLE = """
background-color: #020617;
color: #e5e7eb;
border: 1px solid #22c55e;
padding: 6px 10px;
border-radius: 6px;
font-size: 11px;
"""

# Диалог "занят" (BusyDialog)
BUSY_DIALOG_STYLE = "BusyDialog{ background:transparent; }"
BUSY_TEXT_STYLE = "color:#e5e7eb; font-size:14px;"

# Маленькое экранное уведомление (заголовок + текст)
SCREEN_NOTIF_TITLE = "color: #e5e7eb; font-weight: 600; font-size: 10pt;"
SCREEN_NOTIF_TEXT = "color: #d1d5db; font-size: 11pt; font-weight: 400;"
SCREEN_NOTIF_CLOSE_BUTTON = """
QPushButton {
    border: none;
    background: transparent;
    color: #9ca3af;
    font-size: 9pt;
}
QPushButton:hover {
    color: #f9fafb;
}
"""
# Шаблон рамки для ScreenNotificationPopup (цвет меняется кодом)
SCREEN_NOTIF_FRAME_TEMPLATE = """
QWidget#screenNotificationFrame {{
    background-color: rgba(15, 23, 42, 235);
    border-radius: 8px;
    border: 3px solid {border_color};
}}
"""