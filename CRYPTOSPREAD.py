from datetime import datetime
import sys
import os
import json
from typing import List, Tuple, Optional, Dict
import requests
from PyQt5.QtGui import QIcon
from notifications import NotificationSettingsDialog, ScreenNotificationManager
from graph_window import SpreadGraphDialog
from styles import TABS_STYLE
from typing import Dict, Set
from core import log, log_exc
import sys
from PyQt5.QtCore import Qt, QPoint, QObject, QEvent, QSize, QTimer, QPropertyAnimation
from PyQt5.QtGui import QPixmap, QPainter, QPolygon, QColor
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QFrame,
    QSizePolicy,
    QDialog,
    QTabWidget,
    QLineEdit,
    QFormLayout,
    QSpinBox,
    QDoubleSpinBox,
    QGridLayout,
    QCheckBox,
    QGraphicsOpacityEffect,
    QSizeGrip,
    QMenu,
    QAction,
    QComboBox,
    QFileDialog,
    QSplashScreen,
    QColorDialog,
)

from core import (
    PAIRS,
    PairConfig,
    PriceWorker,
    http_client,
    load_saved_pairs_and_favorites,
    save_pairs_and_favorites,
    load_settings,
    save_settings,
    configure_proxy_settings,
    RESOURCE_DIR,
    _pick_coingecko_id_for_symbol,
)

from ui_parts import (
    FlowLayout,
    TokenCard,
    StickyMenu,
    LogDialog,
    AddTokenDialog,
    MessageDialog,
    BusyDialog,
    make_close_icon,
    make_max_icon,
    make_settings_icon,
    attach_menu_arrow,
    DraggableDialog,
)
from styles import (
    MAIN_WINDOW,
    LABEL_TITLE,
    LABEL_SUBTITLE,
    LABEL_SECTION,
    LABEL_ALERT,
    STATUS_LABEL_IDLE,
    STATUS_LABEL_ONLINE,
    BUTTON_TOP_DARK,
    BUTTON_PRIMARY,
    BUTTON_SECONDARY,
    BUTTON_ICON_TOP,
    BUTTON_ICON_TOP_WARN,
    BUTTON_ICON_TOP_BLUE,
    BUTTON_ROUND_ICON,
    BUTTON_ROUND_ICON_MIN,
    DEX_MENU,
    LABEL_DIALOG_TITLE,
    LABEL_FORM,
    LINEEDIT_DARK,
    DIALOG_ADD,
    SPINBOX_WITH_ARROWS_STYLE,
    BUTTON_CLEAR,
    CHECKBOX_SPREAD,
    SCROLLBAR_DARK,
    TOOLTIP_STYLE,
    # новые:
    TRANSPARENT_BG,
    PANEL_DARK_BG,
    BUTTON_TOP_DARK_NO_ARROW,
    SCROLLAREA_TRANSPARENT,
    DIALOG_FRAME,
    LINEEDIT_SEARCH,
    SCROLLAREA_TOKENS,
    TOKENS_CONTAINER_BG,
    TITLEBAR_BG,
    TITLEBAR_LABEL,
    TITLEBAR_DIVIDER,
    MAIN_BG_WIDGET,
    SPREAD_PALETTES,
    set_spread_palettes,
    get_direct_spread_mid_color,
    get_reverse_spread_mid_color,
    COMBOBOX_DIALOG_MAIN,
    LABEL_SMALL_MUTED,
    CHECKBOX_SPREAD_INLINE,
    BUTTON_ICON_TOP_PURPLE,
    set_main_spread_colors,
    main_spread_bg,
)


class SettingsDialog(DraggableDialog):
    def __init__(
            self,
            parent=None,
            telegram_chat_id: str = "",
            telegram_token: str = "",
            interval_sec: float = 3.0,
            spread_direct_palette: str = "green",
            spread_reverse_palette: str = "red",
            favorites=None,
            proxy_enabled: bool = False,
            proxy_protocol: str = "socks5",
            proxy_file_path: str = "",
            main_positive_spread_color: str = "green",  # ключ палитры
            main_negative_spread_color: str = "red",  # ключ палитры
    ):
        super().__init__(parent)
        self._favorites = favorites if isinstance(favorites, set) else (favorites or set())
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.Dialog)
        self._spread_checkboxes = {}
        self.setModal(False)

        self._palette_choices = [
            ("Зелёный", "green"),
            ("Красный", "red"),
            ("Жёлтый", "yellow"),
            ("Оранжевый", "orange"),
            ("Синий", "blue"),
            ("Голубой", "cyan"),
            ("Фиолетовый", "violet"),
            ("Розовый", "pink"),
            ("Бирюзовый", "teal"),
            ("Серый", "gray"),
        ]

        self._main_color_choices = [
            ("Зелёный", "green"),
            ("Красный", "red"),
            ("Жёлтый", "yellow"),
            ("Оранжевый", "orange"),
            ("Синий", "blue"),
            ("Голубой", "cyan"),
            ("Фиолетовый", "violet"),
            ("Розовый", "pink"),
            ("Бирюзовый", "teal"),
            ("Серый", "gray"),
        ]
        self._direct_palette = spread_direct_palette or "green"
        self._reverse_palette = spread_reverse_palette or "red"
        self._main_positive_color = main_positive_spread_color or "green"  # ключ палитры
        self._main_negative_color = main_negative_spread_color or "red"  # ключ палитры
        self._proxy_enabled = bool(proxy_enabled)
        self._proxy_protocol = (proxy_protocol or "socks5").lower()
        self._proxy_file_path = proxy_file_path or ""

        # прозрачный фон самого окна
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(500, 300)

        # внешний layout на весь диалог
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # внутренняя "карточка" с красивыми скруглёнными углами
        frame = QWidget()
        frame.setObjectName("dialogFrame")
        frame.setAttribute(Qt.WA_StyledBackground, True)  # чтобы фон реально рисовался
        frame.setStyleSheet(DIALOG_FRAME)

        # а дальше — уже "старый" main, только привязанный к frame
        main = QVBoxLayout(frame)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(12)

        outer.addWidget(frame)

        header = QHBoxLayout()
        title = QLabel("Настройки")
        title.setStyleSheet(LABEL_DIALOG_TITLE)
        header.addWidget(title)
        header.addStretch()
        btn_close = QPushButton()
        btn_close.setFixedSize(30, 30)
        btn_close.setStyleSheet(BUTTON_ROUND_ICON)
        btn_close.setIcon(make_close_icon(size=18, thickness=2, color="#e5e7eb"))
        btn_close.setIconSize(QSize(18, 18))
        btn_close.clicked.connect(self.reject)
        header.addWidget(btn_close)
        main.addLayout(header)

        tabs = QTabWidget()
        tabs.setStyleSheet(TABS_STYLE)
        tabs.setUsesScrollButtons(False)

        def create_setting_row(label_text, widget):
            row_layout = QHBoxLayout()
            label = QLabel(label_text)
            label.setStyleSheet(LABEL_FORM)
            row_layout.addWidget(label)
            row_layout.addStretch()
            row_layout.addWidget(widget)
            return row_layout

        # Вкладка 1: Telegram
        tab_telegram = QWidget()
        telegram_layout = QVBoxLayout(tab_telegram)
        telegram_layout.setContentsMargins(16, 24, 16, 16)
        telegram_layout.setSpacing(10)

        self.edit_chat_id = QLineEdit(telegram_chat_id)
        self.edit_chat_id.setStyleSheet(LINEEDIT_DARK)
        self.edit_token = QLineEdit(telegram_token)
        self.edit_token.setStyleSheet(LINEEDIT_DARK)

        form_layout = QFormLayout()
        form_layout.setHorizontalSpacing(30)
        form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form_layout.addRow(QLabel("Telegram chat ID", styleSheet=LABEL_FORM), self.edit_chat_id)
        form_layout.addRow(QLabel("Bot token", styleSheet=LABEL_FORM), self.edit_token)
        telegram_layout.addLayout(form_layout)
        telegram_layout.addStretch()

        # Вкладка 2: Обновление
        tab_update = QWidget()
        update_layout = QVBoxLayout(tab_update)
        update_layout.setContentsMargins(16, 24, 16, 16)

        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 3600)
        self.spin_interval.setValue(int(interval_sec))
        self.spin_interval.setStyleSheet(SPINBOX_WITH_ARROWS_STYLE)
        self.spin_interval.setFixedWidth(70)

        update_layout.addLayout(create_setting_row("Интервал обновления котировок, сек", self.spin_interval))
        update_layout.addStretch()

        self.spin_spread = QDoubleSpinBox()
        self.spin_spread.setRange(0.1, 100.0)
        self.spin_spread.setSingleStep(0.1)
        self.spin_spread.setDecimals(1)
        self.spin_spread.setStyleSheet(SPINBOX_WITH_ARROWS_STYLE)
        self.spin_spread.setFixedWidth(100)
        self.spin_spread.hide()

        # Вкладка 3: Спред
        tab_spread = QWidget()

        spread_layout = QVBoxLayout(tab_spread)
        spread_layout.setContentsMargins(16, 24, 16, 16)

        # строка с кнопкой "Токены"
        row_tokens = QHBoxLayout()
        lbl_tokens = QLabel("Выбор токенов для спред-оповещений")
        lbl_tokens.setStyleSheet(LABEL_FORM)
        row_tokens.addWidget(lbl_tokens)
        row_tokens.addStretch()

        self.btn_tokens = QPushButton("Токены…")
        self.btn_tokens.setStyleSheet(BUTTON_SECONDARY)

        # Высоту сразу делаем такой же, как у кнопки "Сохранить" — 30
        self.btn_tokens.setFixedHeight(30)

        # Ширину пока не трогаем — установим в конце, вместе с кнопкой "Сохранить"
        self.btn_tokens.clicked.connect(self._open_tokens_dialog)
        row_tokens.addWidget(self.btn_tokens)

        spread_layout.addLayout(row_tokens)
        spread_layout.addStretch()

        tab_color = QWidget()
        color_layout = QVBoxLayout(tab_color)
        color_layout.setContentsMargins(16, 24, 16, 16)
        color_layout.setSpacing(12)

        # --- палитры для графика / уведомлений ---
        row_direct = QHBoxLayout()
        row_direct.setSpacing(12)
        lab_direct = QLabel("Цвет для прямого спреда")
        lab_direct.setStyleSheet(LABEL_FORM)
        row_direct.addWidget(lab_direct)

        self.palette_selector_direct = QPushButton()
        self.palette_selector_direct.setFixedSize(30, 30)
        self._update_palette_button(self.palette_selector_direct, self._direct_palette)
        self.palette_selector_direct.clicked.connect(
            lambda: self._show_palette_menu(self.palette_selector_direct, "direct")
        )
        row_direct.addWidget(self.palette_selector_direct)
        row_direct.addStretch()

        row_reverse = QHBoxLayout()
        row_reverse.setSpacing(12)
        lab_reverse = QLabel("Цвет для обратного спреда")
        lab_reverse.setStyleSheet(LABEL_FORM)
        row_reverse.addWidget(lab_reverse)

        self.palette_selector_reverse = QPushButton()
        self.palette_selector_reverse.setFixedSize(30, 30)
        self._update_palette_button(self.palette_selector_reverse, self._reverse_palette)
        self.palette_selector_reverse.clicked.connect(
            lambda: self._show_palette_menu(self.palette_selector_reverse, "reverse")
        )
        row_reverse.addWidget(self.palette_selector_reverse)
        row_reverse.addStretch()

        # --- отдельные цвета для главного меню ---
        row_pos = QHBoxLayout()
        row_pos.setSpacing(12)
        lab_pos = QLabel("Цвет положительного спреда")
        lab_pos.setStyleSheet(LABEL_FORM)
        row_pos.addWidget(lab_pos)

        self.btn_main_positive_color = QPushButton()
        self.btn_main_positive_color.setFixedSize(30, 30)
        self._update_color_button(self.btn_main_positive_color, self._main_positive_color)
        self.btn_main_positive_color.clicked.connect(
            lambda: self._choose_main_color("positive")
        )
        row_pos.addWidget(self.btn_main_positive_color)
        row_pos.addStretch()

        row_neg = QHBoxLayout()
        row_neg.setSpacing(12)
        lab_neg = QLabel("Цвет отрицательного спреда")
        lab_neg.setStyleSheet(LABEL_FORM)
        row_neg.addWidget(lab_neg)

        self.btn_main_negative_color = QPushButton()
        self.btn_main_negative_color.setFixedSize(30, 30)
        self._update_color_button(self.btn_main_negative_color, self._main_negative_color)
        self.btn_main_negative_color.clicked.connect(
            lambda: self._choose_main_color("negative")
        )
        row_neg.addWidget(self.btn_main_negative_color)
        row_neg.addStretch()

        left_label_width = max(
            lab_direct.sizeHint().width(),
            lab_reverse.sizeHint().width()
        )
        lab_direct.setFixedWidth(left_label_width)
        lab_reverse.setFixedWidth(left_label_width)

        right_label_width = max(
            lab_pos.sizeHint().width(),
            lab_neg.sizeHint().width()
        )
        lab_pos.setFixedWidth(right_label_width)
        lab_neg.setFixedWidth(right_label_width)

        # --- раскладываем 4 строки в две колонки: слева 2, справа 2 ---
        col_left = QVBoxLayout()
        col_left.setSpacing(8)
        col_left.addLayout(row_direct)  # прямой спред
        col_left.addLayout(row_reverse)  # ОБРАТНЫЙ спред (палитра) — перенесли слева

        col_right = QVBoxLayout()
        col_right.setSpacing(8)
        col_right.addLayout(row_pos)  # положительный спред (меню) — перенесли справа
        col_right.addLayout(row_neg)

        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(40)  # расстояние между левой и правой колонкой
        columns_layout.addLayout(col_left)
        columns_layout.addLayout(col_right)
        columns_layout.addStretch()

        color_layout.addLayout(columns_layout)
        color_layout.addStretch()

        # Вкладка 5: Прокси
        tab_proxy = QWidget()
        proxy_layout = QVBoxLayout(tab_proxy)
        # чуть больше отступы, чтобы текст не прилипал к краям
        proxy_layout.setContentsMargins(16, 16, 16, 16)
        proxy_layout.setSpacing(10)


        # ----- чекбокс "Использовать прокси" в стиле уведомлений -----
        row_proxy_enabled = QHBoxLayout()
        row_proxy_enabled.setContentsMargins(0, 0, 0, 0)
        row_proxy_enabled.setSpacing(8)

        lbl_proxy_enabled = QLabel("Использовать прокси")
        lbl_proxy_enabled.setStyleSheet(LABEL_FORM)
        row_proxy_enabled.addWidget(lbl_proxy_enabled)
        row_proxy_enabled.addStretch()

        self.chk_proxy_enabled = QCheckBox()
        self.chk_proxy_enabled.setChecked(self._proxy_enabled)
        self.chk_proxy_enabled.setStyleSheet(CHECKBOX_SPREAD_INLINE)
        self.chk_proxy_enabled.setFixedWidth(70)
        self.chk_proxy_enabled.setFixedHeight(22)
        self.chk_proxy_enabled.setCursor(Qt.PointingHandCursor)

        row_proxy_enabled.addWidget(self.chk_proxy_enabled, 0, Qt.AlignLeft | Qt.AlignVCenter)
        proxy_layout.addLayout(row_proxy_enabled)

        # ----- выбор протокола в стиле "Режим: все токены / избранные" -----
        row_proto = QHBoxLayout()
        row_proto.setContentsMargins(0, 0, 0, 0)
        row_proto.setSpacing(8)

        lbl_proto = QLabel("Протокол")
        lbl_proto.setStyleSheet(LABEL_FORM)
        row_proto.addWidget(lbl_proto)
        row_proto.addStretch()

        # Кнопка вместо длинного комбобокса
        self.btn_proxy_proto = QPushButton()
        self.btn_proxy_proto.setFixedHeight(36)  # как в токенах
        self.btn_proxy_proto.setFixedWidth(160)  # как в токенах
        self.btn_proxy_proto.setStyleSheet(BUTTON_TOP_DARK_NO_ARROW)

        # текст по текущему протоколу
        current_proto = (self._proxy_protocol or "socks5").lower()
        if current_proto == "http":
            self.btn_proxy_proto.setText("HTTP")
        else:
            self.btn_proxy_proto.setText("SOCKS5")

        # липкое меню с двумя пунктами, как "Режим"
        self._proxy_proto_actions = {}
        proxy_menu = StickyMenu(self.btn_proxy_proto)
        proxy_menu.setStyleSheet(DEX_MENU)

        for key, label in [
            ("socks5", "SOCKS5"),
            ("http", "HTTP"),
        ]:
            act = proxy_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(key == current_proto)
            self._proxy_proto_actions[key] = act

        def on_proxy_proto_changed(action):
            # находим, какой пункт кликнули
            selected_key = None
            for k, act in self._proxy_proto_actions.items():
                if act is action:
                    selected_key = k
                    break

            if not selected_key:
                return

            # фиксируем выбор
            self._proxy_protocol = selected_key

            # только один пункт активен
            for k, act in self._proxy_proto_actions.items():
                act.setChecked(k == selected_key)

            # обновляем текст кнопки
            self.btn_proxy_proto.setText(action.text())

        proxy_menu.state_changed_callback = on_proxy_proto_changed
        proxy_menu.aboutToShow.connect(lambda m=proxy_menu: m.setFixedWidth(self.btn_proxy_proto.width()))
        self.btn_proxy_proto.setMenu(proxy_menu)

        # стрелочка, как у "Режим"
        attach_menu_arrow(self.btn_proxy_proto, proxy_menu)

        row_proto.addWidget(self.btn_proxy_proto, 0, Qt.AlignRight)
        proxy_layout.addLayout(row_proto)

        # --- путь к txt-файлу с прокси ---
        row_path = QHBoxLayout()
        lbl_path = QLabel("Файл с прокси (.txt)")
        lbl_path.setStyleSheet(LABEL_FORM)

        self.edit_proxy_file = QLineEdit(proxy_file_path)
        self.edit_proxy_file.setStyleSheet(LINEEDIT_DARK)
        # полупрозрачная подсказка внутри поля
        self.edit_proxy_file.setPlaceholderText("Формат: login:pass@ip:port")

        btn_browse_proxy = QPushButton("…")
        # Делаем кнопку строго квадратной
        h = self.edit_proxy_file.sizeHint().height()
        btn_browse_proxy.setFixedSize(h, h)
        btn_browse_proxy.setStyleSheet(BUTTON_TOP_DARK)
        btn_browse_proxy.clicked.connect(self._choose_proxy_file)

        row_path.addWidget(lbl_path)
        row_path.addWidget(self.edit_proxy_file, 1)
        row_path.addWidget(btn_browse_proxy)
        proxy_layout.addLayout(row_path)

        # --- подсказка по формату ---
        proxy_layout.addStretch()

        tabs.addTab(tab_telegram, "Telegram")
        tabs.addTab(tab_update, "Обновление")
        tabs.addTab(tab_spread, "Спред")
        tabs.addTab(tab_color, "Цвет")
        tabs.addTab(tab_proxy, "Прокси")

        main.addWidget(tabs)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Отмена")
        btn_ok = QPushButton("Сохранить")
        btn_cancel.setStyleSheet(BUTTON_CLEAR)
        btn_ok.setStyleSheet(BUTTON_PRIMARY)

        # Берём "эталонный" размер по кнопке Сохранить
        ok_size = btn_ok.sizeHint()
        same_width = ok_size.width()
        same_height = ok_size.height()

        # Делаем все основные кнопки одинакового размера
        btn_ok.setFixedSize(same_width, same_height)
        btn_cancel.setFixedSize(same_width, same_height)

        if hasattr(self, "btn_tokens"):
            self.btn_tokens.setFixedSize(same_width, same_height)

        # Кнопка выбора протокола (HTTP / SOCKS5) — такой же размер, как "Токены"
        if hasattr(self, "btn_proxy_proto"):
            self.btn_proxy_proto.setFixedSize(same_width, same_height)
            self.chk_proxy_enabled.setFixedWidth(same_width)

        btn_cancel.clicked.connect(self.reject)
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        main.addLayout(btn_row)

    def _open_tokens_dialog(self):
        # если окно уже создано и видно — просто поднимаем наверх
        dlg = getattr(self, "_spread_tokens_dialog", None)
        if dlg is not None and dlg.isVisible():
            dlg.raise_()
            dlg.activateWindow()
            return

        # создаём новое окно выбора токенов
        dlg = SpreadTokensDialog(
            self,
            favorites=self._favorites,
            spread_default=0.0,
        )
        self._spread_tokens_dialog = dlg

        # когда окно закроется — очищаем ссылку
        def _on_finished(_result: int) -> None:
            if getattr(self, "_spread_tokens_dialog", None) is dlg:
                self._spread_tokens_dialog = None

        dlg.finished.connect(_on_finished)

        # показываем БЕЗ блокировки других окон
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _palette_display_name(self, key: str) -> str:
        for name, k in self._palette_choices:
            if k == key:
                return name
        return key

    def _palette_preview_color(self, key: str) -> str:
        palette = SPREAD_PALETTES.get(key) or SPREAD_PALETTES.get("green")
        if not palette:
            return "#22c55e"
        # берём "средний" оттенок палитры для отображения в кнопке
        if len(palette) >= 3:
            return palette[1]
        return palette[0]

    def _update_palette_button(self, button: QPushButton, key: str) -> None:
        color = self._palette_preview_color(key)
        button.setProperty("palette_key", key)
        button.setToolTip(self._palette_display_name(key))
        button.setStyleSheet(
            "QPushButton {"
            "  border-radius: 4px;"
            "  border: 1px solid #4b5563;"
            f"  background-color: {color};"
            "}"
            "QPushButton:hover { border-color: #e5e7eb; }"
        )

    def _show_palette_menu(self, button: QPushButton, which: str) -> None:
        current_key = button.property("palette_key") or "green"
        menu = QMenu(self)

        for name, key in self._palette_choices:
            action = QAction(name, self)
            action.setCheckable(True)
            action.setChecked(key == current_key)

            def on_triggered(checked=False, key=key, which=which, btn=button):
                if which == "direct":
                    self._direct_palette = key
                else:
                    self._reverse_palette = key
                self._update_palette_button(btn, key)

            action.triggered.connect(on_triggered)
            menu.addAction(action)

        menu.exec_(button.mapToGlobal(button.rect().bottomLeft()))

    def _update_color_button(self, button: QPushButton, color: str) -> None:
        """
        Кнопки выбора цвета положительного/отрицательного спреда.
        В `color` хранится КЛЮЧ палитры (green/red/...),
        а для превью берём средний оттенок из SPREAD_PALETTES.

        Если пришёл "сырой" цвет (старые настройки, hex) — используем его как есть.
        """
        if not color:
            color = "green"

        key = str(color).strip().lower()
        if key in SPREAD_PALETTES:
            palette = SPREAD_PALETTES[key]
            preview = palette[1] if len(palette) >= 2 else palette[0]
            button.setProperty("color_value", key)  # в settings.json будет лежать ключ
            tooltip_text = next((name for name, k in self._main_color_choices if k == key), key)
        else:
            # legacy: hex/имя базового цвета
            preview = color
            button.setProperty("color_value", color)
            tooltip_text = color

        button.setToolTip(tooltip_text)

        # СВОЙ локальный стиль, без BUTTON_PRIMARY
        button.setStyleSheet(
            "QPushButton {"
            f"  background-color: {preview};"
            "  border-radius: 4px;"
            "  border: 1px solid #4b5563;"
            "}"
            "QPushButton:hover {"
            "  border-color: #e5e7eb;"
            "}"
        )

    def _choose_main_color(self, which: str) -> None:
        """
        Выбор цвета положительного/отрицательного спреда через маленькое меню,
        как у палитр прямого/обратного спреда (без большой палитры QColorDialog).
        """
        # какая кнопка сейчас используется
        if which == "positive":
            button = self.btn_main_positive_color
            current = (self._main_positive_color or "#22c55e").lower()
        else:
            button = self.btn_main_negative_color
            current = (self._main_negative_color or "#ef4444").lower()

        menu = QMenu(self)

        for name, hex_color in self._main_color_choices:
            act = QAction(name, self)
            act.setCheckable(True)
            act.setChecked(hex_color.lower() == current)

            def on_triggered(checked=False, color=hex_color, which=which, btn=button):
                if which == "positive":
                    self._main_positive_color = color
                    self._update_color_button(self.btn_main_positive_color, color)
                else:
                    self._main_negative_color = color
                    self._update_color_button(self.btn_main_negative_color, color)

            act.triggered.connect(on_triggered)
            menu.addAction(act)

        # показываем меню прямо под кнопкой
        pos = button.mapToGlobal(button.rect().bottomLeft())
        menu.exec_(pos)




    def _choose_proxy_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выбор файла с прокси",
            "",
            "Text files (*.txt);;All files (*.*)",
        )
        if path:
            self.edit_proxy_file.setText(path)

    def get_values(self):
        chat_id = self.edit_chat_id.text().strip()
        token = self.edit_token.text().strip()
        interval = float(self.spin_interval.value())

        proxy_enabled = self.chk_proxy_enabled.isChecked()
        proxy_protocol = (self._proxy_protocol or "socks5").lower()
        proxy_file_path = self.edit_proxy_file.text().strip()

        return (
            chat_id,
            token,
            interval,
            self._direct_palette,
            self._reverse_palette,
            self._main_positive_color,
            self._main_negative_color,
            proxy_enabled,
            proxy_protocol,
            proxy_file_path,
        )


    def accept(self):
        super().accept()


def _excepthook(exc_type, exc, tb):
    # логируем все необработанные исключения
    try:
        log_exc("Необработанная ошибка", exc)
    finally:
        sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _excepthook


# ===== Общие хелперы для стрелки в кнопках с меню =====
def _make_triangle(size_px: int = 12, up: bool = False, color: str = "#e5e7eb",
                   supersample: int = 3, inner_margin_px: int = 2) -> QPixmap:
    """
    Рисует гладкий треугольник с суперсэмплингом, затем масштабирует до size_px.
    """
    S = size_px * supersample
    m = inner_margin_px * supersample
    pm = QPixmap(S, S)
    pm.fill(Qt.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.HighQualityAntialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))

    tri = QPolygon([
        QPoint(S // 2, m if up else S - m),
        QPoint(m, S - m if up else m),
        QPoint(S - m, S - m if up else m),
    ])
    p.drawPolygon(tri)
    p.end()

    return pm.scaled(size_px, size_px, Qt.KeepAspectRatio, Qt.SmoothTransformation)


# Один набор иконок на весь файл
_ARROWS_CACHE = None


def _get_arrows():
    global _ARROWS_CACHE
    if _ARROWS_CACHE is None:
        down = _make_triangle(10, up=False)
        up = _make_triangle(10, up=True)
        _ARROWS_CACHE = (down, up)
    return _ARROWS_CACHE


def attach_menu_arrow(button: QPushButton, menu, *, right: int = 6, bottom: int = 4):
    # получаем pixmap’ы только сейчас, когда QApplication уже запущен
    down_pm, up_pm = _get_arrows()

    arrow = QLabel(button)
    arrow.setStyleSheet(TRANSPARENT_BG)
    arrow.setAttribute(Qt.WA_TranslucentBackground, True)
    arrow.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    arrow.setPixmap(down_pm)
    arrow.resize(down_pm.size())

    def place():
        w, h = button.width(), button.height()
        aw, ah = arrow.width(), arrow.height()
        arrow.move(w - aw - right, h - ah - bottom)

    class _ArrowPlacer(QObject):
        def eventFilter(self, obj, ev):
            if ev.type() == QEvent.Resize and obj is button:
                place()
            return False

    # держим ссылки, чтобы GC не удалил
    button._arrow_label = arrow
    _placer = _ArrowPlacer(button)
    button.installEventFilter(_placer)
    button._arrow_placer = _placer

    place()

    def on_show():
        button._arrow_label.setPixmap(up_pm)

    def on_hide():
        button._arrow_label.setPixmap(down_pm)

    menu.aboutToShow.connect(on_show)
    menu.aboutToHide.connect(on_hide)


class SpreadTokensDialog(DraggableDialog):
    def __init__(self, parent=None, favorites=None, spread_default: float = 0.0):
        super().__init__(parent)

        # начальный минимум оставляем только по высоте/ширине,
        # но не растягиваем до 1200
        self.setMinimumSize(700, 800)

        self._spread_default = float(spread_default or 0.0)
        # pair_name -> (chk_direct, chk_reverse)
        self._spread_checkboxes = {}
        # pair_name -> (spin_direct, spin_reverse)
        self._spread_spins = {}

        # список всех строк: (name_lower, label, chk_direct, chk_reverse, spin_dir, spin_rev)
        self._rows = []
        self._max_row = 0

        self._favorites = favorites or {}

        # делаем окно немодальным, как лог/уведомления
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setModal(False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        frame = QWidget()
        frame.setObjectName("dialogFrame")
        frame.setAttribute(Qt.WA_StyledBackground, True)
        frame.setStyleSheet(DIALOG_FRAME)

        main = QVBoxLayout(frame)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(12)

        outer.addWidget(frame)

        # ----- заголовок -----
        header = QHBoxLayout()
        title = QLabel("Токены для спред-оповещений")
        title.setStyleSheet(LABEL_DIALOG_TITLE)
        header.addWidget(title)
        header.addStretch()

        btn_close = QPushButton()
        btn_close.setFixedSize(30, 30)
        btn_close.setStyleSheet(BUTTON_ROUND_ICON)
        btn_close.setIcon(make_close_icon(size=18, thickness=2, color="#e5e7eb"))
        btn_close.setIconSize(QSize(18, 18))
        btn_close.clicked.connect(self.reject)
        header.addWidget(btn_close)

        main.addLayout(header)

        # ----- строка поиска -----
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск токена…")
        self.search_edit.setStyleSheet(LINEEDIT_SEARCH)
        main.addWidget(self.search_edit)
        self.search_edit.textChanged.connect(self._apply_filter)

        # ----- массовые действия -----
        bulk_row = QHBoxLayout()
        bulk_row.setContentsMargins(0, 0, 0, 0)
        bulk_row.setSpacing(8)  # одинаковый зазор между всеми элементами

        lbl_bulk = QLabel("Массовые действия")
        lbl_bulk.setStyleSheet(LABEL_FORM)

        self.btn_all_on = QPushButton("Все ON")
        self.btn_all_on.setFixedHeight(34)
        self.btn_all_on.setStyleSheet(BUTTON_SECONDARY)

        # режим работы кнопки "Все ON":
        # -1 — ещё не нажимали
        #  0 — включены только прямые
        #  1 — включены только обратные
        #  2 — включены оба направления
        self._all_on_mode = -1

        self.btn_all_off = QPushButton("Все OFF")
        self.btn_all_off.setFixedHeight(34)
        self.btn_all_off.setStyleSheet(BUTTON_SECONDARY)

        lbl_spread = QLabel("Спред %:")
        lbl_spread.setStyleSheet(LABEL_FORM)

        self.bulk_thr_spin = QDoubleSpinBox()
        self.bulk_thr_spin.setRange(0.0, 99.0)
        self.bulk_thr_spin.setDecimals(2)
        self.bulk_thr_spin.setSingleStep(0.1)
        self.bulk_thr_spin.setStyleSheet(SPINBOX_WITH_ARROWS_STYLE)
        self.bulk_thr_spin.setFixedWidth(70)
        self.bulk_thr_spin.setValue(self._spread_default)

        thr_btn_style_tpl = (
            "QPushButton { "
            "background-color: #111827; color: #e5e7eb;"
            "border-radius: 4px; padding: 8px 22px; font-size: 14px; border: none; "
            "}"
            "QPushButton:hover { "
            "background-color: %s; color: #111827;"
            "}"
        )

        direct_hover_color = get_direct_spread_mid_color()
        reverse_hover_color = get_reverse_spread_mid_color()

        self.btn_thr_direct = QPushButton("Порог прямого")
        self.btn_thr_direct.setFixedHeight(34)
        self.btn_thr_direct.setStyleSheet(thr_btn_style_tpl % direct_hover_color)

        self.btn_thr_reverse = QPushButton("Порог обратного")
        self.btn_thr_reverse.setFixedHeight(34)
        self.btn_thr_reverse.setStyleSheet(thr_btn_style_tpl % reverse_hover_color)

        # >>> ключ: одинаковая ширина у всех четырёх кнопок <<<
        buttons_same_width = [
            self.btn_all_on,
            self.btn_all_off,
            self.btn_thr_direct,
            self.btn_thr_reverse,
        ]
        max_width = max(b.sizeHint().width() for b in buttons_same_width)
        for b in buttons_same_width:
            b.setFixedWidth(max_width)

        # всё в одну линию
        bulk_row.addWidget(lbl_bulk)
        bulk_row.addWidget(self.btn_all_on)
        bulk_row.addWidget(self.btn_all_off)
        bulk_row.addWidget(lbl_spread)
        bulk_row.addWidget(self.bulk_thr_spin)
        bulk_row.addWidget(self.btn_thr_direct)
        bulk_row.addWidget(self.btn_thr_reverse)
        bulk_row.addStretch()

        self.btn_all_on.clicked.connect(self._on_all_on_clicked)
        self.btn_all_off.clicked.connect(
            lambda: self._apply_bulk(check_direct=False, check_reverse=False)
        )
        self.btn_thr_direct.clicked.connect(
            lambda: self._apply_bulk(set_thr_direct=True)
        )
        self.btn_thr_reverse.clicked.connect(
            lambda: self._apply_bulk(set_thr_reverse=True)
        )

        main.addLayout(bulk_row)

        # ----- скролл с таблицей -----
        scroll = QScrollArea()
        # Растягиваем содержимое по ширине окна, чтобы не было пустого поля справа
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(SCROLLAREA_TOKENS)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        container = QWidget()
        container.setStyleSheet(TOKENS_CONTAINER_BG)
        # важно: говорим, что контейнер должен растягиваться по ширине
        container.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)

        grid = QGridLayout(container)
        grid.setContentsMargins(8, 8, 8, 8)

        # расстояние между колонками – меняешь тут, если хочешь ближе/дальше
        grid.setHorizontalSpacing(70)
        grid.setVerticalSpacing(14)

        # 0 — название токена (самая широкая)
        # 1–4 — одинаковые по ширине столбцы
        for col in range(5):
            grid.setColumnStretch(col, 0)

        # заголовки колонок
        lbl_name = QLabel("Токен")
        lbl_name.setStyleSheet(LABEL_SECTION)
        lbl_dir = QLabel("Прямой")
        lbl_dir.setStyleSheet(LABEL_SECTION)
        lbl_dir_thr = QLabel("Порог прям., %")
        lbl_dir_thr.setStyleSheet(LABEL_SECTION)
        lbl_rev = QLabel("Обратный")
        lbl_rev.setStyleSheet(LABEL_SECTION)
        lbl_rev_thr = QLabel("Порог обр., %")
        lbl_rev_thr.setStyleSheet(LABEL_SECTION)

        header_col_width = 130  # можешь подправить число

        # всем ПЯТИ заголовкам даём одинаковую ширину и центрирование
        for w in (lbl_name, lbl_dir, lbl_dir_thr, lbl_rev, lbl_rev_thr):
            w.setFixedWidth(header_col_width)
            w.setAlignment(Qt.AlignCenter)

        # первый тоже центрируем, чтобы красивее смотрелся

        grid.addWidget(lbl_name, 0, 0, alignment=Qt.AlignCenter)
        grid.addWidget(lbl_dir, 0, 1, alignment=Qt.AlignCenter)
        grid.addWidget(lbl_dir_thr, 0, 2, alignment=Qt.AlignCenter)
        grid.addWidget(lbl_rev, 0, 3, alignment=Qt.AlignCenter)
        grid.addWidget(lbl_rev_thr, 0, 4, alignment=Qt.AlignCenter)

        row = 1
        for pair_name, cfg in sorted(PAIRS.items()):
            label = QLabel(pair_name)
            label.setStyleSheet(LABEL_FORM)
            # Центрируем текст токенов по колонке, чтобы они были под словом «Токен»
            label.setAlignment(Qt.AlignCenter)

            chk_direct = QCheckBox()
            chk_reverse = QCheckBox()
            chk_direct.setStyleSheet(CHECKBOX_SPREAD)
            chk_reverse.setStyleSheet(CHECKBOX_SPREAD)
            chk_direct.setChecked(getattr(cfg, "spread_direct", True))
            chk_reverse.setChecked(getattr(cfg, "spread_reverse", True))

            spin_dir = QDoubleSpinBox()
            spin_dir.setRange(0.0, 99.0)
            spin_dir.setDecimals(2)
            spin_dir.setSingleStep(0.1)
            spin_dir.setStyleSheet(SPINBOX_WITH_ARROWS_STYLE)
            spin_dir.setFixedWidth(70)

            spin_rev = QDoubleSpinBox()
            spin_rev.setRange(0.0, 99.0)
            spin_rev.setDecimals(2)
            spin_rev.setSingleStep(0.1)
            spin_rev.setStyleSheet(SPINBOX_WITH_ARROWS_STYLE)
            spin_rev.setFixedWidth(70)

            # читаем индивидуальные пороги, если есть
            thr_common = getattr(cfg, "spread_threshold", None)
            thr_dir_cfg = getattr(cfg, "spread_direct_threshold", None)
            thr_rev_cfg = getattr(cfg, "spread_reverse_threshold", None)

            def _norm(v):
                try:
                    if v is None:
                        return None
                    v = float(v)
                    return v if v > 0 else None
                except Exception:
                    return None

            thr_common = _norm(thr_common)
            thr_dir_val = _norm(thr_dir_cfg) or thr_common or self._spread_default
            thr_rev_val = _norm(thr_rev_cfg) or thr_common or self._spread_default

            spin_dir.setValue(thr_dir_val)
            spin_rev.setValue(thr_rev_val)

            # любое изменение сразу сохраняем настройки спреда
            chk_direct.stateChanged.connect(self._on_spread_controls_changed)
            chk_reverse.stateChanged.connect(self._on_spread_controls_changed)
            spin_dir.valueChanged.connect(self._on_spread_controls_changed)
            spin_rev.valueChanged.connect(self._on_spread_controls_changed)

            grid.addWidget(label, row, 0)
            grid.addWidget(chk_direct, row, 1, alignment=Qt.AlignCenter)
            grid.addWidget(spin_dir, row, 2, alignment=Qt.AlignCenter)
            grid.addWidget(chk_reverse, row, 3, alignment=Qt.AlignCenter)
            grid.addWidget(spin_rev, row, 4, alignment=Qt.AlignCenter)

            self._spread_checkboxes[pair_name] = (chk_direct, chk_reverse)
            self._spread_spins[pair_name] = (spin_dir, spin_rev)

            self._rows.append((pair_name.lower(), label, chk_direct, chk_reverse, spin_dir, spin_rev))
            grid.setRowMinimumHeight(row, 30)
            row += 1

        self._max_row = row - 1

        scroll.setWidget(container)
        main.addWidget(scroll, stretch=1)

        # ---- Ресайз-уголок в правом нижнем углу ----
        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 0, 0)
        grip_row.setSpacing(0)
        grip_row.addStretch()

        self._size_grip = QSizeGrip(frame)
        self._size_grip.setStyleSheet(TRANSPARENT_BG)
        grip_row.addWidget(self._size_grip, 0, Qt.AlignBottom | Qt.AlignRight)

        main.addLayout(grip_row)

        self._scroll = scroll
        self._grid = grid

        # стартовое отображение
        self._apply_filter("")

        self._scroll = scroll
        self._grid = grid

        # стартовое отображение
        self._apply_filter("")

    def _apply_filter(self, text: str):
        """
        Перекладываем строки в грид, чтобы не было дырок между заголовком
        и найденными токенами.
        """
        text = (text or "").strip().lower()

        # убираем все токены из грида и скрываем их
        for name, label, chk_direct, chk_reverse, spin_dir, spin_rev in self._rows:
            for w in (label, chk_direct, chk_reverse, spin_dir, spin_rev):
                self._grid.removeWidget(w)
                w.hide()

        for r in range(1, self._max_row + 1):
            self._grid.setRowMinimumHeight(r, 0)

        row = 1
        for name, label, chk_direct, chk_reverse, spin_dir, spin_rev in self._rows:
            if text and text not in name:
                continue

            self._grid.addWidget(label, row, 0)
            self._grid.addWidget(chk_direct, row, 1, alignment=Qt.AlignCenter)
            self._grid.addWidget(spin_dir, row, 2, alignment=Qt.AlignCenter)
            self._grid.addWidget(chk_reverse, row, 3, alignment=Qt.AlignCenter)
            self._grid.addWidget(spin_rev, row, 4, alignment=Qt.AlignCenter)

            for w in (label, chk_direct, chk_reverse, spin_dir, spin_rev):
                w.show()

            self._grid.setRowMinimumHeight(row, 30)
            row += 1

        self._grid.invalidate()
        self._grid.activate()

        container = self._scroll.widget()
        container.adjustSize()
        self._scroll.widget()

    def _on_all_on_clicked(self):
        """
        1-й клик: включить все прямые
        2-й клик: включить все обратные
        3-й клик: включить оба направления
        далее цикл повторяется.
        """
        # на всякий случай, если по каким-то причинам атрибут не создан
        if not hasattr(self, "_all_on_mode"):
            self._all_on_mode = -1

        # меняем режим: -1→0→1→2→0→1→2→...
        self._all_on_mode = (self._all_on_mode + 1) % 3

        if self._all_on_mode == 0:
            # только прямые
            self._apply_bulk(check_direct=True, check_reverse=False)
        elif self._all_on_mode == 1:
            # только обратные
            self._apply_bulk(check_direct=False, check_reverse=True)
        else:
            # оба направления
            self._apply_bulk(check_direct=True, check_reverse=True)



    def _apply_bulk(self, check_direct=None, check_reverse=None, set_thr_direct=False, set_thr_reverse=False):
        """
        Массовое применение настроек.
        Если в поиске есть текст — применяется только к найденным токенам.
        """
        text = (self.search_edit.text() or "").strip().lower()

        for name, label, chk_direct, chk_reverse, spin_dir, spin_rev in self._rows:
            if text and text not in name:
                continue

            if check_direct is not None:
                chk_direct.setChecked(check_direct)
            if check_reverse is not None:
                chk_reverse.setChecked(check_reverse)
            if set_thr_direct:
                spin_dir.setValue(self.bulk_thr_spin.value())
            if set_thr_reverse:
                spin_rev.setValue(self.bulk_thr_spin.value())

        # перерисовываем только для надёжности
        self._apply_filter(text)

    def _save_spread_settings(self) -> None:
        """
        Применяем текущие галки/пороги к PairConfig и пишем всё в tokens.json.
        Вызывается при любом изменении и при нажатии ОК.
        """
        try:
            for name, (chk_dir, chk_rev) in self._spread_checkboxes.items():
                cfg = PAIRS.get(name)
                if not cfg:
                    continue

                is_dir = chk_dir.isChecked()
                is_rev = chk_rev.isChecked()
                cfg.spread_direct = is_dir
                cfg.spread_reverse = is_rev

                if name in self._spread_spins:
                    spin_dir, spin_rev = self._spread_spins[name]
                    thr_direct = max(0.0, float(spin_dir.value()))
                    thr_reverse = max(0.0, float(spin_rev.value()))

                    cfg.spread_direct_threshold = None if thr_direct <= 0 else thr_direct
                    cfg.spread_reverse_threshold = None if thr_reverse <= 0 else thr_reverse

            # сохраняем весь набор в tokens.json
            save_pairs_and_favorites(PAIRS, self._favorites)
        except Exception as e:
            log(f"Ошибка сохранения настроек токенов спреда: {e}")

    def _on_spread_controls_changed(self, *args) -> None:
        """
        Любое изменение галки/цифры сразу сохраняет настройки.
        """
        self._save_spread_settings()

    def accept(self):
        """
        Применяем флаги и индивидуальные пороги спреда к PairConfig и сохраняем tokens.json.
        """
        self._save_spread_settings()
        super().accept()


class SpreadMonitorWindow(QMainWindow):
    def __init__(self, pairs: Dict[str, PairConfig]):
        super().__init__()

        self.log_dialog = None
        self.notif_dialog = None  # текущее окно уведомлений (если открыто)

        self._prev_spreads = {}
        self._alert_flags = {}
        self.notifications_enabled = True  # показывать ли карточки на экране
        self.notifications_max_count = 1  # по умолчанию только одна карточка
        self.notifications_history = []

        # in-memory история спредов (pair -> dex -> [(ts, direct, reverse)])
        self.spread_history = {}
        self.graph_dialog = None

        # === новый файл с историей спреда за 2 дня ===
        # будет лежать в папке RESOURCE_DIR и постоянно обновляться
        self.spread_history_file = os.path.join(
            str(RESOURCE_DIR),
            "spread_history_2d.json",
        )

        # при запуске пытаемся подтянуть историю из файла
        self._load_spread_history_from_file()

        # логотипы
        self._small_logo = None
        self._bg_logo = None
        self._bg_logo_pixmap = None

        ...
        self.telegram_chat_id: str = ""
        self.telegram_token: str = ""

        settings = load_settings()
        self.telegram_chat_id = settings.get("telegram_chat_id", "")
        self.telegram_token = settings.get("telegram_token", "")
        start_interval = settings.get("interval_sec", 3.0)
        self.interval_sec = float(start_interval)

        # настройки экранных уведомлений из settings.json
        self.notifications_enabled = bool(settings.get("notifications_enabled", self.notifications_enabled))
        try:
            self.notifications_max_count = int(settings.get("notifications_max_count", self.notifications_max_count))

            self.spread_direct_palette = settings.get("spread_direct_palette", "green")
            self.spread_reverse_palette = settings.get("spread_reverse_palette", "red")

            # для главного меню храним КЛЮЧ палитры (green/red/…)
            self.main_positive_spread_color = settings.get("main_positive_spread_color", "green")
            self.main_negative_spread_color = settings.get("main_negative_spread_color", "red")

            # Пробрасываем выбранные палитры в модуль styles (для графика/уведомлений)
            set_spread_palettes(self.spread_direct_palette, self.spread_reverse_palette)

            # Отдельно пробрасываем цвета для главного меню
            set_main_spread_colors(self.main_positive_spread_color, self.main_negative_spread_color)

            dlg_graph = getattr(self, "graph_dialog", None)
            if dlg_graph is not None:
                try:
                    dlg_graph.update_palette_colors()
                except Exception:
                    pass

            self.proxy_enabled = bool(settings.get("proxy_enabled", False))
            self.proxy_protocol = settings.get("proxy_protocol", "socks5")
            self.proxy_file_path = settings.get("proxy_file_path", "")

            # сразу применяем прокси к http_client
            configure_proxy_settings(
                self.proxy_enabled,
                self.proxy_protocol,
                self.proxy_file_path,
            )


            if self.notifications_max_count <= 0:
                self.notifications_max_count = 1
        except Exception:
            self.notifications_max_count = 1





        # для перетаскивания и максимизации
        self._drag_pos = None
        self._is_maximized = False

        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        TOP_BTN_WIDTH = 180
        ADD_BTN_WIDTH = 190

        ICON_SIZE = 36  # размер квадрата иконок
        BTN_ROW_SPACING = 6  # расстояние между иконками в btns_row
        GRID_H_SPACING = 6  # расстояние между колонками грида

        # 3 иконки (график + шестерёнка + колокол) + два промежутка между ними + отступ между
        # колонками + капсула статуса шириной как кнопки сверху
        STATUS_PANEL_WIDTH = TOP_BTN_WIDTH + 3 * ICON_SIZE + 2 * BTN_ROW_SPACING + GRID_H_SPACING

        def wrap(vbox: QVBoxLayout) -> QWidget:
            w = QWidget()
            w.setLayout(vbox)
            w.setContentsMargins(0, 0, 0, 0)
            return w

        self.pairs = pairs
        self.last_states: Dict[str, dict] = {}
        self.cards: Dict[str, TokenCard] = {}
        self.favorites: Set[str] = set()
        self.visible_dexes: Set[str] = {"pancake", "jupiter", "matcha"}
        self.dex_actions: Dict[str, object] = {}

        # ожидание добавляемого/редактируемого токена
        self.pending_token_name = None
        self._pending_loader = None  # BusyDialog при добавлении/изменении
        self.initial_loading = False

        # режим отображения токенов: "all" / "fav"
        self.current_mode = "all"

        # текущая CEX
        self.current_cex = "MEXC"
        self.setWindowTitle("Спред монитор — CEX vs DEX")
        self.resize(1600, 900)
        self.setStyleSheet(MAIN_WINDOW)

        central = QWidget(self)
        central.setObjectName("MainBg")
        central.setStyleSheet(MAIN_BG_WIDGET)
        self.setCentralWidget(central)

        # включаем отслеживание движения мыши,
        # чтобы eventFilter получал MouseMove без зажатой кнопки
        central.setMouseTracking(True)
        self.setMouseTracking(True)

        # --- РЕСАЙЗ МЫШКОЙ С ПРАВОГО-НИЖНЕГО УГЛА ---
        self._resize_margin = 6  # толщина "зоны" у границы окна
        self._resizing = False  # флаг, что сейчас тянем
        self._resize_edge = None  # какая грань/угол: "left", "right", "bottom", "br"
        self._resize_start_geom = None  # исходная геометрия окна
        self._resize_start_mouse = None  # позиция мыши при начале ресайза

        # слушаем события и от центрального виджета, и глобально от всего приложения
        central.installEventFilter(self)
        QApplication.instance().installEventFilter(self)

        root = QVBoxLayout(central)
        root.setContentsMargins(8, 6, 8, 8)
        root.setSpacing(8)

        # ---- КАСТОМНЫЙ TITLEBAR ----
        titlebar_widget = QWidget()
        titlebar_widget.setObjectName("Titlebar")
        titlebar_widget.setStyleSheet(TITLEBAR_BG)
        titlebar = QHBoxLayout(titlebar_widget)
        titlebar.setContentsMargins(12, 8, 12, 8)
        titlebar.setSpacing(10)

        # маленький логотип слева от заголовка
        self._small_logo = QLabel()
        self._small_logo.setObjectName("TitlebarLogo")
        self._small_logo.setFixedSize(40, 40)

        logo_path = os.path.join(str(RESOURCE_DIR), "icon", "mainLogo.png")
        pm_small = QPixmap(logo_path)
        if not pm_small.isNull():
            pm_small = pm_small.scaled(
                self._small_logo.width(),
                self._small_logo.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self._small_logo.setPixmap(pm_small)

        titlebar.addWidget(self._small_logo)

        title_label = QLabel("Спред монитор — CEX vs DEX")
        title_label.setObjectName("TitlebarLabel")
        title_label.setStyleSheet(TITLEBAR_LABEL)

        divider = QFrame()
        divider.setObjectName("TitlebarDivider")
        divider.setFixedHeight(1)
        divider.setStyleSheet(TITLEBAR_DIVIDER)

        titlebar.addWidget(title_label)
        titlebar.addStretch()

        # общие стили для кнопок управления окном
        btn_min = QPushButton("–")
        btn_min.setObjectName("WinMinBtn")
        btn_min.setFixedSize(30, 30)
        btn_min.setAttribute(Qt.WA_StyledBackground, True)
        btn_min.setStyleSheet(BUTTON_ROUND_ICON_MIN)  # ← новый стиль
        btn_min.setText("–")
        btn_min.clicked.connect(self.showMinimized)
        titlebar.addWidget(btn_min)

        # кнопка максимизировать / восстановить (такая же круглая)
        btn_max = QPushButton()
        btn_max.setObjectName("WinMaxBtn")
        btn_max.setFixedSize(30, 30)
        btn_max.setAttribute(Qt.WA_StyledBackground, True)
        btn_max.setStyleSheet(BUTTON_ROUND_ICON_MIN)  # тот же стиль, что и у "–"
        btn_max.setIcon(make_max_icon(size=18, thickness=2, color="#e5e7eb"))
        btn_max.setIconSize(QSize(18, 18))
        btn_max.setText("")

        def toggle_maximize():
            if self._is_maximized:
                self.showNormal()
                self._is_maximized = False
                # можно не менять иконку, пусть квадрат остаётся тем же
            else:
                self.showMaximized()
                self._is_maximized = True

        btn_max.clicked.connect(toggle_maximize)
        titlebar.addWidget(btn_max)

        # кнопка закрыть — ИДЕНТИЧНАЯ как в диалогах (иконка X + круг)
        btn_close = QPushButton()
        btn_close.setObjectName("WinCloseBtn")
        btn_close.setFixedSize(30, 30)
        btn_close.setAttribute(Qt.WA_StyledBackground, True)
        btn_close.setStyleSheet(BUTTON_ROUND_ICON)
        btn_close.setIcon(make_close_icon(size=18, thickness=2, color="#e5e7eb"))
        btn_close.setIconSize(QSize(18, 18))
        btn_close.setText("")
        btn_close.clicked.connect(self.close)
        titlebar.addWidget(btn_close)

        # привязываем перетаскивание к titlebar_widget
        def tb_mousePress(event):
            if event.button() == Qt.LeftButton:
                self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()
            else:
                QWidget.mousePressEvent(titlebar_widget, event)

        def tb_mouseMove(event):
            if event.buttons() & Qt.LeftButton and self._drag_pos is not None:
                self.move(event.globalPos() - self._drag_pos)
                event.accept()
            else:
                QWidget.mouseMoveEvent(titlebar_widget, event)

        def tb_mouseRelease(event):
            self._drag_pos = None
            QWidget.mouseReleaseEvent(titlebar_widget, event)

        titlebar_widget.mousePressEvent = tb_mousePress
        titlebar_widget.mouseMoveEvent = tb_mouseMove
        titlebar_widget.mouseReleaseEvent = tb_mouseRelease

        root.addWidget(titlebar_widget)

        # разделитель под заголовком
        divider = QFrame()
        divider.setObjectName("TitlebarDivider")
        divider.setFixedHeight(1)
        divider.setStyleSheet(TITLEBAR_DIVIDER)
        root.addWidget(divider)

        # верхняя панель
        top = QHBoxLayout()
        top.setSpacing(12)

        # слева теперь ничего фиксированного — всё место под будущие настройки
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(6)

        def wrap(vbox: QVBoxLayout) -> QWidget:
            w = QWidget()
            w.setLayout(vbox)
            w.setContentsMargins(0, 0, 0, 0)
            return w

        # ------- Статус -------
        status_panel = QFrame()
        status_panel.setFrameShape(QFrame.NoFrame)
        status_panel.setFixedWidth(STATUS_PANEL_WIDTH)  # используем значение сверху
        status_panel.setStyleSheet("QFrame { background: transparent; }")

        box_status = QVBoxLayout(status_panel)
        box_status.setContentsMargins(0, 0, 0, 0)
        box_status.setSpacing(6)

        from PyQt5.QtWidgets import QGridLayout  # импорт уже есть выше? если нет — добавь

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(GRID_H_SPACING)
        grid.setVerticalSpacing(4)

        # квадратная шестерёнка
        self.btn_graph = QPushButton()
        self.btn_graph.setFixedSize(36, 36)
        self.btn_graph.setCursor(Qt.PointingHandCursor)
        self.btn_graph.setIcon(QIcon("icon/graf.png"))
        self.btn_graph.setIconSize(QSize(22, 22))
        self.btn_graph.setText("")
        # тёмная, при наведении — аккуратный серый
        self.btn_graph.setStyleSheet(BUTTON_ICON_TOP_PURPLE)
        self.btn_graph.clicked.connect(self.open_spread_graph)

        # квадратная шестерёнка


        # квадратная шестерёнка
        self.btn_settings = QPushButton()
        self.btn_settings.setFixedSize(36, 36)
        # шестерёнка: тёмная, при наведении — СИНИЙ
        self.btn_settings.setStyleSheet(BUTTON_ICON_TOP_BLUE)
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.setIcon(QIcon("icon/option.png"))
        self.btn_settings.setIconSize(QSize(25, 25))
        self.btn_settings.setText("")
        self.btn_settings.clicked.connect(self.open_settings_dialog)

        # колокольчик
        self.btn_notif = QPushButton()
        self.btn_notif.setFixedSize(36, 36)
        self.btn_notif.setCursor(Qt.PointingHandCursor)
        self.btn_notif.setIcon(QIcon("icon/notif.png"))
        self.btn_notif.setIconSize(QSize(22, 22))
        self.btn_notif.setText("")
        # колокольчик: тёмная, при наведении — ЖЁЛТЫЙ
        self.btn_notif.setStyleSheet(BUTTON_ICON_TOP_WARN)
        self.btn_notif.clicked.connect(self.open_notifications_dialog)

        # капсула "Обновление: оффлайн/онлайн"
        self.status_label = QLabel("Обновление: ожидание")
        self.status_label.setFixedHeight(36)
        self.status_label.setFixedWidth(TOP_BTN_WIDTH)  # ← делаем как MEXC Futures
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(False)
        self.status_label.setStyleSheet(STATUS_LABEL_IDLE)
        self.status_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # заголовки
        lbl_settings = QLabel("")
        lbl_settings.setStyleSheet(LABEL_SECTION)

        lbl_status = QLabel("Статус")
        lbl_status.setStyleSheet(LABEL_SECTION)

        # строка 0: заголовки
        grid.addWidget(lbl_settings, 0, 0, alignment=Qt.AlignLeft)
        grid.addWidget(lbl_status, 0, 1, alignment=Qt.AlignLeft)

        # строка 1: шестерёнка и табло
        btns_row = QHBoxLayout()
        btns_row.setContentsMargins(0, 0, 0, 0)
        btns_row.setSpacing(6)
        btns_row.addWidget(self.btn_graph)
        btns_row.addWidget(self.btn_settings)
        btns_row.addWidget(self.btn_notif)

        grid.addLayout(btns_row, 1, 0, alignment=Qt.AlignLeft)
        grid.addWidget(self.status_label, 1, 1)

        box_status.addLayout(grid)
        controls.addWidget(status_panel)

        # Вставляем в верхнюю панель как фиксированный виджет (не тянется)

        # ------- Биржа -------
        box_cex = QVBoxLayout()
        l_cex = QLabel("Биржа")
        l_cex.setStyleSheet(LABEL_SECTION)

        self.cex_button = QPushButton("MEXC Futures")
        self.cex_button.setFixedHeight(36)
        self.cex_button.setFixedWidth(TOP_BTN_WIDTH)
        # убираем стандартный menu-indicator, чтобы не было второй стрелки
        self.cex_button.setStyleSheet(BUTTON_TOP_DARK + "QPushButton::menu-indicator{image:none;width:0;height:0;}")

        cex_menu = StickyMenu(self.cex_button)
        cex_menu.setStyleSheet(DEX_MENU)
        cex_menu.state_changed_callback = self.on_cex_menu_changed

        self.cex_actions = {}
        act_mexc = cex_menu.addAction("MEXC Futures")
        act_mexc.setCheckable(True)
        act_mexc.setChecked(True)
        self.cex_actions["MEXC"] = act_mexc

        cex_menu.aboutToShow.connect(lambda: cex_menu.setFixedWidth(self.cex_button.width()))
        self.cex_button.setMenu(cex_menu)

        # стрелка
        attach_menu_arrow(self.cex_button, cex_menu)

        box_cex.addWidget(l_cex)
        box_cex.addWidget(self.cex_button)

        # ------- DEX-фильтр -------
        box_dex = QVBoxLayout()
        l_dex = QLabel("DEXы")
        l_dex.setStyleSheet(LABEL_SECTION)

        self.dex_button = QPushButton("Все")
        self.dex_button.setFixedHeight(36)
        self.dex_button.setFixedWidth(TOP_BTN_WIDTH)
        self.dex_button.setStyleSheet(BUTTON_TOP_DARK + "QPushButton::menu-indicator{image:none;width:0;height:0;}")

        dex_menu = StickyMenu(self.dex_button)
        dex_menu.state_changed_callback = self.on_dex_menu_changed
        dex_menu.setStyleSheet(DEX_MENU)
        self.dex_actions = {}

        for key, label in [
            ("pancake", "Pancake"),
            ("jupiter", "Jupiter"),
            ("matcha", "Matcha"),
        ]:
            act = dex_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(True)
            self.dex_actions[key] = act

        dex_menu.aboutToShow.connect(self.adjust_dex_menu_width)
        self.dex_button.setMenu(dex_menu)

        # стрелка
        attach_menu_arrow(self.dex_button, dex_menu)

        box_dex.addWidget(l_dex)
        box_dex.addWidget(self.dex_button)

        # ------- Режим -------
        box_mode = QVBoxLayout()
        l_mode = QLabel("Режим")
        l_mode.setStyleSheet(LABEL_SECTION)

        self.mode_button = QPushButton("Все токены")
        self.mode_button.setFixedHeight(36)
        self.mode_button.setFixedWidth(TOP_BTN_WIDTH)
        self.mode_button.setStyleSheet(BUTTON_TOP_DARK_NO_ARROW)

        mode_menu = StickyMenu(self.mode_button)
        mode_menu.setStyleSheet(DEX_MENU)
        mode_menu.state_changed_callback = self.on_mode_menu_changed

        self.mode_actions: Dict[str, object] = {}
        for key, label in [
            ("all", "Все токены"),
            ("fav", "Избранные"),
        ]:
            act = mode_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(key == "all")
            self.mode_actions[key] = act

        mode_menu.aboutToShow.connect(lambda: mode_menu.setFixedWidth(self.mode_button.width()))
        self.mode_button.setMenu(mode_menu)

        # стрелка
        attach_menu_arrow(self.mode_button, mode_menu)

        box_mode.addWidget(l_mode)
        box_mode.addWidget(self.mode_button)

        # ------- Лог -------
        box_log = QVBoxLayout()
        l_log = QLabel("Лог")
        l_log.setStyleSheet(LABEL_SECTION)
        self.btn_log = QPushButton("Открыть лог")
        self.btn_log.setFixedHeight(36)
        self.btn_log.setFixedWidth(TOP_BTN_WIDTH)
        self.btn_log.setStyleSheet(BUTTON_TOP_DARK)
        self.btn_log.clicked.connect(self.open_log_dialog)
        box_log.addWidget(l_log)
        box_log.addWidget(self.btn_log)

        # ------- Добавить токен -------
        box_add = QVBoxLayout()
        l_add = QLabel("Токены")
        l_add.setStyleSheet(LABEL_SECTION)
        self.btn_add = QPushButton("+ Добавить токен")
        self.btn_add.setFixedHeight(36)
        self.btn_add.setFixedWidth(ADD_BTN_WIDTH)
        self.btn_add.setStyleSheet(BUTTON_PRIMARY)
        self.btn_add.clicked.connect(self.open_add_dialog)
        box_add.addWidget(l_add)
        box_add.addWidget(self.btn_add)

        # Порядок в верхней панели

        controls.addLayout(box_cex)
        controls.addLayout(box_dex)
        controls.addLayout(box_mode)
        controls.addLayout(box_log)
        controls.addLayout(box_add)

        # сначала растяжка, потом контролы → блок уходит вправо
        top.addStretch(1)
        top.addLayout(controls)

        root.addLayout(top)
        root.addSpacing(25)

        # зона карточек

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(SCROLLAREA_TRANSPARENT)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        # включаем tracking и тут, чтобы движения мыши внизу окна тоже ловились
        self.scroll.setMouseTracking(True)

        self.cards_host = QWidget()
        self.cards_host.setMouseTracking(True)
        self.cards_host.setStyleSheet(PANEL_DARK_BG)

        self.flow = FlowLayout(self.cards_host, margin=6, spacing=10)
        self.scroll.setWidget(self.cards_host)
        root.addWidget(self.scroll, stretch=1)

        # большой логотип на фоне главного экрана (поверх блоков, но полупрозрачный и не реагирует на мышь)
        self._bg_logo = QLabel(central)
        self._bg_logo.setObjectName("MainBigLogo")
        self._bg_logo.setAttribute(Qt.WA_TranslucentBackground, True)
        self._bg_logo.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._bg_logo.setStyleSheet("background: transparent;")

        logo_big_path = os.path.join(str(RESOURCE_DIR), "icon", "mainLogo.png")
        pm_big = QPixmap(logo_big_path)
        if not pm_big.isNull():
            self._bg_logo_pixmap = pm_big
            effect = QGraphicsOpacityEffect(self._bg_logo)
            effect.setOpacity(0.06)  # тут регулируешь «призрачность»
            self._bg_logo.setGraphicsEffect(effect)

            self._update_bg_logo_geometry()
            self._bg_logo.show()
        else:
            self._bg_logo.hide()

        self.alerts = QLabel("Нажмите «Добавить токен», выберите CEX, DEX и токен.")
        self.alerts.setStyleSheet(LABEL_ALERT)
        root.addWidget(self.alerts)

        self._notif_panel = QWidget(self)
        self._notif_panel.setStyleSheet(TRANSPARENT_BG)
        self._notif_panel.setAttribute(Qt.WA_TranslucentBackground, True)

        self._notif_layout = QVBoxLayout(self._notif_panel)
        self._notif_layout.setContentsMargins(0, 0, 0, 0)
        self._notif_layout.setSpacing(6)

        # фиксированная ширина карточек (используется для внутренних карточек)
        self._notif_panel.setFixedWidth(320)
        self._notif_panel.hide()

        # менеджер экранных уведомлений (правый нижний угол ЭКРАНА)
        self.screen_notifications = ScreenNotificationManager(
            anchor_widget=self,
            enabled=self.notifications_enabled,
            max_visible=int(self.notifications_max_count),
            timeout_ms=6000,  # базово 6 сек, при очереди сжимается до 3 сек
        )

        # worker
        self.worker = PriceWorker(self.pairs, interval=self.interval_sec)
        self.worker.data_ready.connect(self.on_data_ready)
        self.worker.start()
        if self.pairs:
            # включаем режим "ожидания добавления", чтобы крутилка была по центру
            self.initial_loading = True
            self.pending_token_name = "__initial__"  # временный маркер
            self._show_pending_label("Загружаем сохранённые токены…")

    # -------- CEX меню --------
    def on_cex_menu_changed(self, changed_action):
        act = self.cex_actions["MEXC"]
        if act.isChecked():
            # Биржа выбрана — работаем с MEXC
            self.current_cex = "MEXC"
            self.cex_button.setText(act.text())
        else:
            # Ничего не выбрано — биржа отсутствует
            self.current_cex = None
            self.cex_button.setText("Выбрать биржу")

        # ВАЖНО: пересчитать видимость карточек при смене биржи
        self.update_cards_visibility()

    # -------- DEX меню --------
    def adjust_dex_menu_width(self):
        menu = self.dex_button.menu()
        if menu:
            menu.setFixedWidth(self.dex_button.width())

    def on_dex_menu_changed(self, changed_action):
        selected = {key for key, act in self.dex_actions.items() if act.isChecked()}
        self.visible_dexes = selected

        if not selected:
            text = "Выбрать DEX"
        elif len(selected) == 1:
            text = next(self.dex_actions[k].text() for k in selected)
        else:
            text = "Неск. DEX"
        self.dex_button.setText(text)

        # обновляем строки внутри карточек
        for card in self.cards.values():
            card.set_visible_dexes(self.visible_dexes)

        # и обновляем видимость самих карточек по выбранным DEX
        self.update_cards_visibility()

    # -------- режим (все / избранные) --------
    def on_mode_menu_changed(self, changed_action):
        clicked_key = None
        for k, act in self.mode_actions.items():
            if act is changed_action:
                clicked_key = k
                break
        if clicked_key is None:
            return

        if not changed_action.isChecked():
            changed_action.setChecked(True)
        self.current_mode = clicked_key

        for k, act in self.mode_actions.items():
            if k != clicked_key:
                act.setChecked(False)

        self.mode_button.setText(self.mode_actions[self.current_mode].text())
        self.update_cards_visibility()

    def _collect_dex_states(self) -> dict:
        """
        Состояния DEX-фильтра (какие DEX включены).
        Ключи: "pancake", "jupiter", "matcha".
        """
        return {key: bool(act.isChecked()) for key, act in self.dex_actions.items()}

    def _collect_cex_states(self) -> dict:
        """
        Состояние CEX (сейчас по сути одна биржа MEXC).
        """
        return {key: bool(act.isChecked()) for key, act in self.cex_actions.items()}

    def _collect_mode_states(self) -> dict:
        """
        Режим отображения токенов: all / fav.
        """
        return {key: bool(act.isChecked()) for key, act in self.mode_actions.items()}

    def _collect_pairs_list(self) -> list:
        """
        Список имён токенов, который кладём в settings (дополнительно к tokens.json).
        Сейчас достаточно сохранить просто список ключей.
        """
        return sorted(self.pairs.keys())

    # -------- диалоги --------
    def open_log_dialog(self):
        # создаём лог-окно один раз и переиспользуем
        if self.log_dialog is None:
            self.log_dialog = LogDialog(self)

        self.log_dialog.refresh()
        self.log_dialog.show()
        self.log_dialog.raise_()
        self.log_dialog.activateWindow()

    def open_add_dialog(self):
        dlg = AddTokenDialog(self)
        if dlg.exec_() != dlg.Accepted:
            return

        dex_a, dex_b, token, j_mint, j_dec, bsc_addr, mexc_ps, matcha_addr, matcha_decimals = dlg.get_values()
        if not token:
            return

        base = token.upper()
        quote = "USDT"
        name = f"{base}-{quote}"

        all_dexes = ["pancake", "jupiter", "matcha"]

        # какие DEX выбрал пользователь
        if dex_a in all_dexes:
            new_dexes = {dex_a}
            dex_label = dex_a
        else:
            new_dexes = set(all_dexes)
            dex_label = dex_a or "-"

        # логируем важное действие
        log(f"Добавлен токен {name} (DEX: {dex_label}, CEX : {dex_b or '-'})")

        # если пара уже есть — просто добавляем к ней новые DEX
        if name in self.pairs:
            cfg = self.pairs[name]
            current = set(cfg.dexes or all_dexes)

            # если ВСЕ выбранные DEX уже есть → считаем дублем
            if new_dexes.issubset(current):
                MessageDialog.error(
                    self,
                    f"Токен «{name}» для выбранного DEX уже есть в списке.",
                )
                return

            added = sorted(new_dexes - current)
            cfg.dexes = sorted(current | new_dexes)

            log(f"Для токена {name} добавлены DEX: {', '.join(added)}")
            MessageDialog.success(
                self,
                f"Для токена «{base}» добавлен(ы) DEX: {', '.join(added)}.",
            )
            # воркер уже таскает этот токен, лоадер не нужен
            return

        # токен новый — создаём PairConfig
        cfg = PairConfig(
            name=name,
            base=base,
            quote=quote,
            dexes=sorted(new_dexes) if len(new_dexes) < len(all_dexes) else None,
            jupiter_mint=j_mint,
            jupiter_decimals=j_dec,
            bsc_address=bsc_addr,
            matcha_address=matcha_addr,
            matcha_decimals=matcha_decimals,
            mexc_price_scale=mexc_ps,
            # ЧТОБЫ ЧЕКБОКСЫ ПО УМОЛЧАНИЮ БЫЛИ ВЫКЛЮЧЕНЫ
            spread_direct=False,
            spread_reverse=False,
        )
        try:
            cg_id = _pick_coingecko_id_for_symbol(base)
            if cg_id:
                cfg.cg_id = cg_id
                log(f"Для {base} подобран cg_id: {cg_id}")
            else:
                log(f"Не удалось подобрать cg_id для {base}")
        except Exception as e:
            log(f"Ошибка подбора cg_id для {base}: {e}")

        self.pairs[name] = cfg

        # --- СРАЗУ сохраняем токены и избранные, а не только при выходе ---
        try:
            save_pairs_and_favorites(self.pairs, self.favorites)
        except Exception as e:
            # чтобы падение записи не убило добавление токена
            log(f"Ошибка мгновенного сохранения токенов: {e}")

        # ждём появления токена
        self.pending_token_name = name
        self._show_pending_label(f"Ожидайте, добавляется токен «{base}»…")

    def open_settings_dialog(self):
        current_interval = 3.0
        try:
            if hasattr(self, "worker") and hasattr(self.worker, "interval"):
                current_interval = float(self.worker.interval)
        except Exception:
            pass

        # Если окно уже открыто — просто поднимаем его наверх
        if getattr(self, "settings_dialog", None) is not None and self.settings_dialog.isVisible():
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return

        dlg = SettingsDialog(
            self,
            telegram_chat_id=self.telegram_chat_id,
            telegram_token=self.telegram_token,
            interval_sec=self.interval_sec,
            spread_direct_palette=self.spread_direct_palette,
            spread_reverse_palette=self.spread_reverse_palette,
            favorites=self.favorites,
            proxy_enabled=self.proxy_enabled,
            proxy_protocol=self.proxy_protocol,
            proxy_file_path=self.proxy_file_path,
            main_positive_spread_color=self.main_positive_spread_color,
            main_negative_spread_color=self.main_negative_spread_color,
        )
        self.settings_dialog = dlg

        # Логика, которая раньше была внутри "if dlg.exec_() == QDialog.Accepted"
        def _on_accepted():
            (
                chat_id,
                token,
                interval_sec,
                direct_palette,
                reverse_palette,
                main_pos_color,
                main_neg_color,
                proxy_enabled,
                proxy_protocol,
                proxy_file_path,
            ) = dlg.get_values()

            self.telegram_chat_id = chat_id
            self.telegram_token = token
            self.interval_sec = interval_sec
            self.spread_direct_palette = direct_palette
            self.spread_reverse_palette = reverse_palette
            self.main_positive_spread_color = main_pos_color
            self.main_negative_spread_color = main_neg_color

            self.proxy_enabled = proxy_enabled
            self.proxy_protocol = proxy_protocol
            self.proxy_file_path = proxy_file_path

            # применяем палитры
            set_spread_palettes(self.spread_direct_palette, self.spread_reverse_palette)
            set_main_spread_colors(self.main_positive_spread_color, self.main_negative_spread_color)

            # если окно графика уже открыто — обновляем цвета легенды
            graph = getattr(self, "graph_dialog", None)
            if graph is not None and graph.isVisible():
                try:
                    graph.update_palette_colors()
                except Exception as e:
                    log(f"Не удалось обновить цвета легенды графика: {e}")

            # применяем прокси к http_client
            configure_proxy_settings(
                self.proxy_enabled,
                self.proxy_protocol,
                self.proxy_file_path,
            )

            if interval_sec <= 0:
                interval_sec = 1.0

            try:
                self.worker.interval = float(interval_sec)
                log(f"Интервал обновления цен изменён на {interval_sec:.0f} сек.")
            except Exception as e:
                log(f"Не удалось обновить интервал цен: {e}")

            try:
                save_settings(
                    self.telegram_chat_id,
                    self.telegram_token,
                    self.interval_sec,
                    favorites=list(self.favorites),
                    dex_states=self._collect_dex_states(),
                    cex_states=self._collect_cex_states(),
                    mode_states=self._collect_mode_states(),
                    spread_direct_palette=self.spread_direct_palette,
                    spread_reverse_palette=self.spread_reverse_palette,
                    spread_pairs=self._collect_pairs_list(),
                    notif_enabled=self.notifications_enabled,
                    notif_max_count=self.notifications_max_count,
                    proxy_enabled=self.proxy_enabled,
                    proxy_protocol=self.proxy_protocol,
                    proxy_file_path=self.proxy_file_path,
                    main_positive_spread_color=self.main_positive_spread_color,
                    main_negative_spread_color=self.main_negative_spread_color,
                )
                log("Настройки сохранены в settings.json")
            except Exception as e:
                log(f"Ошибка сохранения настроек: {e}")

            try:
                save_pairs_and_favorites(self.pairs, self.favorites)
                log("Токены и флаги спреда сохранены в tokens.json")
            except Exception as e:
                log(f"Ошибка сохранения токенов после настроек: {e}")

        dlg.accepted.connect(_on_accepted)

        # Когда окно закроется — очищаем ссылку
        def _on_finished(_result: int) -> None:
            if getattr(self, "settings_dialog", None) is dlg:
                self.settings_dialog = None

        dlg.finished.connect(_on_finished)

        # Показываем без блокировки, как лог и уведомления
        dlg.show()

    def _on_notif_settings_changed(self, enabled: bool, max_count: int) -> None:
        """Вызывается при изменении чекбокса/количества в окне уведомлений."""
        self.notifications_enabled = bool(enabled)
        self.notifications_max_count = int(max_count)

        if hasattr(self, "screen_notifications") and self.screen_notifications is not None:
            self.screen_notifications.set_enabled(self.notifications_enabled)
            self.screen_notifications.set_max_visible(self.notifications_max_count)

        # сохраняем в settings.json вместе с остальными настройками
        try:
            interval_sec = 3.0
            if hasattr(self, "worker") and self.worker is not None:
                try:
                    interval_sec = float(self.worker.interval)
                except Exception:
                    pass

            save_settings(
                self.telegram_chat_id,
                self.telegram_token,
                interval_sec,
                notif_enabled=self.notifications_enabled,
                notif_max_count=self.notifications_max_count,
            )
        except Exception as e:
            log(f"Ошибка сохранения настроек уведомлений: {e}")

    def open_notifications_dialog(self):
        """
        Окно настроек всплывающих уведомлений спреда.
        Как лог: один экземпляр на всё приложение,
        чтобы сохранялись позиция и размер.
        """
        dlg = getattr(self, "notif_dialog", None)

        # Если уже есть созданное окно — просто обновляем историю и показываем
        if dlg is not None:
            dlg.set_history(self.notifications_history)
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
            return

        # Первый запуск — создаём диалог
        dlg = NotificationSettingsDialog(
            self,
            enabled=self.notifications_enabled,
            max_count=int(self.notifications_max_count),
            history=self.notifications_history,
        )
        self.notif_dialog = dlg

        # Любое изменение чекбокса / спинбокса сразу сохраняем в settings.json
        dlg.valuesChanged.connect(self._on_notif_settings_changed)

        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def open_spread_graph(self):
        """
        Отдельное окно с графиком прямого / обратного спреда.
        Один экземпляр на всё приложение, размер/позиция сохраняются в QSettings.
        """
        dlg = getattr(self, "graph_dialog", None)

        # если уже создавали окно — просто обновляем данные
        if dlg is None:
            dlg = SpreadGraphDialog(
                self,
                pairs=self.pairs,
                history=self.spread_history,
            )
            self.graph_dialog = dlg
        else:
            # подкидываем свежую историю в уже существующее окно
            dlg.set_data(self.pairs, self.spread_history)

        dlg.show()
        dlg.raise_()
        dlg.activateWindow()





    def _show_pending_label(self, text: str):
        """Показать маленький диалог-загрузку с крутилкой и текстом."""
        if self._pending_loader is None:
            dlg = BusyDialog(self, text=text)
            # чуть поджимаем размер (можно не трогать)
            dlg.resize(260, 130)

            # центрируем относительно главного окна
            parent_geo = self.geometry()
            x = parent_geo.center().x() - dlg.width() // 2
            y = parent_geo.center().y() - dlg.height() // 2
            dlg.move(x, y)

            self._pending_loader = dlg
        else:
            # если уже открыт — просто обновляем текст
            self._pending_loader.setText(text)

        self._pending_loader.show()
        self._pending_loader.raise_()

    def _hide_pending_label(self):
        """Спрятать диалог-загрузку."""
        if self._pending_loader is not None:
            self._pending_loader.hide()
            self._pending_loader.deleteLater()
            self._pending_loader = None

    def _update_bg_logo_geometry(self):
        """Центрируем большой логотип по центру главного окна."""
        if not getattr(self, "_bg_logo", None) or self._bg_logo_pixmap is None:
            return

        central = self.centralWidget()
        if not central:
            return

        # Берём всю центральную область, а не только scroll
        area = central.rect()
        if area.width() <= 0 or area.height() <= 0:
            return

        # Размер логотипа (например, 55% от центральной области)
        max_w = int(area.width() * 0.8)
        max_h = int(area.height() * 0.8)

        pm_scaled = self._bg_logo_pixmap.scaled(
            max_w,
            max_h,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._bg_logo.setPixmap(pm_scaled)
        self._bg_logo.resize(pm_scaled.size())

        # Центрируем по central.rect()
        x = (area.width() - self._bg_logo.width()) // 2

        offset_y = 30  # на сколько пикселей опустить логотип
        y = (area.height() - self._bg_logo.height()) // 2 + offset_y

        self._bg_logo.move(x, y)



    def _reposition_notifications(self):
        if self._notif_panel is None or not self._notif_panel.isVisible():
            return

        margin = 16
        w = self._notif_panel.width()
        h = self._notif_panel.sizeHint().height()

        # важно
        self._notif_panel.resize(w, h)

        self._notif_panel.move(
            self.width() - w - margin,
            self.height() - h - margin,
        )
        self._notif_panel.raise_()

    def _remove_notification_card(self, card: QFrame):
        """
        Удалить карточку уведомления из панели и при необходимости спрятать панель.
        """
        try:
            if card in self._notif_cards:
                self._notif_cards.remove(card)
            if self._notif_layout is not None:
                self._notif_layout.removeWidget(card)
        except Exception:
            pass

        try:
            card.deleteLater()
        except Exception:
            pass

        # если карточек больше нет — прячем панель
        if not self._notif_cards and self._notif_panel is not None:
            self._notif_panel.hide()
        else:
            self._reposition_notifications()

    def _send_telegram_message(self, text: str) -> None:
        """
        Отправка сообщения в Telegram.

        Поддерживает:
          - несколько chat_id / токенов через ';'
          - формат chat_id с message_thread_id: "-100..._264"
            (до '_' — chat_id, после '_' — ID ветки/топика).
        """
        raw_chat = (self.telegram_chat_id or "").strip()
        raw_token = (self.telegram_token or "").strip()
        if not raw_chat or not raw_token:
            return

        # Разбиваем по ';' и чистим пробелы
        chat_items = [s.strip() for s in raw_chat.split(";") if s.strip()]
        token_items = [s.strip() for s in raw_token.split(";") if s.strip()]

        if not chat_items or not token_items:
            return

        # Шлём минимум по общему количеству пар chat_id <-> token
        n = min(len(chat_items), len(token_items))

        for idx in range(n):
            chat_raw = chat_items[idx]
            token = token_items[idx]

            if not chat_raw or not token:
                continue

            chat_id = chat_raw
            thread_id = None

            # Поддержка формата -1003227839047_264
            if "_" in chat_raw:
                base, maybe_thread = chat_raw.rsplit("_", 1)
                if base.strip():
                    try:
                        thread_id = int(maybe_thread)
                        chat_id = base.strip()
                    except ValueError:
                        # если хвост не число — считаем, что это обычный chat_id
                        chat_id = chat_raw

            try:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": text,
                    "disable_web_page_preview": True,
                    "parse_mode": "HTML",
                }
                if thread_id is not None:
                    payload["message_thread_id"] = thread_id

                r = http_client.post(url, data=payload, timeout=10.0)
                if getattr(r, "status_code", 200) != 200:
                    try:
                        body = r.text[:200]
                    except Exception:
                        body = ""
                    log(
                        f"Telegram: HTTP {r.status_code} при отправке уведомления "
                        f"в chat_id={chat_id} (thread_id={thread_id}): {body}"
                    )
            except Exception as e:
                try:
                    log(
                        f"Telegram: ошибка при отправке уведомления "
                        f"в chat_id={chat_id} (thread_id={thread_id}): {e}"
                    )
                except Exception:
                    pass

    def _add_screen_notification(self, text: str):
        # добавляем ВРЕМЯ только в историю/диалог,
        # а всплывающий попап оставляем без времени
        ts = datetime.now().strftime("%H:%M:%S")
        history_line = f"[{ts}] {text}"

        # история для окна настроек
        self.notifications_history.append(history_line)
        if len(self.notifications_history) > 50:
            self.notifications_history = self.notifications_history[-50:]

        # если окно настроек уведомлений открыто — сразу добавляем туда строку
        if getattr(self, "notif_dialog", None) is not None and self.notif_dialog.isVisible():
            try:
                self.notif_dialog.append_notification(history_line)
            except Exception:
                # не ломаем основную логику, если окно вдруг упало
                pass

        # экранные уведомления вообще не зависят от Telegram
        try:
            if hasattr(self, "screen_notifications") and self.screen_notifications is not None:
                # клик по всплывающему уведомлению ОТКРЫВАЕТ окно уведомлений
                self.screen_notifications.show_notification(
                    text,  # тут БЕЗ времени
                    on_click=self.open_notifications_dialog,
                )
        except Exception as e:
            try:
                log(f"Ошибка показа экранного уведомления: {e}")
            except Exception:
                pass

    def _process_spread_alerts(self, snapshot: dict) -> None:
        """
        Проверка спредов и отправка оповещений при достижении порога.

        Экранные уведомления показываются всегда (если включены),
        Telegram — только если заполнены chat_id и token.
        """
        if not hasattr(self, "_alert_flags"):
            self._alert_flags = {}

        for pair_name, data in snapshot.items():
            pair_cfg = self.pairs.get(pair_name)
            spreads = data.get("spreads") or {}

            # индивидуальный порог для этой пары (только из tokens.json)
            thr_common = None
            thr_direct = None
            thr_reverse = None

            if pair_cfg is not None:
                # общий порог (для совместимости со старыми версиями)
                try:
                    pt = getattr(pair_cfg, "spread_threshold", None)
                    if pt is not None:
                        thr_common = float(pt)
                except Exception:
                    thr_common = None

                # новый порог для ПРЯМОГО
                try:
                    ptd = getattr(pair_cfg, "spread_direct_threshold", None)
                    if ptd is not None:
                        thr_direct = float(ptd)
                except Exception:
                    thr_direct = None

                # новый порог для ОБРАТНОГО
                try:
                    ptr = getattr(pair_cfg, "spread_reverse_threshold", None)
                    if ptr is not None:
                        thr_reverse = float(ptr)
                except Exception:
                    thr_reverse = None

            # если отдельный порог не задан, используем общий
            if thr_direct is None or thr_direct <= 0:
                thr_direct = thr_common
            if thr_reverse is None or thr_reverse <= 0:
                thr_reverse = thr_common

            # если в итоге оба направления без порога — по этой паре не шлём ничего
            if (thr_direct is None or thr_direct <= 0) and (thr_reverse is None or thr_reverse <= 0):
                continue

            base, _, quote = pair_name.partition("-")
            base = (base or "").upper() or "TOKEN"
            allow_direct = True
            allow_reverse = True
            if pair_cfg is not None:
                allow_direct = getattr(pair_cfg, "spread_direct", True)
                allow_reverse = getattr(pair_cfg, "spread_reverse", True)

            for dex_key, info in spreads.items():
                if not isinstance(info, dict):
                    continue

                dex_price = info.get("dex_price")
                cex_bid = info.get("cex_bid")
                cex_ask = info.get("cex_ask")
                direct = info.get("direct")
                reverse = info.get("reverse")

                # Человекочитаемое имя сети
                chain_name = {
                    "pancake": "BSC",
                    "jupiter": "SOL",
                    "matcha": "BASE",
                }.get(dex_key, dex_key.upper())

                # Адрес токена под конкретный DEX
                token_addr = ""
                if pair_cfg:
                    if dex_key == "pancake":
                        token_addr = getattr(pair_cfg, "bsc_address", "") or ""
                    elif dex_key == "jupiter":
                        token_addr = getattr(pair_cfg, "jupiter_mint", "") or ""
                    elif dex_key == "matcha":
                        token_addr = getattr(pair_cfg, "matcha_address", "") or ""

                # ---------- ПРЯМОЙ спред: DEX -> MEXC ----------
                key_direct = (pair_name, dex_key, "direct")

                if direct is not None:
                    try:
                        direct_val = float(direct)
                    except Exception:
                        direct_val = None
                else:
                    direct_val = None

                # ВАЖНО: без каких-либо prev/флагов — каждый тик при direct_val >= thr_direct
                if direct_val is not None and allow_direct and thr_direct is not None and thr_direct > 0:
                    if direct_val >= thr_direct:
                        lines = [
                            "‼️ПРЯМОЙ‼️",
                            "",
                            f"🚨 {base} | {direct_val:.2f}% | 🟢 | {chain_name} -> MEXC",
                            "",
                        ]

                        # Цены: сначала DEX (BSC/SOL/BASE), потом MEXC
                        if dex_price is not None:
                            lines.append(f"{chain_name}: {dex_price:.10g}")
                        if cex_bid is not None:
                            lines.append(f"MEXC: {cex_bid:.10g}")

                        # Контракт
                        if token_addr:
                            lines.append("")
                            lines.append(f"📋 <code>{token_addr}</code>")

                        msg = "\n".join(lines)

                        # короткое уведомление на экран
                        short = f"DIRECT {base}-{quote} | {chain_name} vs MEXC | {direct_val:.2f}%"
                        self._add_screen_notification(short)

                        # Телеграм сам проверит, есть ли токен/чат
                        self._send_telegram_message(msg)

                # ---------- ОБРАТНЫЙ спред: MEXC -> DEX ----------
                key_reverse = (pair_name, dex_key, "reverse")

                if reverse is not None:
                    try:
                        reverse_val = float(reverse)
                    except Exception:
                        reverse_val = None
                else:
                    reverse_val = None

                # Тоже убираем prev/флаги — каждый тик при reverse_val >= thr_reverse
                if reverse_val is not None and allow_reverse and thr_reverse is not None and thr_reverse > 0:
                    if reverse_val >= thr_reverse:
                        lines = [
                            "",
                            "❌Обратный❌",
                            "",
                            f"🚨 {base} | {reverse_val:.2f}% | 🔴 | {chain_name} -> MEXC",
                            "",
                        ]

                        # Цены: сначала DEX (BSC/SOL/BASE), потом MEXC
                        if dex_price is not None:
                            lines.append(f"{chain_name}: {dex_price:.10g}")
                        if cex_ask is not None:
                            lines.append(f"MEXC: {cex_ask:.10g}")

                        # Контракт
                        if token_addr:
                            lines.append("")
                            lines.append(f"📋 <code>{token_addr}</code>")

                        msg = "\n".join(lines)

                        short = f"REVERSE {quote}-{base} | MEXC vs {chain_name} | {reverse_val:.2f}%"
                        self._add_screen_notification(short)

                        self._send_telegram_message(msg)

    def _update_spread_history(self, snapshot: dict) -> None:
        """
        Копим историю спредов для каждого токена / DEX.
        Храним максимум ~48 часов.
        """
        if not hasattr(self, "spread_history"):
            self.spread_history = {}

        now_ts = datetime.now().timestamp()
        cutoff = now_ts - 48 * 3600  # 2 дня

        for pair_name, data in snapshot.items():
            spreads = (data or {}).get("spreads") or {}
            for dex_name, s in spreads.items():
                if not isinstance(s, dict):
                    continue
                direct = s.get("direct")
                reverse = s.get("reverse")
                if direct is None and reverse is None:
                    continue

                pair_hist = self.spread_history.setdefault(pair_name, {})
                lst: List[Tuple[float, Optional[float], Optional[float]]] = pair_hist.setdefault(
                    dex_name, []
                )
                try:
                    d_val = float(direct) if direct is not None else None
                    r_val = float(reverse) if reverse is not None else None
                except Exception:
                    continue

                lst.append((now_ts, d_val, r_val))

                # чистим старые точки
                while lst and lst[0][0] < cutoff:
                    lst.pop(0)

    def _load_spread_history_from_file(self) -> None:
        """
        Загружаем историю спреда из файла spread_history_2d.json (если он есть).
        При загрузке сразу обрезаем старые точки (старше 2 дней).
        """
        self.spread_history = {}

        path = getattr(self, "spread_history_file", None)
        if not path:
            return

        # если файла ещё нет — создаём пустой
        if not os.path.exists(path):
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({}, f, ensure_ascii=False)
            except Exception as e:
                try:
                    log(f"Не удалось создать файл истории спреда: {e}")
                except Exception:
                    pass
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f) or {}
        except Exception as e:
            try:
                log(f"Не удалось прочитать историю спреда из {path}: {e}")
            except Exception:
                pass
            return

        now_ts = datetime.now().timestamp()
        cutoff = now_ts - 48 * 3600  # 2 суток

        for pair_name, dex_dict in raw.items():
            if not isinstance(dex_dict, dict):
                continue

            for dex_name, points in dex_dict.items():
                if not isinstance(points, list):
                    continue

                cleaned: List[Tuple[float, Optional[float], Optional[float]]] = []
                for item in points:
                    # ожидаем формат [ts, direct, reverse]
                    if not isinstance(item, (list, tuple)) or len(item) != 3:
                        continue
                    try:
                        ts = float(item[0])
                        direct = None if item[1] is None else float(item[1])
                        reverse = None if item[2] is None else float(item[2])
                    except Exception:
                        continue

                    if ts >= cutoff:
                        cleaned.append((ts, direct, reverse))

                if cleaned:
                    pair_hist = self.spread_history.setdefault(pair_name, {})
                    pair_hist[dex_name] = cleaned

        # если окно графика уже открыто — подкинем ему загруженную историю
        dlg = getattr(self, "graph_dialog", None)
        if dlg is not None and dlg.isVisible():
            try:
                dlg.set_data(self.pairs, self.spread_history)
            except Exception as e:
                log(f"Ошибка обновления окна графика после загрузки истории: {e}")

    def _save_spread_history_to_file(self) -> None:
        """
        Сохраняем текущую self.spread_history в spread_history_2d.json.
        В файле остаётся только история за последние 2 дня.
        """
        path = getattr(self, "spread_history_file", None)
        if not path:
            return

        try:
            now_ts = datetime.now().timestamp()
            cutoff = now_ts - 48 * 3600  # 2 суток

            data_to_save = {}

            for pair_name, dex_dict in (self.spread_history or {}).items():
                if not isinstance(dex_dict, dict):
                    continue

                out_dex = {}
                for dex_name, points in dex_dict.items():
                    if not points:
                        continue

                    cleaned = []
                    for t, d, r in points:
                        try:
                            t_val = float(t)
                        except Exception:
                            continue
                        if t_val >= cutoff:
                            # в JSON пишем списки, не tuple
                            cleaned.append([t_val, d, r])

                    if cleaned:
                        out_dex[dex_name] = cleaned

                if out_dex:
                    data_to_save[pair_name] = out_dex

            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, ensure_ascii=False)

        except Exception as e:
            try:
                log(f"Не удалось сохранить историю спреда в {path}: {e}")
            except Exception:
                pass




    # -------- обновление данных --------
    def on_data_ready(self, snapshot: dict):
        # оставляем только те токены, которые ещё есть в self.pairs
        filtered = {
            name: data
            for name, data in snapshot.items()
            if name in self.pairs
        }

        # НОВОЕ: если активных токенов нет — возвращаемся в режим "ожидание"
        if not filtered:
            self.last_states = {}
            self.status_label.setText("Обновление: ожидание")
            self.status_label.setStyleSheet(STATUS_LABEL_IDLE)
            self.update_cards()

            # если был стартовый лоадер — гасим его
            if getattr(self, "initial_loading", False):
                self._hide_pending_label()
                if self.pending_token_name == "__initial__":
                    self.pending_token_name = None
                self.initial_loading = False

            return

        # как и раньше, когда токены есть — статус онлайн
        self.last_states = filtered
        self.status_label.setText("Обновление: онлайн")
        self.status_label.setStyleSheet(STATUS_LABEL_ONLINE)
        self.update_cards()

        # обновляем историю спредов для графика (до 2 суток)
        try:
            self._update_spread_history(filtered)
            self._save_spread_history_to_file()
        except Exception as e:
            log(f"Ошибка обновления/сохранения истории спреда: {e}")

        # если окно графика уже открыто — подкидываем ему свежие данные
        dlg = getattr(self, "graph_dialog", None)
        if dlg is not None and dlg.isVisible():
            try:
                dlg.set_data(self.pairs, self.spread_history)
            except Exception as e:
                log(f"Ошибка обновления окна графика спреда: {e}")

        try:
            self._process_spread_alerts(filtered)
        except Exception as e:
            log(f"Ошибка обработки Telegram-оповещений: {e}")

        # --- гасим стартовый лоадер, если он был ---
        if getattr(self, "initial_loading", False):
            self._hide_pending_label()
            if self.pending_token_name == "__initial__":
                self.pending_token_name = None
            self.initial_loading = False

        # проверяем появление ожидаемого токена (добавление/редактирование)
        if self.pending_token_name:
            if self.pending_token_name in self.cards:
                base = self.pending_token_name.split("-")[0]
                self.pending_token_name = None
                self._hide_pending_label()
                MessageDialog.success(self, f"Токен «{base}» добавлен.")

    def on_card_favorite_toggle(self, name: str, is_favorite: bool):
        if is_favorite:
            self.favorites.add(name)
        else:
            self.favorites.discard(name)

        # сразу сохраняем токены + избранные в tokens.json
        try:
            save_pairs_and_favorites(self.pairs, self.favorites)
        except Exception as e:
            log(f"Ошибка сохранения избранных токенов: {e}")

        # обновляем видимость карточек (режим all/fav)
        self.update_cards_visibility()

    def on_card_edit(self, name: str):
        """
        Редактирование токена: открываем то же окно, что и «Добавить токен»,
        но с другим заголовком и уже подставленным тикером.
        """
        base, _, quote = name.partition("-")
        base = base.upper()
        if not quote:
            quote = "USDT"

        # определяем, какой DEX уже использует эта пара
        initial_dex_key = None
        lock_dex = False

        cfg_current = self.pairs.get(name)
        if cfg_current is not None:
            dexes_list = getattr(cfg_current, "dexes", None)
            if dexes_list:
                # если ровно один DEX — считаем агрегатор фиксированным
                if len(dexes_list) == 1:
                    key0 = str(dexes_list[0]).lower()
                    if key0 in ("pancake", "jupiter", "matcha"):
                        initial_dex_key = key0
                        lock_dex = True

        dlg = AddTokenDialog(
            self,
            title="Изменить токен",
            ok_text="Сохранить",
            initial_token=base,
            initial_dex=initial_dex_key,
            lock_dex=lock_dex,
        )
        if dlg.exec_() != QDialog.Accepted:
            return

        dex_a, dex_b, token, j_mint, j_dec, bsc_addr, mexc_ps, matcha_addr, matcha_decimals = dlg.get_values()
        token = (token or "").strip().upper()
        if not token:
            return

        new_name = f"{token}-{quote}"

        # общий список поддерживаемых DEX
        all_dexes = {"pancake", "jupiter", "matcha"}

        if dex_a in all_dexes:
            new_dexes = {dex_a}
            dex_label = dex_a
        else:
            # на всякий случай — считаем, что нужно всё
            new_dexes = set(all_dexes)
            dex_label = dex_a or "-"

        # ---------- СЛУЧАЙ 1: имя токена НЕ меняем ----------
        # (редактированием просто добавляем DEX’ы)
        if new_name == name:
            cfg = self.pairs.get(name)
            if not cfg:
                return

            current = set(getattr(cfg, "dexes", None) or all_dexes)

            # обновляем все доступные поля
            if j_mint:
                cfg.jupiter_mint = j_mint
            if j_dec is not None:
                cfg.jupiter_decimals = j_dec
            if bsc_addr:
                cfg.bsc_address = bsc_addr
            if matcha_addr:
                cfg.matcha_address = matcha_addr
            if matcha_decimals is not None:
                cfg.matcha_decimals = matcha_decimals
            if mexc_ps is not None:
                cfg.mexc_price_scale = mexc_ps

            added = []
            # если выбрали DEX и его ещё не было — добавим
            if dex_a in all_dexes and dex_a not in current:
                current.add(dex_a)
                added = [dex_a]

            # сохраняем список DEX’ов обратно
            cfg.dexes = sorted(current) if current else None

            if added:
                MessageDialog.success(
                    self,
                    f"Для токена «{token}» добавлен(ы) DEX: {', '.join(added)}.",
                )
            else:
                MessageDialog.success(
                    self,
                    f"Настройки для токена «{token}» обновлены.",
                )

            log(
                f"Токен {name}: обновлены параметры, DEX: {', '.join(sorted(current)) or '-'}"
            )
            # ничего ждать не надо: воркер уже таскает спреды
            return

            card = self.cards.get(name)
            if card:
                card.set_link_icons(cfg)

        # ---------- СЛУЧАЙ 2: имя токена МЕНЯЕМ ----------
        # такой уже есть?
        if new_name in self.pairs and new_name != name:
            MessageDialog.error(self, f"Токен «{new_name}» уже есть в списке.")
            return

        was_fav = name in self.favorites

        # сохраняем старую конфигурацию до удаления
        old_cfg = self.pairs.get(name)
        old_dexes = getattr(old_cfg, "dexes", None) if old_cfg else None

        # удаляем старый
        if name in self.pairs:
            del self.pairs[name]
        self.last_states.pop(name, None)
        if name in self.cards:
            card = self.cards.pop(name)
            card.setParent(None)
        self.favorites.discard(name)

        # добавляем новый, перенося DEX’ы как были
        self.pairs[new_name] = PairConfig(
            name=new_name,
            base=token,
            quote=quote,
            dexes=old_dexes,
            bsc_address=bsc_addr,
            matcha_address=matcha_addr,
            matcha_decimals=matcha_decimals,
            mexc_price_scale=mexc_ps,
        )
        if was_fav:
            self.favorites.add(new_name)

        # логируем изменение токена
        log(
            f"Токен «{name}» изменён на «{new_name}» "
            f"(DEX: {dex_label}, CEX B: {dex_b or '-'})"
        )

        # ждём, пока воркер подтащит данные, и показываем лоадер
        self.pending_token_name = new_name
        self._show_pending_label(
            f"Ожидайте, меняется токен «{base}» на «{token}»…"
        )

    def on_card_delete(self, name: str):
        """
        Удаление токена: убираем из pairs, last_states, cards, favorites
        и сразу сохраняем tokens.json.
        """
        base = name.split("-")[0]

        # 1) убираем из всех структур
        if name in self.pairs:
            del self.pairs[name]
        self.last_states.pop(name, None)

        if name in self.cards:
            card = self.cards.pop(name)
            card.setParent(None)

        self.favorites.discard(name)

        # 2) если как раз ждали этот токен — сбрасываем ожидание и скрываем лоадер
        if self.pending_token_name == name:
            self.pending_token_name = None
            self._hide_pending_label()

        # 3) сразу сохраняем обновлённый список токенов и избранных в tokens.json
        save_pairs_and_favorites(self.pairs, self.favorites)

        # 4) лог и сообщение пользователю
        log(f"Токен «{name}» удалён")
        MessageDialog.success(self, f"Токен «{base}» удалён.")

    def update_cards(self):
        all_dexes = {"pancake", "jupiter", "matcha"}

        for name in sorted(self.last_states.keys()):
            if name not in self.cards:
                card = TokenCard(
                    name,
                    self.on_card_favorite_toggle,
                    edit_callback=self.on_card_edit,
                    delete_callback=self.on_card_delete,
                )
                self.cards[name] = card
                self.flow.addWidget(card)

                # --- ВАЖНО: иконки вешаем ТОЛЬКО при создании карточки ---
                cfg_init = self.pairs.get(name)
                if cfg_init is not None:
                    card.set_link_icons(cfg_init)

            card = self.cards[name]

            # НОВОЕ: восстанавливаем состояние звезды по self.favorites
            card.set_favorite(name in self.favorites)
            spreads_all = self.last_states[name].get("spreads", {})

            cfg = self.pairs.get(name)
            if cfg is not None:
                active_dexes = set(getattr(cfg, "dexes", None) or all_dexes)
            else:
                active_dexes = all_dexes

            # !!! БЫЛО: card.set_link_icons(cfg)
            # УБРАЛИ, чтобы не пересоздавать иконки каждую секунду

            # в spreads передаём только активные DEX
            filtered_spreads = {
                k: v for k, v in spreads_all.items() if k in active_dexes
            }

            card.update_spreads(filtered_spreads)
            card.set_visible_dexes(self.visible_dexes)

        # чистим лишние карточки, которых больше нет в данных
        for name in list(self.cards.keys()):
            if name not in self.last_states:
                card = self.cards.pop(name)
                card.setParent(None)

        self.update_cards_visibility()

    def update_cards_visibility(self):
        """
        Прячет/показывает карточки токенов с учётом:
          - выбранной CEX (self.current_cex)
          - режима (все / избранные)
          - фильтра DEX (self.visible_dexes)
        """
        mode = self.current_mode
        has_cex = self.current_cex is not None
        all_dexes = {"pancake", "jupiter", "matcha"}
        selected_dexes = set(self.visible_dexes or set())

        # отключаем лишние перерисовки
        self.cards_host.setUpdatesEnabled(False)
        try:
            for name, card in self.cards.items():
                # Если биржа не выбрана — ничего не показываем
                if not has_cex:
                    card.hide()
                    continue

                # Если ни один DEX не выбран — тоже ничего не показываем
                if not selected_dexes:
                    card.hide()
                    continue

                # Берём список DEX’ов, по которым реально есть этот токен
                cfg = self.pairs.get(name)
                if cfg is not None:
                    token_dexes = set(getattr(cfg, "dexes", None) or all_dexes)
                else:
                    token_dexes = all_dexes

                # Если пересечения с выбранными DEX нет — прячем карточку целиком
                if not (token_dexes & selected_dexes):
                    card.hide()
                    continue

                # Дальше фильтр по режиму (все / избранные)
                if mode == "all":
                    card.show()
                else:
                    card.setVisible(name in self.favorites)
        finally:
            self.cards_host.setUpdatesEnabled(True)
            self.flow.invalidate()
            self.cards_host.updateGeometry()

    def _hit_test_resize_zone(self, global_pos):
        """
        Проверяем, попала ли мышь в зону ресайза.
        Возвращаем:
          "br"     – правый нижний угол
          "right"  – правый край
          "left"   – левый край
          "bottom" – нижний край
          None     – вне зоны ресайза
        """
        if self._is_maximized or self.isMaximized():
            return None

        local = self.mapFromGlobal(global_pos)
        rect = self.rect()
        m = self._resize_margin

        left = local.x() <= m
        right = local.x() >= rect.width() - m
        bottom = local.y() >= rect.height() - m

        # приоритет угла
        if right and bottom:
            return "br"
        if right:
            return "right"
        if left:
            return "left"
        if bottom:
            return "bottom"
        return None

    def eventFilter(self, obj, event):
        """
        Обработчик ресайза по краю для всего приложения.
        ВАЖНО: не трогаем диалоги/другие окна, чтобы не ломать перетаскивание лог-окна.
        """
        # Обрабатываем только события, которые приходят от самого окна
        # или от центрального виджета. Всё остальное (диалоги, меню и т.п.)
        # пропускаем мимо.
        if obj is not self and obj is not self.centralWidget():
            return False

        et = event.type()

        if et == QEvent.MouseMove:
            gp = event.globalPos()

            if self._resizing and self._resize_edge:
                # тянем активный край/угол
                dx = gp.x() - self._resize_start_mouse.x()
                dy = gp.y() - self._resize_start_mouse.y()
                g = self._resize_start_geom

                min_w = self.minimumWidth()
                min_h = self.minimumHeight()

                x = g.x()
                y = g.y()
                w = g.width()
                h = g.height()

                edge = self._resize_edge

                if edge in ("right", "br"):
                    new_w = max(min_w, w + dx)
                    w = new_w
                if edge == "left":
                    new_w = max(min_w, w - dx)
                    # сдвигаем левую границу, чтобы правый край стоял на месте
                    x = g.x() + (w - new_w)
                    w = new_w

                if edge in ("bottom", "br"):
                    new_h = max(min_h, h + dy)
                    h = new_h

                self.setGeometry(x, y, w, h)
                return False
            else:
                # просто подсвечиваем курсор, если в зоне ресайза
                zone = self._hit_test_resize_zone(gp)
                if zone == "br":
                    self.setCursor(Qt.SizeFDiagCursor)
                elif zone in ("right", "left"):
                    self.setCursor(Qt.SizeHorCursor)
                elif zone == "bottom":
                    self.setCursor(Qt.SizeVerCursor)
                else:
                    if not self._resizing:
                        self.unsetCursor()
                return False

        elif et == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            gp = event.globalPos()
            zone = self._hit_test_resize_zone(gp)
            if zone is not None:
                self._resizing = True
                self._resize_edge = zone
                self._resize_start_mouse = gp
                self._resize_start_geom = self.geometry()
                return True  # "съели" событие

        elif et == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            if self._resizing:
                self._resizing = False
                self._resize_edge = None
                self.unsetCursor()
                return True

        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # если открыт мини-лоадер — центрируем его заново
        if getattr(self, "_pending_loader", None) is not None and self._pending_loader.isVisible():
            dlg = self._pending_loader
            parent_geo = self.geometry()
            cx = parent_geo.center().x()
            cy = parent_geo.center().y()
            x = cx - dlg.width() // 2
            y = cy - dlg.height() // 2
            dlg.move(x, y)

        # обновляем позицию панели уведомлений (правый нижний угол)
        self._reposition_notifications()

        # и позицию большого логотипа на фоне
        self._update_bg_logo_geometry()

    def closeEvent(self, event):
        # сохраняем текущие токены и избранные перед выходом
        try:
            save_pairs_and_favorites(self.pairs, self.favorites)
        except Exception:
            pass

        try:
            self.worker.stop()
            self.worker.wait(2000)
        except Exception:
            pass
        try:
            http_client.close()
        except Exception:
            pass
        event.accept()


def main():
    app = QApplication(sys.argv)

    # путь к логотипу
    logo_path = os.path.join(str(RESOURCE_DIR), "icon", "mainLogo.png")

    pix = None
    if os.path.exists(logo_path):
        # иконка приложения
        app.setWindowIcon(QIcon(logo_path))
        pix = QPixmap(logo_path)

    # стиль тултипов
    app.setStyleSheet(TOOLTIP_STYLE + DEX_MENU)

    splash = None
    if pix is not None and not pix.isNull():
        # показываем сплэш на основе того же mainLogo.png
        splash = QSplashScreen(pix)
        splash.setWindowFlag(Qt.FramelessWindowHint)
        splash.setWindowFlag(Qt.WindowStaysOnTopHint)
        splash.show()
        app.processEvents()

    # через 3 секунды запускаем основное окно
    # (можешь поменять 3000 на 4000–6000 по вкусу)
    def start_main_window():
        saved_favs = load_saved_pairs_and_favorites()
        win = SpreadMonitorWindow(PAIRS)

        if saved_favs:
            win.favorites = saved_favs

        win.show()

        # закрываем сплэш, если был
        if splash is not None:
            splash.finish(win)

    QTimer.singleShot(3000, start_main_window)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()