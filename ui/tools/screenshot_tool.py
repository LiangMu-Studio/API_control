"""轻量级截图工具 - 基于 tkinter + mss + PIL"""

import tkinter as tk
from tkinter import colorchooser
from PIL import Image, ImageTk, ImageDraw, ImageFont
import mss
import time
import json
import ctypes
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum
import math

# 设置 DPI 感知，确保高分辨率屏幕正确截图
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor DPI Aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# 配置文件路径
CONFIG_PATH = Path(__file__).parent.parent.parent / "data" / "screenshot.json"

def load_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {"width": 3}

def save_config(width: int):
    """只保存线条粗细，颜色不记忆"""
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"width": width}, f)
    except:
        pass


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
    color: str
    width: int
    start: tuple  # (x, y)
    end: tuple    # (x, y)
    text: str = ""
    points: List[tuple] = None

    def __post_init__(self):
        if self.points is None:
            self.points = []


class ScreenshotTool:
    # 预设颜色
    PRESET_COLORS = ["#ff0000", "#ffff00", "#0000ff"]  # 红、黄、蓝

    def __init__(self, save_dir: str = None):
        # 确保有有效的保存目录
        if save_dir and save_dir.strip():
            self.save_dir = Path(save_dir)
        else:
            # 默认使用项目根目录下的 screenshots
            self.save_dir = Path(__file__).parent.parent.parent / "screenshots"
        self.save_dir.mkdir(parents=True, exist_ok=True)

        self.root = None
        self.canvas = None
        self.screenshot_image = None
        self.tk_image = None
        self.result_path = None

        # 选区
        self.start_x = self.start_y = 0
        self.end_x = self.end_y = 0
        self.selecting = True
        self.selection_rect = None

        # 标注
        self.annotations: List[Annotation] = []
        self.undo_stack: List[Annotation] = []
        self.selected_index = -1  # 选中的标注索引

        # 加载保存的设置（只有粗细，颜色每次默认红色）
        config = load_config()
        self.current_tool = ToolType.NONE
        self.current_color = "#ff0000"  # 默认红色，不记忆
        self.current_width = config.get("width", 3)
        self.drawing = False
        self.draw_start = None
        self.current_points = []

        # UI 元素
        self.toolbar_frame = None
        self.tool_buttons = {}
        self.text_entry = None
        self.text_pos = None
        self.width_var = None
        self.color_btn = None

    def start(self) -> Optional[str]:
        """启动截图，返回保存路径或 None"""
        # 截取全屏
        with mss.mss() as sct:
            monitor = sct.monitors[0]
            sct_img = sct.grab(monitor)
            self.screenshot_image = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

        # 创建全屏窗口
        self.root = tk.Tk()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(cursor="cross")

        # 创建画布
        self.tk_image = ImageTk.PhotoImage(self.screenshot_image)
        self.canvas = tk.Canvas(self.root, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image, tags="bg")

        # 绑定事件
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<ButtonPress-3>", self.on_right_click)
        self.root.bind("<Escape>", self.on_escape)
        self.root.bind("<Return>", self.on_confirm)
        self.root.bind("<Control-z>", self.on_undo)
        self.root.bind("<Control-Shift-Z>", self.on_redo)
        self.root.bind("<Control-y>", self.on_redo)

        self.root.mainloop()
        return self.result_path

    def _hit_test(self, x, y) -> int:
        """检测点击位置是否在某个标注上，返回索引或-1"""
        for i in range(len(self.annotations) - 1, -1, -1):
            ann = self.annotations[i]
            ax1, ay1 = min(ann.start[0], ann.end[0]), min(ann.start[1], ann.end[1])
            ax2, ay2 = max(ann.start[0], ann.end[0]), max(ann.start[1], ann.end[1])
            # 扩大点击区域
            margin = max(ann.width * 2, 10)
            if ann.tool == ToolType.PEN and ann.points:
                for p in ann.points:
                    if abs(p[0] - x) < margin and abs(p[1] - y) < margin:
                        return i
            elif ann.tool == ToolType.TEXT:
                if ax1 - margin <= x <= ax2 + 100 and ay1 - margin <= y <= ay2 + 30:
                    return i
            else:
                if ax1 - margin <= x <= ax2 + margin and ay1 - margin <= y <= ay2 + margin:
                    return i
        return -1

    def on_mouse_down(self, event):
        # 如果有文字输入框，先保存文字
        if self.text_entry and self.text_pos:
            self._confirm_text(self.text_pos[0], self.text_pos[1])

        if self.selecting:
            self.start_x, self.start_y = event.x, event.y
            self.end_x, self.end_y = event.x, event.y
        elif self.current_tool == ToolType.NONE:
            # 没选工具时，检测是否点击了已有标注
            hit = self._hit_test(event.x, event.y)
            if hit >= 0:
                self.selected_index = hit
                # 更新当前颜色和粗细为选中标注的值
                ann = self.annotations[hit]
                self.current_color = ann.color
                self.current_width = ann.width
                if self.color_btn:
                    self.color_btn.configure(bg=self.current_color)
                if self.width_var:
                    self.width_var.set(self.current_width)
                self._draw_all()
            else:
                self.selected_index = -1
                self._draw_all()
        elif self.current_tool != ToolType.NONE:
            x1, y1, x2, y2 = self._get_selection_rect()
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.selected_index = -1
                self.drawing = True
                self.draw_start = (event.x, event.y)
                self.current_points = [(event.x, event.y)]
                self.undo_stack.clear()
                if self.current_tool == ToolType.TEXT:
                    self._show_text_input(event.x, event.y)

    def on_mouse_move(self, event):
        if self.selecting and self.start_x:
            self.end_x, self.end_y = event.x, event.y
            self._draw_selection()
        elif self.drawing:
            if self.current_tool == ToolType.PEN:
                self.current_points.append((event.x, event.y))
            self._draw_all()

    def on_mouse_up(self, event):
        if self.selecting:
            self.end_x, self.end_y = event.x, event.y
            x1, y1, x2, y2 = self._get_selection_rect()
            if abs(x2 - x1) > 10 and abs(y2 - y1) > 10:
                self.selecting = False
                self.root.configure(cursor="arrow")
                self._create_toolbar()
                self._draw_all()
        elif self.drawing and self.current_tool != ToolType.TEXT:
            self.drawing = False
            ann = Annotation(
                tool=self.current_tool,
                color=self.current_color,
                width=self.current_width,
                start=self.draw_start,
                end=(event.x, event.y),
                points=list(self.current_points)
            )
            self.annotations.append(ann)
            # 画笔工具不自动取消，其他工具取消选中
            if self.current_tool != ToolType.PEN:
                self._select_tool(ToolType.NONE)
            else:
                self._draw_all()

    def on_right_click(self, event):
        """右键删除：正在绘制取消 -> 选中的删除 -> 最后一个删除 -> 取消截图"""
        if self.drawing:
            self.drawing = False
            self.draw_start = None
            self.current_points = []
            self._draw_all()
        elif self.selected_index >= 0:
            # 删除选中的标注
            self.undo_stack.append(self.annotations.pop(self.selected_index))
            self.selected_index = -1
            self._draw_all()
        elif self.annotations:
            # 删除最后一个标注
            self.undo_stack.append(self.annotations.pop())
            self._draw_all()
        else:
            # 没有标注，取消截图
            self.root.destroy()

    def on_escape(self, event):
        if self.selecting:
            self.root.destroy()
        elif self.drawing:
            self.drawing = False
            self.draw_start = None
            self.current_points = []
            self._draw_all()
        elif self.selected_index >= 0:
            self.selected_index = -1
            self._draw_all()
        elif self.annotations:
            self.annotations.clear()
            self.undo_stack.clear()
            self._draw_all()
        else:
            self.selecting = True
            self.start_x = self.start_y = 0
            self.end_x = self.end_y = 0
            self.current_tool = ToolType.NONE
            self.root.configure(cursor="cross")
            if self.toolbar_frame:
                self.toolbar_frame.destroy()
                self.toolbar_frame = None
            self._draw_all()

    def on_confirm(self, event=None):
        if not self.selecting:
            self._save_screenshot()
            self.root.destroy()

    def on_undo(self, event=None):
        if self.annotations:
            self.undo_stack.append(self.annotations.pop())
            self.selected_index = -1
            self._draw_all()

    def on_redo(self, event=None):
        if self.undo_stack:
            self.annotations.append(self.undo_stack.pop())
            self._draw_all()

    def _get_selection_rect(self):
        x1, x2 = min(self.start_x, self.end_x), max(self.start_x, self.end_x)
        y1, y2 = min(self.start_y, self.end_y), max(self.start_y, self.end_y)
        return x1, y1, x2, y2

    def _draw_selection(self):
        self.canvas.delete("overlay")
        x1, y1, x2, y2 = self._get_selection_rect()

        w, h = self.screenshot_image.size
        # 遮罩区域（无边框，避免延长线）
        self.canvas.create_rectangle(0, 0, w, y1, fill="black", stipple="gray50", outline="", tags="overlay")
        self.canvas.create_rectangle(0, y2, w, h, fill="black", stipple="gray50", outline="", tags="overlay")
        self.canvas.create_rectangle(0, y1, x1, y2, fill="black", stipple="gray50", outline="", tags="overlay")
        self.canvas.create_rectangle(x2, y1, w, y2, fill="black", stipple="gray50", outline="", tags="overlay")

        self.canvas.create_rectangle(x1, y1, x2, y2, outline="#00aeff", width=2, tags="overlay")
        self.canvas.create_text(x1, y1 - 5, text=f"{x2-x1} x {y2-y1}",
                               fill="white", anchor=tk.SW, tags="overlay")

    def _draw_all(self):
        self.canvas.delete("overlay")
        self.canvas.delete("annotation")

        if not self.selecting:
            self._draw_selection()

            for i, ann in enumerate(self.annotations):
                selected = (i == self.selected_index)
                self._draw_annotation(ann, selected)

            if self.drawing and self.draw_start:
                current_ann = Annotation(
                    tool=self.current_tool,
                    color=self.current_color,
                    width=self.current_width,
                    start=self.draw_start,
                    end=self.canvas.winfo_pointerxy(),
                    points=list(self.current_points)
                )
                rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
                current_ann.end = (current_ann.end[0] - rx, current_ann.end[1] - ry)
                self._draw_annotation(current_ann, False)

    def _draw_annotation(self, ann: Annotation, selected: bool = False):
        x1, y1 = ann.start
        x2, y2 = ann.end

        if ann.tool == ToolType.RECT:
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=ann.color,
                                        width=ann.width, tags="annotation")
        elif ann.tool == ToolType.ELLIPSE:
            self.canvas.create_oval(x1, y1, x2, y2, outline=ann.color,
                                   width=ann.width, tags="annotation")
        elif ann.tool == ToolType.LINE:
            self.canvas.create_line(x1, y1, x2, y2, fill=ann.color,
                                   width=ann.width, tags="annotation")
        elif ann.tool == ToolType.ARROW:
            self._draw_arrow(x1, y1, x2, y2, ann.color, ann.width)
        elif ann.tool == ToolType.PEN and ann.points:
            if len(ann.points) > 1:
                self.canvas.create_line(ann.points, fill=ann.color,
                                       width=ann.width, smooth=True, tags="annotation")
        elif ann.tool == ToolType.TEXT and ann.text:
            font_size = ann.width * 6
            self.canvas.create_text(x1, y1, text=ann.text, fill=ann.color,
                                   anchor=tk.NW, font=("Microsoft YaHei", font_size),
                                   tags="annotation")

        # 选中状态显示边框
        if selected:
            bx1, by1 = min(x1, x2), min(y1, y2)
            bx2, by2 = max(x1, x2), max(y1, y2)
            if ann.tool == ToolType.TEXT:
                bx2 += 100
                by2 += 30
            self.canvas.create_rectangle(bx1 - 5, by1 - 5, bx2 + 5, by2 + 5,
                                        outline="#00aeff", width=2, dash=(4, 4), tags="annotation")

    def _draw_arrow(self, x1, y1, x2, y2, color, width):
        angle = math.atan2(y2 - y1, x2 - x1)
        arrow_size = max(width * 5, 15)
        # 线条终点稍微进入三角形内部
        line_end_x = x2 - arrow_size * 0.8 * math.cos(angle)
        line_end_y = y2 - arrow_size * 0.8 * math.sin(angle)
        self.canvas.create_line(x1, y1, line_end_x, line_end_y, fill=color, width=width, tags="annotation")
        # 箭头三角形
        p1 = (x2 - arrow_size * math.cos(angle - math.pi/6),
              y2 - arrow_size * math.sin(angle - math.pi/6))
        p2 = (x2 - arrow_size * math.cos(angle + math.pi/6),
              y2 - arrow_size * math.sin(angle + math.pi/6))
        self.canvas.create_polygon([x2, y2, p1[0], p1[1], p2[0], p2[1]],
                                  fill=color, outline=color, tags="annotation")

    def _create_toolbar(self):
        x1, y1, x2, y2 = self._get_selection_rect()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        # 先创建工具栏获取实际宽度
        self.toolbar_frame = tk.Frame(self.root, bg="#333333")

        tools = [
            ("\u2b1c", ToolType.RECT, "矩形"),
            ("\u25ef", ToolType.ELLIPSE, "椭圆"),
            ("\u279c", ToolType.ARROW, "箭头"),
            ("\u2571", ToolType.LINE, "直线"),
            ("A", ToolType.TEXT, "文字"),
            ("\u270e", ToolType.PEN, "画笔"),
        ]

        for icon, tool_type, tip in tools:
            btn = tk.Button(self.toolbar_frame, text=icon, width=2, height=1,
                           bg="#333333", fg="white", relief=tk.FLAT,
                           font=("Segoe UI Symbol", 16),
                           command=lambda t=tool_type: self._select_tool(t))
            btn.pack(side=tk.LEFT, padx=2, pady=4)
            self.tool_buttons[tool_type] = btn

        # 分隔
        tk.Frame(self.toolbar_frame, width=2, bg="#555555").pack(side=tk.LEFT, padx=4, pady=4, fill=tk.Y)

        # 预设颜色
        for color in self.PRESET_COLORS:
            btn = tk.Button(self.toolbar_frame, text=" ", width=2, height=1,
                           bg=color, relief=tk.FLAT, font=("Arial", 16),
                           command=lambda c=color: self._set_color(c))
            btn.pack(side=tk.LEFT, padx=1, pady=4)

        # 色盘按钮（彩色图标，不随选择变化）
        self.color_btn = tk.Button(self.toolbar_frame, text="\U0001F3A8", width=2, height=1,
                                   bg="#333333", fg="white", relief=tk.FLAT,
                                   font=("Segoe UI Emoji", 14), command=self._pick_color)
        self.color_btn.pack(side=tk.LEFT, padx=2, pady=4)

        # 分隔
        tk.Frame(self.toolbar_frame, width=2, bg="#555555").pack(side=tk.LEFT, padx=4, pady=4, fill=tk.Y)

        # 粗细调节
        self.width_var = tk.IntVar(value=self.current_width)
        width_spin = tk.Spinbox(self.toolbar_frame, from_=1, to=30, width=3,
                               textvariable=self.width_var,
                               command=self._on_width_change,
                               font=("Arial", 10))
        width_spin.pack(side=tk.LEFT, padx=2, pady=4)
        width_spin.bind("<Return>", lambda e: self._on_width_change())
        width_spin.bind("<FocusOut>", lambda e: self._on_width_change())
        self.width_var.trace_add("write", lambda *args: self._on_width_change())

        # 分隔
        tk.Frame(self.toolbar_frame, width=2, bg="#555555").pack(side=tk.LEFT, padx=4, pady=4, fill=tk.Y)

        # 撤销
        tk.Button(self.toolbar_frame, text="\u27f2", width=2, height=1,
                 bg="#333333", fg="white", relief=tk.FLAT, font=("Segoe UI Symbol", 16),
                 command=self.on_undo).pack(side=tk.LEFT, padx=2, pady=4)

        # 重做
        tk.Button(self.toolbar_frame, text="\u27f3", width=2, height=1,
                 bg="#333333", fg="white", relief=tk.FLAT, font=("Segoe UI Symbol", 16),
                 command=self.on_redo).pack(side=tk.LEFT, padx=2, pady=4)

        # 分隔
        tk.Frame(self.toolbar_frame, width=2, bg="#555555").pack(side=tk.LEFT, padx=4, pady=4, fill=tk.Y)

        # 取消
        tk.Button(self.toolbar_frame, text="\u2715", width=2, height=1,
                 bg="#dc3545", fg="white", relief=tk.FLAT, font=("Segoe UI Symbol", 16),
                 command=lambda: self.on_escape(None)).pack(side=tk.LEFT, padx=2, pady=4)

        # 确认
        tk.Button(self.toolbar_frame, text="\u2713", width=2, height=1,
                 bg="#07c160", fg="white", relief=tk.FLAT, font=("Segoe UI Symbol", 16),
                 command=self.on_confirm).pack(side=tk.LEFT, padx=2, pady=4)

        # 计算工具栏位置（自适应屏幕边界）
        self.toolbar_frame.update_idletasks()
        toolbar_w = self.toolbar_frame.winfo_reqwidth()
        toolbar_h = self.toolbar_frame.winfo_reqheight()

        # Y 位置：优先在选区下方，空间不够则在选区内顶部
        if screen_h - y2 < toolbar_h + 10:
            toolbar_y = y1 + 8  # 选区内顶部
        else:
            toolbar_y = y2 + 8  # 选区下方

        # X 位置：优先左对齐，超出右边界则右对齐
        toolbar_x = x1
        if toolbar_x + toolbar_w > screen_w:
            toolbar_x = screen_w - toolbar_w - 10

        self.toolbar_frame.place(x=toolbar_x, y=toolbar_y)

    def _select_tool(self, tool: ToolType):
        self.current_tool = tool
        self.selected_index = -1
        for t, btn in self.tool_buttons.items():
            btn.configure(bg="#0078d4" if t == tool else "#333333")
        if self.text_entry:
            self.text_entry.destroy()
            self.text_entry = None
        self._draw_all()

    def _set_color(self, color: str):
        """设置颜色，更新选中或最后一个标注"""
        self.current_color = color
        # 色盘按钮保持彩色图标，不改变背景
        if self.selected_index >= 0:
            self.annotations[self.selected_index].color = color
        elif self.annotations:
            self.annotations[-1].color = color
        self._draw_all()

    def _pick_color(self):
        color = colorchooser.askcolor(color=self.current_color)[1]
        if color:
            self._set_color(color)

    def _on_width_change(self):
        try:
            self.current_width = self.width_var.get()
            if self.selected_index >= 0:
                self.annotations[self.selected_index].width = self.current_width
            elif self.annotations:
                self.annotations[-1].width = self.current_width
            self._draw_all()
            save_config(self.current_width)  # 只保存粗细
        except:
            pass

    def _show_text_input(self, x, y):
        if self.text_entry:
            self.text_entry.destroy()
        self.text_entry = tk.Entry(self.root, font=("Microsoft YaHei", 14),
                                   bg="#222222", fg=self.current_color,
                                   insertbackground=self.current_color,
                                   relief=tk.FLAT, highlightthickness=1,
                                   highlightcolor=self.current_color)
        self.text_entry.place(x=x, y=y)
        self.text_entry.focus_set()
        self.text_entry.bind("<Return>", lambda e: self._confirm_text(x, y))
        self.text_pos = (x, y)

    def _confirm_text(self, x, y):
        if self.text_entry:
            text = self.text_entry.get().strip()
            if text:
                ann = Annotation(
                    tool=ToolType.TEXT,
                    color=self.current_color,
                    width=self.current_width,
                    start=(x, y),
                    end=(x, y),
                    text=text
                )
                self.annotations.append(ann)
            self.text_entry.destroy()
            self.text_entry = None
            self.drawing = False
            self._select_tool(ToolType.NONE)  # 取消工具选中

    def _save_screenshot(self):
        x1, y1, x2, y2 = self._get_selection_rect()
        cropped = self.screenshot_image.crop((x1, y1, x2, y2))
        draw = ImageDraw.Draw(cropped)

        for ann in self.annotations:
            ax1, ay1 = ann.start[0] - x1, ann.start[1] - y1
            ax2, ay2 = ann.end[0] - x1, ann.end[1] - y1

            if ann.tool == ToolType.RECT:
                draw.rectangle([ax1, ay1, ax2, ay2], outline=ann.color, width=ann.width)
            elif ann.tool == ToolType.ELLIPSE:
                draw.ellipse([ax1, ay1, ax2, ay2], outline=ann.color, width=ann.width)
            elif ann.tool == ToolType.LINE:
                draw.line([ax1, ay1, ax2, ay2], fill=ann.color, width=ann.width)
            elif ann.tool == ToolType.ARROW:
                angle = math.atan2(ay2 - ay1, ax2 - ax1)
                arrow_size = max(ann.width * 5, 15)
                line_end_x = ax2 - arrow_size * 0.8 * math.cos(angle)
                line_end_y = ay2 - arrow_size * 0.8 * math.sin(angle)
                draw.line([ax1, ay1, line_end_x, line_end_y], fill=ann.color, width=ann.width)
                p1 = (ax2 - arrow_size * math.cos(angle - math.pi/6),
                      ay2 - arrow_size * math.sin(angle - math.pi/6))
                p2 = (ax2 - arrow_size * math.cos(angle + math.pi/6),
                      ay2 - arrow_size * math.sin(angle + math.pi/6))
                draw.polygon([(ax2, ay2), p1, p2], fill=ann.color)
            elif ann.tool == ToolType.PEN and ann.points:
                points = [(p[0] - x1, p[1] - y1) for p in ann.points]
                if len(points) > 1:
                    draw.line(points, fill=ann.color, width=ann.width)
            elif ann.tool == ToolType.TEXT and ann.text:
                try:
                    font = ImageFont.truetype("msyh.ttc", ann.width * 6)
                except:
                    font = ImageFont.load_default()
                draw.text((ax1, ay1), ann.text, fill=ann.color, font=font)

        file_path = self.save_dir / f"screenshot_{int(time.time())}.png"
        cropped.save(str(file_path))
        self.result_path = str(file_path)


def take_screenshot(save_dir: str = None) -> Optional[str]:
    """截图入口函数"""
    tool = ScreenshotTool(save_dir)
    return tool.start()


if __name__ == "__main__":
    import sys
    save_dir = sys.argv[1] if len(sys.argv) > 1 else None
    path = take_screenshot(save_dir)
    if path:
        print(path)
