from datetime import datetime
import math
import time
import queue
from typing import List, Tuple, Optional, Dict
from PyQt5.QtCore import (
    Qt,
    QRect,
    QSize,
    QPoint,
    QEvent,
    QPropertyAnimation,
    pyqtProperty,
    QEasingCurve,
    QSettings,
    QThread,
    pyqtSignal,
    QTimer,
)
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
)

from ui_parts import DraggableDialog, make_close_icon, StickyMenu, attach_menu_arrow
from styles import (
    DIALOG_FRAME,
    LABEL_DIALOG_TITLE,
    LABEL_FORM,
    LABEL_SMALL_MUTED,
    BUTTON_ROUND_ICON,
    PANEL_DARK_BG,
    BUTTON_TOP_DARK_NO_ARROW,
    DEX_MENU,
    get_direct_spread_mid_color,
    get_reverse_spread_mid_color,
    SPREAD_BOX_BASE,
    STATUS_LABEL_IDLE,
    STATUS_LABEL_ONLINE,
)
from core import PairConfig, fetch_L_M_for_pair, load_settings

class LmWorker(QThread):

    # dialog, pair_key, data (dict или None)
    result_ready = pyqtSignal(object, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: "queue.Queue[tuple]" = queue.Queue()
        self._stopped = False

    def enqueue(self, dialog, pair_key: str, cfg: PairConfig) -> None:

        try:
            self._queue.put_nowait((dialog, pair_key, cfg))
        except Exception:
            # на всякий случай, чтобы не уронить UI
            pass

    def stop(self) -> None:
        self._stopped = True
        # подкинем пустую задачу, чтобы разбудить .get()
        try:
            self._queue.put_nowait((None, None, None))
        except Exception:
            pass

    def run(self) -> None:  # type: ignore[override]
        last_ts = 0.0

        while not self._stopped:
            dialog, pair_key, cfg = self._queue.get()
            if self._stopped:
                break

            # если положили "пустую" задачу для остановки — пропускаем
            if dialog is None or cfg is None:
                continue

            # выдерживаем паузу минимум 10 секунд между токенами
            try:
                cfg_settings = load_settings()
                min_delay = float(cfg_settings.get("interval_sec", 20.0))
            except Exception:
                min_delay = 20.0

                # на всякий случай не даём поставить совсем 0
            if min_delay <= 0:
                min_delay = 15.0

                now = time.time()
                delta = now - last_ts
                if last_ts > 0 and delta < min_delay:
                    try:
                        time.sleep(min_delay - delta)
                    except Exception:
                        pass
            last_ts = time.time()

            data = None
            try:
                # Здесь как раз и идут запросы к MEXC + CoinGecko
                data = fetch_L_M_for_pair(cfg)
            except Exception:
                data = None

            # возвращаем результат в UI-поток
            self.result_ready.emit(dialog, pair_key, data or {})


_LM_WORKER: "LmWorker | None" = None


def get_lm_worker() -> LmWorker:
    """
    Ленивое создание глобального воркера. Один на всё приложение.
    """
    global _LM_WORKER
    if _LM_WORKER is None:
        _LM_WORKER = LmWorker()
        _LM_WORKER.start()
    return _LM_WORKER
# История:
# pair_name -> dex_name -> список (timestamp, direct, reverse)
HistoryDict = Dict[str, Dict[str, List[Tuple[float, Optional[float], Optional[float]]]]]


class SpreadChartWidget(QWidget):
    """
    Простой кастомный график прямого / обратного спреда.
    Без сторонних библиотек, только QPainter.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._points: List[Tuple[float, Optional[float], Optional[float]]] = []
        self._view_t_min: Optional[float] = None
        self._view_t_max: Optional[float] = None
        self.setMinimumHeight(260)
        self.setAutoFillBackground(False)

        # --- для hover-подсказки ---
        self.setMouseTracking(True)
        self._hover_point: Optional[Tuple[float, Optional[float], Optional[float]]] = None
        self._hover_opacity: float = 0.0

        self._hover_anim = QPropertyAnimation(self, b"hoverOpacity", self)
        self._hover_anim.setDuration(160)  # скорость появления/исчезновения
        self._hover_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._hover_anim.finished.connect(self._on_hover_anim_finished)

    # --- свойство для анимации прозрачности hover-оверлея ---
    def getHoverOpacity(self) -> float:
        return self._hover_opacity

    def setHoverOpacity(self, value: float) -> None:
        self._hover_opacity = value
        self.update()

    hoverOpacity = pyqtProperty(float, fget=getHoverOpacity, fset=setHoverOpacity)

    # --- служебное: прямоугольник области графика ---
    def _plot_rect(self) -> QRect:
        full = self.rect()
        left_margin = 60
        top_margin = 20      # чуть больше воздуха сверху
        right_margin = 44
        bottom_margin = 40   # место под подписи времени
        return full.adjusted(left_margin, top_margin, -right_margin, -bottom_margin)

    def reset_view(self) -> None:
        """Сбросить зум к полному диапазону данных."""
        self._view_t_min = None
        self._view_t_max = None
        self.update()

    def set_points(
        self,
        points: List[Tuple[float, Optional[float], Optional[float]]],
        *,
        reset_view: bool = False,
    ) -> None:
        self._points = list(points or [])

        if reset_view:
            self._view_t_min = None
            self._view_t_max = None

        # всегда сбрасываем hover
        self._hover_point = None
        self._hover_opacity = 0.0
        self.update()

    # --- расчёт диапазонов X/Y для текущих данных и зума ---
    def _compute_ranges(self):
        if not self._points:
            return None

        xs = [t for (t, _, _) in self._points]
        directs = [d for (_, d, _) in self._points]
        reverses = [r for (_, _, r) in self._points]

        # проверяем, есть ли вообще хоть одно числовое значение
        any_values = any(v is not None for v in directs + reverses)
        if not any_values:
            return None

        # диапазон по X (данные и видимая область)
        data_t_min = min(xs)
        data_t_max = max(xs)
        if data_t_max == data_t_min:
            data_t_max = data_t_min + 1.0

        view_t_min = self._view_t_min if self._view_t_min is not None else data_t_min
        view_t_max = self._view_t_max if self._view_t_max is not None else data_t_max

        # корректируем, чтобы окно просмотра не вываливалось за данные
        if view_t_max <= view_t_min:
            view_t_min, view_t_max = data_t_min, data_t_max

        if view_t_min < data_t_min:
            view_t_min = data_t_min
        if view_t_max > data_t_max:
            view_t_max = data_t_max
        if view_t_max <= view_t_min:
            view_t_min, view_t_max = data_t_min, data_t_max

        # диапазон по Y — считаем только по тем точкам, которые попадают в видимое окно по X
        vals: List[float] = []
        for t, d, r in self._points:
            if t < view_t_min or t > view_t_max:
                continue
            if d is not None:
                vals.append(float(d))
            if r is not None:
                vals.append(float(r))

        if not vals:
            y_min, y_max = -1.0, 1.0
        else:
            max_abs = max(abs(v) for v in vals)
            if max_abs == 0:
                max_abs = 1.0
            max_abs *= 1.1  # небольшой запас сверху/снизу
            y_min, y_max = -max_abs, max_abs

        return data_t_min, data_t_max, view_t_min, view_t_max, y_min, y_max

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        full_rect = self.rect()
        rect = self._plot_rect()

        # фон карточки
        painter.fillRect(rect, QColor("#020617"))

        if not self._points:
            painter.setPen(QColor("#64748b"))
            painter.drawText(
                rect,
                Qt.AlignCenter,
                "Нет данных для выбранного токена / DEX.",
            )
            painter.end()
            return

        ranges = self._compute_ranges()
        if ranges is None:
            painter.setPen(QColor("#64748b"))
            painter.drawText(
                rect,
                Qt.AlignCenter,
                "Нет числовых значений спреда для выбранного токена / DEX.",
            )
            painter.end()
            return

        data_t_min, data_t_max, view_t_min, view_t_max, y_min, y_max = ranges

        def map_x(t: float) -> float:
            return rect.left() + (t - view_t_min) / (view_t_max - view_t_min) * rect.width()

        def map_y(v: float) -> float:
            return rect.bottom() - (v - y_min) / (y_max - y_min) * rect.height()

        # горизонтальные линии (средняя 0% — оранжевая пунктирная)
        min_h_spacing = 34  # минимальное расстояние между линиями в пикселях
        max_h_lines = 11
        num_h_lines = max(3, min(max_h_lines, int(rect.height() / min_h_spacing) + 1))

        # делаем количество линий нечётным, чтобы одна линия проходила по 0%
        if num_h_lines % 2 == 0:
            num_h_lines = max(3, num_h_lines - 1)

        h_levels: List[float] = []
        mid_index = num_h_lines // 2

        for i in range(num_h_lines):
            frac = i / (num_h_lines - 1) if num_h_lines > 1 else 0.0
            v = y_min + frac * (y_max - y_min)
            h_levels.append(v)
            y = map_y(v)

            is_middle = (i == mid_index)

            pen = QPen()
            if is_middle:
                # центральная линия — оранжевая ПУНКТИРНАЯ
                pen.setColor(QColor("#f97316"))
                pen.setStyle(Qt.DashLine)
                pen.setWidth(2)
            else:
                pen.setColor(QColor("#4b5563"))
                pen.setStyle(Qt.DashLine)
                pen.setWidth(1)

            painter.setPen(pen)
            painter.drawLine(rect.left(), int(y), rect.right(), int(y))

        # подписи по Y слева от графика — для каждой линии сетки
        painter.setPen(QColor("#9ca3af"))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)

        # правый край подписей совмещаем с левой границей графика - 4px
        label_width = 60 - 8  # совпадает с left_margin внутри _plot_rect
        label_right = rect.left() - 8
        label_left = int(label_right - label_width)

        for idx, v in enumerate(h_levels):
            y = map_y(v)

            # небольшое смещение, чтобы крайние подписи
            # не прилипали к краям и к подписям времени
            dy = 0
            if idx == 0:
                dy = -6  # нижняя линия
            elif idx == len(h_levels) - 1:
                dy = 10  # верхняя линия

            if idx == mid_index:
                text = "0.00%"
            else:
                text = f"{v:.2f}%"

            painter.drawText(
                QRect(label_left, int(y) - 8 + dy, label_width, 16),
                Qt.AlignRight | Qt.AlignVCenter,
                text,
            )

        # цвета линий берём из текущих палитр спреда
        direct_color = QColor(get_direct_spread_mid_color())
        reverse_color = QColor(get_reverse_spread_mid_color())

        def draw_line(selector_index: int, color: QColor):
            # selector_index: 1 -> direct, 2 -> reverse
            series: List[Tuple[float, float]] = []
            for t, d, r in self._points:
                val = d if selector_index == 1 else r
                if val is None:
                    continue
                # фильтруем по окну просмотра по X
                if t < view_t_min or t > view_t_max:
                    continue
                series.append((t, float(val)))

            if not series:
                return

            # на всякий случай сортируем по времени
            series.sort(key=lambda x: x[0])

            # считаем типичный шаг по времени (минимальный dt)
            min_dt = None
            for i in range(1, len(series)):
                dt = series[i][0] - series[i - 1][0]
                if dt <= 0:
                    continue
                if min_dt is None or dt < min_dt:
                    min_dt = dt

            # если есть нормальный шаг — считаем, что "дырка" это > 5 * dt,
            # но не меньше 30 секунд, чтобы не рвать линию из-за мелких лагов
            max_gap = None
            if min_dt is not None:
                max_gap = max(min_dt * 5.0, 30.0)

            pen = QPen(color)
            pen.setWidth(2)
            painter.setPen(pen)

            prev_t: Optional[float] = None
            prev_x: Optional[float] = None
            prev_y: Optional[float] = None

            for t, v in series:
                x = map_x(t)
                y = map_y(v)

                # рисуем линию только если нет большого разрыва по времени
                if (
                    prev_t is not None
                    and max_gap is not None
                    and (t - prev_t) <= max_gap
                ):
                    painter.drawLine(int(prev_x), int(prev_y), int(x), int(y))

                prev_t, prev_x, prev_y = t, x, y

            # маленькие точки — рисуем всегда, даже если между ними был разрыв
            pen.setWidth(4)
            painter.setPen(pen)
            for t, v in series:
                x = map_x(t)
                y = map_y(v)
                painter.drawPoint(int(x), int(y))

        # Прямой / обратный спред
        draw_line(1, direct_color)
        draw_line(2, reverse_color)

        # подписи по времени (максимум 4) под графиком
        painter.setPen(QColor("#9ca3af"))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)

        span_seconds = max(view_t_max - view_t_min, 1.0)
        width_px = max(rect.width(), 1)
        min_px_between = 80  # минимальное расстояние между вертикальными линиями
        max_ticks = 16  # максимальное количество линий

        # "красивые" шаги по времени (в секундах)
        candidates = [
            1, 2, 5, 10, 15, 30,
            60, 2 * 60, 5 * 60, 10 * 60, 15 * 60, 30 * 60,
                60 * 60, 2 * 60 * 60, 4 * 60 * 60, 6 * 60 * 60, 12 * 60 * 60,
                24 * 60 * 60, 2 * 24 * 60 * 60,
        ]

        step = candidates[-1]
        for cand in candidates:
            if cand > span_seconds:
                break
            tick_count = span_seconds / cand
            if tick_count < 2:
                continue
            if tick_count > max_ticks:
                continue
            px_between = width_px / tick_count
            if px_between >= min_px_between:
                step = cand
                break

        # если вдруг ни один кандидат не подошёл — делаем хотя бы 3 деления
        if step > span_seconds:
            step = span_seconds / 4.0

        # первый "красивый" тик справа от левого края
        first_tick = math.floor(view_t_min / step) * step
        if first_tick < view_t_min:
            first_tick += step

        t = first_tick
        while t <= view_t_max + step * 0.5:
            x = map_x(t)

            # вертикальная пунктирная линия
            v_pen = QPen(QColor("#1f2937"))
            v_pen.setStyle(Qt.DashLine)
            v_pen.setWidth(1)
            painter.setPen(v_pen)
            painter.drawLine(int(x), rect.top(), int(x), rect.bottom())

            # подпись времени — формат зависит от масштаба
            painter.setPen(QColor("#9ca3af"))
            dt = datetime.fromtimestamp(t)
            if span_seconds <= 5 * 60:
                label = dt.strftime("%H:%M:%S")
            elif span_seconds <= 2 * 60 * 60:
                label = dt.strftime("%H:%M")
            else:
                label = dt.strftime("%d.%m %H:%M")

            text_width = 90
            text_height = 14
            text_rect = QRect(
                int(x) - text_width // 2,
                rect.bottom() + 6,
                text_width,
                text_height,
            )
            painter.drawText(text_rect, Qt.AlignCenter, label)

            t += step

        # --- hover-оверлей (карточки подсказки) ---
        if self._hover_point is not None and self._hover_opacity > 0.01:
            self._draw_hover_overlay(painter, rect, map_x, map_y, view_t_min, view_t_max)

        painter.end()

    # --- рисуем подсказки при наведении ---
    def _draw_hover_overlay(self, painter: QPainter, rect: QRect,
                            map_x, map_y, view_t_min: float, view_t_max: float) -> None:
        ts, direct, reverse = self._hover_point
        if ts < view_t_min or ts > view_t_max:
            return

        alpha = int(255 * self._hover_opacity)

        # вертикальная линия под курсором
        x = map_x(ts)
        pen = QPen(QColor(148, 163, 184, int(120 * self._hover_opacity)))
        pen.setStyle(Qt.DashLine)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(int(x), rect.top(), int(x), rect.bottom())

        # подсветка точек
        direct_color = QColor(get_direct_spread_mid_color())
        direct_color.setAlpha(alpha)
        reverse_color = QColor(get_reverse_spread_mid_color())
        reverse_color.setAlpha(alpha)

        direct_y = None
        reverse_y = None

        if direct is not None:
            direct_y = map_y(direct)
            painter.setPen(QPen(direct_color, 5))
            painter.drawPoint(int(x), int(direct_y))
        if reverse is not None:
            reverse_y = map_y(reverse)
            painter.setPen(QPen(reverse_color, 5))
            painter.drawPoint(int(x), int(reverse_y))

        # карточки
        dt = datetime.fromtimestamp(ts)
        time_label = dt.strftime("%Y-%m-%d %H:%M:%S")

        card_w = 210
        card_h = 32
        margin = 8

        cards = []
        if reverse is not None:
            cards.append(("Обратный спред (%):", reverse, reverse_color))
        if direct is not None:
            cards.append(("Прямой спред (%):", direct, direct_color))

        if not cards:
            return

        bg = QColor("#020617")
        bg.setAlpha(alpha)
        border = QColor("#4b5563")
        border.setAlpha(alpha)
        txt_color = QColor("#e5e7eb")
        txt_color.setAlpha(alpha)

        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)

        # --- позиционирование карточек возле точки ---

        # база по Y: около точек (берём минимальную, чтобы карточки пытаться ставить над ними)
        values_y = []
        if reverse_y is not None:
            values_y.append(reverse_y)
        if direct_y is not None:
            values_y.append(direct_y)

        if values_y:
            base_y = min(values_y)
        else:
            base_y = rect.center().y()

        total_h = len(cards) * card_h + (len(cards) - 1) * 4

        # сначала пробуем разместить карточки НАД точкой
        top = base_y - margin - total_h
        if top < rect.top() + margin:
            # если наверху не влезают — ставим под точкой
            top = max(rect.top() + margin, base_y + margin)

        # по X: если точка слева — карточки справа от неё, если справа — слева от неё
        if x < rect.center().x():
            left = int(x + margin)
        else:
            left = int(x - card_w - margin)

        # не выходим за границы rect по X
        if left < rect.left() + margin:
            left = rect.left() + margin
        if left + card_w > rect.right() - margin:
            left = rect.right() - margin - card_w

        # отрисовка карточек
        for idx, (label_text, value, color) in enumerate(cards):
            card_top = int(top + idx * (card_h + 4))
            card_rect = QRect(int(left), card_top, card_w, card_h)

            # фон
            painter.setPen(border)
            painter.setBrush(bg)
            painter.drawRoundedRect(card_rect, 5, 5)

            # первая строка: дата/время
            painter.setPen(txt_color)
            painter.drawText(
                QRect(card_rect.left() + 6, card_rect.top() + 2, card_w - 12, 12),
                Qt.AlignLeft | Qt.AlignVCenter,
                time_label,
            )

            # квадрат цвета серии
            square_size = 10
            sq_x = card_rect.left() + 6
            sq_y = card_rect.top() + 16
            sq_rect = QRect(sq_x, sq_y, square_size, square_size)
            painter.fillRect(sq_rect, color)

            # подпись спреда
            text_rect = QRect(
                sq_x + square_size + 4,
                card_rect.top() + 14,
                card_w - (sq_x + square_size + 8 - card_rect.left()),
                14,
            )
            painter.drawText(
                text_rect,
                Qt.AlignLeft | Qt.AlignVCenter,
                f"{label_text} {value:.4f}",
            )

    # --- управление hover (поиск ближайшей точки) ---
    def _set_hover_point(self, point: Optional[Tuple[float, Optional[float], Optional[float]]]) -> None:
        # если ничего не меняется — не дёргаем анимацию
        if point is None and self._hover_point is None and self._hover_opacity == 0.0:
            return
        if point is not None:
            self._hover_point = point
            self._start_hover_anim(1.0)
        else:
            # просто скрываем с анимацией
            self._start_hover_anim(0.0)

    def _start_hover_anim(self, target: float) -> None:
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_opacity)
        self._hover_anim.setEndValue(target)
        self._hover_anim.start()

    def _on_hover_anim_finished(self) -> None:
        # когда полностью исчезли — очищаем точку
        if self._hover_opacity <= 0.01:
            self._hover_point = None
            self.update()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if not self._points:
            return

        rect = self._plot_rect()
        pos = event.pos()

        if not rect.contains(pos):
            self._set_hover_point(None)
            return

        ranges = self._compute_ranges()
        if ranges is None:
            self._set_hover_point(None)
            return

        _, _, view_t_min, view_t_max, _, _ = ranges

        def map_x(t: float) -> float:
            return rect.left() + (t - view_t_min) / (view_t_max - view_t_min) * rect.width()

        mouse_x = pos.x()
        closest: Optional[Tuple[float, Optional[float], Optional[float]]] = None
        closest_dist: Optional[float] = None

        for p in self._points:
            ts = p[0]
            if ts < view_t_min or ts > view_t_max:
                continue
            x = map_x(ts)
            dist = abs(x - mouse_x)
            if closest_dist is None or dist < closest_dist:
                closest_dist = dist
                closest = p

        # порог в пикселях, чтобы подсказка не прыгала далеко от точки
        threshold_px = 20
        if closest is None or closest_dist is None or closest_dist > threshold_px:
            self._set_hover_point(None)
        else:
            self._set_hover_point(closest)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        # когда мышь уходит с виджета — плавно скрываем подсказку
        self._set_hover_point(None)
        super().leaveEvent(event)

    # --- зум по колесу мыши ---
    def wheelEvent(self, event) -> None:  # type: ignore[override]
        if not self._points:
            return

        xs = [t for (t, _, _) in self._points]
        data_t_min = min(xs)
        data_t_max = max(xs)
        if data_t_max == data_t_min:
            return

        rect = self._plot_rect()
        if rect.width() <= 0:
            return

        # текущий видимый диапазон
        view_t_min = self._view_t_min if self._view_t_min is not None else data_t_min
        view_t_max = self._view_t_max if self._view_t_max is not None else data_t_max
        if view_t_max <= view_t_min:
            view_t_min, view_t_max = data_t_min, data_t_max

        data_range = data_t_max - data_t_min
        if data_range <= 0:
            return

        pos = event.pos()
        # зумим только внутри области графика
        if pos.x() < rect.left() or pos.x() > rect.right():
            return

        frac = (pos.x() - rect.left()) / rect.width()
        frac = max(0.0, min(1.0, frac))
        center_t = view_t_min + frac * (view_t_max - view_t_min)

        delta = event.angleDelta().y()
        if delta == 0:
            return

        zoom_out = delta < 0

        range_t = view_t_max - view_t_min
        if range_t <= 0:
            range_t = data_range

        zoom_factor = 0.2
        if zoom_out:
            zoom_factor = -zoom_factor

        # считаем новый диапазон
        new_range = range_t * (1.0 - zoom_factor)

        # ограничения по зуму: минимум 1% данных, максимум — весь диапазон
        min_range = data_range * 0.01
        if new_range < min_range:
            new_range = min_range
        if new_range > data_range:
            new_range = data_range

        epsilon = data_range * 1e-6

        # если уже полностью отдалены и крутим ещё назад — просто игнорируем
        if (
            zoom_out
            and abs(view_t_min - data_t_min) < epsilon
            and abs(view_t_max - data_t_max) < epsilon
        ):
            return

        # рассчитываем новое окно относительно центра
        new_min = center_t - (center_t - view_t_min) * (new_range / range_t)
        new_max = new_min + new_range

        # поджимаем к границам данных
        if new_min < data_t_min:
            new_min = data_t_min
            new_max = new_min + new_range
        if new_max > data_t_max:
            new_max = data_t_max
            new_min = new_max - new_range

        # финальная защита
        new_min = max(new_min, data_t_min)
        new_max = min(new_max, data_t_max)
        if new_max - new_min < min_range:
            half = min_range / 2.0
            new_min = max(center_t - half, data_t_min)
            new_max = min(center_t + half, data_t_max)
            if new_max - new_min < min_range:
                new_min, new_max = data_t_min, data_t_max

        # если реально ничего не изменилось — тоже игнорируем событие
        if (
            abs(new_min - view_t_min) < epsilon
            and abs(new_max - view_t_max) < epsilon
        ):
            return

        self._view_t_min = new_min
        self._view_t_max = new_max

        # при зуме убираем hover
        self._set_hover_point(None)

        self.update()
        event.accept()


class SpreadGraphDialog(DraggableDialog):
    """
    Диалог с графиком прямого и обратного спреда.
    История (до 2 суток) передаётся из главного окна.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        pairs: Dict[str, object],
        history: Optional[HistoryDict] = None,
    ) -> None:
        super().__init__(parent)

        self._RESIZE_MARGIN = 6
        self._resize_active = False
        self._resize_edge: Optional[str] = None
        self._resize_start_geom: Optional[QRect] = None
        self._resize_start_mouse: Optional[QPoint] = None

        self.setMouseTracking(True)
        self.setMinimumSize(1200, 700)


        self._pairs: Dict[str, object] = pairs or {}
        self._history: HistoryDict = history or {}

        self._current_cex: Optional[str] = "MEXC"
        self._current_dex: Optional[str] = None
        self._current_pair: Optional[str] = None

        self._last_chart_pair: Optional[str] = None
        self._last_chart_dex: Optional[str] = None
        self._last_chart_tf: Optional[str] = None

        # --- ТАЙМЕР ДЛЯ ПЕРИОДИЧЕСКОГО ОБНОВЛЕНИЯ L/M ---
        self._lm_timer = QTimer(self)
        self._lm_timer.setTimerType(Qt.VeryCoarseTimer)
        self._lm_timer.setSingleShot(False)
        self._lm_timer.timeout.connect(self._on_lm_timer_timeout)

        # таймфреймы
        self._timeframes = [
            ("1m", "1 мин", 60),
            ("5m", "5 мин", 5 * 60),
            ("15m", "15 мин", 15 * 60),
            ("1h", "1 час", 60 * 60),
            ("4h", "4 часа", 4 * 60 * 60),
            ("1d", "1 день", 24 * 60 * 60),
            ("2d", "2 дня", 2 * 24 * 60 * 60),
        ]
        self._tf_actions: Dict[str, object] = {}
        self._tf_seconds: Dict[str, int] = {k: s for k, _, s in self._timeframes}

        # дефолтный таймфрейм — всегда 15 минут
        self._current_timeframe_key: str = "15m"

        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        frame = QWidget()
        frame.setObjectName("dialogFrame")
        frame.setAttribute(Qt.WA_StyledBackground, True)
        frame.setStyleSheet(DIALOG_FRAME)
        frame.setMouseTracking(True)
        frame.installEventFilter(self)

        main = QVBoxLayout(frame)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(12)

        # заголовок
        header = QHBoxLayout()
        lbl_title = QLabel("График отклонения цен (спред)")
        lbl_title.setStyleSheet(LABEL_DIALOG_TITLE)
        header.addWidget(lbl_title)
        header.addStretch()

        btn_close = QPushButton()
        btn_close.setFixedSize(30, 30)
        btn_close.setAttribute(Qt.WA_StyledBackground, True)
        btn_close.setStyleSheet(BUTTON_ROUND_ICON)
        btn_close.setIcon(make_close_icon())
        btn_close.setIconSize(QSize(18, 18))
        btn_close.clicked.connect(self.reject)
        header.addWidget(btn_close)

        main.addLayout(header)

        # описание (без "Выберите DEX…")
        lbl_desc = QLabel(
            "История прямого и обратного спреда "
            "между выбранными CEX и DEX за выбранный таймфрейм."
        )
        lbl_desc.setStyleSheet(LABEL_SMALL_MUTED)
        lbl_desc.setWordWrap(True)
        main.addWidget(lbl_desc)

        # ---- фильтры: CEX -> DEX -> токен -> таймфрейм ----
        filters = QHBoxLayout()
        filters.setSpacing(12)

        # CEX
        box_cex = QVBoxLayout()
        lbl_cex = QLabel("CEX")
        lbl_cex.setStyleSheet(LABEL_FORM)
        box_cex.addWidget(lbl_cex)

        self.btn_cex = QPushButton("MEXC Futures")
        self.btn_cex.setFixedHeight(32)
        self.btn_cex.setStyleSheet(BUTTON_TOP_DARK_NO_ARROW)
        box_cex.addWidget(self.btn_cex)

        cex_menu = StickyMenu(self.btn_cex)
        cex_menu.setStyleSheet(DEX_MENU)
        self._cex_actions: Dict[str, object] = {}

        act_mexc = cex_menu.addAction("MEXC Futures")
        act_mexc.setCheckable(True)
        act_mexc.setChecked(True)
        self._cex_actions["MEXC"] = act_mexc

        fm_cex = self.btn_cex.fontMetrics()
        max_cex_text = max((a.text() for a in self._cex_actions.values()), default="MEXC")
        padding = 100  # больше места под текст и стрелку
        self.btn_cex.setMinimumWidth(fm_cex.horizontalAdvance(max_cex_text) + padding)






        def on_cex_changed(action):
            # у нас один вариант, но оставляем на будущее
            for key, a in self._cex_actions.items():
                a.setChecked(a is action)
                if a is action and a.isChecked():
                    self._current_cex = key

        cex_menu.state_changed_callback = on_cex_changed
        # меню строго той же ширины, что и кнопка
        cex_menu.aboutToShow.connect(
            lambda m=cex_menu, b=self.btn_cex: m.setFixedWidth(b.width())
        )
        self.btn_cex.setMenu(cex_menu)
        attach_menu_arrow(self.btn_cex, cex_menu)

        filters.addLayout(box_cex)

        # DEX
        box_dex = QVBoxLayout()
        lbl_dex = QLabel("DEX")
        lbl_dex.setStyleSheet(LABEL_FORM)
        box_dex.addWidget(lbl_dex)

        self.btn_dex = QPushButton("—")
        self.btn_dex.setFixedHeight(32)
        self.btn_dex.setStyleSheet(BUTTON_TOP_DARK_NO_ARROW)
        box_dex.addWidget(self.btn_dex)

        dex_menu = StickyMenu(self.btn_dex)
        dex_menu.setStyleSheet(DEX_MENU)
        dex_menu.state_changed_callback = self._on_dex_menu_changed
        dex_menu.aboutToShow.connect(
            lambda m=dex_menu, b=self.btn_dex: m.setFixedWidth(b.width())
        )
        self.btn_dex.setMenu(dex_menu)
        attach_menu_arrow(self.btn_dex, dex_menu)
        self._dex_actions: Dict[str, object] = {}

        filters.addLayout(box_dex)

        # Токен
        box_pair = QVBoxLayout()
        lbl_pair = QLabel("Токен")
        lbl_pair.setStyleSheet(LABEL_FORM)
        box_pair.addWidget(lbl_pair)

        self.btn_pair = QPushButton("—")
        self.btn_pair.setFixedHeight(32)
        self.btn_pair.setStyleSheet(BUTTON_TOP_DARK_NO_ARROW)
        box_pair.addWidget(self.btn_pair)

        pair_menu = StickyMenu(self.btn_pair)
        pair_menu.setStyleSheet(DEX_MENU)
        pair_menu.state_changed_callback = self._on_pair_menu_changed
        pair_menu.aboutToShow.connect(
            lambda m=pair_menu, b=self.btn_pair: m.setFixedWidth(b.width())
        )
        self.btn_pair.setMenu(pair_menu)
        attach_menu_arrow(self.btn_pair, pair_menu)
        self._pair_actions: Dict[str, object] = {}

        filters.addLayout(box_pair)

        # Таймфрейм
        box_tf = QVBoxLayout()
        lbl_tf = QLabel("Таймфрейм")
        lbl_tf.setStyleSheet(LABEL_FORM)
        box_tf.addWidget(lbl_tf)

        self.btn_tf = QPushButton("15 мин")
        self.btn_tf.setFixedHeight(32)
        self.btn_tf.setStyleSheet(BUTTON_TOP_DARK_NO_ARROW)
        box_tf.addWidget(self.btn_tf)

        tf_menu = StickyMenu(self.btn_tf)
        tf_menu.setStyleSheet(DEX_MENU)
        tf_menu.state_changed_callback = self._on_tf_menu_changed
        tf_menu.aboutToShow.connect(
            lambda m=tf_menu, b=self.btn_tf: m.setFixedWidth(b.width())
        )
        self.btn_tf.setMenu(tf_menu)
        attach_menu_arrow(self.btn_tf, tf_menu)

        for key, label, _secs in self._timeframes:
            act = tf_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(key == self._current_timeframe_key)
            self._tf_actions[key] = act
            if key == self._current_timeframe_key:
                self.btn_tf.setText(label)

        # уже после цикла
        fm_tf = self.btn_tf.fontMetrics()
        max_tf_label = max((label for _, label, _ in self._timeframes), default="")
        self.btn_tf.setMinimumWidth(fm_tf.horizontalAdvance(max_tf_label) + 32)

        filters.addLayout(box_tf)

        # ---------- Табло L / M справа от таймфрейма ----------
        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)

        def make_stat_column(title: str, prefix: str) -> Tuple[QVBoxLayout, QLabel]:
            """
            Одна колонка: сверху заголовок (как у Токен/Таймфрейм),
            снизу капсула в стиле статуса.
            """
            box = QVBoxLayout()
            box.setSpacing(4)

            lbl_title = QLabel(title)
            lbl_title.setStyleSheet(LABEL_FORM)
            box.addWidget(lbl_title)

            value = QLabel(f"{prefix} —")
            value.setAlignment(Qt.AlignCenter)
            value.setFixedHeight(32)
            value.setMinimumWidth(170)
            value.setWordWrap(False)
            value.setStyleSheet(STATUS_LABEL_IDLE)
            box.addWidget(value)

            return box, value

        box_L, self.lbl_L_value = make_stat_column("Ликвидность", "L")
        box_M, self.lbl_M_value = make_stat_column("Капитализация", "M")

        filters.addLayout(box_L)
        filters.addLayout(box_M)

        filters.addStretch()
        main.addLayout(filters)



        # маленькая легенда под фильтрами
        legend_row = QHBoxLayout()
        legend_row.setSpacing(12)

        legend_row.addStretch()

        self._direct_legend_box = QLabel()
        self._direct_legend_box.setFixedSize(32, 10)
        self._direct_legend_box.setStyleSheet(
            f"background-color: {get_direct_spread_mid_color()};"
            "border-radius: 1px;"
        )
        direct_label = QLabel("Прямой спред (%)")
        direct_label.setStyleSheet(LABEL_SMALL_MUTED)
        legend_row.addWidget(self._direct_legend_box)
        legend_row.addWidget(direct_label)

        legend_row.addSpacing(24)

        self._reverse_legend_box = QLabel()
        self._reverse_legend_box.setFixedSize(32, 10)
        self._reverse_legend_box.setStyleSheet(
            f"background-color: {get_reverse_spread_mid_color()};"
            "border-radius: 1px;"
        )
        reverse_label = QLabel("Обратный спред (%)")
        reverse_label.setStyleSheet(LABEL_SMALL_MUTED)
        legend_row.addWidget(self._reverse_legend_box)
        legend_row.addWidget(reverse_label)

        legend_row.addStretch()
        main.addLayout(legend_row)


        # график
        self.chart = SpreadChartWidget()
        self.chart.setStyleSheet(PANEL_DARK_BG)
        main.addWidget(self.chart, stretch=1)

        # нижняя строка с инфой
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(LABEL_SMALL_MUTED)
        main.addWidget(self.lbl_status)

        # grip для растягивания окна
        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 0, 0)
        grip_row.setSpacing(0)
        grip_row.addStretch()

        self._size_grip = QSizeGrip(frame)
        self._size_grip.setStyleSheet("background: transparent;")
        grip_row.addWidget(self._size_grip, 0, Qt.AlignBottom | Qt.AlignRight)

        main.addLayout(grip_row)

        outer.addWidget(frame)

        # восстановить размер/позицию окна, если они уже сохранялись
        try:
            self._settings = QSettings("CRYPTOSPREAD", "SpreadGraphDialog")
            geom = self._settings.value("geometry")
            if geom is not None:
                self.restoreGeometry(geom)
            else:
                self.resize(900, 420)
        except Exception:
            # на всякий случай, если что-то пойдёт не так — используем дефолт
            self.resize(900, 420)

        self._rebuild_filters()

        # что сейчас реально показано на графике
        self._last_chart_pair: Optional[str] = None
        self._last_chart_dex: Optional[str] = None
        self._last_chart_tf: Optional[str] = None

        # подписываем это окно на глобальный воркер L/M
        try:
            worker = get_lm_worker()
            worker.result_ready.connect(self._on_lm_result)
        except Exception:
            # если что-то пошло не так — просто живём без L/M
            pass

    # ==== внешнее API ====

    def update_palette_colors(self) -> None:
        if getattr(self, "_direct_legend_box", None) is not None:
            self._direct_legend_box.setStyleSheet(
                f"background-color: {get_direct_spread_mid_color()};"
                "border-radius: 1px;"
            )

        if getattr(self, "_reverse_legend_box", None) is not None:
            self._reverse_legend_box.setStyleSheet(
                f"background-color: {get_reverse_spread_mid_color()};"
                "border-radius: 1px;"
            )




    def set_data(self, pairs: Dict[str, object], history: Optional[HistoryDict]) -> None:
        """
        Обновить пары/историю из главного окна.
        Вызывается при открытии окна и на каждый тик on_data_ready,
        если окно уже открыто.
        """
        self._pairs = pairs or {}
        self._history = history or {}

        # здесь гарантируем, что история по всем токенам не старше 2 дней
        self._trim_history_to_last_2_days()

        self._rebuild_filters()

    def _trim_history_to_last_2_days(self) -> None:
        """
        Обрезает self._history так, чтобы по каждому токену и DEX
        хранились только данные за последние 2 дня.
        При этом сами токены и структуры словарей не удаляются.
        """
        max_age_secs = 2 * 24 * 60 * 60
        now_ts = datetime.now().timestamp()
        min_ts = now_ts - max_age_secs

        for pair_key, dex_dict in list(self._history.items()):
            if not isinstance(dex_dict, dict):
                continue

            for dex_key, points in list(dex_dict.items()):
                if not points:
                    continue

                # оставляем только точки свежей истории
                new_points = [p for p in points if p[0] >= min_ts]

                dex_dict[dex_key] = new_points



    # ==== служебные методы ====

    def _sync_filter_widths(self) -> None:
        """
        Делает CEX / DEX / Токен / Таймфрейм одинаковой ширины.
        Меню берут ширину от кнопки, поэтому всё будет ровно.
        """
        buttons = [self.btn_cex, self.btn_dex, self.btn_pair, self.btn_tf]
        buttons = [b for b in buttons if b is not None]

        if not buttons:
            return

        max_width = max(
            max(
                b.minimumWidth(),
                b.minimumSizeHint().width(),
                b.sizeHint().width(),
            )
            for b in buttons
        )

        for b in buttons:
            b.setMinimumWidth(max_width)

    def _pair_label(self, key: Optional[str]) -> str:
        """
        Преобразует внутренний ключ пары в подпись для UI:
        'ABC-USDT' -> 'ABC'
        Остальные пары остаются как есть.
        """
        if not key:
            return "—"
        up = key.upper()
        suffix = "-USDT"
        if up.endswith(suffix):
            return key[:-len(suffix)]
        return key

    def _rebuild_filters(self) -> None:
        prev_dex = self._current_dex
        prev_pair = self._current_pair

        # ----- пересобираем меню DEX -----
        dex_menu = self.btn_dex.menu()
        if dex_menu is None:
            return
        dex_menu.clear()
        self._dex_actions.clear()

        # какие DEX реально есть у токенов
        available_for_dex = {"pancake": False, "jupiter": False, "matcha": False}
        for cfg in self._pairs.values():
            try:
                dexes = getattr(cfg, "dexes", None) or []
            except Exception:
                dexes = []
            for dx in dexes:
                if dx in available_for_dex:
                    available_for_dex[dx] = True

        # если старые конфиги без списка dexes – считаем, что все доступны
        if not any(available_for_dex.values()):
            for k in available_for_dex:
                available_for_dex[k] = True

        def add_dex(key: str, title: str):
            act = dex_menu.addAction(title)
            act.setCheckable(True)
            self._dex_actions[key] = act

        # всегда добавляем три известных DEX, порядок фиксированный
        add_dex("pancake", "Pancake")
        add_dex("jupiter", "Jupiter")
        add_dex("matcha", "Matcha")

        if not self._dex_actions:
            act = dex_menu.addAction("Нет доступных DEX")
            act.setEnabled(False)
            self.btn_dex.setText("Нет DEX")
            self._current_dex = None
        else:
            # выбираем текущий DEX с приоритетом: сохранённый -> jupiter -> первый доступный
            enabled_keys = [k for k, a in self._dex_actions.items() if a.isEnabled()]
            if prev_dex in self._dex_actions and (self._dex_actions[prev_dex].isEnabled() or not enabled_keys):
                self._current_dex = prev_dex
            elif "jupiter" in enabled_keys:
                self._current_dex = "jupiter"
            elif enabled_keys:
                self._current_dex = enabled_keys[0]
            else:
                # все отключены – берём любой, чтобы не было None
                self._current_dex = next(iter(self._dex_actions.keys()))

            for key, act in self._dex_actions.items():
                act.setChecked(key == self._current_dex)

            # подпись на кнопке
            if self._current_dex == "pancake":
                self.btn_dex.setText("Pancake")
            elif self._current_dex == "jupiter":
                self.btn_dex.setText("Jupiter")
            elif self._current_dex == "matcha":
                self.btn_dex.setText("Matcha")
            else:
                self.btn_dex.setText("DEX")

        # ----- пересобираем меню токенов (фильтрация по выбранному DEX) -----
        pair_menu = self.btn_pair.menu()
        if pair_menu is None:
            return
        pair_menu.clear()
        self._pair_actions.clear()

        first_pair_key: Optional[str] = None
        for name, cfg in sorted(self._pairs.items()):
            # если выбран конкретный DEX – оставляем только те пары, где он есть
            if self._current_dex:
                try:
                    dexes = getattr(cfg, "dexes", None)
                except Exception:
                    dexes = None
                if dexes and self._current_dex not in dexes:
                    continue

            label = self._pair_label(name)  # только имя токена без -USDT
            act = pair_menu.addAction(label)
            act.setCheckable(True)
            self._pair_actions[name] = act
            if first_pair_key is None:
                first_pair_key = name

        if not self._pair_actions:
            act = pair_menu.addAction("Пусто")
            act.setEnabled(False)
            self.btn_pair.setText("Пусто")
            self._current_pair = None
        else:
            # восстанавливаем выделение пары, если она осталась в списке
            if prev_pair in self._pair_actions:
                self._current_pair = prev_pair
            else:
                self._current_pair = first_pair_key

            for key, act in self._pair_actions.items():
                act.setChecked(key == self._current_pair)

            self.btn_pair.setText(self._pair_label(self._current_pair))

            padding = 56

            # DEX — независимо от наличия пар
            if self._dex_actions:
                fm_dex = self.btn_dex.fontMetrics()
                max_dex_text = max((a.text() for a in self._dex_actions.values()), default="")
                self.btn_dex.setMinimumWidth(fm_dex.horizontalAdvance(max_dex_text) + padding)

            if not self._pair_actions:
                # нет ни одного токена для выбранного DEX
                act = pair_menu.addAction("Пусто")
                act.setEnabled(False)
                self.btn_pair.setText("Пусто")
                self._current_pair = None
            else:
                # восстанавливаем выделение пары, если она осталась в списке
                if prev_pair in self._pair_actions:
                    self._current_pair = prev_pair
                else:
                    self._current_pair = first_pair_key

                for key, act in self._pair_actions.items():
                    act.setChecked(key == self._current_pair)

                self.btn_pair.setText(self._pair_label(self._current_pair))

                # ширина кнопки Токен по максимальному тексту
                fm_pair = self.btn_pair.fontMetrics()
                max_pair_text = max((a.text() for a in self._pair_actions.values()), default="")
                self.btn_pair.setMinimumWidth(fm_pair.horizontalAdvance(max_pair_text) + padding)

                # определяем, изменился ли выбранный DEX или токен
                filters_changed = (self._current_dex != prev_dex) or (self._current_pair != prev_pair)

                # если фильтры не менялись, просто обновляем график без перезапуска L/M таймера
                self._update_chart(restart_lm_timer=filters_changed)

            self._sync_filter_widths()

    def current_pair_key(self) -> Optional[str]:
        return self._current_pair

    def current_dex_key(self) -> Optional[str]:
        return self._current_dex

    # ---- callbacks меню ----

    def _on_dex_menu_changed(self, changed_action):
        clicked_key = None
        for k, act in self._dex_actions.items():
            if act is changed_action:
                clicked_key = k
                break
        if clicked_key is None:
            return

        for k, act in self._dex_actions.items():
            act.setChecked(k == clicked_key)

        self._current_dex = clicked_key
        self.btn_dex.setText(changed_action.text())

        self._rebuild_filters()

    def _on_pair_menu_changed(self, changed_action):
        clicked_key = None
        for k, act in self._pair_actions.items():
            if act is changed_action:
                clicked_key = k
                break
        if clicked_key is None:
            return

        for k, act in self._pair_actions.items():
            act.setChecked(k == clicked_key)

        self._current_pair = clicked_key
        self.btn_pair.setText(changed_action.text())
        self._update_chart()

    def _on_tf_menu_changed(self, changed_action):
        clicked_key = None
        for key, act in self._tf_actions.items():
            if act is changed_action:
                clicked_key = key
                break
        if clicked_key is None:
            return

        for key, act in self._tf_actions.items():
            act.setChecked(key == clicked_key)

        self._current_timeframe_key = clicked_key
        self.btn_tf.setText(changed_action.text())
        self._update_chart()

    # ---- обновление графика ----

    def _format_big_number(self, value: Optional[float]) -> str:
        """Красивый формат для больших чисел (K / M / B)."""
        if value is None or value <= 0:
            return "—"
        v = float(value)
        av = abs(v)
        if av >= 1_000_000_000:
            return f"{v / 1_000_000_000:.2f}B"
        if av >= 1_000_000:
            return f"{v / 1_000_000:.2f}M"
        if av >= 1_000:
            return f"{v / 1_000:.2f}K"
        return f"{v:.2f}"

    def _lm_interval_ms(self) -> int:
        """
        Интервал опроса L/M в миллисекундах.

        Здесь делаем фиксированные 15 секунд, независимо от общего interval_sec
        для основного воркера.
        """
        sec = 15.0
        return int(sec * 1000)

    def _restart_lm_timer_for_current_pair(self) -> None:
        """
        Вызывается при смене токена / DEX / таймфрейма.
        - Сразу показывает 'Расчёт...' в L и M.
        - Перезапускает таймер, который через interval_sec поставит запрос в очередь.
        """
        pair_key = self._current_pair
        if not pair_key:
            if self._lm_timer.isActive():
                self._lm_timer.stop()
            if hasattr(self, "lbl_L_value"):
                self.lbl_L_value.setText("L —")
                self.lbl_L_value.setStyleSheet(STATUS_LABEL_IDLE)
            if hasattr(self, "lbl_M_value"):
                self.lbl_M_value.setText("M —")
                self.lbl_M_value.setStyleSheet(STATUS_LABEL_IDLE)
            return

        # Показываем статус "Расчёт..." сразу при переключении
        if hasattr(self, "lbl_L_value"):
            self.lbl_L_value.setText("L Расчёт…")
            self.lbl_L_value.setStyleSheet(STATUS_LABEL_IDLE)
        if hasattr(self, "lbl_M_value"):
            self.lbl_M_value.setText("M Расчёт…")
            self.lbl_M_value.setStyleSheet(STATUS_LABEL_IDLE)

        interval_ms = self._lm_interval_ms()
        self._lm_timer.stop()
        self._lm_timer.start(interval_ms)

    def _on_lm_timer_timeout(self) -> None:
        """
        Каждые interval_sec секунд, пока окно открыто и выбран токен,
        ставим задачу на получение L/M для текущей пары.
        """
        pair_key = self._current_pair
        if not pair_key:
            return

        cfg = self._pairs.get(pair_key)
        if not cfg:
            return

        # Здесь НЕ меняем подписи (они уже 'Расчёт…'),
        # просто ставим задачу в воркер
        self._update_lm_panels(pair_key)



    def _update_lm_panels(self, pair_key: Optional[str]) -> None:
        """
        Обновить табло L / M для текущего токена.

        Теперь запросы к MEXC и CoinGecko выполняются НЕ сразу,
        а попадают в глобальную очередь LmWorker с паузой между токенами.
        """
        # если карточки ещё не созданы (на всякий случай)
        if not hasattr(self, "lbl_L_value") or not hasattr(self, "lbl_M_value"):
            return

        # если токен не выбран — тут уже можно явно очистить
        if not pair_key:
            self.lbl_L_value.setText("L —")
            self.lbl_L_value.setStyleSheet(STATUS_LABEL_IDLE)
            self.lbl_M_value.setText("M —")
            self.lbl_M_value.setStyleSheet(STATUS_LABEL_IDLE)
            return

        cfg = self._pairs.get(pair_key)
        if not isinstance(cfg, PairConfig):
            # конфиг битый — тоже имеет смысл очистить
            self.lbl_L_value.setText("L —")
            self.lbl_L_value.setStyleSheet(STATUS_LABEL_IDLE)
            self.lbl_M_value.setText("M —")
            self.lbl_M_value.setStyleSheet(STATUS_LABEL_IDLE)
            return

        # Пока идёт запрос L/M — показываем, что идёт расчёт именно для текущего токена
        self.lbl_L_value.setText("L Расчёт…")
        self.lbl_L_value.setStyleSheet(STATUS_LABEL_IDLE)
        self.lbl_M_value.setText("M Расчёт…")
        self.lbl_M_value.setStyleSheet(STATUS_LABEL_IDLE)

        try:
            worker = get_lm_worker()
            # в очередь кладём: какой диалог, какой токен и его конфиг
            worker.enqueue(self, pair_key, cfg)
        except Exception:
            # если вдруг воркер не поднялся — очищаем табло
            self.lbl_L_value.setText("L —")
            self.lbl_L_value.setStyleSheet(STATUS_LABEL_IDLE)
            self.lbl_M_value.setText("M —")
            self.lbl_M_value.setStyleSheet(STATUS_LABEL_IDLE)

    def _on_lm_result(self, dialog, pair_key: str, data: object) -> None:
        """
        Слот, который вызывается LmWorker, когда готов результат L / M.
        Обновляет табло только для своего окна и только для текущего токена.
        """
        # Результат не для этого окна — игнорируем
        if dialog is not self:
            return

        # Пока воркер считал, пользователь мог переключить токен —
        # в этом случае старый результат нам не нужен.
        if pair_key != self.current_pair_key():
            return

        if not hasattr(self, "lbl_L_value") or not hasattr(self, "lbl_M_value"):
            return

        data = data or {}
        L = data.get("L") if isinstance(data, dict) else None
        M = data.get("M") if isinstance(data, dict) else None

        L_txt = self._format_big_number(L)
        M_txt = self._format_big_number(M)

        # Если получили хоть какое-то значение — считаем, что расчёт прошёл успешно
        if L_txt == "—" and M_txt == "—":
            style = STATUS_LABEL_IDLE
        else:
            style = STATUS_LABEL_ONLINE

        self.lbl_L_value.setText(f"L {L_txt}")
        self.lbl_L_value.setStyleSheet(style)
        self.lbl_M_value.setText(f"M {M_txt}")
        self.lbl_M_value.setStyleSheet(style)

    def _update_chart(self, restart_lm_timer: bool = True) -> None:
        pair = self.current_pair_key()
        dex = self.current_dex_key()
        tf = self._current_timeframe_key

        # обновляем табло L / M для текущего токена (по желанию)
        if restart_lm_timer:
            self._restart_lm_timer_for_current_pair()

        if not pair or not dex:
            self.chart.set_points([])
            self.lbl_status.setText("Нет данных для выбранного токена / DEX.")
            self._last_chart_pair = pair
            self._last_chart_dex = dex
            self._last_chart_tf = tf
            return

        need_reset = (
                pair != self._last_chart_pair
                or dex != self._last_chart_dex
                or tf != self._last_chart_tf
        )

        pair_hist = self._history.get(pair, {})
        points = list(pair_hist.get(dex, []))

        if points:
            secs = self._tf_seconds.get(self._current_timeframe_key, 2 * 24 * 60 * 60)
            max_secs = 2 * 24 * 60 * 60
            secs = min(secs, max_secs)

            now_ts = datetime.now().timestamp()
            min_ts = now_ts - secs
            points = [p for p in points if p[0] >= min_ts]

        self.chart.set_points(points, reset_view=need_reset)

        self._last_chart_pair = pair
        self._last_chart_dex = dex
        self._last_chart_tf = tf

        if not points:
            self.lbl_status.setText("Нет данных для выбранного токена / DEX.")
            return

        t_min = datetime.fromtimestamp(points[0][0])
        t_max = datetime.fromtimestamp(points[-1][0])
        self.lbl_status.setText(
            f"Точек: {len(points)}   Период: {t_min:%d.%m %H:%M} — {t_max:%d.%m %H:%M}"
        )

        if not pair or not dex:
            self.chart.set_points([])
            self.lbl_status.setText("Нет данных для выбранного токена / DEX.")
            self._last_chart_pair = pair
            self._last_chart_dex = dex
            self._last_chart_tf = tf
            return

        need_reset = (
            pair != self._last_chart_pair
            or dex != self._last_chart_dex
            or tf != self._last_chart_tf
        )

        pair_hist = self._history.get(pair, {})
        points = list(pair_hist.get(dex, []))

        if points:
            secs = self._tf_seconds.get(self._current_timeframe_key, 2 * 24 * 60 * 60)
            max_secs = 2 * 24 * 60 * 60
            secs = min(secs, max_secs)

            now_ts = datetime.now().timestamp()
            min_ts = now_ts - secs
            points = [p for p in points if p[0] >= min_ts]

        self.chart.set_points(points, reset_view=need_reset)

        self._last_chart_pair = pair
        self._last_chart_dex = dex
        self._last_chart_tf = tf

        if not points:
            self.lbl_status.setText("Нет данных для выбранного токена / DEX.")
            return

        t_min = datetime.fromtimestamp(points[0][0])
        t_max = datetime.fromtimestamp(points[-1][0])
        self.lbl_status.setText(
            f"Точек: {len(points)}   Период: {t_min:%d.%m %H:%M} — {t_max:%d.%m %H:%M}"
        )

    def closeEvent(self, event) -> None:  # type: ignore[override]
        # сохраняем геометрию окна (позиция + размер)
        try:
            if hasattr(self, "_settings"):
                self._settings.setValue("geometry", self.saveGeometry())
        except Exception:
            pass
        super().closeEvent(event)


    def eventFilter(self, obj, event):
        # перехватываем движения мыши по внутреннему frame,
        # чтобы корректно обновлять курсор (стрелочки ресайза)
        if event.type() == QEvent.MouseMove:
            global_pos = event.globalPos()
            local_pos = self.mapFromGlobal(global_pos)

            # если не тянем и кнопка не зажата — просто меняем курсор
            if not (event.buttons() & Qt.LeftButton) and not self._resize_active:
                self._update_cursor(local_pos)

        return super().eventFilter(obj, event)

    def _detect_edge(self, pos: QPoint) -> Optional[str]:
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
