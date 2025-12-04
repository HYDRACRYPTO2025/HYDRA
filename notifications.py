from typing import Iterable, List, Callable, Optional
import html
from datetime import datetime
from PyQt5.QtCore import Qt, QSize, QPoint, QRect, QTimer, pyqtSignal, QObject, QPropertyAnimation, QEvent
from PyQt5.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QSpinBox,
    QScrollArea,
    QWidget,
    QGridLayout,
    QApplication,
    QGraphicsOpacityEffect,
)

from ui_parts import DraggableDialog, make_close_icon
from styles import (
    DIALOG_LOG,
    DIALOG_ADD,
    LABEL_DIALOG_TITLE,
    LABEL_SECTION,
    LABEL_FORM,
    BUTTON_CLEAR,
    BUTTON_PRIMARY,
    BUTTON_ROUND_ICON,
    SCROLLBAR_DARK,
    CHECKBOX_SPREAD_INLINE,
    # новые
    TRANSPARENT_BG,
    PANEL_DARK_BG,
    SCROLLAREA_DARK,
    DIALOG_FRAME,
    SCREEN_NOTIF_TITLE,
    SCREEN_NOTIF_TEXT,
    SCREEN_NOTIF_FRAME_TEMPLATE,
    SPINBOX_MAX_NOTIF,
    SCREEN_NOTIF_CLOSE_BUTTON,
    get_direct_spread_mid_color,
    get_reverse_spread_mid_color,
)
def colorize_direction_words(text: str) -> str:
    """
    Красит слова Reverse/Direct в цвета текущих палитр
    (средний оттенок прямого/обратного спреда).
    Работает и для истории, и для всплывающих уведомлений.
    """
    safe = html.escape(text)

    reverse_color = get_reverse_spread_mid_color()
    direct_color = get_direct_spread_mid_color()

    # КРАСНЫЙ (но теперь из палитры) для reverse / реверс
    red_words = ["REVERSE", "Reverse", "reverse", "Реверс", "реверс"]
    for w in red_words:
        safe = safe.replace(
            w,
            f'<span style="color:{reverse_color};">{w}</span>'
        )

    # ЗЕЛЁНЫЙ (из палитры) для direct / директ
    green_words = ["DIRECT", "Direct", "direct", "Директ", "директ"]
    for w in green_words:
        safe = safe.replace(
            w,
            f'<span style="color:{direct_color};">{w}</span>'
        )

    return safe



class ScreenNotificationPopup(QWidget):


    BASE_HEIGHT = 90
    """Одна всплывающая карточка (экранное уведомление)."""

    closed = pyqtSignal(object)  # сигнал: popup сам закрылся

    def __init__(
        self,
        text: str,
        timeout_ms: int = 5000,
        parent: Optional[QWidget] = None,
        on_click: Optional[Callable[[], None]] = None,
        border_color: str = "#22c55e",   # зелёный по умолчанию
    ) -> None:
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        super().__init__(parent, flags=flags)

        self._on_click = on_click
        self._is_fading_out = False
        self._border_color = border_color
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        super().__init__(parent, flags=flags)

        self._on_click = on_click
        self._is_fading_out = False

        # без системной рамки и с прозрачным фоном вокруг
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setStyleSheet(TRANSPARENT_BG)

        # эффект прозрачности для анимаций
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(0.0)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        frame = QWidget()
        frame.setObjectName("screenNotificationFrame")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(10, 8, 10, 10)
        frame_layout.setSpacing(4)

        # верхняя строка: заголовок + крестик
        top = QHBoxLayout()
        lbl_title = QLabel("Уведомление")
        lbl_title.setStyleSheet(SCREEN_NOTIF_TITLE)
        top.addWidget(lbl_title)
        top.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(18, 18)

        btn_close.setStyleSheet(SCREEN_NOTIF_CLOSE_BUTTON)
        btn_close.clicked.connect(self._start_fade_out)
        top.addWidget(btn_close)
        frame_layout.addLayout(top)

        # текст уведомления
        lbl_text = QLabel(text)
        lbl_text.setWordWrap(True)
        lbl_text.setStyleSheet(SCREEN_NOTIF_TEXT)
        lbl_text.setTextFormat(Qt.PlainText)
        frame_layout.addWidget(lbl_text)

        root.addWidget(frame)

        # фон + ЗЕЛЁНАЯ рамка как у "скопировано", но чуть толще
        frame.setStyleSheet(
            SCREEN_NOTIF_FRAME_TEMPLATE.format(
                border_color=self._border_color
            )
        )

        # фиксируем минимальную высоту карточки,
        # чтобы все однострочные были одинаковые
        self.setMinimumHeight(self.BASE_HEIGHT)

        # таймер авто-закрытия
        self._timeout_ms = int(timeout_ms)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        if self._timeout_ms > 0:
            self._timer.timeout.connect(self._start_fade_out)

        # плавное появление
        self._fade_anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade_anim.setDuration(150)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def _start_fade_out(self) -> None:
        if self._is_fading_out:
            return
        self._is_fading_out = True

        effect = self._effect or QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(200)
        anim.setStartValue(effect.opacity())
        anim.setEndValue(0.0)

        def _finish():
            # обычное закрытие — сработает closeEvent, там уже есть closed.emit
            super(ScreenNotificationPopup, self).close()

        anim.finished.connect(_finish)
        anim.start()
        self._fade_anim = anim

    def mousePressEvent(self, event) -> None:
        # клик ЛКМ по уведомлению — открыть окно уведомлений + плавно скрыть
        if event.button() == Qt.LeftButton and self._on_click is not None:
            self._on_click()
            self._start_fade_out()
            event.accept()
            return
        super().mousePressEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        # сообщаем менеджеру, что нас закрыли
        self.closed.emit(self)
        super().closeEvent(event)

    def start_timeout(self) -> None:
        """Запустить таймер автозакрытия (зовётся менеджером при показе)."""
        if getattr(self, "_timeout_ms", 0) > 0 and self._timer is not None:
            self._timer.start(self._timeout_ms)


class ScreenNotificationManager(QObject):
    """Менеджер экранных уведомлений.

    ✔ показывает каждое новое уведомление справа внизу ЭКРАНА
    ✔ одновременно до max_visible карточек — одна НАД другой
    ✔ лишние не пропадают, а ждут в очереди
    ✔ вообще никак не зависит от Telegram
    """

    def __init__(
        self,
        anchor_widget: QWidget,
        *,
        enabled: bool = True,
        max_visible: int = 2,
        timeout_ms: int = 6000,
        margin: int = 16,
        spacing: int = 8,
    ) -> None:
        super().__init__(anchor_widget)
        self._anchor = anchor_widget
        self._enabled = bool(enabled)
        self._max_visible = max(1, int(max_visible))

        # базовый таймаут и "быстрый", когда есть очередь
        self._timeout_ms_long = int(timeout_ms)
        self._timeout_ms_short = min(self._timeout_ms_long, 3000)

        self._margin = margin
        self._spacing = spacing

        self._active: List[ScreenNotificationPopup] = []
        self._queue: List[ScreenNotificationPopup] = []
        self._history: List[str] = []

    # ==== публичное API ====

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_max_visible(self, n: int) -> None:
        self._max_visible = max(1, int(n))
        self._reposition()

    @property
    def max_visible(self) -> int:
        return self._max_visible

    @property
    def history(self) -> List[str]:
        # наружу только копию
        return list(self._history)

    def clear_history(self) -> None:
        self._history.clear()

    def show_notification(
            self,
            text: str,
            on_click: Optional[Callable[[], None]] = None,
            border_color: Optional[str] = None,
    ) -> None:
        """Показать новое уведомление (НЕ зависит от Telegram)."""

        # добавляем время только в ИСТОРИЮ,
        # а текст попапа оставляем чистым
        ts = datetime.now().strftime("%H:%M:%S")
        history_line = f"[{ts}] {text}"
        self._history.append(history_line)

        if not self._enabled:
            # экранные отключены – только пишем в историю
            return

        # если уже есть очередь — ускоряемся до 3 сек
        if self._queue:
            timeout_ms = self._timeout_ms_short
        else:
            timeout_ms = self._timeout_ms_long

        # --- выбор цвета рамки ---
        if border_color is None:
            upper_text = text.upper()

            if upper_text.startswith("REVERSE "):
                border_color = get_reverse_spread_mid_color()
            else:
                border_color = get_direct_spread_mid_color()

        popup = ScreenNotificationPopup(
            text=text,  # здесь по-прежнему БЕЗ времени
            timeout_ms=timeout_ms,
            parent=None,
            on_click=on_click,
            border_color=border_color,
        )
        popup.closed.connect(self._on_popup_closed)

        if len(self._active) < self._max_visible:
            self._show_popup_now(popup)
        else:
            self._queue.append(popup)

    # ==== внутренняя логика ====

    def _anchor_geometry(self) -> QRect:
        """Берём ВСЁ окно экрана, а не окно программы."""
        screen = QApplication.primaryScreen()
        if screen is not None:
            return screen.availableGeometry()
        return QRect(0, 0, 800, 600)

    def _show_popup_now(self, popup: ScreenNotificationPopup) -> None:
        self._active.append(popup)

        # геометрия экрана
        geom = self._anchor_geometry()
        available_width = max(220, geom.width() - 2 * self._margin)
        width = min(320, available_width)

        # высота: не меньше базовой, но если текста много — берём больше
        h = popup.sizeHint().height()
        if h <= 0:
            h = popup.height()
        if not h or h <= 0:
            h = ScreenNotificationPopup.BASE_HEIGHT
        if h < ScreenNotificationPopup.BASE_HEIGHT:
            h = ScreenNotificationPopup.BASE_HEIGHT

        popup.resize(width, h)
        self._reposition()
        popup.show()

        # запускаем таймер только теперь, когда попап реально показан
        try:
            popup.start_timeout()
        except AttributeError:
            # на случай, если где-то старый объект без этого метода — не падаем
            pass

    def _reposition(self) -> None:
        """Расставляем активные карточки справа внизу столбиком вверх."""
        if not self._active:
            return

        # подчищаем "мёртвые" виджеты, если Qt их уже удалил
        alive: List[ScreenNotificationPopup] = []
        for popup in self._active:
            try:
                popup.sizeHint()
            except RuntimeError:
                continue
            else:
                alive.append(popup)
        self._active = alive
        if not self._active:
            return

        geom = self._anchor_geometry()

        right = geom.right() - self._margin
        bottom = geom.bottom() - self._margin

        # старый порядок: self._active = [старые -> новые]
        popups = list(self._active)

        # ширина карточек: не шире 320 и обязательно влезает между margin'ами
        available_width = max(220, geom.width() - 2 * self._margin)
        width = min(320, available_width)

        # начинаем от низа и поднимаемся вверх: новые снизу, старые над ними
        y = bottom
        for popup in reversed(popups):  # идём: новые -> старые
            h = popup.sizeHint().height()
            if h <= 0:
                h = popup.height()
            if not h or h <= 0:
                h = ScreenNotificationPopup.BASE_HEIGHT
            if h < ScreenNotificationPopup.BASE_HEIGHT:
                h = ScreenNotificationPopup.BASE_HEIGHT

            popup.resize(width, h)
            x = right - width

            y -= h  # место для карточки
            popup.move(x, y)  # ставим её
            y -= self._spacing

    def _on_popup_closed(self, popup: ScreenNotificationPopup) -> None:
        # карточка закрылась (сама по таймеру или крестик)
        if popup in self._active:
            self._active.remove(popup)
        if popup in self._queue:
            self._queue.remove(popup)
        popup.deleteLater()

        # если в очереди что-то есть – показываем следующее
        if self._queue and len(self._active) < self._max_visible:
            next_popup = self._queue.pop(0)
            self._show_popup_now(next_popup)
        else:
            self._reposition()


class NotificationSettingsDialog(DraggableDialog):
    """
    Окно настроек уведомлений спреда:
      - включить/выключить всплывающие уведомления
      - макс. количество одновременно отображаемых всплывающих уведомлений
      - история последних уведомлений
    """
    # сигнал: любое изменение чекбокса/спинбокса
    # bool  -> включены ли всплывающие уведомления
    # int   -> максимальное количество одновременных уведомлений
    valuesChanged = pyqtSignal(bool, int)

    _RESIZE_MARGIN = 6

    def __init__(
        self,
        parent=None,
        enabled: bool = True,
        max_count: int = 3,
        history: Iterable[str] | None = None,
    ):
        super().__init__(parent)

        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(False)

        # прозрачный фон вокруг, как у других диалогов
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._resize_active = False
        self._resize_edge: str | None = None
        self._resize_start_geom: QRect | None = None
        self._resize_start_mouse = None

        self.setMouseTracking(True)

        # в этих переменных будем хранить историю логов
        self._history: list[str] = list(history or [])
        self._history_layout: QVBoxLayout | None = None
        self._history_placeholder: QLabel | None = None

        # внешний layout на весь диалог (0 отступов)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # внутренняя "карточка" с красивыми скруглёнными углами
        frame = QWidget()
        frame.setObjectName("dialogFrame")
        frame.setAttribute(Qt.WA_StyledBackground, True)
        frame.setStyleSheet(DIALOG_FRAME)

        frame.setMouseTracking(True)
        frame.installEventFilter(self)

        # основной layout уже внутри фрейма
        main = QVBoxLayout(frame)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(12)

        outer.addWidget(frame)




        # ---------- заголовок ----------
        header = QHBoxLayout()
        lbl_title = QLabel("Уведомления спреда")
        lbl_title.setStyleSheet(LABEL_DIALOG_TITLE)
        header.addWidget(lbl_title)
        header.addStretch()

        btn_close = QPushButton()
        btn_close.setFixedSize(30, 30)
        btn_close.setAttribute(Qt.WA_StyledBackground, True)  # как в логе
        btn_close.setStyleSheet(BUTTON_ROUND_ICON)
        btn_close.setIcon(make_close_icon())
        btn_close.setIconSize(QSize(18, 18))

        btn_close.clicked.connect(self.reject)
        header.addWidget(btn_close)

        main.addLayout(header)

        # доп. отступ между заголовком и первой строкой
        main.addSpacing(12)

        # ---------- настройки в виде сетки (2 строки, 2 колонки) ----------
        grid = QGridLayout()
        grid.setColumnStretch(0, 1)  # левый столбец тянется
        grid.setColumnStretch(1, 0)  # правый — под контролы

        # строка 0: чекбокс
        lbl_enabled = QLabel("Показывать всплывающие уведомления")
        lbl_enabled.setStyleSheet(LABEL_FORM)
        grid.addWidget(lbl_enabled, 0, 0)

        self.chk_enabled = QCheckBox()
        self.chk_enabled.setChecked(bool(enabled))
        self.chk_enabled.setStyleSheet(CHECKBOX_SPREAD_INLINE)

        self.chk_enabled.setCursor(Qt.PointingHandCursor)

        # делаем ширину такой же, как у спинбокса, чтобы правая граница совпадала
        self.chk_enabled.setFixedWidth(70)
        self.chk_enabled.setFixedHeight(22)

        grid.addWidget(self.chk_enabled, 0, 1, alignment=Qt.AlignRight | Qt.AlignVCenter)

        # строка 1: максимум карточек
        lbl_max = QLabel("Максимум карточек одновременно")
        lbl_max.setStyleSheet(LABEL_FORM)
        grid.addWidget(lbl_max, 1, 0)

        self.spin_max = QSpinBox()
        self.spin_max.setRange(1, 3)
        self.spin_max.setSingleStep(1)

        # значение по умолчанию (1..3)
        self.spin_max.setValue(max(1, min(3, int(max_count or 1))))

        # мягкий фон и скруглённые углы
        self.spin_max.setStyleSheet(SPINBOX_MAX_NOTIF)

        self.spin_max.setFixedWidth(70)
        grid.addWidget(self.spin_max, 1, 1, alignment=Qt.AlignRight | Qt.AlignVCenter)
        self.chk_enabled.stateChanged.connect(self._on_controls_changed)
        self.spin_max.valueChanged.connect(self._on_controls_changed)

        main.addLayout(grid)

        # ---------- заголовок истории ----------
        main.addSpacing(8)
        lbl_hist = QLabel("Последние уведомления")
        lbl_hist.setStyleSheet(LABEL_SECTION)
        main.addWidget(lbl_hist)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(160)

        # делаем такое же «квадратное» поле с рамкой, как у других виджетов
        scroll.setStyleSheet(SCROLLAREA_DARK)

        container = QWidget()
        # фон берём из scroll'а, чтобы не было двойной заливки
        container.setStyleSheet(TRANSPARENT_BG)
        v = QVBoxLayout(container)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(4)

        self._history_layout = v
        self._history_placeholder = None

        # первый рендер истории
        self._rebuild_history_widgets()

        scroll.setWidget(container)
        main.addWidget(scroll)

        self.resize(480, 460)  # чуть шире и выше
        self.setMinimumSize(400, 360)



    def _rebuild_history_widgets(self) -> None:
        """Перестроить виджет истории по self._history (лайв-обновление)."""
        if self._history_layout is None:
            return

        layout = self._history_layout

        # очищаем старые виджеты
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        self._history_placeholder = None

        if self._history:
            # показываем от новых к старым
            for text in reversed(self._history):
                lab = QLabel(colorize_direction_words(text))
                lab.setStyleSheet(LABEL_FORM)
                lab.setWordWrap(True)
                lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
                lab.setTextFormat(Qt.RichText)
                layout.addWidget(lab)
        else:
            placeholder = QLabel("Пока нет ни одного уведомления")
            placeholder.setStyleSheet(LABEL_FORM)
            placeholder.setEnabled(False)
            layout.addWidget(placeholder)
            self._history_placeholder = placeholder

        layout.addStretch()

    def eventFilter(self, obj, event):
        # Перехватываем движения мыши по внутреннему frame,
        # чтобы корректно обновлять курсор (стрелочки ресайза)
        if event.type() == QEvent.MouseMove:
            # глобальные → в систему координат диалога
            global_pos = event.globalPos()
            local_pos = self.mapFromGlobal(global_pos)

            # если не тянем и кнопка не зажата — просто меняем курсор
            if not (event.buttons() & Qt.LeftButton) and not self._resize_active:
                self._update_cursor(local_pos)

        # остальное обрабатываем как обычно
        return super().eventFilter(obj, event)


    # ======== переопределение событий мыши для ресайза =========

    def _detect_edge(self, pos: QPoint) -> str | None:
        """Определяем, у какой границы мышь (для изменения размера)."""
        r = self.rect()
        x, y = pos.x(), pos.y()
        m = self._RESIZE_MARGIN

        left = x <= r.left() + m
        right = x >= r.right() - m
        top = y <= r.top() + m
        bottom = y >= r.bottom() - m

        if top and left:
            return "topleft"
        if top and right:
            return "topright"
        if bottom and left:
            return "bottomleft"
        if bottom and right:
            return "bottomright"
        if left:
            return "left"
        if right:
            return "right"
        if top:
            return "top"
        if bottom:
            return "bottom"
        return None

    def _update_cursor(self, pos: QPoint) -> None:
        edge = self._detect_edge(pos)
        if edge in ("left", "right"):
            self.setCursor(Qt.SizeHorCursor)
        elif edge in ("top", "bottom"):
            self.setCursor(Qt.SizeVerCursor)
        elif edge in ("topleft", "bottomright"):
            self.setCursor(Qt.SizeFDiagCursor)
        elif edge in ("topright", "bottomleft"):
            self.setCursor(Qt.SizeBDiagCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            edge = self._detect_edge(event.pos())
            if edge:
                # запускаем режим ресайза
                self._resize_active = True
                self._resize_edge = edge
                self._resize_start_geom = self.geometry()
                self._resize_start_mouse = event.globalPos()
                event.accept()
                return
        # если не у границы — обычное перетаскивание от DraggableDialog
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # --- режим ресайза ---
        if self._resize_active and (event.buttons() & Qt.LeftButton):
            if not (self._resize_start_geom and self._resize_start_mouse):
                return

            delta = event.globalPos() - self._resize_start_mouse
            g = QRect(self._resize_start_geom)

            min_w = self.minimumWidth()
            min_h = self.minimumHeight()

            # горизонталь
            if "left" in self._resize_edge:
                new_left = g.left() + delta.x()
                max_left = g.right() - min_w
                new_left = min(new_left, max_left)
                g.setLeft(new_left)
            if "right" in self._resize_edge:
                new_right = g.right() + delta.x()
                min_right = g.left() + min_w
                if new_right < min_right:
                    new_right = min_right
                g.setRight(new_right)

            # вертикаль
            if "top" in self._resize_edge:
                new_top = g.top() + delta.y()
                max_top = g.bottom() - min_h
                new_top = min(new_top, max_top)
                g.setTop(new_top)
            if "bottom" in self._resize_edge:
                new_bottom = g.bottom() + delta.y()
                min_bottom = g.top() + min_h
                if new_bottom < min_bottom:
                    new_bottom = min_bottom
                g.setBottom(new_bottom)

            self.setGeometry(g)
            event.accept()
            return

        # --- кнопка не нажата: просто обновляем курсор у границы ---
        if not (event.buttons() & Qt.LeftButton):
            self._update_cursor(event.pos())
            event.accept()
            return

        # --- ЛКМ зажата, но не ресайзим: даём DraggableDialog двигать окно ---
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._resize_active:
            self._resize_active = False
            self._resize_edge = None
            self._resize_start_geom = None
            self._resize_start_mouse = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def set_history(self, history: Iterable[str]) -> None:
        """Полностью заменить историю и обновить отображение."""
        self._history = list(history or [])
        self._rebuild_history_widgets()

    def append_notification(self, text: str) -> None:
        """Добавить одно новое уведомление в историю и сразу показать его."""
        # сохраняем в историю (как раньше)
        self._history.append(text)

        # если layout ещё не создан – просто выходим
        if self._history_layout is None:
            return

        layout = self._history_layout

        # если был плейсхолдер "Пока нет ни одного уведомления" – убираем его
        if self._history_placeholder is not None:
            layout.removeWidget(self._history_placeholder)
            self._history_placeholder.deleteLater()
            self._history_placeholder = None

        # создаём виджет для НОВОГО уведомления
        lab = QLabel(colorize_direction_words(text))
        lab.setStyleSheet(LABEL_FORM)
        lab.setWordWrap(True)
        lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lab.setTextFormat(Qt.RichText)

        # новые уведомления – сверху (как и было в _rebuild_history_widgets)
        layout.insertWidget(0, lab)

    # забираем значения наружу
    def get_values(self) -> tuple[bool, int]:
        return self.chk_enabled.isChecked(), int(self.spin_max.value())

    def _on_controls_changed(self) -> None:
        """Когда пользователь меняет чекбокс/кол-во — сообщаем наружу."""
        self.valuesChanged.emit(
            self.chk_enabled.isChecked(),
            int(self.spin_max.value()),
        )