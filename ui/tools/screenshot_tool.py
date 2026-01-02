"""截图工具 - 微信风格：框选后显示工具条，直接在选区标注"""

from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QColorDialog, QSpinBox, QLineEdit
)
from PySide6.QtGui import (
    QPixmap, QCursor, QPainter, QColor, QPen, QFont, QBrush
)
from PySide6.QtCore import Qt, QRect, Signal, QPoint
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
import time
import math
import traceback

def debug(msg):
    import sys
    print(f"[DEBUG] {msg}", file=sys.stderr)


class ToolType(Enum):
    NONE = "none"
    RECT = "rect"
    ELLIPSE = "ellipse"
    ARROW = "arrow"
    LINE = "line"
    TEXT = "text"
    PEN = "pen"


@dataclass
class Annotation:
    tool: ToolType
    color: QColor
    width: int
    start: QPoint
    end: QPoint
    text: str = ""
    points: List[QPoint] = None

    def __post_init__(self):
        if self.points is None:
            self.points = []


class ScreenshotSelector(QWidget):
    """截图选择器 - 微信风格"""

    screenshot_taken = Signal(str)
    screenshot_cancelled = Signal()

    def __init__(self, save_dir: str = None):
        super().__init__()
        self.save_dir = Path(save_dir) if save_dir else Path.cwd() / "screenshots"
        self.screenshot = None
        self.start_pos = None
        self.end_pos = None
        self.selecting = True  # 是否在框选阶段
        self.selection_rect = None

        # 标注相关
        self.annotations: List[Annotation] = []
        self.undo_stack: List[Annotation] = []
        self.current_tool = ToolType.NONE
        self.current_color = QColor(255, 0, 0)
        self.current_width = 3
        self.drawing = False
        self.draw_start = None
        self.current_points = []

        # 工具栏按钮
        self.toolbar_buttons = []
        self.color_btn = None
        self.width_spin = None
        self.text_input = None
        self.text_pos = None

    def start_screenshot(self):
        """开始截图"""
        screen = QApplication.primaryScreen()
        self.screenshot = screen.grabWindow(0)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setGeometry(0, 0, self.screenshot.width(), self.screenshot.height())
        self.setCursor(Qt.CrossCursor)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.screenshot)

        # 绘制遮罩和选区
        if self.start_pos and self.end_pos:
            rect = QRect(self.start_pos, self.end_pos).normalized()
            mask = QColor(0, 0, 0, 120)

            # 四周遮罩
            painter.fillRect(0, 0, self.width(), rect.top(), mask)
            painter.fillRect(0, rect.bottom() + 1, self.width(), self.height() - rect.bottom() - 1, mask)
            painter.fillRect(0, rect.top(), rect.left(), rect.height(), mask)
            painter.fillRect(rect.right() + 1, rect.top(), self.width() - rect.right() - 1, rect.height(), mask)

            # 选区边框
            pen = QPen(QColor(0, 174, 255), 2)
            painter.setPen(pen)
            painter.drawRect(rect)

            # 尺寸提示
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Arial", 10))
            size_text = f"{rect.width()} x {rect.height()}"
            painter.drawText(rect.left(), rect.top() - 5, size_text)

            # 绘制标注
            for ann in self.annotations:
                self._draw_annotation(painter, ann)

            # 绘制当前正在画的
            if self.drawing and self.draw_start:
                current_ann = Annotation(
                    tool=self.current_tool,
                    color=self.current_color,
                    width=self.current_width,
                    start=self.draw_start,
                    end=self.mapFromGlobal(QCursor.pos()),
                    points=list(self.current_points)
                )
                self._draw_annotation(painter, current_ann)

    def _draw_annotation(self, painter: QPainter, ann: Annotation):
        pen = QPen(ann.color, ann.width)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        if ann.tool == ToolType.RECT:
            painter.drawRect(QRect(ann.start, ann.end))
        elif ann.tool == ToolType.ELLIPSE:
            painter.drawEllipse(QRect(ann.start, ann.end))
        elif ann.tool == ToolType.LINE:
            painter.drawLine(ann.start, ann.end)
        elif ann.tool == ToolType.ARROW:
            self._draw_arrow(painter, ann.start, ann.end, ann.color, ann.width)
        elif ann.tool == ToolType.PEN and ann.points:
            for i in range(1, len(ann.points)):
                painter.drawLine(ann.points[i-1], ann.points[i])
        elif ann.tool == ToolType.TEXT and ann.text:
            font = QFont("Microsoft YaHei", ann.width * 4)
            painter.setFont(font)
            painter.drawText(ann.start, ann.text)

    def _draw_arrow(self, painter: QPainter, start: QPoint, end: QPoint, color: QColor, width: int):
        painter.drawLine(start, end)
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        arrow_size = width * 4
        p1 = QPoint(int(end.x() - arrow_size * math.cos(angle - math.pi/6)),
                    int(end.y() - arrow_size * math.sin(angle - math.pi/6)))
        p2 = QPoint(int(end.x() - arrow_size * math.cos(angle + math.pi/6)),
                    int(end.y() - arrow_size * math.sin(angle + math.pi/6)))
        painter.setBrush(QBrush(color))
        painter.drawPolygon([end, p1, p2])

    def mousePressEvent(self, event):
        debug(f"mousePressEvent: button={event.button()}, selecting={self.selecting}, tool={self.current_tool}")
        if event.button() == Qt.LeftButton:
            if self.selecting:
                self.start_pos = event.pos()
                self.end_pos = event.pos()
            elif self.current_tool != ToolType.NONE:
                rect = QRect(self.start_pos, self.end_pos).normalized()
                if rect.contains(event.pos()):
                    self.drawing = True
                    self.draw_start = event.pos()
                    self.current_points = [event.pos()]
                    self.undo_stack.clear()
                    if self.current_tool == ToolType.TEXT:
                        self._show_text_input(event.pos())

    def mouseMoveEvent(self, event):
        if self.selecting and self.start_pos:
            self.end_pos = event.pos()
            self.update()
        elif self.drawing:
            if self.current_tool == ToolType.PEN:
                self.current_points.append(event.pos())
            self.update()

    def mouseReleaseEvent(self, event):
        debug(f"mouseReleaseEvent: button={event.button()}, selecting={self.selecting}, annotations={len(self.annotations)}")
        try:
            if event.button() == Qt.LeftButton:
                if self.selecting and self.start_pos and self.end_pos:
                    rect = QRect(self.start_pos, self.end_pos).normalized()
                    if rect.width() > 10 and rect.height() > 10:
                        self.selecting = False
                        self.selection_rect = rect
                        self.setCursor(Qt.ArrowCursor)
                        self._create_toolbar()
                elif self.drawing and self.current_tool != ToolType.TEXT:
                    self.drawing = False
                    ann = Annotation(
                        tool=self.current_tool,
                        color=self.current_color,
                        width=self.current_width,
                        start=self.draw_start,
                        end=event.pos(),
                        points=list(self.current_points)
                    )
                    self.annotations.append(ann)
                    self.update()
            elif event.button() == Qt.RightButton:
                debug(f"RightButton: selecting={self.selecting}, annotations={len(self.annotations)}")
                if self.selecting:
                    debug("RightButton: 框选阶段退出")
                    self.screenshot_cancelled.emit()
                    self.close()
                elif self.annotations:
                    debug("RightButton: 清除标注")
                    self.annotations.clear()
                    self.undo_stack.clear()
                    self.update()
                else:
                    debug("RightButton: 返回框选模式")
                    self._clear_toolbar()
                    self.selecting = True
                    self.start_pos = None
                    self.end_pos = None
                    self.current_tool = ToolType.NONE
                    self.setCursor(Qt.CrossCursor)
                    self.update()
        except Exception as e:
            debug(f"mouseReleaseEvent ERROR: {e}")
            traceback.print_exc()

    def keyPressEvent(self, event):
        debug(f"keyPressEvent: key={event.key()}, selecting={self.selecting}, annotations={len(self.annotations)}")
        try:
            if event.key() == Qt.Key_Escape:
                if self.selecting:
                    debug("ESC: 框选阶段退出")
                    self.screenshot_cancelled.emit()
                    self.close()
                elif self.annotations:
                    debug("ESC: 清除标注")
                    self.annotations.clear()
                    self.undo_stack.clear()
                    self.update()
                else:
                    debug("ESC: 返回框选模式")
                    self._clear_toolbar()
                    self.selecting = True
                    self.start_pos = None
                    self.end_pos = None
                    self.current_tool = ToolType.NONE
                    self.setCursor(Qt.CrossCursor)
                    self.update()
            elif event.key() == Qt.Key_Return:
                if not self.selecting and self.start_pos and self.end_pos:
                    self._confirm()
            elif event.key() == Qt.Key_Z and event.modifiers() & Qt.ControlModifier:
                if event.modifiers() & Qt.ShiftModifier:
                    self._redo()
                else:
                    self._undo()
        except Exception as e:
            debug(f"keyPressEvent ERROR: {e}")
            traceback.print_exc()

    def _create_toolbar(self):
        """创建工具条"""
        debug("_create_toolbar: 开始创建工具栏")
        try:
            rect = QRect(self.start_pos, self.end_pos).normalized()
            toolbar_y = rect.bottom() + 8
            btn_size = 40
            if toolbar_y + btn_size + 10 > self.height():
                toolbar_y = rect.top() - btn_size - 8

            btn_style = "QPushButton { background: rgba(50,50,50,0.9); color: white; border: none; border-radius: 6px; font-size: 18px; } QPushButton:hover { background: rgba(80,80,80,0.95); }"
            btn_style_selected = "QPushButton { background: #07c160; color: white; border: none; border-radius: 6px; font-size: 18px; }"

            x = rect.left()
            # 微信风格图标和提示
            tools = [
                ("□", ToolType.RECT, "矩形框"),
                ("○", ToolType.ELLIPSE, "椭圆"),
                ("➔", ToolType.ARROW, "箭头"),
                ("╱", ToolType.LINE, "直线"),
                ("A", ToolType.TEXT, "文字"),
                ("✐", ToolType.PEN, "画笔"),
            ]

            for icon, tool_type, tip in tools:
                btn = QPushButton(icon, self)
                btn.setGeometry(x, toolbar_y, btn_size, btn_size)
                btn.setStyleSheet(btn_style)
                btn.setToolTip(tip)
                btn.clicked.connect(lambda _, t=tool_type: self._select_tool(t))
                btn.show()
                self.toolbar_buttons.append((btn, tool_type))
                x += btn_size + 4

            x += 8  # 分隔

            # 颜色按钮
            self.color_btn = QPushButton(self)
            self.color_btn.setGeometry(x, toolbar_y, btn_size, btn_size)
            self.color_btn.setStyleSheet(f"background-color: {self.current_color.name()}; border-radius: 6px; border: 2px solid white;")
            self.color_btn.setToolTip("选择颜色")
            self.color_btn.clicked.connect(self._pick_color)
            self.color_btn.show()
            x += btn_size + 4

            # 线宽
            self.width_spin = QSpinBox(self)
            self.width_spin.setRange(1, 10)
            self.width_spin.setValue(3)
            self.width_spin.setGeometry(x, toolbar_y, 50, btn_size)
            self.width_spin.setStyleSheet("color: white; background: rgba(50,50,50,0.9); border-radius: 6px; font-size: 14px;")
            self.width_spin.setToolTip("线条粗细")
            self.width_spin.valueChanged.connect(lambda v: setattr(self, 'current_width', v))
            self.width_spin.show()
            x += 58

            # 撤销
            undo_btn = QPushButton("↩", self)
            undo_btn.setGeometry(x, toolbar_y, btn_size, btn_size)
            undo_btn.setStyleSheet(btn_style)
            undo_btn.setToolTip("撤销 (Ctrl+Z)")
            undo_btn.clicked.connect(self._undo)
            undo_btn.show()
            self.toolbar_buttons.append((undo_btn, None))
            x += btn_size + 4

            # 重做
            redo_btn = QPushButton("↪", self)
            redo_btn.setGeometry(x, toolbar_y, btn_size, btn_size)
            redo_btn.setStyleSheet(btn_style)
            redo_btn.setToolTip("重做 (Ctrl+Shift+Z)")
            redo_btn.clicked.connect(self._redo)
            redo_btn.show()
            self.toolbar_buttons.append((redo_btn, None))
            x += btn_size + 12

            # 取消
            cancel_btn = QPushButton("✕", self)
            cancel_btn.setGeometry(x, toolbar_y, btn_size, btn_size)
            cancel_btn.setStyleSheet("QPushButton { background: rgba(220,53,69,0.9); color: white; border: none; border-radius: 6px; font-size: 18px; } QPushButton:hover { background: rgba(200,35,51,0.95); }")
            cancel_btn.setToolTip("取消 (Esc)")
            cancel_btn.clicked.connect(self._cancel)
            cancel_btn.show()
            self.toolbar_buttons.append((cancel_btn, None))
            x += btn_size + 4

            # 确认
            confirm_btn = QPushButton("✓", self)
            confirm_btn.setGeometry(x, toolbar_y, btn_size, btn_size)
            confirm_btn.setStyleSheet("QPushButton { background: rgba(7,193,96,0.9); color: white; border: none; border-radius: 6px; font-size: 18px; } QPushButton:hover { background: rgba(6,170,84,0.95); }")
            confirm_btn.setToolTip("完成 (Enter)")
            confirm_btn.clicked.connect(self._confirm)
            confirm_btn.show()
            self.toolbar_buttons.append((confirm_btn, None))
            debug("_create_toolbar: 工具栏创建完成")
        except Exception as e:
            debug(f"_create_toolbar ERROR: {e}")
            traceback.print_exc()

    def _clear_toolbar(self):
        debug(f"_clear_toolbar: 开始清理, buttons={len(self.toolbar_buttons)}")
        try:
            for btn, _ in self.toolbar_buttons:
                btn.deleteLater()
            self.toolbar_buttons.clear()
            if self.color_btn:
                self.color_btn.deleteLater()
                self.color_btn = None
            if self.width_spin:
                self.width_spin.deleteLater()
                self.width_spin = None
            if self.text_input:
                self.text_input.deleteLater()
                self.text_input = None
            debug("_clear_toolbar: 清理完成")
        except Exception as e:
            debug(f"_clear_toolbar ERROR: {e}")
            traceback.print_exc()

    def _select_tool(self, tool: ToolType):
        self.current_tool = tool
        btn_style = "QPushButton { background: #333; color: white; border: none; border-radius: 4px; font-size: 14px; } QPushButton:hover { background: #555; }"
        btn_style_selected = "QPushButton { background: #0078d4; color: white; border: none; border-radius: 4px; font-size: 14px; }"
        for btn, t in self.toolbar_buttons:
            if t is not None:
                btn.setStyleSheet(btn_style_selected if t == tool else btn_style)
        if self.text_input:
            self.text_input.hide()

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self)
        if color.isValid():
            self.current_color = color
            self.color_btn.setStyleSheet(f"background-color: {color.name()}; border-radius: 4px;")

    def _undo(self):
        if self.annotations:
            self.undo_stack.append(self.annotations.pop())
            self.update()

    def _redo(self):
        if self.undo_stack:
            self.annotations.append(self.undo_stack.pop())
            self.update()

    def _show_text_input(self, pos: QPoint):
        if not self.text_input:
            self.text_input = QLineEdit(self)
            self.text_input.setStyleSheet("background: white; border: 2px solid #0078d4; border-radius: 4px; padding: 4px;")
            self.text_input.returnPressed.connect(self._confirm_text)
        self.text_input.move(pos)
        self.text_input.setFixedWidth(200)
        self.text_input.clear()
        self.text_input.show()
        self.text_input.setFocus()
        self.text_pos = pos

    def _confirm_text(self):
        if self.text_input and self.text_pos:
            text = self.text_input.text().strip()
            if text:
                ann = Annotation(
                    tool=ToolType.TEXT,
                    color=self.current_color,
                    width=self.current_width,
                    start=self.text_pos,
                    end=self.text_pos,
                    text=text
                )
                self.annotations.append(ann)
            self.text_input.hide()
            self.text_pos = None
            self.drawing = False
            self.update()

    def _cancel(self):
        debug("_cancel: 取消截图")
        self.screenshot_cancelled.emit()
        self.close()

    def _confirm(self):
        """确认截图"""
        debug("_confirm: 确认截图")
        try:
            rect = QRect(self.start_pos, self.end_pos).normalized()

            # 隐藏工具栏后截取
            self._clear_toolbar()
            self.update()
            QApplication.processEvents()

            # 创建最终图片
            result = self.screenshot.copy(rect)
            painter = QPainter(result)
            painter.setRenderHint(QPainter.Antialiasing)

            # 绘制标注（坐标转换到裁剪区域）
            for ann in self.annotations:
                offset_ann = Annotation(
                    tool=ann.tool,
                    color=ann.color,
                    width=ann.width,
                    start=ann.start - rect.topLeft(),
                    end=ann.end - rect.topLeft(),
                    text=ann.text,
                    points=[p - rect.topLeft() for p in ann.points]
                )
                self._draw_annotation(painter, offset_ann)
            painter.end()

            # 保存
            self.save_dir.mkdir(parents=True, exist_ok=True)
            file_path = self.save_dir / f"screenshot_{int(time.time())}.png"
            result.save(str(file_path))
            debug(f"_confirm: 保存到 {file_path}")
            self.screenshot_taken.emit(str(file_path))
            self.close()
        except Exception as e:
            debug(f"_confirm ERROR: {e}")
            traceback.print_exc()


def take_screenshot(save_dir: str = None) -> Optional[str]:
    """启动截图工具（阻塞式）"""
    app = QApplication.instance()
    if not app:
        app = QApplication([])

    result = [None]
    selector = ScreenshotSelector(save_dir)
    selector.screenshot_taken.connect(lambda p: result.__setitem__(0, p))
    selector.start_screenshot()
    app.exec()
    return result[0]


if __name__ == "__main__":
    import sys
    save_dir = sys.argv[1] if len(sys.argv) > 1 else None
    path = take_screenshot(save_dir)
    if path:
        print(path)  # 只输出路径，供父进程读取
