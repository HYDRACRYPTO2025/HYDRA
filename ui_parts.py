# ui_parts.py
import requests
from typing import List, Dict, Optional
import re
from PyQt5.QtGui import QPixmap, QPainter, QPen, QIcon, QPolygon, QColor, QCursor, QTextCursor

from PyQt5.QtCore import QObject, QEvent
from PyQt5.QtCore import Qt, QRect, QSize, QPoint, QTimer
from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import QTimer, Qt
from core import (
    LOG_LINES,
    log,
    http_client,
    bsc_web3,
    ERC20_ABI,
    DEXSCREENER_TOKENS_URL,
    BASE_DIR,
    JUPITER_USDT_MINT,
    BSC_USDT,
    get_matcha_token_info,
    MATCHA_CHAIN_ID,
    MATCHA_USDT,
    RESOURCE_DIR,
)


from PyQt5.QtWidgets import (
    QMessageBox,
    QProgressDialog,
    QWidget,
    QLayout,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QLineEdit,
    QSizePolicy,
    QDialog,
    QMenu,
    QToolTip,
    QApplication,
)

from styles import (
    # цвета и функции
    color_direct,
    color_reverse,
    text_color,
    main_spread_bg,
    CARD_WIDGET,
    LABEL_TOKEN_NAME,
    LABEL_TOKEN_NAME_BIG,
    LABEL_STAR_DEFAULT,
    LABEL_STAR_FAVORITE,
    LABEL_DEX_NAME,
    LABEL_SMALL_MUTED,
    SPREAD_BOX_BASE,
    DIALOG_LOG,
    DIALOG_ADD,
    LABEL_DIALOG_TITLE,
    MESSAGE_CARD_STYLE,
    ACCENT_STRIP_LEFT,
    LABEL_FORM,
    BUTTON_CLEAR,
    BUTTON_ROUND_ICON,
    BUTTON_PRIMARY,
    BUTTON_TOP_DARK,
    TEXTEDIT_LOG,
    LINEEDIT_DARK,
    DEX_MENU,
    SCROLLBAR_DARK,
    TRANSPARENT_BG,
    MESSAGE_TEXT_STYLE,
    PANEL_DARK_BG,
    POPUP_COPIED_STYLE,
    BUSY_DIALOG_STYLE,
    BUSY_TEXT_STYLE,
    DIALOG_FRAME,
)


from core import LOG_LINES  # общий лог из core.py
def make_close_icon(size: int = 16, thickness: int = 2, color: str = "#e5e7eb") -> QIcon:
    supersample = 4
    S = size * supersample
    pm = QPixmap(S, S)
    pm.fill(Qt.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.HighQualityAntialiasing, True)
    pen = QPen(QColor(color))
    pen.setWidth(int(thickness * supersample))
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)

    m = int(3.5 * supersample)
    p.drawLine(m, m, S - m, S - m)
    p.drawLine(S - m, m, m, S - m)
    p.end()

    # снижение масштаба со сглаживанием
    pm = pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return QIcon(pm)

import math
from PyQt5.QtGui import QPainterPath

def make_max_icon(size: int = 16, thickness: int = 2, color: str = "#e5e7eb") -> QIcon:
    """
    Иконка квадрата для кнопки максимизации окна.
    Размер и толщина задаются параметрами.
    """
    supersample = 4
    S = size * supersample
    pm = QPixmap(S, S)
    pm.fill(Qt.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.HighQualityAntialiasing, True)

    pen = QPen(QColor(color))
    pen.setWidth(int(thickness * supersample))
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    margin = int(4 * supersample)
    rect = QRect(margin, margin, S - 2 * margin, S - 2 * margin)
    p.drawRect(rect)

    p.end()

    pm = pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return QIcon(pm)


def make_settings_icon(size: int = 18, thickness: int = 2, color: str = "#e5e7eb") -> QIcon:
    """
    Простая "шестерёнка": круг + лучи, рисуется с суперсэмплингом, чтобы не быть пиксельной.
    """
    supersample = 4
    S = size * supersample
    pm = QPixmap(S, S)
    pm.fill(Qt.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.HighQualityAntialiasing, True)

    pen = QPen(QColor(color))
    pen.setWidth(int(thickness * supersample))
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    cx = cy = S / 2
    r_inner = S * 0.22
    r_outer = S * 0.32
    r_teeth1 = S * 0.36
    r_teeth2 = S * 0.44

    # внешний круг
    p.drawEllipse(
        int(cx - r_outer),
        int(cy - r_outer),
        int(r_outer * 2),
        int(r_outer * 2),
    )

    # зубцы (лучи)
    for i in range(8):
        ang = i * (math.pi / 4.0)
        x1 = cx + r_teeth1 * math.cos(ang)
        y1 = cy + r_teeth1 * math.sin(ang)
        x2 = cx + r_teeth2 * math.cos(ang)
        y2 = cy + r_teeth2 * math.sin(ang)
        p.drawLine(int(x1), int(y1), int(x2), int(y2))


    p.drawEllipse(
        int(cx - r_inner),
        int(cy - r_inner),
        int(r_inner * 2),
        int(r_inner * 2),
    )

    p.end()

    pm = pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return QIcon(pm)

def make_star_pixmap(size: int = 18, filled: bool = False,
                     fill: str = "#facc15", stroke: str = "#4b5563",
                     thickness: int = 2) -> QPixmap:
    supersample = 4
    S = size * supersample
    pm = QPixmap(S, S)
    pm.fill(Qt.transparent)

    cx = cy = S / 2
    outer = S * 0.42
    inner = outer * 0.5

    path = QPainterPath()
    for i in range(10):
        r = outer if i % 2 == 0 else inner
        ang = (-90 + i * 36) * math.pi / 180.0
        x = cx + r * math.cos(ang)
        y = cy + r * math.sin(ang)
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.closeSubpath()

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.HighQualityAntialiasing, True)
    if filled:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(fill))
        p.drawPath(path)
    else:
        pen = QPen(QColor(stroke))
        pen.setWidth(int(thickness * supersample))
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
    p.end()

    return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

def make_edit_pixmap(size: int = 26, color: str = "#3b82f6") -> QPixmap:
    supersample = 4
    S = size * supersample
    pm = QPixmap(S, S)
    pm.fill(Qt.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.HighQualityAntialiasing)

    pen = QPen(QColor(color))
    pen.setWidth(int(3.0 * supersample))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)


    p.drawLine(int(S * 0.22), int(S * 0.78), int(S * 0.78), int(S * 0.22))

    # наконечник
    tri = QPolygon([
        QPoint(int(S * 0.78), int(S * 0.22)),
        QPoint(int(S * 0.84), int(S * 0.16)),
        QPoint(int(S * 0.72), int(S * 0.24)),
    ])
    p.setBrush(QColor(color))
    p.drawPolygon(tri)

    p.end()
    return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
def make_trash_minimal_pixmap(size: int = 26, color: str = "#e5e7eb") -> QPixmap:
    """Минималистичная корзина — простая иконка из обводки."""
    supersample = 4
    S = size * supersample
    pm = QPixmap(S, S)
    pm.fill(Qt.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.HighQualityAntialiasing, True)

    pen = QPen(QColor(color))
    pen.setWidth(int(2.2 * supersample))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)


    margin = S * 0.22
    p.drawRoundedRect(int(margin), int(S*0.32),
                      int(S - margin*2), int(S*0.50),
                      int(6 * supersample), int(6 * supersample))

    # крышка
    p.drawLine(int(margin*0.9), int(S*0.32 - S*0.08),
               int(S - margin*0.9), int(S*0.32 - S*0.08))

    # ручка крышки
    p.drawLine(int(S*0.45), int(S*0.32 - S*0.17),
               int(S*0.55), int(S*0.32 - S*0.17))

    p.end()

    return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

def make_trash_mesh_pixmap(size: int = 28, color: str = "#ef4444") -> QPixmap:
    """Сетчатая корзина — очень красивая иконка."""
    supersample = 4
    S = size * supersample
    pm = QPixmap(S, S)
    pm.fill(Qt.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.HighQualityAntialiasing, True)

    pen = QPen(QColor(color))
    pen.setWidth(int(2.5 * supersample))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    # --- корпус ---
    left   = S * 0.28
    right  = S * 0.72
    top    = S * 0.40
    bottom = S * 0.80

    p.drawRoundedRect(
        int(left),
        int(top),
        int(right - left),
        int(bottom - top),
        int(10 * supersample),
        int(10 * supersample),
    )

    # --- крышка ---
    p.drawLine(int(left - S*0.04), int(top - S*0.07),
               int(right + S*0.04), int(top - S*0.07))

    # --- ручка крышки ---
    p.drawLine(int(S*0.45), int(top - S*0.16),
               int(S*0.55), int(top - S*0.16))

    # --- сетка внутри корзины ---
    # вертикальные
    for k in (0.38, 0.50, 0.62):
        x = S * k
        p.drawLine(int(x), int(top + S*0.02), int(x), int(bottom - S*0.02))

    # горизонтальные
    for k in (0.48, 0.58, 0.68):
        y = S * k
        p.drawLine(int(left + S*0.02), int(y), int(right - S*0.02), int(y))

    p.end()
    return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

def _make_triangle(size_px: int = 12, up: bool = False, color: str = "#e5e7eb",
                   supersample: int = 3, inner_margin_px: int = 2) -> QPixmap:
    S = size_px * supersample
    m = inner_margin_px * supersample
    pm = QPixmap(S, S); pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.HighQualityAntialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    p.setPen(Qt.NoPen); p.setBrush(QColor(color))
    tri = QPolygon([
        QPoint(S // 2, m if up else S - m),
        QPoint(m,      S - m if up else m),
        QPoint(S - m,  S - m if up else m),
    ])
    p.drawPolygon(tri); p.end()
    return pm.scaled(size_px, size_px, Qt.KeepAspectRatio, Qt.SmoothTransformation)

__ARROWS_CACHE = None
def __get_arrows():
    global __ARROWS_CACHE
    if __ARROWS_CACHE is None:
        down = _make_triangle(10, up=False)
        up   = _make_triangle(10, up=True)
        __ARROWS_CACHE = (down, up)
    return __ARROWS_CACHE

def attach_menu_arrow(button: QPushButton, menu: QMenu, *, right: int = 6, bottom: int = 4):
    """Вешает маленькую стрелку в правый нижний угол и переворачивает её при открытии/закрытии меню."""
    down_pm, up_pm = __get_arrows()

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


    button._arrow_label = arrow
    _placer = _ArrowPlacer(button)
    button.installEventFilter(_placer)
    button._arrow_placer = _placer

    place()

    def on_show(): arrow.setPixmap(up_pm)
    def on_hide(): arrow.setPixmap(down_pm)
    menu.aboutToShow.connect(on_show)
    menu.aboutToHide.connect(on_hide)


class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=10):
        super().__init__(parent)
        self.itemList: List = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)



    def show_info(self, title: str, text: str):
        QMessageBox.information(self, title, text)

    def show_error(self, title: str, text: str):
        QMessageBox.critical(self, title, text)

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0

        for item in self.itemList:
            wid = item.widget()
            if wid is None:
                continue


            if not wid.isVisible():
                continue

            spaceX = self.spacing()
            spaceY = self.spacing()
            hint = wid.sizeHint()
            nextX = x + hint.width() + spaceX

            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + hint.width() + spaceX
                lineHeight = 0

            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), hint))

            x = nextX
            lineHeight = max(lineHeight, hint.height())

        return y + lineHeight - rect.y()




class ClickableLabel(QLabel):
    from PyQt5.QtCore import pyqtSignal
    clicked = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pm = None
        self._y_offset = 0
        self._pressed_inside = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:

            self._pressed_inside = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):

        if self._pressed_inside and not self.rect().contains(event.pos()):
            self._pressed_inside = False
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):

        was_pressed_inside = self._pressed_inside
        self._pressed_inside = False


        try:
            super().mouseReleaseEvent(event)
        except RuntimeError:

            return


        if event.button() == Qt.LeftButton and was_pressed_inside:
            self.clicked.emit()


    def setPixmap(self, pm: QPixmap):
        self._pm = pm
        super().setPixmap(pm)
        self.update()


    def setYOffset(self, dy: int):
        self._y_offset = dy
        self.update()

    def paintEvent(self, event):

        if self._pm is not None:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setRenderHint(QPainter.SmoothPixmapTransform, True)
            x = (self.width() - self._pm.width()) // 2 - 2
            if x < 0:
                x = 0
            y = (self.height() - self._pm.height()) // 2 + self._y_offset
            p.drawPixmap(x, y, self._pm)
            p.end()
        else:

            super().paintEvent(event)





class TokenCard(QWidget):
    def __init__(
        self,
        pair_name: str,
        favorite_callback,
        parent=None,
        edit_callback=None,
        delete_callback=None,
    ):
        super().__init__(parent)
        self.pair_name = pair_name
        self.favorite_callback = favorite_callback
        self.edit_callback = edit_callback
        self.delete_callback = delete_callback
        self.is_favorite = False
        self._contract_addr = None

        self.setStyleSheet(CARD_WIDGET)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 10)
        outer.setSpacing(8)


        header_wrap = QWidget()
        header_wrap.setFixedHeight(36)
        header_wrap.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        lay_header = QHBoxLayout(header_wrap)
        lay_header.setContentsMargins(0, 0, 0, 0)
        lay_header.setSpacing(8)

        # ⭐ избранное
        self.lbl_star = ClickableLabel("")
        self.lbl_star.setFixedSize(32, 32)
        self.lbl_star.setCursor(Qt.PointingHandCursor)
        self.lbl_star.setStyleSheet(TRANSPARENT_BG)

        self._star_off = make_star_pixmap(
            size=26, filled=False, stroke="#4b5563", thickness=3
        )
        self._star_on = make_star_pixmap(size=26, filled=True, fill="#facc15")
        self.lbl_star.setPixmap(self._star_off)
        self.lbl_star.setYOffset(0)
        self.lbl_star.clicked.connect(self.toggle_favorite)

        # название пары
        self.lbl_token = ClickableLabel(pair_name)
        self.lbl_token.setStyleSheet(LABEL_TOKEN_NAME_BIG)
        self.lbl_token.setFixedHeight(24)
        self.lbl_token.setAlignment(Qt.AlignVCenter)
        self.lbl_token.setCursor(Qt.PointingHandCursor)
        self.lbl_token.clicked.connect(self._on_token_clicked)

        # ✏ редактирование
        self.lbl_edit = ClickableLabel("")
        self.lbl_edit.setFixedSize(32, 32)
        self.lbl_edit.setCursor(Qt.PointingHandCursor)
        self.lbl_edit.setStyleSheet(TRANSPARENT_BG)
        self.lbl_edit.setPixmap(make_edit_pixmap(size=26))
        self.lbl_edit.setYOffset(0)
        self.lbl_edit.clicked.connect(self._on_edit_clicked)

        # 🗑 удаление
        self.lbl_delete = ClickableLabel("")
        self.lbl_delete.setFixedSize(32, 32)
        self.lbl_delete.setCursor(Qt.PointingHandCursor)
        self.lbl_delete.setStyleSheet(TRANSPARENT_BG)
        self.lbl_delete.setPixmap(make_trash_minimal_pixmap(size=26, color="#ef4444"))
        self.lbl_delete.setYOffset(0)
        self.lbl_delete.clicked.connect(self._on_delete_clicked)

        lay_header.addWidget(self.lbl_star, 0, Qt.AlignVCenter)
        lay_header.addWidget(self.lbl_token, 0, Qt.AlignVCenter)
        lay_header.addStretch()
        lay_header.addWidget(self.lbl_edit)
        lay_header.addSpacing(6)
        lay_header.addWidget(self.lbl_delete)

        outer.addWidget(header_wrap)


        self.rows: Dict[str, Dict[str, QLabel]] = {}
        for dex_key, dex_label in [
            ("pancake", "Pancake"),
            ("jupiter", "Jupiter"),
            ("matcha", "Matcha"),
        ]:
            row = self._make_spread_row(dex_label)
            self.rows[dex_key] = row
            outer.addWidget(row["widget"])

    def _show_copied_popup(self):
        popup = QLabel("Скопировано", self)
        popup.setStyleSheet(POPUP_COPIED_STYLE)
        popup.setWindowFlags(Qt.ToolTip)

        # позиция под надписью токена
        pos = self.lbl_token.mapToGlobal(self.lbl_token.rect().bottomLeft())
        pos.setY(pos.y() + 4)
        popup.move(pos)

        popup.show()

        QTimer.singleShot(2000, popup.close)


    def _make_spread_row(self, dex_label: str) -> dict:
        """
        Строка:
        [Pancake]   [ -3.04% ] (иконки) [ -0.37% ]
        """
        row_widget = QWidget()
        row_widget.setAttribute(Qt.WA_StyledBackground, True)
        row_widget.setStyleSheet(PANEL_DARK_BG)

        layout = QHBoxLayout(row_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        row_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row_widget.setFixedHeight(40)

        # стиль боксов
        BOX_STYLE = f"""{SPREAD_BOX_BASE}
        border-radius: 6px;
        padding: 2px 6px;
        """

        # название DEX
        name_lbl = QLabel(dex_label)
        name_lbl.setStyleSheet(
            f"{LABEL_DEX_NAME} font-size: 15px; font-weight: 600;"
        )
        name_lbl.setFixedWidth(100)


        direct_box = QLabel("-")
        reverse_box = QLabel("-")

        for box in (direct_box, reverse_box):
            box.setAlignment(Qt.AlignCenter)
            box.setFixedHeight(30)
            box.setMinimumWidth(96)
            box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            box.setAttribute(Qt.WA_StyledBackground, True)
            box.setStyleSheet(BOX_STYLE)


        icons_box = QHBoxLayout()
        icons_box.setContentsMargins(0, 0, 0, 0)
        icons_box.setSpacing(4)


        title_box = QHBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(6)
        title_box.addWidget(name_lbl)
        title_box.addLayout(icons_box)

        layout.addLayout(title_box)
        layout.addWidget(direct_box, 1, Qt.AlignVCenter)
        layout.addWidget(reverse_box, 1, Qt.AlignVCenter)
        layout.addStretch()

        return {
            "widget": row_widget,
            "name": name_lbl,
            "direct": direct_box,
            "reverse": reverse_box,
            "icons": icons_box,  # контейнер для иконок между спредами
        }

    # ------------ sizeHint / служебные ------------
    def sizeHint(self):
        visible_rows = sum(1 for r in self.rows.values() if r["widget"].isVisible())
        if visible_rows == 0:
            visible_rows = len(self.rows)

        header_h = 40
        row_h = 30
        spacing = 8
        top_bottom = 20

        total_h = top_bottom + header_h + visible_rows * row_h
        if visible_rows > 1:
            total_h += (visible_rows - 1) * spacing

        return QSize(350, total_h)

    def _on_edit_clicked(self):
        if self.edit_callback:
            self.edit_callback(self.pair_name)

    def _on_delete_clicked(self):
        if not self.delete_callback:
            return
        if MessageDialog.confirm_delete(self.window(), self.pair_name):
            self.delete_callback(self.pair_name)

    def _on_token_clicked(self):
        print("_on_token_clicked")

        addr = getattr(self, "_contract_addr", None)
        if not addr:
            self._show_copied_popup()
            return

        QApplication.clipboard().setText(str(addr).strip())
        self._show_copied_popup()


    def toggle_favorite(self):
        self.is_favorite = not self.is_favorite
        if self.is_favorite:
            self.lbl_star.setPixmap(self._star_on)
        else:
            self.lbl_star.setPixmap(self._star_off)

        if self.favorite_callback:
            self.favorite_callback(self.pair_name, self.is_favorite)

    def set_favorite(self, value: bool):

        self.is_favorite = bool(value)
        if self.is_favorite:
            self.lbl_star.setPixmap(self._star_on)
        else:
            self.lbl_star.setPixmap(self._star_off)

    def set_visible_dexes(self, visible):
        changed = False
        for key, row in self.rows.items():
            w = row["widget"]
            want = key in visible
            if w.isVisible() != want:
                w.setVisible(want)
                changed = True
        if changed:
            self.updateGeometry()

    def update_spreads(self, spreads_for_pair: Dict[str, Dict[str, Optional[float]]]):
        def _fmt(v: Optional[float]) -> str:
            if v is None:
                return "-"
            try:
                if abs(v) > 9999:
                    return ">9999%"
                return f"{v:.2f}%"
            except Exception:
                return "-"

        for dex_key, row in self.rows.items():
            info = spreads_for_pair.get(dex_key, {})
            d = info.get("direct")
            r = info.get("reverse")

            # прямой спред
            row["direct"].setText(_fmt(d))
            bg_d = main_spread_bg(d)
            fg_d = text_color(d)
            row["direct"].setStyleSheet(
                f"{SPREAD_BOX_BASE} background-color: {bg_d.name()}; color: {fg_d.name()};"
            )

            # обратный спред
            row["reverse"].setText(_fmt(r))
            bg_r = main_spread_bg(r)
            fg_r = text_color(r)
            row["reverse"].setStyleSheet(
                f"{SPREAD_BOX_BASE} background-color: {bg_r.name()}; color: {fg_r.name()};"
            )

    # ------------ ИКОНКИ DEX/CEX ------------
    def set_link_icons(self, pair_cfg):

        from PyQt5.QtGui import QPixmap, QDesktopServices
        from PyQt5.QtCore import QUrl
        import os

        # очищаем старые иконки (при обновлении карточки)
        for row in self.rows.values():
            icons_box = row.get("icons")
            if icons_box is None:
                continue
            while icons_box.count():
                item = icons_box.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()


        if not pair_cfg:
            self._contract_addr = None
            return


        self._contract_addr = (
                getattr(pair_cfg, "jupiter_mint", None)
                or getattr(pair_cfg, "bsc_address", None)
                or getattr(pair_cfg, "matcha_address", None)
        )


        base = (getattr(pair_cfg, "base", "") or "").upper() or "BTC"

        # папка с иконками — рядом с exe / .py (через BASE_DIR из core.py)
        base_path = os.path.join(str(RESOURCE_DIR), "icon")

        def add_icon(row_key: str, filename: str, link: str):
            row = self.rows.get(row_key)
            if not row:
                return

            icons_box = row.get("icons")
            if icons_box is None:
                return

            full_path = os.path.join(base_path, filename)

            lbl = QLabel()
            lbl.setCursor(Qt.PointingHandCursor)


            if "mexc" in filename.lower():
                size = 26
            else:
                size = 20

            lbl.setFixedSize(size, size)

            pm = QPixmap(full_path)
            if not pm.isNull():
                pm = pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                lbl.setPixmap(pm)

            def open_url(_, url=link):
                QDesktopServices.openUrl(QUrl(url))

            lbl.mousePressEvent = open_url
            icons_box.addWidget(lbl)


        mexc_url = f"https://www.mexc.com/ru-RU/futures/{base}_USDT?_from=search"


        jupiter_mint = getattr(pair_cfg, "jupiter_mint", None)
        if jupiter_mint:

            jup_url = f"https://jup.ag/?sell={jupiter_mint}&buy={JUPITER_USDT_MINT}"
        else:
            jup_url = "https://jup.ag/"


        bsc_address = getattr(pair_cfg, "bsc_address", None)
        if bsc_address:

            pancake_url = (
                "https://pancakeswap.finance/swap"
                f"?outputCurrency={BSC_USDT}&inputCurrency={bsc_address}"
            )
        else:
            pancake_url = "https://pancakeswap.finance/swap"


        add_icon("jupiter", "mexc_icon.png", mexc_url)
        add_icon("jupiter", "jupiter_icon.png", jup_url)

        # Pancake → MEXC + Pancake
        add_icon("pancake", "mexc_icon.png", mexc_url)
        add_icon("pancake", "pancakeswap_icon.png", pancake_url)

        # Matcha → MEXC + Matcha
        matcha_addr = getattr(pair_cfg, "matcha_address", None)

        if matcha_addr:

            matcha_url = (
                f"https://matcha.xyz/tokens/base/{matcha_addr}"
                f"/select?sellChain={MATCHA_CHAIN_ID}&sellAddress={MATCHA_USDT}"
            )
        else:
            matcha_url = "https://matcha.xyz/"
        add_icon("matcha", "mexc_icon.png", mexc_url)
        add_icon("matcha", "matcha_icon.png", matcha_url)






class DraggableDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos: Optional[QPoint] = None
        self._dragging: bool = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:

            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            self._dragging = True
            self.grabMouse()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._dragging
            and (event.buttons() & Qt.LeftButton)
            and self._drag_pos is not None
        ):
            self.move(event.globalPos() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._dragging:
            # отпускаем захват мыши, когда ЛКМ отпущена
            self._dragging = False
            self._drag_pos = None
            self.releaseMouse()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

class BusyDialog(DraggableDialog):

    def __init__(self, parent=None, text: str = "Загрузка…"):
        super().__init__(parent)
        from PyQt5.QtWidgets import QVBoxLayout
        from PyQt5.QtCore import QTimer

        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # ~60 FPS
        self._tick()
        # делаем первый шаг сразу, чтобы при появлении окна
        # анимация уже была "в движении", без паузы
        self._tick()

        self._text = QLabel(text)
        self._text.setStyleSheet(BUSY_TEXT_STYLE)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(6)


        lay.addStretch()
        lay.addWidget(self._text, 0, Qt.AlignHCenter | Qt.AlignBottom)
        lay.addSpacing(8)

        self.resize(240, 120)
        # лёгкая тень/округление через стили
        self.setStyleSheet(BUSY_DIALOG_STYLE)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def setText(self, text: str):
        self._text.setText(text)

    def _tick(self):
        self._angle = (self._angle - 6) % 360
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        # фон
        r = self.rect().adjusted(6, 6, -6, -6)
        p.setBrush(QColor(2, 6, 23, 230))  # тёмная карточка
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, 12, 12)

        # спиннер
        size = 36
        cx = self.width() // 2
        cy = self.height() // 2 - 24
        radius = size // 2

        pen = QPen(QColor("#60a5fa"))   # голубое кольцо
        pen.setWidth(4)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)

        # рисуем дугу 270°
        start = int(self._angle * 16)
        span = int(-270 * 16)
        p.drawArc(cx - radius, cy - radius, size, size, start, span)
        p.end()



class LogDialog(DraggableDialog):
    _RESIZE_MARGIN = 6

    def __init__(self, parent=None):
        super().__init__(parent)


        self._resize_active = False
        self._resize_edge: Optional[str] = None
        self._resize_start_geom: Optional[QRect] = None
        self._resize_start_mouse: Optional[QPoint] = None


        self.setMouseTracking(True)

        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.Dialog)

        self.setModal(False)


        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(800, 500)


        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)


        frame = QWidget()
        frame.setObjectName("dialogFrame")
        frame.setAttribute(Qt.WA_StyledBackground, True)
        frame.setStyleSheet(DIALOG_FRAME)
        outer.addWidget(frame)

        frame.setMouseTracking(True)
        frame.installEventFilter(self)


        main = QVBoxLayout(frame)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Лог")
        title.setStyleSheet(LABEL_DIALOG_TITLE)
        header.addWidget(title)
        header.addStretch()

        btn_close = QPushButton()
        btn_close.setObjectName("CloseBtn")
        btn_close.setFixedSize(30, 30)
        btn_close.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_close.setAttribute(Qt.WA_StyledBackground, True)  # ← обязательно
        btn_close.setStyleSheet(BUTTON_ROUND_ICON)
        btn_close.setIcon(make_close_icon(size=18, thickness=2, color="#e5e7eb"))
        btn_close.setIconSize(QSize(18, 18))
        btn_close.setText("")
        btn_close.clicked.connect(self.reject)
        header.addWidget(btn_close)

        main.addLayout(header)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setStyleSheet(TEXTEDIT_LOG + SCROLLBAR_DARK)
        main.addWidget(self.text)


        self._last_log_len = 0

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_clear = QPushButton("Очистить")
        btn_clear.setStyleSheet(BUTTON_CLEAR)
        btn_clear.clicked.connect(self.clear_log)
        btn_row.addWidget(btn_clear)
        main.addLayout(btn_row)

        self.refresh()


        self._timer = QTimer(self)
        self._timer.setInterval(500)  # раз в 0.5 секунды
        self._timer.timeout.connect(self._on_timer_tick)
        self._timer.start()

    def refresh(self):

        start_index = getattr(self, "_last_log_len", 0)
        new_items = LOG_LINES[start_index:]
        if not new_items:
            return
        def _escape(s: str) -> str:
            return (
                s.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;")
            )

        html_lines = []

        for raw in new_items:
            safe = _escape(str(raw))
            low = safe.lower()


            if (
                    "ошибка" in low
                    or "error" in low
                    or "исключение" in low
                    or "не удалось" in low
                    or "traceback" in low
                    or "неуспешный ответ" in low
            ):
                line = f'<span style="color:#ef4444;">{safe}</span>'
            else:
                line = safe


                def replace_first(original: str, target: str, replacement: str):
                    idx = original.find(target)
                    if idx == -1:
                        return original
                    return (
                            original[:idx]
                            + replacement
                            + original[idx + len(target):]
                    )




                line = replace_first(
                    line,
                    "MEXC",
                    '<span style="color:#3b82f6;"><b>MEXC</b></span>'
                )

                # Jupiter (лайм-зелёный, bold)
                line = replace_first(
                    line,
                    "Jupiter",
                    '<span style="color:#4ade80;"><b>Jupiter</b></span>'
                )
                line = replace_first(
                    line,
                    "JUPITER",
                    '<span style="color:#4ade80;"><b>JUPITER</b></span>'
                )

                # Pancake (нежно-голубой, bold)
                line = replace_first(
                    line,
                    "Pancake",
                    '<span style="color:#38bdf8;"><b>Pancake</b></span>'
                )
                line = replace_first(
                    line,
                    "PANCAKE",
                    '<span style="color:#38bdf8;"><b>PANCAKE</b></span>'
                )

                # Matcha (тёмно-зелёный, bold)
                line = replace_first(
                    line,
                    "Matcha",
                    '<span style="color:#15803d;"><b>Matcha</b></span>'
                )
                line = replace_first(
                    line,
                    "matcha",
                    '<span style="color:#15803d;"><b>matcha</b></span>'
                )


            html_lines.append(line)

        html = "<br>".join(html_lines)

        # были ли мы почти внизу ДО обновления
        bar = self.text.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - 5

        # добавляем новые строки в конец документа отдельным курсором,
        # чтобы не сбросить текущее выделение
        cursor = QTextCursor(self.text.document())
        cursor.movePosition(QTextCursor.End)
        if self.text.document().characterCount() > 1:
            cursor.insertHtml("<br>" + html)
        else:
            cursor.insertHtml(html)


        self._last_log_len = len(LOG_LINES)


        if at_bottom:
            bar = self.text.verticalScrollBar()
            bar.setValue(bar.maximum())


        if at_bottom:
            bar = self.text.verticalScrollBar()
            bar.setValue(bar.maximum())

    def clear_log(self):
        LOG_LINES.clear()
        self.text.clear()
        self._last_log_len = 0
        log("Лог очищен пользователем")
        self.refresh()

    def _on_timer_tick(self):

        if self.isVisible():
            self.refresh()



    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseMove:
            global_pos = event.globalPos()
            local_pos = self.mapFromGlobal(global_pos)

            # Если не тянем окно и ЛКМ не зажата — хотим только подсветить край
            if not (event.buttons() & Qt.LeftButton) and not self._resize_active:
                self._update_cursor(local_pos)

        return super().eventFilter(obj, event)



    def _detect_edge(self, pos: QPoint):
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

        # --- ЛКМ не зажата: просто обновляем курсор у границ окна ---
        if not (event.buttons() & Qt.LeftButton):
            self._update_cursor(event.pos())

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


# =========================
#  "Липкое" меню DEX / CEX / Режим
# =========================

class StickyMenu(QMenu):
    """
    Меню, в котором чекбоксы не закрывают меню при клике.
    Мы сами переключаем isChecked и зовём callback с действием.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # сюда мы назначаем функцию вида: callback(action)
        self.state_changed_callback = None

    def mouseReleaseEvent(self, event):
        action = self.actionAt(event.pos())
        if action and action.isCheckable():
            # Только переключаем галку, БЕЗ action.trigger(),
            # чтобы не было двойного toggling
            action.setChecked(not action.isChecked())

            if self.state_changed_callback:
                try:
                    # новая версия — ожидаем функцию callback(action)
                    self.state_changed_callback(action)
                except TypeError:
                    # если вдруг где-то ещё остался callback без аргументов — не падаем
                    self.state_changed_callback()

            event.accept()
        else:
            super().mouseReleaseEvent(event)


# =========================
#  Диалог "Добавить токен" (Биржа A/B с такой же стрелкой, как наверху)
# =========================
class MessageDialog(DraggableDialog):
    """Универсальный диалог: frameless, наш фон, наш OK."""
    def __init__(self, parent=None, title: str = "Предупреждение", text: str = "", kind: str = "warn"):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # верхний лэйаут сразу делаем горизонтальным (для цветной полоски слева)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # карточка
        card = QWidget()
        card.setObjectName("MsgCard")
        card.setStyleSheet(MESSAGE_CARD_STYLE)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)

        # Заголовок + крестик
        head = QHBoxLayout()
        self._title = QLabel(title)
        self._title.setStyleSheet(LABEL_DIALOG_TITLE)
        head.addWidget(self._title)
        head.addStretch()

        btn_close = QPushButton()
        btn_close.setObjectName("CloseBtn")
        btn_close.setFixedSize(30, 30)
        btn_close.setAttribute(Qt.WA_StyledBackground, True)
        btn_close.setStyleSheet(BUTTON_ROUND_ICON)
        btn_close.setIcon(make_close_icon(size=18, thickness=2, color="#e5e7eb"))
        btn_close.setIconSize(QSize(18, 18))
        btn_close.clicked.connect(self.reject)
        head.addWidget(btn_close)
        lay.addLayout(head)

        # Текст
        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setStyleSheet(MESSAGE_TEXT_STYLE)
        lay.addWidget(self._label)

        # Низ: кнопка OK в нашем стиле
        row = QHBoxLayout()
        row.addStretch()

        # Кнопка "Отмена" (по умолчанию прячем, будем включать только там,
        # где нужен диалог подтверждения)
        self._cancel = QPushButton("Отмена")
        self._cancel.setStyleSheet(BUTTON_CLEAR)
        self._cancel.setFixedSize(120, 36)
        self._cancel.clicked.connect(self.reject)
        row.addWidget(self._cancel)
        self._cancel.hide()

        # Кнопка "ОК"
        self._ok = QPushButton("OK")
        self._ok.setStyleSheet(BUTTON_PRIMARY)
        self._ok.setFixedSize(120, 36)
        self._ok.clicked.connect(self.accept)
        row.addWidget(self._ok)

        lay.addLayout(row)

        self.resize(420, 160)

        # Цветовая полоска слева
        self._kind = kind
        self._accent = QWidget()
        self._accent.setFixedWidth(4)
        self._accent.setStyleSheet(
            f"background-color: {self._kind_color(kind)}; {ACCENT_STRIP_LEFT}"
        )

        # соберём финальный вид
        outer.addWidget(self._accent)
        outer.addWidget(card)

    def _kind_color(self, kind: str) -> str:
        if kind == "success":
            return "#22c55e"  # зелёный
        if kind == "error":
            return "#ef4444"  # красный
        return "#f59e0b"      # жёлтый (warn)

    @staticmethod
    def warn(parent, reasons: List[str]):
        # Заголовок всегда «Предупреждение», тело — список причин
        body = "Пожалуйста, исправьте:\n" + "\n".join(f"• {r}" for r in reasons)
        dlg = MessageDialog(parent, "Предупреждение", body, "warn")
        dlg.exec_()

    @staticmethod
    def error(parent, reason: str):
        dlg = MessageDialog(parent, "Ошибка", reason, "error")
        dlg.exec_()

    @staticmethod
    def success(parent, text: str):
        dlg = MessageDialog(parent, "Успех", text, "success")
        dlg.exec_()

    @staticmethod
    def confirm_delete(parent, token_name: str) -> bool:
        """
        Окно подтверждения удаления токена.
        Возвращает True, если нажали «Удалить».
        """
        text = f"Удалить токен «{token_name}» из списка?"
        dlg = MessageDialog(parent, "Подтверждение", text, "error")

        # переназначаем подпись ОК и показываем кнопку Отмена
        dlg._ok.setText("Удалить")
        dlg._cancel.show()
        dlg._cancel.setText("Отмена")

        return dlg.exec_() == QDialog.Accepted


class AddTokenDialog(DraggableDialog):
    def __init__(
        self,
        parent=None,
        title: str = "Добавить токен",
        ok_text: str = "Добавить",
        initial_token: str = "",
        initial_dex: Optional[str] = None,
        lock_dex: bool = False,
    ):
        super().__init__(parent)

        # режим редактирования: можем передать уже выбранный DEX и залочить его
        self._lock_dex = bool(lock_dex)
        self._initial_dex = (initial_dex or "").lower() if initial_dex else None

        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setModal(True)
        self.setStyleSheet(DIALOG_ADD)

        # Прозрачный фон окна, чтобы углы реально были скруглённые
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.resize(380, 300)

        # внутренние значения выбранных бирж и токена
        self.dex_a_key = None
        self.dex_b_key = None
        self._final_token = None
        self.jupiter_mint: Optional[str] = None
        self.jupiter_decimals: Optional[int] = None
        self.bsc_address: Optional[str] = None
        self._mexc_price_scale: Optional[int] = None
        self.matcha_address: Optional[str] = None
        self.matcha_decimals: Optional[int] = None

        # ---------- основной layout ----------
        main = QVBoxLayout(self)
        main.setContentsMargins(20, 20, 20, 16)
        main.setSpacing(14)

        # ---------- заголовок ----------
        header = QHBoxLayout()
        self.lbl_title = QLabel(title)                      # ← используем параметр title
        self.lbl_title.setStyleSheet(LABEL_DIALOG_TITLE)
        header.addWidget(self.lbl_title)
        header.addStretch()

        btn_close = QPushButton()
        btn_close.setObjectName("CloseBtn")
        btn_close.setFixedSize(30, 30)
        btn_close.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_close.setAttribute(Qt.WA_StyledBackground, True)
        btn_close.setStyleSheet(BUTTON_ROUND_ICON)
        btn_close.setIcon(make_close_icon(size=18, thickness=2, color="#e5e7eb"))
        btn_close.setIconSize(QSize(18, 18))
        btn_close.setText("")
        btn_close.clicked.connect(self.reject)

        header.addWidget(btn_close)
        main.addLayout(header)
        main.addSpacing(20)

        # ---------- Биржа A (DEX) ----------
        lbl_a = QLabel("DEX")
        lbl_a.setStyleSheet(LABEL_FORM)

        self.btn_a = QPushButton("Выбрать DEX")
        self.btn_a.setFixedSize(160, 36)
        self.btn_a.setStyleSheet(BUTTON_TOP_DARK)

        menu_a = StickyMenu(self.btn_a)
        menu_a.setStyleSheet(DEX_MENU)

        def set_a(key: str, text: str):
            self.dex_a_key = key
            self.btn_a.setText(text)

        dex_variants = [
            ("pancake", "Pancake"),
            ("jupiter", "Jupiter"),
            ("matcha", "Matcha"),
        ]

        for key, text in dex_variants:
            act = menu_a.addAction(text)
            act.setCheckable(False)
            act.triggered.connect(
                lambda checked, k=key, t=text: set_a(k, t)
            )

        # если диалог открыт в режиме редактирования и нам передали DEX —
        # сразу выставляем его в кнопку
        if self._initial_dex:
            for key, text in dex_variants:
                if key == self._initial_dex:
                    set_a(key, text)
                    break

        # если DEX залочен (редактирование) — делаем кнопку некликабельной
        if self._lock_dex and self.dex_a_key:
            self.btn_a.setEnabled(False)
            self.btn_a.setStyleSheet(
                BUTTON_TOP_DARK
                + """
                        QPushButton:disabled {
                            background-color: #374151;  /* тёмно-серый фон */
                            color: #9ca3af;             /* светло-серый текст */
                            border: 1px solid #4b5563;  /* чуть более тёмная рамка */
                        }
                        """
            )

        menu_a.aboutToShow.connect(
            lambda m=menu_a: m.setFixedWidth(self.btn_a.width())
        )
        self.btn_a.setMenu(menu_a)
        attach_menu_arrow(self.btn_a, menu_a)

        # ---------- Биржа B (CEX) ----------
        lbl_b = QLabel("CEX фьючерсы")
        lbl_b.setStyleSheet(LABEL_FORM)

        self.btn_b = QPushButton("Выбрать биржу")
        self.btn_b.setFixedSize(160, 36)
        self.btn_b.setStyleSheet(BUTTON_TOP_DARK)

        menu_b = StickyMenu(self.btn_b)
        menu_b.setStyleSheet(DEX_MENU)

        def set_b(key: str, text: str):
            self.dex_b_key = key
            self.btn_b.setText(text)

        act_mexc = menu_b.addAction("MEXC")
        act_mexc.setCheckable(False)
        act_mexc.triggered.connect(
            lambda checked, k="MEXC", t="MEXC": set_b(k, t)
        )

        menu_b.aboutToShow.connect(
            lambda m=menu_b: m.setFixedWidth(self.btn_b.width())
        )
        self.btn_b.setMenu(menu_b)
        attach_menu_arrow(self.btn_b, menu_b)

        # ---------- две биржи в один ряд ----------
        row_ab = QHBoxLayout()
        col_a = QVBoxLayout()
        col_b = QVBoxLayout()

        # СЛЕВА — биржа (MEXC)
        col_a.addWidget(lbl_b)
        col_a.addWidget(self.btn_b)

        # СПРАВА — DEX
        col_b.addWidget(lbl_a)
        col_b.addWidget(self.btn_a)

        row_ab.addStretch()
        row_ab.addLayout(col_a)
        row_ab.addSpacing(12)
        row_ab.addLayout(col_b)
        row_ab.addStretch()

        main.addLayout(row_ab)

        # ---------- Токен ----------
        main.addSpacing(16)
        lbl_token = QLabel("Токен")
        lbl_token.setStyleSheet(LABEL_FORM)

        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText("Адрес контракта")
        self.token_edit.setStyleSheet(LINEEDIT_DARK)
        if initial_token:                              # ← подставляем токен при редактировании
            self.token_edit.setText(initial_token)

        main.addWidget(lbl_token)
        main.addWidget(self.token_edit)

        main.addSpacing(32)

        # ---------- Кнопки ОК / Отмена ----------
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 8, 0, 0)
        btn_row.setSpacing(24)

        btn_cancel = QPushButton("Отмена")
        btn_ok = QPushButton(ok_text)                  # ← используем параметр ok_text

        btn_cancel.setStyleSheet(BUTTON_CLEAR)
        btn_ok.setStyleSheet(BUTTON_PRIMARY)

        BTN_W, BTN_H = 130, 36
        for b in (btn_cancel, btn_ok):
            b.setFixedSize(BTN_W, BTN_H)
            b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        btn_cancel.clicked.connect(self.reject)
        btn_ok.clicked.connect(self.on_add_clicked)

        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        btn_row.addStretch()

        main.addLayout(btn_row)

    def paintEvent(self, event):
        # Рисуем только фон с закруглёнными углами, дети (кнопки/лейблы)
        # рисуются сами, поэтому их сюда НЕ трогаем
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        r = self.rect().adjusted(1, 1, -1, -1)
        p.setBrush(QColor("#020617"))  # фон диалога
        p.setPen(QPen(QColor("#1f2937")))  # рамка
        p.drawRoundedRect(r, 12, 12)
        p.end()




    def _normalize_mexc_symbol(self, token: str) -> str:
        """
        Приводим тикер к формату AAA_BBB (например MEMERUSH_USDT).

        Поддерживаем:
        - MEMERUSH        -> MEMERUSH_USDT
        - MEMERUSHUSDT    -> MEMERUSH_USDT
        - MEMERUSH_USDT   -> MEMERUSH_USDT (без изменений)
        """
        t = (token or "").upper().replace(" ", "").strip()
        if not t:
            return ""

        # Уже нормальный формат
        if t.endswith("_USDT"):
            return t

        # MEMERUSHUSDT или MEMERUSH_USDT (без нижнего подчёркивания)
        if t.endswith("USDT"):
            base = t[:-4]  # отрезаем 'USDT'
            if base.endswith("_"):
                base = base[:-1]
            return f"{base}_USDT"

        # Просто MEMERUSH -> MEMERUSH_USDT
        return f"{t}_USDT"

    def _check_mexc_symbol(self, token: str) -> Optional[str]:
        """
        Возвращает None, если контракт существует.
        Возвращает строку-ошибку, если контракта нет или запрос неудачен.
        Заодно сохраняет priceScale в self._mexc_price_scale.
        """
        try:
            symbol = self._normalize_mexc_symbol(token)
            if not symbol:
                return "Пустой тикер для проверки на MEXC."

            url = "https://contract.mexc.com/api/v1/contract/detail"
            resp = http_client.get(url, params={"symbol": symbol}, timeout=5)
            data = resp.json() if hasattr(resp, "json") else resp

            # логируем полный ответ
            log(f"MEXC detail ответ для {symbol}: {data}")

            # MEXC: success=false, code=1001 => 合约不存在! (контракт не существует)
            if not data.get("success", False):
                code = data.get("code")
                msg = data.get("message", "")
                if code == 1001 or "不存在" in str(msg):
                    return f"Контракт {symbol} не существует на MEXC (code 1001). Проверьте тикер."
                return f"Ошибка MEXC для {symbol}: code={code}, message={msg}"

            # success=True — контракт есть, забираем priceScale один раз
            detail = data.get("data") or {}
            ps = detail.get("priceScale")

            self._mexc_price_scale = None
            if ps is not None:
                try:
                    self._mexc_price_scale = int(ps)
                    log(f"MEXC detail: priceScale для {symbol} = {self._mexc_price_scale}")
                except Exception as e:
                    log(f"MEXC detail: не удалось преобразовать priceScale для {symbol}: {ps} ({e})")

            return None

        except Exception as e:
            return f"Сеть/запрос к MEXC не удался: {e}"

    def _resolve_jupiter_symbol(self, query: str) -> (Optional[str], Optional[str]):
        """
        По адресу контракта или символу возвращает symbol из Jupiter.
        Возвращает (symbol, None) при успехе или (None, текст_ошибки) при неудаче.
        Дополнительно сохраняет mint и decimals во внутренние поля.
        """
        q = (query or "").strip()
        if not q:
            return None, "Пустой запрос в Jupiter."

        try:
            url = "https://lite-api.jup.ag/tokens/v2/search"
            resp = http_client.get(url, params={"query": q}, timeout=5)
            data = resp.json() if hasattr(resp, "json") else resp

            if not isinstance(data, list) or not data:
                return None, "Jupiter: токен с таким контрактом не найден."

            # сначала пытаемся найти точное совпадение по id (mint)
            best = None
            q_lower = q.lower()
            for item in data:
                try:
                    if str(item.get("id", "")).lower() == q_lower:
                        best = item
                        break
                except Exception:
                    continue

            if best is None:
                best = data[0]

            symbol = str(best.get("symbol") or "").strip()
            name = str(best.get("name") or "").strip()

            if not symbol and not name:
                return None, "Jupiter: в ответе нет symbol/name для этого контракта."

            final = symbol or name

            # --- НОВОЕ: mint + decimals ---
            mint = str(best.get("id") or "").strip()
            dec_raw = best.get("decimals")
            try:
                dec_val = int(dec_raw) if dec_raw is not None else None
            except Exception:
                dec_val = None

            self.jupiter_mint = mint or q  # если вдруг id пустой
            self.jupiter_decimals = dec_val

            log(
                f"Jupiter: query={q} -> symbol={symbol}, name={name}, "
                f"decimals={dec_val}, id={mint}"
            )
            return final, None

        except Exception as e:
            return None, f"Ошибка запроса к Jupiter: {e}"

    def _resolve_mexc_symbol_by_contract(
            self,
            contract_addr: str,
            use_bscscan: bool = False,
    ):
        """
        По адресу контракта (Solana mint / EVM) ищем токен на MEXC.

        1) Пытаемся найти контракт в symbolsV2 (поле ca) и взять vn.
        2) Если не нашли:
           - собираем ВСЕ token_symbol из Solscan /v2/account?address=...&view_as=token
             (metadata.tokens[*].token_symbol),
           - по очереди проверяем MEXC futures/<SYMBOL>_USDT
        Возвращает (base_symbol, None) при успехе
        или (None, текст_ошибки) при неудаче.
        """
        q = (contract_addr or "").strip()
        if not q:
            return None, "Пустой адрес контракта для MEXC."

        MEXC_HEADERS = {
            "Host": "www.mexc.com",
            "Connection": "keep-alive",
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8,"
                "application/signed-exchange;v=b3;q=0.7"
            ),
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/141.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.8",
        }

        SOLSCAN_HEADERS = {
            "accept": "application/json, text/plain, */*",
            "origin": "https://solscan.io",
            "referer": "https://solscan.io/",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/141.0.0.0 Safari/537.36"
            ),
        }

        q_norm = q.lower()

        try:
            # ------------------------------------------------------------------
            # 1. Основная ветка — symbolsV2
            # ------------------------------------------------------------------
            url = "https://www.mexc.com/api/platform/spot/market-v2/web/symbolsV2"
            log(f"MEXC symbolsV2: GET {url}")
            resp = http_client.get(url, headers=MEXC_HEADERS, timeout=20)

            raw = resp.text or ""
            log(
                f"MEXC symbolsV2: status={resp.status_code}, "
                f"raw[:80]={raw[:80]!r}"
            )

            if resp.status_code == 200 and raw.strip():
                try:
                    data = resp.json()
                except Exception as e:
                    log(
                        "MEXC symbolsV2: невалидный JSON, "
                        f"raw[:200]={raw[:200]!r}, error={e}"
                    )
                    return None, f"Ошибка MEXC symbolsV2: {e}"

                root = data.get("data") or {}
                symbols_root = root.get("symbols") or {}
                if not isinstance(symbols_root, dict):
                    log(
                        "MEXC symbolsV2: symbols_root type="
                        f"{type(symbols_root)}"
                    )
                else:
                    found = None
                    for quote_asset, token_list in symbols_root.items():
                        if not isinstance(token_list, list):
                            continue
                        for item in token_list:
                            try:
                                ca = str(item.get("ca", "")).strip()
                                if not ca:
                                    continue
                                if ca.lower() == q_norm:
                                    found = item
                                    break
                            except Exception:
                                continue
                        if found:
                            break

                    if found:
                        base_symbol = str(found.get("vn") or "").strip()
                        if not base_symbol:
                            return None, (
                                "MEXC: symbolsV2 не вернул vn "
                                "для этого контракта."
                            )

                        log(
                            "MEXC symbolsV2: contract={q} -> vn={vn}".format(
                                q=q_norm, vn=base_symbol
                            )
                        )
                        return base_symbol, None
                    else:
                        log(
                            "MEXC symbolsV2: контракт {q} не найден по ca, "
                            "делаем fallback через Solscan.".format(q=q_norm)
                        )
            else:
                log(
                    "MEXC symbolsV2: HTTP {code}, пустой или нет тела, "
                    "делаем fallback через Solscan.".format(
                        code=resp.status_code
                    )
                )

            if use_bscscan and q_norm.startswith("0x") and len(q_norm) == 42:
                # Здесь мы используем bsc_web3 и ERC20_ABI из core.py
                try:
                    checksum = bsc_web3.to_checksum_address(q)
                except Exception as e:
                    return None, f"BSC: неверный формат адреса {q}: {e}"

                try:
                    if not bsc_web3.is_connected():
                        return None, "BSC web3: нет соединения с RPC"

                    token = bsc_web3.eth.contract(address=checksum, abi=ERC20_ABI)

                    # читаем symbol() у контракта
                    symbol = token.functions.symbol().call()

                    # иногда symbol может быть bytes
                    if isinstance(symbol, bytes):
                        symbol = symbol.decode("utf-8", "ignore").rstrip("\x00")

                    base_symbol = (str(symbol) or "").strip().upper()
                    if not base_symbol:
                        return None, "BSC web3: symbol() вернул пустую строку."

                    # Доп. шаг как в zibil.py: сразу проверяем, что фьючерс существует
                    fut_url = f"https://www.mexc.com/en-US/futures/{base_symbol}_USDT"
                    log(
                        "MEXC BSC web3 futures check: {sym}_USDT -> {url}".format(
                            sym=base_symbol, url=fut_url
                        )
                    )

                    last_status = None
                    try:
                        fut_resp = http_client.get(fut_url, headers=MEXC_HEADERS, timeout=20)
                        last_status = fut_resp.status_code
                        log(
                            "MEXC BSC web3 futures check: {sym}_USDT -> HTTP {code}".format(
                                sym=base_symbol,
                                code=fut_resp.status_code,
                            )
                        )
                        if fut_resp.status_code == 200:
                            # всё ок: символ подходит, вернём его как vn для второстепенной проверки
                            return base_symbol, None
                    except Exception as e:
                        log(
                            f"MEXC BSC web3 futures check error for {base_symbol}: {e}"
                        )

                    err_msg = (
                        "MEXC: через web3 получили symbol={sym}, "
                        "но страница фьючерса {sym}_USDT не вернула 200."
                    ).format(sym=base_symbol)
                    if last_status is not None:
                        err_msg += f" HTTP статус: {last_status}."
                    return None, err_msg

                except Exception as e:
                    return None, f"Ошибка BSC web3 fallback для контракта {q_norm}: {e}"
            # ------------------------------------------------------------------
            # 2. Fallback через Solscan + проверка futures
            # ------------------------------------------------------------------
            try:
                solscan_url = (
                    "https://api-v2.solscan.io/v2/account"
                    f"?address={q}&view_as=token"
                )
                log(f"Solscan fallback: GET {solscan_url}")
                s_resp = http_client.get(
                    solscan_url, headers=SOLSCAN_HEADERS, timeout=20
                )
                log(
                    "Solscan fallback: status={code} for {addr}".format(
                        code=s_resp.status_code, addr=q
                    )
                )

                symbol_candidates = []  # сюда соберём ВСЕ token_symbol

                if s_resp.status_code == 200:
                    try:
                        s_data = s_resp.json()
                    except Exception as e:
                        log(f"Solscan fallback: invalid JSON for {q}: {e}")
                        s_data = None

                    if isinstance(s_data, dict):
                        meta = s_data.get("metadata") or {}
                        tokens_md = meta.get("tokens") or {}
                        if isinstance(tokens_md, dict):
                            # 1) Сначала пробуем токен, чей адрес == нашему контракту
                            primary_tinfo = (
                                tokens_md.get(q)
                                or tokens_md.get(q_norm)
                            )
                            if isinstance(primary_tinfo, dict):
                                tsym = (
                                    primary_tinfo.get("token_symbol")
                                    or primary_tinfo.get("symbol")
                                    or primary_tinfo.get("tokenSymbol")
                                )
                                if tsym:
                                    tsym = str(tsym).strip()
                                    if tsym and tsym not in symbol_candidates:
                                        symbol_candidates.append(tsym)

                            # 2) Потом добавляем ВСЕ остальные token_symbol
                            for mint_addr, tinfo in tokens_md.items():
                                if not isinstance(tinfo, dict):
                                    continue
                                tsym = (
                                    tinfo.get("token_symbol")
                                    or tinfo.get("symbol")
                                    or tinfo.get("tokenSymbol")
                                )
                                if not tsym:
                                    continue
                                tsym = str(tsym).strip()
                                if tsym and tsym not in symbol_candidates:
                                    symbol_candidates.append(tsym)

                        # 3) Если совсем ничего не нашли — пробуем data.symbol
                        if not symbol_candidates:
                            d_node = s_data.get("data") or {}
                            if isinstance(d_node, dict):
                                tsym = (
                                    d_node.get("symbol")
                                    or d_node.get("tokenSymbol")
                                )
                                if tsym:
                                    tsym = str(tsym).strip()
                                    if tsym:
                                        symbol_candidates.append(tsym)
                else:
                    log(
                        "Solscan fallback: HTTP {code} for {addr}".format(
                            code=s_resp.status_code, addr=q
                        )
                    )

                if not symbol_candidates:
                    log(
                        f"Solscan fallback: ни одного token_symbol "
                        f"не найдено для {q}"
                    )
                    return None, (
                        f"MEXC: токен с контрактом {q_norm} не найден в "
                        f"symbolsV2 и token_symbol не удалось получить через Solscan."
                    )

                log(
                    "Solscan fallback: найденные token_symbol: "
                    + ", ".join(symbol_candidates)
                )

                # 3) по очереди проверяем наличие фьючерса на MEXC
                last_status = None
                last_err = None

                for sym in symbol_candidates:
                    base_symbol = sym.strip().upper()
                    if not base_symbol:
                        continue

                    try:
                        fut_url = (
                            "https://www.mexc.com/en-US/futures/"
                            f"{base_symbol}_USDT"
                        )
                        log(f"MEXC fallback futures: GET {fut_url}")
                        fut_resp = http_client.get(
                            fut_url, headers=MEXC_HEADERS, timeout=20
                        )
                        last_status = fut_resp.status_code
                        log(
                            "MEXC fallback futures: {sym}_USDT -> HTTP {code}".format(
                                sym=base_symbol, code=fut_resp.status_code
                            )
                        )

                        if fut_resp.status_code == 200:
                            # всё ок — подтверждаем именно этот тикер
                            return base_symbol, None
                    except Exception as e:
                        last_err = str(e)
                        log(
                            f"MEXC fallback futures: error for "
                            f"{base_symbol}_USDT: {e}"
                        )
                        # пробуем следующий symbol

                # если ни один symbol не прошёл проверку
                return None, (
                    "MEXC: контракт {q}, пробовали token_symbol: {syms}, "
                    "но страница futures вернула не 200 (последний статус: {st}){err}."
                ).format(
                    q=q_norm,
                    syms=", ".join(symbol_candidates),
                    st=last_status,
                    err=f", ошибка: {last_err}" if last_err else "",
                )

            except Exception as e:
                log(f"Solscan fallback: общая ошибка для {q}: {e}")
                return None, (
                    f"MEXC: токен с контрактом {q_norm} не найден в symbolsV2 "
                    f"и возникла ошибка Solscan: {e}"
                )

        except Exception as e:
            return None, f"Сеть/запрос к MEXC symbolsV2 не удался: {e}"

    def _resolve_mexc_symbol_for_base(self, contract_addr: str):
        """
        Для Base (Matcha + MEXC): двухуровневая проверка как в zibil.py:
        1) пробуем обычный _resolve_mexc_symbol_by_contract (symbolsV2 по ca)
        2) если не нашли — fallback через web3 на Base RPC + проверка futures HTML
        Возвращает (base_symbol, None) или (None, текст_ошибки).
        """
        q = (contract_addr or "").strip()
        if not q:
            return None, "Пустой адрес контракта для Base/MEXC."

        # 1) основной путь — твой текущий поиск через symbolsV2
        base_symbol, err1 = self._resolve_mexc_symbol_by_contract(q)
        if base_symbol:
            return base_symbol, None

        # если symbolsV2 не нашёл — логируем и пробуем web3 на Base
        if err1:
            log(f"Base secondary: primary MEXC symbolsV2 failed: {err1}")

        q_norm = q.lower()
        if not (q_norm.startswith("0x") and len(q_norm) == 42):
            # для не-EVM адреса fallback через Base web3 не имеет смысла
            return None, err1 or "Base: адрес не похож на EVM (0x + 40 hex)."

        # импортируем web3 локально, чтобы не падать при старте, если пакет не установлен
        try:
            from web3 import Web3
            from web3.exceptions import BadFunctionCallOutput, ContractLogicError
        except ImportError:
            return None, (
                "Для Base-fallback нужен пакет web3. "
                "Установи его: pip install web3"
            )

        BASE_RPC = "https://mainnet.base.org"

        try:
            checksum = Web3.to_checksum_address(q)
        except Exception as e:
            return None, f"Base: неверный формат адреса {q}: {e}"

        try:
            w3 = Web3(Web3.HTTPProvider(BASE_RPC))
            if not w3.is_connected():
                return None, "Base web3: нет соединения с RPC mainnet.base.org"

            token = w3.eth.contract(address=checksum, abi=ERC20_ABI)

            symbol_val = token.functions.symbol().call()

            # symbol может быть bytes
            if isinstance(symbol_val, bytes):
                symbol_val = symbol_val.decode("utf-8", "ignore").rstrip("\x00")

            base_symbol = (str(symbol_val) or "").strip().upper()
            if not base_symbol:
                return None, "Base web3: symbol() вернул пустую строку."

            log(
                "Base web3 fallback: contract={addr} -> symbol={sym}".format(
                    addr=checksum, sym=base_symbol
                )
            )

            # 3) Проверяем страницу фьючерса как в zibil.py / BSC-fallback
            MEXC_HEADERS = {
                "Host": "www.mexc.com",
                "Connection": "keep-alive",
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,image/apng,*/*;q=0.8,"
                    "application/signed-exchange;v=b3;q=0.7"
                ),
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/141.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.8",
            }

            fut_url = f"https://www.mexc.com/en-US/futures/{base_symbol}_USDT"
            log(
                "MEXC Base web3 futures check: {sym}_USDT -> {url}".format(
                    sym=base_symbol, url=fut_url
                )
            )

            last_status = None
            try:
                fut_resp = http_client.get(fut_url, headers=MEXC_HEADERS, timeout=20)
                last_status = fut_resp.status_code
                log(
                    "MEXC Base web3 futures check: {sym}_USDT -> HTTP {code}".format(
                        sym=base_symbol,
                        code=fut_resp.status_code,
                    )
                )
                if fut_resp.status_code == 200:
                    # всё ок — symbol подходит как vn для второстепенной проверки
                    return base_symbol, None
            except Exception as e:
                log(f"MEXC Base web3 futures check error for {base_symbol}: {e}")

            err_msg = (
                "MEXC: через Base web3 получили symbol={sym}, "
                "но страница фьючерса {sym}_USDT не вернула 200."
            ).format(sym=base_symbol)
            if last_status is not None:
                err_msg += f" HTTP статус: {last_status}."
            return None, err_msg

        except (BadFunctionCallOutput, ContractLogicError) as e:
            return None, f"Base web3: контракт не похож на стандартный ERC20: {e}"
        except Exception as e:
            return None, f"Ошибка Base web3 fallback для контракта {q_norm}: {e}"

    def _resolve_pancake_symbol(self, contract: str) -> (Optional[str], Optional[str]):
        """
        По адресу контракта на BSC возвращает (symbol, None) или (None, текст_ошибки).
        Также сохраняет checksum-адрес в self.bsc_address.
        """
        addr = (contract or "").strip()
        if not addr:
            return None, "Пустой адрес контракта Pancake."

        try:
            checksum = bsc_web3.to_checksum_address(addr)
        except Exception as e:
            return None, f"Pancake: некорректный адрес контракта: {e}"

        try:
            erc20 = bsc_web3.eth.contract(address=checksum, abi=ERC20_ABI)
            symbol = erc20.functions.symbol().call()
            symbol = str(symbol or "").strip()

            # Убираем пробелы, табы, невидимые символы
            symbol = symbol.replace(" ", "").replace("\t", "").replace("\n", "")
            if not symbol:
                return None, "Pancake: контракт не вернул symbol()."

            # сохраним адрес, чтобы потом положить в PairConfig
            self.bsc_address = checksum
            return symbol, None
        except Exception as e:
            log(f"Pancake: ошибка при получении symbol для {checksum}: {e}")
            return None, "Pancake: не удалось получить symbol для этого контракта."

    def _resolve_matcha_symbol(self, contract: str) -> (Optional[str], Optional[str]):
        """
        По адресу контракта (EVM, Matcha) возвращает (symbol, None) или (None, текст_ошибки).
        Запрашиваем метаданные у matcha API через core.get_matcha_token_info().
        Сохраняем self.matcha_address и self.matcha_decimals.
        """
        addr = (contract or "").strip()
        if not addr:
            return None, "Пустой адрес контракта Matcha."

        if not addr.startswith("0x") or len(addr) != 42:
            return None, "Matcha: некорректный формат адреса контракта."

        # Запрашиваем метаданные у Matcha (через core.get_matcha_token_info)
        try:
            info = get_matcha_token_info(addr, chain_id=MATCHA_CHAIN_ID)
        except Exception as e:
            return None, f"Matcha: ошибка получения метаданных: {e}"

        if not info:
            return None, "Matcha: не удалось получить метаданные для этого контракта."

        # Сохраняем адрес и decimals в диалоге (чтобы потом попали в PairConfig и tokens.json)
        self.matcha_address = info.get("address") or addr
        try:
            self.matcha_decimals = int(info.get("decimals"))
        except Exception:
            self.matcha_decimals = None

        symbol = (info.get("symbol") or "").strip().upper() or self.matcha_address
        return symbol, None



    def _check_pancake_markets(self) -> Optional[str]:
        """

        Возвращает:
          • None  — всё ок, можно работать;
          • str   — текст ошибки для MessageDialog.error().
        """
        addr = (self.bsc_address or "").strip()
        if not addr:
            return "Pancake: неизвестен адрес контракта (bsc_address пуст)."

        try:
            url = f"{DEXSCREENER_TOKENS_URL}/{addr}"
        except NameError:
            # Если вдруг константа не импортирована, подстрахуемся.
            url = f"https://api.dexscreener.com/latest/dex/tokens/{addr}"

        try:
            resp = http_client.get(url, timeout=5)
        except Exception as e:
            return f"Ошибка запроса к Pancake: {e}"

        if resp.status_code != 200:
            try:
                txt = resp.text[:150]
            except Exception:
                txt = ""
            return f"Pancake вернул статус {resp.status_code} для этого контракта.\n{txt}"

        try:
            data = resp.json()
        except Exception as e:
            return f"Pancake вернул невалидный JSON: {e}"

        pairs = data.get("pairs") or []
        if not isinstance(pairs, list) or not pairs:
            # аналог твоего "No markets found for token"
            return (
                "Pancake: для этого контракта не найдено ни одного рынка.\n"
                "Возможно, у токена нет ликвидности или он ещё не подхвачен."
            )

        # Ищем любой PancakeSwap пул
        has_pancake = False
        for p in pairs:
            dex_id = str(p.get("dexId", "")).lower()
            if "pancake" in dex_id:
                has_pancake = True
                break

        if not has_pancake:
            return (
                "Pancake: для этого контракта нет пула на PancakeSwap.\n"
                "Проверьте адрес контракта и наличие ликвидности на Pancake."
            )

        # Всё ок
        return None



    def _mexc_contract_missing(self, token: str) -> bool:
        """
        True, если в последних логах есть MEXC code 1001 для этого токена.
        Ищем ABC, ABCUSDT и ABC_USDT. Срабатывает и на китайское сообщение '合约不存在!'.
        """
        t = token.upper().strip()
        candidates = {t, f"{t}USDT", f"{t}_USDT"}

        # проверим побольше строк, т.к. лог мог появиться с задержкой
        for line in reversed(LOG_LINES[-600:]):
            s = str(line).upper()
            if "MEXC:" in s and ("CODE': 1001" in s or "CODE\": 1001" in s or "合约不存在" in s):
                if any(c in s for c in candidates):
                    return True
        return False

    def get_values(self):
        token = (self._final_token or self.token_edit.text()).strip()
        return (
            self.dex_a_key,
            self.dex_b_key,
            self._final_token,
            self.jupiter_mint,
            self.jupiter_decimals,
            self.bsc_address,
            self._mexc_price_scale,
            self.matcha_address,
            self.matcha_decimals,  # ← вот этот девятый элемент
        )


    def on_add_clicked(self):
        raw = self.token_edit.text().strip()

        # сбросим всё, что могли запомнить с предыдущего вызова
        self._final_token = None
        self.jupiter_mint = None
        self.jupiter_decimals = None
        self.bsc_address = None
        self.matcha_address = None
        self._mexc_price_scale = None

        reasons = []
        if not raw:
            if self.dex_a_key in ("jupiter", "pancake", "matcha"):
                reasons.append("Введите адрес контракта токена.")
            else:
                reasons.append("Введите тикер токена.")

        if not self.dex_a_key:
            reasons.append("Выберите DEX.")
        if not self.dex_b_key:
            reasons.append("Выберите биржу.")

        if reasons:
            MessageDialog.warn(self, reasons)
            return

        # по умолчанию считаем, что финальный токен — то, что ввёл пользователь
        final_token = raw.upper()

        # ====== ОСОБЫЙ СЛУЧАЙ: Jupiter + MEXC ======
        if self.dex_a_key == "jupiter" and self.dex_b_key == "MEXC":
            # 1) сначала забираем данные из Jupiter (mint + decimals)
            symbol, err = self._resolve_jupiter_symbol(raw)
            if err:
                MessageDialog.error(self, err)
                return

            # mint мы сохранили внутри _resolve_jupiter_symbol
            mint = (self.jupiter_mint or raw).strip()
            if not mint:
                MessageDialog.error(
                    self,
                    "Jupiter не вернул mint для этого контракта.",
                )
                return

            # 2) по mint ищем тикер на MEXC через symbolsV2 (поле ca -> vn)
            mexc_base, err2 = self._resolve_mexc_symbol_by_contract(mint)
            if err2:
                MessageDialog.error(self, err2)
                return

            final_token = (mexc_base or "").strip().upper()
            if not final_token:
                MessageDialog.error(
                    self,
                    "MEXC: не удалось получить корректный тикер (vn) для этого контракта.",
                )
                return

            # 3) Проверяем, что фьючерсный контракт существует на MEXC
            err_m = self._check_mexc_symbol(final_token)
            if err_m:
                MessageDialog.error(self, err_m)
                return


        # ====== ОСОБЫЙ СЛУЧАЙ: Matcha + MEXC ======
        elif self.dex_a_key == "matcha" and self.dex_b_key == "MEXC":
            # raw — адрес контракта (EVM)
            symbol, err = self._resolve_matcha_symbol(raw)
            if err:
                MessageDialog.error(self, err)
                return

            # _resolve_matcha_symbol уже сохранил нормализованный адрес в self.matcha_address
            contract = (self.matcha_address or raw or "").strip()
            if not contract:
                MessageDialog.error(self, "Не удалось получить адрес контракта Matcha.")
                return

            # Ищем токен на MEXC по адресу контракта:
            # 1) symbolsV2
            # 2) при ошибке — fallback через Base web3 (как в zibil.py)
            mexc_base, err2 = self._resolve_mexc_symbol_for_base(contract)
            if err2:
                MessageDialog.error(self, err2)
                return

            final_token = (mexc_base or "").strip().upper()
            if not final_token:
                MessageDialog.error(
                    self,
                    "MEXC не вернул vn (тикер) для этого контракта.",
                )
                return

            # Проверяем, что такой фьючерсный контракт есть на MEXC
            err_m = self._check_mexc_symbol(final_token)
            if err_m:
                MessageDialog.error(self, err_m)
                return



        # ====== ОСОБЫЙ СЛУЧАЙ: Pancake + MEXC ======
        elif self.dex_a_key == "pancake" and self.dex_b_key == "MEXC":
            # 1) BSC: получаем symbol() и checksum адрес
            symbol, err = self._resolve_pancake_symbol(raw)
            if err:
                MessageDialog.error(self, err)
                return

            # Здесь у тебя self.bsc_address уже сохранён
            contract = self.bsc_address

            # 2) Проверяем, есть ли Pancake рынок
            err_ds = self._check_pancake_markets()
            if err_ds:
                MessageDialog.error(self, err_ds)
                return

            # 3) Ищем MEXC vn по адресу контракта (теперь и BSC адрес тоже ищем!)
            mexc_base, err2 = self._resolve_mexc_symbol_by_contract(
                contract,
                use_bscscan=True,  # ← включаем BscScan-fallback
            )
            if err2:
                MessageDialog.error(self, err2)
                return

            final_token = (mexc_base or "").strip().upper()
            if not final_token:
                MessageDialog.error(
                    self,
                    "MEXC: не удалось получить vn для этого контракта.",
                )
                return


            err_m = self._check_mexc_symbol(final_token)
            if err_m:
                MessageDialog.error(self, err_m)
                return


        self._final_token = final_token
        self.accept()
