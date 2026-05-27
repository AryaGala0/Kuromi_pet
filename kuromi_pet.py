# -*- coding: utf-8 -*-
"""
库洛米桌面宠物 Kuromi Desktop Pet
功能：
  1. 透明无边框置顶窗口，可自由拖拽
  2. 定时提醒：吃饭、下班、喝水
  3. 右键菜单 + 系统托盘
  4. 可爱气泡对话
"""

import os
import sys
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QPoint, QRectF, QSize
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QFontMetrics, QAction, QIcon,
    QPainterPath, QPen, QCursor, QMouseEvent
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QMenu, QSystemTrayIcon,
    QVBoxLayout, QHBoxLayout, QMessageBox, QDialog, QLineEdit,
    QTimeEdit, QPushButton, QFormLayout
)
from PySide6.QtCore import QTime

# AI 对话模块（按需导入，未配置时不影响主功能）
try:
    from ai_chat import ChatHistory, ChatWorker, DEFAULT_SYSTEM_PROMPT
    _AI_AVAILABLE = True
except Exception as _e:
    print(f"[WARN] AI 模块不可用: {_e}")
    _AI_AVAILABLE = False


# ---------------------------------------------------------------------------
# 路径处理：同时兼容「开发模式」和「PyInstaller 打包后」两种运行环境
# ---------------------------------------------------------------------------
def _resource_dir() -> Path:
    """只读资源目录（图片等）。

    - 开发模式：脚本所在目录
    - PyInstaller onefile：解压到的临时目录 sys._MEIPASS
    - PyInstaller onedir：可执行文件所在目录
    """
    if getattr(sys, "frozen", False):
        # 被 PyInstaller 冻结
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).parent
    return Path(__file__).parent


def _user_dir() -> Path:
    """用户数据目录（可写：config.json 等用户修改的内容）。

    无论 onefile/onedir/开发模式，都放在 exe 或脚本所在目录，
    保证用户改的提醒重启后不会丢失。
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


BASE_DIR = _resource_dir()           # 只读资源根目录
USER_DIR = _user_dir()               # 用户可写目录
ASSETS_DIR = BASE_DIR / "assets"
FRAMES_DIR = ASSETS_DIR / "frames"
CONFIG_PATH = USER_DIR / "config.json"
DEFAULT_CONFIG_PATH = BASE_DIR / "config.json"   # 打包内置的默认配置

# 四种状态（与 slice_sheet.py 的行顺序一致）
STATES = ["normal", "happy", "angry", "peek"]
STATE_LABELS = {
    "normal": "日常",
    "happy":  "开心",
    "angry":  "生气",
    "peek":   "偷看",
}
STATE_PHRASES = {
    "normal": ["今天也要元气满满哦~", "主人在忙什么呀？", "嘿嘿嘿~"],
    "happy":  ["好开心呀♡", "陪着主人最幸福了~", "么么哒~"],
    "angry":  ["哼！别不理人家！", "再不休息我就生气啦！", "讨厌啦！(╬◣д◢)"],
    "peek":   ["嘘…我在偷偷看你", "主人在做什么呢？", "被发现啦！"],
}

# 紫色主题菜单样式（深紫底 + 粉紫高亮 + 白字）
MENU_QSS = """
QMenu {
    background-color: #3a1f4d;
    color: #f5e6ff;
    border: 2px solid #b070d8;
    border-radius: 10px;
    padding: 6px;
    font-family: 'Microsoft YaHei', 'Segoe UI';
    font-size: 12px;
}
QMenu::item {
    background-color: transparent;
    padding: 7px 28px 7px 20px;
    border-radius: 6px;
    margin: 1px 4px;
    color: #f5e6ff;
}
QMenu::item:selected {
    background-color: #8b3fb8;
    color: #ffffff;
}
QMenu::item:disabled {
    color: #a98bbb;
}
QMenu::separator {
    height: 1px;
    background: #6a3e8a;
    margin: 5px 10px;
}
QMenu::indicator {
    width: 14px;
    height: 14px;
    margin-left: 6px;
}
QMenu::indicator:checked {
    background-color: #ff9cd8;
    border: 1px solid #ffffff;
    border-radius: 3px;
}
QMenu::indicator:unchecked {
    background-color: transparent;
    border: 1px solid #b070d8;
    border-radius: 3px;
}
QMenu::right-arrow {
    image: none;
    width: 0;
    height: 0;
    border-left: 5px solid #f5e6ff;
    border-top: 4px solid transparent;
    border-bottom: 4px solid transparent;
    margin-right: 8px;
}
"""

# 添加提醒对话框样式（紫色主题）
DIALOG_QSS = """
QDialog, QMessageBox {
    background-color: #3a1f4d;
    color: #f5e6ff;
    font-family: 'Microsoft YaHei', 'Segoe UI';
    font-size: 12px;
}
QMessageBox QLabel {
    color: #f5e6ff;
    min-width: 320px;
    padding: 4px;
}
QLabel {
    color: #f5e6ff;
    font-size: 12px;
    background: transparent;
}
QLineEdit, QTimeEdit {
    background-color: #2a1538;
    color: #ffffff;
    border: 1px solid #b070d8;
    border-radius: 5px;
    padding: 5px 8px;
    selection-background-color: #8b3fb8;
}
QLineEdit:focus, QTimeEdit:focus {
    border: 1px solid #ff9cd8;
}
QPushButton {
    background-color: #8b3fb8;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 22px;
    font-weight: bold;
    min-width: 72px;
    min-height: 22px;
}
QPushButton:hover {
    background-color: #a04fce;
}
QPushButton:pressed {
    background-color: #6a2e96;
}
QPushButton#cancel_btn {
    background-color: #5a3970;
}
QPushButton#cancel_btn:hover {
    background-color: #6e4a86;
}
"""


# ---------------------------------------------------------------------------
# 头顶输入气泡：双击库洛米呼出，回车直接发送给 AI
# ---------------------------------------------------------------------------
CHAT_INPUT_QSS = """
QWidget#chat_input_root {
    background-color: rgba(58, 31, 77, 240);
    border: 2px solid #b070d8;
    border-radius: 14px;
}
QLineEdit {
    background-color: #2a1538;
    color: #ffffff;
    border: 1px solid #b070d8;
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: #8b3fb8;
    font-family: 'Microsoft YaHei', 'Segoe UI';
    font-size: 12px;
    min-height: 22px;
}
QLineEdit:focus { border: 1px solid #ff9cd8; }
QLineEdit:disabled { background-color: #3a2550; color: #a98bbb; }
"""


class ChatInputBubble(QWidget):
    """漂浮在库洛米头顶的小输入框：回车 → 发送给 AI；Esc / 失焦 → 隐藏。"""

    def __init__(self, pet: "KuromiPet"):
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.pet = pet
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 强制创建原生窗口句柄，便于多屏 setScreen
        self.create()

        # 根容器（用于绘制圆角紫色背景）
        self._root = QWidget(self)
        self._root.setObjectName("chat_input_root")
        self._root.setStyleSheet(CHAT_INPUT_QSS)

        self.input_edit = QLineEdit(self._root)
        self.input_edit.setPlaceholderText("和库洛米说点什么... (Enter 发送, Esc 关闭)")
        self.input_edit.returnPressed.connect(self._on_submit)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self._root)

        inner = QHBoxLayout(self._root)
        inner.setContentsMargins(10, 8, 10, 8)
        inner.addWidget(self.input_edit)

        self.resize(300, 46)

    # 失去焦点时自动收起（点击桌宠之外的地方）
    def focusOutEvent(self, e):
        QTimer.singleShot(120, self._hide_if_no_focus)
        super().focusOutEvent(e)

    def _hide_if_no_focus(self):
        # 如果焦点没有跑到子控件上，就隐藏
        fw = QApplication.focusWidget()
        if fw is None or (fw is not self.input_edit and not self.isAncestorOf(fw)):
            self.hide()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(e)

    def show_at_pet(self):
        """放在桌宠头顶并显示。"""
        self.input_edit.setEnabled(True)
        self.input_edit.setPlaceholderText("和库洛米说点什么... (Enter 发送, Esc 关闭)")
        self.input_edit.clear()

        pet_center_x = self.pet.x() + self.pet.width() // 2
        x = pet_center_x - self.width() // 2
        y = self.pet.y() - self.height() - 6

        screen = self.pet._current_screen_geometry()
        x = max(screen.left() + 5, min(x, screen.right() - self.width() - 5))
        if y < screen.top():
            y = self.pet.y() + self.pet.height() + 6
        self.move(x, y)

        # 多屏：把窗口句柄绑到桌宠所在屏幕
        wh = self.windowHandle()
        if wh is not None:
            target = QApplication.screenAt(self.pet.frameGeometry().center())
            if target is not None and wh.screen() is not target:
                wh.setScreen(target)

        self.show()
        self.raise_()
        self.activateWindow()
        self.input_edit.setFocus()

    def _on_submit(self):
        text = self.input_edit.text().strip()
        if not text:
            return
        # 交给 pet 去发送，输入框临时禁用 + 显示等待提示
        self.input_edit.setEnabled(False)
        self.input_edit.setPlaceholderText("库洛米正在想... ٩(ˊᗜˋ*)و")
        self.input_edit.clear()
        # 隐藏输入框，让头顶气泡能干净地显示回复
        self.hide()
        self.pet.send_to_ai(text)


# ---------------------------------------------------------------------------
# 添加提醒对话框
# ---------------------------------------------------------------------------
class AddReminderDialog(QDialog):
    """添加 / 修改 提醒对话框。

    传入 reminder 时进入「修改」模式，会预填字段并以保存方式返回。
    """

    def __init__(self, parent=None, reminder: dict | None = None):
        super().__init__(parent)
        self._editing = reminder is not None
        self._origin = reminder  # 保留原始引用，便于复用 id/enabled

        self.setWindowTitle("修改提醒" if self._editing else "添加新提醒")
        self.setStyleSheet(DIALOG_QSS)
        self.setMinimumWidth(420)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 14)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：吃早餐")
        self.name_edit.setMinimumHeight(30)

        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(QTime.currentTime())
        self.time_edit.setMinimumHeight(30)

        self.msg_edit = QLineEdit()
        self.msg_edit.setPlaceholderText("提醒时库洛米要说的话~")
        self.msg_edit.setMinimumHeight(30)

        # 预填（修改模式）
        if self._editing:
            self.name_edit.setText(reminder.get("name", ""))
            try:
                hh, mm = map(int, reminder.get("time", "00:00").split(":"))
                self.time_edit.setTime(QTime(hh, mm))
            except Exception:
                pass
            self.msg_edit.setText(reminder.get("message", ""))

        form.addRow("名称：", self.name_edit)
        form.addRow("时间：", self.time_edit)
        form.addRow("内容：", self.msg_edit)
        layout.addLayout(form)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("保存" if self._editing else "添加")
        ok_btn.clicked.connect(self._on_accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("cancel_btn")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _on_accept(self):
        if not self.name_edit.text().strip():
            self._warn("请填写提醒名称~")
            return
        if not self.msg_edit.text().strip():
            self._warn("请填写提醒内容~")
            return
        self.accept()

    def _warn(self, text: str):
        box = QMessageBox(self)
        box.setStyleSheet(DIALOG_QSS)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("提示")
        box.setText(text)
        box.exec()

    def get_data(self) -> dict:
        """返回数据：新增→生成新 id；修改→沿用原 id 和 enabled 状态。"""
        if self._editing and self._origin is not None:
            return {
                "id": self._origin.get("id", f"custom_{int(datetime.now().timestamp() * 1000)}"),
                "name": self.name_edit.text().strip(),
                "time": self.time_edit.time().toString("HH:mm"),
                "message": self.msg_edit.text().strip(),
                "enabled": self._origin.get("enabled", True),
            }
        return {
            "id": f"custom_{int(datetime.now().timestamp() * 1000)}",
            "name": self.name_edit.text().strip(),
            "time": self.time_edit.time().toString("HH:mm"),
            "message": self.msg_edit.text().strip(),
            "enabled": True,
        }


# ---------------------------------------------------------------------------
# 气泡对话框：圆角 + 小尾巴，跟随宠物显示
# ---------------------------------------------------------------------------
class SpeechBubble(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 强制创建原生窗口句柄，便于多屏环境提前 setScreen
        self.create()
        self.text = ""
        self.padding = 14
        self.max_width = 240
        self.tail_height = 10
        # 与 paintEvent 中绘制使用完全一致的字体，保证测量 == 实际绘制
        self._text_font = QFont("Microsoft YaHei", 10)
        self._text_font.setBold(True)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_text(self, text: str, duration_ms: int = 6000):
        """只更新文字与尺寸，不在此处 show，避免使用旧坐标先闪一下。
        调用方应在 resize 后 move() 到正确位置，再调用 reveal()。
        """
        self.text = text
        fm = QFontMetrics(self._text_font)

        inner_w = self.max_width - self.padding * 2
        flags = Qt.TextWordWrap | Qt.AlignLeft

        # 用一个足够大的高度让 boundingRect 算出真实换行后的高度
        rect = fm.boundingRect(
            0, 0, inner_w, 10000,
            flags, text
        )

        # 多行中文 + 显式 \n 时再加一点冗余，避免最后一行被截
        line_h = fm.lineSpacing()
        text_w = max(rect.width(), fm.horizontalAdvance("库洛米"))
        text_h = rect.height() + line_h // 2  # 冗余半行防止下沉字符被切

        w = min(text_w, inner_w) + self.padding * 2
        h = text_h + self.padding * 2 + self.tail_height

        self.resize(w, h)
        self.update()
        self._hide_timer.start(duration_ms)

    def reveal(self):
        """在已经 move 到目标位置后显示。"""
        self.show()
        self.raise_()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        body_h = h - self.tail_height  # 减去尾巴

        # 圆角矩形主体
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, body_h), 14, 14)

        # 小尾巴（指向下方宠物）
        tail = QPainterPath()
        tail.moveTo(w / 2 - 10, body_h - 1)
        tail.lineTo(w / 2, h)
        tail.lineTo(w / 2 + 10, body_h - 1)
        tail.closeSubpath()
        path.addPath(tail)

        # 填充
        p.setPen(QPen(QColor(180, 130, 200), 2))
        p.setBrush(QColor(255, 245, 252, 240))
        p.drawPath(path)

        # 文字（与 show_text 中用于测量的字体保持一致）
        p.setPen(QColor(60, 30, 80))
        p.setFont(self._text_font)
        text_rect = QRectF(
            self.padding, self.padding,
            w - self.padding * 2,
            body_h - self.padding * 2
        )
        p.drawText(text_rect, Qt.AlignLeft | Qt.TextWordWrap, self.text)


# ---------------------------------------------------------------------------
# 桌宠主窗口
# ---------------------------------------------------------------------------
class KuromiPet(QWidget):
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.pet_size = config["pet"].get("size", 180)
        anim_cfg = config.get("animation", {})
        self.fps = anim_cfg.get("fps", 10)
        self.state_switch_minutes = anim_cfg.get("state_switch_minutes", 20)

        # ----- 窗口属性 -----
        flags = Qt.FramelessWindowHint | Qt.Tool
        if config["pet"].get("always_on_top", True):
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(self.pet_size, self.pet_size)

        # ----- 加载帧动画 -----
        # frames[state] = [QPixmap, QPixmap, ...]
        self.frames: dict[str, list[QPixmap]] = self._load_all_frames()
        self.available_states = [s for s in STATES if self.frames.get(s)]
        if not self.available_states:
            # 没切过图，给个占位
            self.available_states = ["normal"]
            self.frames["normal"] = [self._placeholder_pixmap()]

        self.current_state = self.available_states[0]
        self.frame_index = 0

        self.label = QLabel(self)
        self.label.resize(self.pet_size, self.pet_size)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setPixmap(self.frames[self.current_state][0])

        # ----- 帧播放定时器 -----
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._next_frame)
        self.anim_timer.start(int(1000 / max(1, self.fps)))

        # ----- 状态自动切换定时器 -----
        self.state_timer = QTimer(self)
        self.state_timer.timeout.connect(self.cycle_state)
        self.state_timer.start(self.state_switch_minutes * 60 * 1000)

        # ----- 气泡 -----
        self.bubble = SpeechBubble()

        # ----- 拖拽 -----
        self._drag_pos: QPoint | None = None

        # ----- 提醒定时器（每 30 秒检查一次）-----
        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self.check_reminders)
        self.reminder_timer.start(30 * 1000)
        self._last_fired: dict[str, str] = {}  # id -> "YYYY-MM-DD HH:MM"

        # ----- 闲聊定时器 -----
        self.chat_timer = QTimer(self)
        self.chat_timer.timeout.connect(self.say_random)
        self.chat_timer.start(5 * 60 * 1000)  # 每5分钟一次随机话

        # ----- 临时状态还原定时器（提醒触发时短暂切到 happy）-----
        self._temp_state_timer = QTimer(self)
        self._temp_state_timer.setSingleShot(True)
        self._temp_state_timer.timeout.connect(self._restore_state)
        self._prev_state_before_temp: str | None = None

        # ----- AI 对话历史 + 输入气泡 + worker -----
        ai_cfg = config.get("ai", {}) or {}
        if _AI_AVAILABLE:
            self.chat_history = ChatHistory(
                system_prompt=ai_cfg.get("system_prompt") or DEFAULT_SYSTEM_PROMPT,
                max_turns=int(ai_cfg.get("max_history", 10)),
            )
        else:
            self.chat_history = None
        self._chat_input: ChatInputBubble | None = None
        self._chat_worker: ChatWorker | None = None
        self._streaming_buffer: list[str] = []
        self._streaming_user_input: str = ""

        # ----- 全局热键 Shift+G 呼出聊天 -----
        self._hotkey_id = 1   # Windows RegisterHotKey ID
        self._hotkey_registered = False
        self._register_global_hotkey()

        # 初始位置：屏幕右下角
        self._move_to_corner()

        # 启动问候
        QTimer.singleShot(500, lambda: self.say(
            f"库洛米上线咯！现在是 {datetime.now().strftime('%H:%M')} ~"
        ))

    # ----------------- 工具方法 -----------------
    def _placeholder_pixmap(self) -> QPixmap:
        pm = QPixmap(self.pet_size, self.pet_size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(180, 130, 200))
        p.setPen(Qt.NoPen)
        p.drawEllipse(10, 10, self.pet_size - 20, self.pet_size - 20)
        p.setPen(QColor(255, 255, 255))
        p.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        p.drawText(pm.rect(), Qt.AlignCenter,
                   "请先运行\nslice_sheet.py")
        p.end()
        return pm

    def _load_all_frames(self) -> dict:
        """从 assets/frames/<state>/frame_*.png 加载每个状态的帧序列。"""
        result: dict[str, list[QPixmap]] = {}
        if not FRAMES_DIR.exists():
            return result
        for state in STATES:
            state_dir = FRAMES_DIR / state
            if not state_dir.exists():
                continue
            files = sorted(state_dir.glob("frame_*.png"),
                           key=lambda p: int(p.stem.split("_")[-1]))
            pixs = []
            for f in files:
                pm = QPixmap(str(f))
                if pm.isNull():
                    continue
                pm = pm.scaled(self.pet_size, self.pet_size,
                               Qt.KeepAspectRatio, Qt.SmoothTransformation)
                pixs.append(pm)
            if pixs:
                result[state] = pixs
        return result

    def _next_frame(self):
        frames = self.frames.get(self.current_state)
        if not frames:
            return
        self.frame_index = (self.frame_index + 1) % len(frames)
        self.label.setPixmap(frames[self.frame_index])

    def set_state(self, state: str, announce: bool = True):
        if state not in self.frames or not self.frames[state]:
            return
        self.current_state = state
        self.frame_index = 0
        self.label.setPixmap(self.frames[state][0])
        # 重启自动切换计时（避免手动切完马上又被自动切）
        self.state_timer.start(self.state_switch_minutes * 60 * 1000)
        if announce:
            phrase = random.choice(STATE_PHRASES.get(state, [""]))
            self.say(f"切换到「{STATE_LABELS.get(state, state)}」状态\n{phrase}",
                     happy=False, duration=4000)

    def cycle_state(self):
        """按顺序切到下一个可用状态。"""
        if len(self.available_states) <= 1:
            return
        idx = self.available_states.index(self.current_state)
        nxt = self.available_states[(idx + 1) % len(self.available_states)]
        self.set_state(nxt, announce=True)

    def _temp_set_state(self, state: str, duration_ms: int):
        """临时切到某状态，到点恢复（用于提醒触发时）。"""
        if state not in self.frames:
            return
        if self._prev_state_before_temp is None:
            self._prev_state_before_temp = self.current_state
        self.current_state = state
        self.frame_index = 0
        self.label.setPixmap(self.frames[state][0])
        self._temp_state_timer.start(duration_ms)

    def _restore_state(self):
        if self._prev_state_before_temp:
            self.current_state = self._prev_state_before_temp
            self.frame_index = 0
            if self.frames.get(self.current_state):
                self.label.setPixmap(self.frames[self.current_state][0])
            self._prev_state_before_temp = None

    def _move_to_corner(self):
        screen = self._current_screen_geometry()
        x = screen.right() - self.width() - 20
        y = screen.bottom() - self.height() - 20
        self.move(x, y)

    # ----------------- 气泡说话 -----------------
    def _current_screen_geometry(self):
        """获取桌宠当前所在屏幕的可用区域（多屏环境下正确返回该屏边界）。"""
        # 优先用窗口句柄关联的屏幕（最准确）
        wh = self.windowHandle()
        if wh is not None and wh.screen() is not None:
            return wh.screen().availableGeometry()
        # 回退：根据窗口中心点查找所在屏幕
        center = self.frameGeometry().center()
        scr = QApplication.screenAt(center)
        if scr is None:
            scr = QApplication.primaryScreen()
        return scr.availableGeometry()

    def _position_bubble(self):
        """根据桌宠当前位置把气泡放到合适位置（支持多屏）。"""
        pet_center_x = self.x() + self.width() // 2
        bx = pet_center_x - self.bubble.width() // 2
        by = self.y() - self.bubble.height() - 5
        # 防止超出【桌宠所在那块屏幕】
        screen = self._current_screen_geometry()
        bx = max(screen.left() + 5,
                 min(bx, screen.right() - self.bubble.width() - 5))
        if by < screen.top():
            by = self.y() + self.height() + 5
        self.bubble.move(bx, by)
        # 把气泡的窗口句柄也指到当前屏幕，避免它被系统强行拽回主屏
        bwh = self.bubble.windowHandle()
        if bwh is not None:
            target_screen = QApplication.screenAt(self.frameGeometry().center())
            if target_screen is not None and bwh.screen() is not target_screen:
                bwh.setScreen(target_screen)

    def say(self, text: str, happy: bool = True, duration: int = 6000):
        # 先准备好气泡尺寸（不显示）
        self.bubble.show_text(text, duration)
        # 再根据当前桌宠位置摆放
        self._position_bubble()
        # 最后才显示，避免先在旧位置闪一下
        self.bubble.reveal()

        if happy and "happy" in self.frames:
            self._temp_set_state("happy", duration)

    def say_random(self):
        phrases = STATE_PHRASES.get(self.current_state) or STATE_PHRASES["normal"]
        self.say(random.choice(phrases), happy=False, duration=4000)

    # ----------------- 定时提醒 -----------------
    def check_reminders(self):
        now = datetime.now()
        now_hm = now.strftime("%H:%M")
        today = now.strftime("%Y-%m-%d")
        key_now = f"{today} {now_hm}"

        for r in self.config.get("reminders", []):
            if not r.get("enabled", True):
                continue
            if r["time"] == now_hm and self._last_fired.get(r["id"]) != key_now:
                self._last_fired[r["id"]] = key_now
                self.fire_reminder(r)

    def fire_reminder(self, reminder: dict):
        msg = f"{reminder['name']}\n{reminder['message']}"
        self.say(msg, happy=True, duration=10000)
        # 系统托盘也来一发
        if hasattr(self, "tray"):
            self.tray.showMessage(
                f"库洛米提醒 - {reminder['name']}",
                reminder["message"],
                QSystemTrayIcon.Information,
                8000,
            )

    # ----------------- 鼠标交互 -----------------
    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._drag_pos is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)
            # 拖动时气泡跟随
            if self.bubble.isVisible():
                self._position_bubble()
            e.accept()

    def mouseReleaseEvent(self, e: QMouseEvent):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            # 双击：呼出头顶输入气泡（AI 启用时），否则保留原来的小生气
            ai_cfg = self.config.get("ai", {}) or {}
            if _AI_AVAILABLE and ai_cfg.get("enabled", False):
                self.open_chat_input()
            else:
                if "angry" in self.frames:
                    self._temp_set_state("angry", 4000)
                self.say("哼！别摸我啦~(>﹏<)", happy=False, duration=4000)

    # ----------------- AI 聊天（头顶输入气泡） -----------------
    def open_chat_input(self):
        """在桌宠头顶弹出一个输入气泡。"""
        if not _AI_AVAILABLE:
            self.say("AI 模块未安装~\n请先 pip install zai-sdk", happy=False, duration=5000)
            return
        ai_cfg = self.config.get("ai", {}) or {}
        if not ai_cfg.get("enabled", False):
            self.say("AI 功能未启用哦~\n请在 config.json 里把 ai.enabled 改成 true",
                     happy=False, duration=6000)
            return
        if not (ai_cfg.get("api_key") or "").strip():
            self.say("还没填 API Key 呢~\n去 config.json 配置一下吧",
                     happy=False, duration=6000)
            return
        # 正在回复中？提示用户稍等
        if self._chat_worker is not None and self._chat_worker.isRunning():
            self.say("等等啦~还在想上一句呢 (>﹏<)", happy=False, duration=2500)
            return
        # 把可能还没散去的气泡先关掉，让输入框干净地出现
        if self.bubble.isVisible():
            self.bubble.hide()

        if self._chat_input is None:
            self._chat_input = ChatInputBubble(self)
        self._chat_input.show_at_pet()

    def send_to_ai(self, user_text: str):
        """把用户输入发送给 GLM，回复以头顶气泡形式展示（流式更新）。"""
        ai_cfg = self.config.get("ai", {}) or {}
        api_key = (ai_cfg.get("api_key") or "").strip()
        if not api_key or self.chat_history is None:
            return

        # 构造 messages
        messages = self.chat_history.build_messages(user_text)

        # 桌宠先开口提示一下，进入“思考”视觉
        self.say("嗯…让我想想 (｡•ㅅ•｡)", happy=False, duration=60000)

        self._streaming_buffer = []
        self._streaming_user_input = user_text

        self._chat_worker = ChatWorker(
            api_key=api_key,
            base_url=ai_cfg.get("base_url", ""),
            model=ai_cfg.get("model", "glm-4-flash"),
            messages=messages,
            stream=bool(ai_cfg.get("stream", True)),
            timeout=int(ai_cfg.get("timeout", 30)),
        )
        self._chat_worker.chunk_received.connect(self._on_ai_chunk)
        self._chat_worker.finished_ok.connect(self._on_ai_finished)
        self._chat_worker.error.connect(self._on_ai_error)
        self._chat_worker.start()

    def _on_ai_chunk(self, piece: str):
        """流式接收：实时更新头顶气泡。"""
        from ai_chat import EMOTION_PATTERN
        self._streaming_buffer.append(piece)
        full = "".join(self._streaming_buffer)
        # 显示前剥掉（可能不完整的）情绪标签碎片
        show = EMOTION_PATTERN.sub("", full).rstrip()
        if not show:
            return
        # 复用 say()：但不要每次都把状态切到 happy（避免抖动），只刷新气泡内容
        self.bubble.show_text(show, duration_ms=60000)
        self._position_bubble()
        self.bubble.reveal()

    def _on_ai_finished(self, full_text: str, emotion: str):
        """完整回复就绪：写历史 + 切动画 + 最终气泡停留。"""
        text = full_text.strip() or "……"
        if self.chat_history is not None:
            self.chat_history.add_user(self._streaming_user_input)
            self.chat_history.add_assistant(
                text + (f" [emotion:{emotion}]" if emotion else "")
            )

        # 调试输出：方便确认情绪是否被正确识别
        print(f"[AI] full_text={text!r}, emotion={emotion!r}, "
              f"frames_keys={list(self.frames.keys())}")

        # 先显示气泡（注意 happy=False，避免 say() 内部覆盖我们要切的情绪状态）
        self.say(text, happy=False, duration=8000)

        # 再切到对应情绪动画（放在 say 之后，确保不被覆盖）
        if emotion and emotion in self.frames:
            self._temp_set_state(emotion, 6000)
            print(f"[AI] -> 切换到 '{emotion}' 状态 6 秒")
        elif emotion:
            print(f"[AI] WARN: 情绪 '{emotion}' 不在可用 frames 中，跳过切换")

        self._streaming_buffer = []
        self._streaming_user_input = ""
        self._chat_worker = None

    def _on_ai_error(self, msg: str):
        self.say(f"呜...出错啦~\n{msg}", happy=False, duration=5000)
        self._streaming_buffer = []
        self._streaming_user_input = ""
        self._chat_worker = None

    # ----------------- 全局快捷键 Shift+G -----------------
    def _register_global_hotkey(self):
        """注册系统级全局快捷键 Shift+G。

        - Windows：使用 ctypes 调 RegisterHotKey + nativeEvent 监听 WM_HOTKEY
        - 其他平台：降级为窗口级 QShortcut（仅在桌宠获得焦点时生效）
        """
        if sys.platform == "win32":
            try:
                import ctypes
                MOD_SHIFT = 0x0004
                MOD_NOREPEAT = 0x4000  # 防止按住时连续触发
                VK_G = 0x47
                hwnd = int(self.winId())
                ok = ctypes.windll.user32.RegisterHotKey(
                    hwnd, self._hotkey_id, MOD_SHIFT | MOD_NOREPEAT, VK_G
                )
                if ok:
                    self._hotkey_registered = True
                    print("[INFO] 全局热键 Shift+G 已注册")
                    return
                else:
                    print("[WARN] 全局热键 Shift+G 注册失败（可能被其他程序占用），降级为窗口快捷键")
            except Exception as e:
                print(f"[WARN] 注册全局热键失败：{e}，降级为窗口快捷键")

        # 降级方案：窗口级快捷键（需要桌宠拥有焦点）
        try:
            from PySide6.QtGui import QShortcut, QKeySequence
            sc = QShortcut(QKeySequence("Shift+G"), self)
            sc.setContext(Qt.ApplicationShortcut)
            sc.activated.connect(self.open_chat_input)
        except Exception as e:
            print(f"[WARN] 窗口级快捷键也注册失败：{e}")

    def _unregister_global_hotkey(self):
        if self._hotkey_registered and sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.UnregisterHotKey(int(self.winId()), self._hotkey_id)
            except Exception:
                pass
            self._hotkey_registered = False

    def nativeEvent(self, eventType, message):
        """监听 Windows 原生消息：捕获 WM_HOTKEY 触发聊天框。"""
        if sys.platform == "win32" and self._hotkey_registered:
            try:
                import ctypes
                from ctypes import wintypes
                WM_HOTKEY = 0x0312
                msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG))[0]
                if msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id:
                    # 在主线程异步触发，避免阻塞消息泵
                    QTimer.singleShot(0, self.open_chat_input)
                    return True, 0
            except Exception:
                pass
        return super().nativeEvent(eventType, message)

    def closeEvent(self, e):
        self._unregister_global_hotkey()
        super().closeEvent(e)

    def contextMenuEvent(self, e):
        menu = self._build_menu()
        menu.exec(e.globalPos())

    # ----------------- 菜单 -----------------
    def _build_menu(self) -> QMenu:
        menu = QMenu()
        menu.setStyleSheet(MENU_QSS)

        act_hi = QAction("打个招呼", self)
        act_hi.triggered.connect(self.say_random)
        menu.addAction(act_hi)

        act_time = QAction("现在几点啦？", self)
        act_time.triggered.connect(
            lambda: self.say(f"现在是 {datetime.now().strftime('%H:%M:%S')} 哦~")
        )
        menu.addAction(act_time)

        # AI 聊天入口（头顶输入气泡）
        ai_cfg = self.config.get("ai", {}) or {}
        ai_enabled = _AI_AVAILABLE and ai_cfg.get("enabled", False)
        act_chat = QAction("💬 和库洛米说话...（双击我也行~）", self)
        act_chat.triggered.connect(self.open_chat_input)
        act_chat.setEnabled(ai_enabled)
        if not ai_enabled:
            act_chat.setText("💬 和库洛米说话（未启用）")
        menu.addAction(act_chat)

        menu.addSeparator()

        # 状态切换子菜单
        state_menu = menu.addMenu(
            f"切换状态（当前：{STATE_LABELS.get(self.current_state, self.current_state)}）"
        )
        state_menu.setStyleSheet(MENU_QSS)
        for s in self.available_states:
            label = STATE_LABELS.get(s, s)
            mark = " ●" if s == self.current_state else ""
            act = QAction(f"{label}{mark}", self)
            act.triggered.connect(lambda _=False, st=s: self.set_state(st))
            state_menu.addAction(act)
        state_menu.addSeparator()
        act_cycle = QAction("下一个状态 →", self)
        act_cycle.triggered.connect(self.cycle_state)
        state_menu.addAction(act_cycle)

        menu.addSeparator()

        # 提醒子菜单
        rem_menu = menu.addMenu("今日提醒")
        rem_menu.setStyleSheet(MENU_QSS)

        reminders = self.config.get("reminders", [])
        if reminders:
            for r in reminders:
                status = "✓" if r.get("enabled", True) else "✗"
                # 每个提醒一个子菜单，里面有：启用/禁用、删除
                item_menu = rem_menu.addMenu(f"{status} {r['time']}  {r['name']}")
                item_menu.setStyleSheet(MENU_QSS)

                act_toggle = QAction(
                    "已启用" if r.get("enabled", True) else "已禁用", self
                )
                act_toggle.setCheckable(True)
                act_toggle.setChecked(r.get("enabled", True))
                act_toggle.triggered.connect(
                    lambda checked, rr=r: self._toggle_reminder(rr, checked)
                )
                item_menu.addAction(act_toggle)

                item_menu.addSeparator()

                act_edit = QAction("✏️ 修改此提醒...", self)
                act_edit.triggered.connect(
                    lambda _=False, rr=r: self._edit_reminder(rr)
                )
                item_menu.addAction(act_edit)

                act_del = QAction("🗑 删除此提醒", self)
                act_del.triggered.connect(
                    lambda _=False, rr=r: self._delete_reminder(rr)
                )
                item_menu.addAction(act_del)
        else:
            act_empty = QAction("（暂无提醒）", self)
            act_empty.setEnabled(False)
            rem_menu.addAction(act_empty)

        rem_menu.addSeparator()
        act_add = QAction("➕ 添加新提醒...", self)
        act_add.triggered.connect(self._add_reminder)
        rem_menu.addAction(act_add)

        act_next = QAction("下一个提醒是？", self)
        act_next.triggered.connect(self._announce_next_reminder)
        menu.addAction(act_next)

        menu.addSeparator()

        act_corner = QAction("回到右下角", self)
        act_corner.triggered.connect(self._move_to_corner)
        menu.addAction(act_corner)

        act_about = QAction("关于库洛米", self)
        act_about.triggered.connect(self._show_about)
        menu.addAction(act_about)

        menu.addSeparator()

        act_quit = QAction("拜拜~退出", self)
        act_quit.triggered.connect(QApplication.quit)
        menu.addAction(act_quit)

        return menu

    def _toggle_reminder(self, reminder: dict, enabled: bool):
        reminder["enabled"] = enabled
        save_config(self.config)
        state = "开启" if enabled else "关闭"
        self.say(f"已{state}：{reminder['name']} ({reminder['time']})", duration=3000)

    def _add_reminder(self):
        """弹出对话框添加新提醒。"""
        dlg = AddReminderDialog(self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            self.config.setdefault("reminders", []).append(data)
            save_config(self.config)
            self.say(
                f"✨ 新提醒已添加~\n「{data['name']}」 {data['time']}",
                happy=True, duration=4000
            )

    def _edit_reminder(self, reminder: dict):
        """弹出对话框修改现有提醒。"""
        dlg = AddReminderDialog(self, reminder=reminder)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.get_data()
        # 原地更新 dict（保持 list 引用与顺序不变）
        old_time = reminder.get("time")
        reminder.update(data)
        # 时间变化时清理已触发记录，避免新时间不再触发
        if old_time != data["time"]:
            self._last_fired.pop(reminder.get("id", ""), None)
        save_config(self.config)
        self.say(
            f"📝 提醒已更新~\n「{data['name']}」 {data['time']}",
            happy=True, duration=4000
        )

    def _delete_reminder(self, reminder: dict):
        """弹确认框删除指定提醒。"""
        box = QMessageBox(self)
        box.setStyleSheet(DIALOG_QSS)
        box.setWindowTitle("删除提醒")
        box.setIcon(QMessageBox.Question)
        box.setText(
            f"确定要删除提醒吗？\n\n"
            f"⏰ {reminder['time']}  {reminder['name']}"
        )
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        box.button(QMessageBox.Yes).setText("删除")
        box.button(QMessageBox.No).setText("取消")
        if box.exec() != QMessageBox.Yes:
            return

        reminders = self.config.get("reminders", [])
        try:
            reminders.remove(reminder)
        except ValueError:
            return
        # 清理已触发记录
        self._last_fired.pop(reminder.get("id", ""), None)
        save_config(self.config)
        self.say(
            f"已删除：「{reminder['name']}」({reminder['time']})",
            happy=False, duration=3000
        )

    def _announce_next_reminder(self):
        now = datetime.now()
        upcoming = []
        for r in self.config.get("reminders", []):
            if not r.get("enabled", True):
                continue
            hh, mm = map(int, r["time"].split(":"))
            t = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if t < now:
                t += timedelta(days=1)
            upcoming.append((t, r))
        if not upcoming:
            self.say("今天没有提醒啦~", duration=3000)
            return
        upcoming.sort(key=lambda x: x[0])
        t, r = upcoming[0]
        delta = t - now
        mins = int(delta.total_seconds() // 60)
        h, m = divmod(mins, 60)
        when = f"{h}小时{m}分钟后" if h > 0 else f"{m}分钟后"
        self.say(f"下一个提醒：\n{when} 「{r['name']}」({r['time']})", duration=6000)

    def _show_about(self):
        box = QMessageBox(self)
        box.setStyleSheet(DIALOG_QSS)
        box.setWindowTitle("关于库洛米桌宠")
        box.setText(
            "🖤 库洛米桌面宠物 v1.0\n\n"
            "• 拖动：左键按住移动\n"
            "• 互动：双击我\n"
            "• 菜单：右键\n\n"
            "提醒功能可在 config.json 中自定义~"
        )
        box.setIcon(QMessageBox.Information)
        box.exec()


# ---------------------------------------------------------------------------
# 配置加载 / 保存
# ---------------------------------------------------------------------------
def load_config() -> dict:
    """加载配置：优先读 USER_DIR/config.json，没有则读打包内置默认配置。

    注意：本函数**不会**在用户目录创建 config.json 文件。
    """
    target = CONFIG_PATH if CONFIG_PATH.exists() else DEFAULT_CONFIG_PATH
    if not target.exists():
        return {"pet": {"size": 180, "always_on_top": True}, "reminders": []}
    try:
        with open(target, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] 读取配置失败：{e}")
        return {"pet": {"size": 180, "always_on_top": True}, "reminders": []}


def save_config(cfg: dict):
    """仅当 config.json 已存在时才覆盖写入；否则不创建新文件。

    这样运行过程中（包括打包后的 exe 旁边）不会凭空生成 config.json。
    """
    if not CONFIG_PATH.exists():
        # 文件不存在：什么都不做，避免在运行目录生成 config.json
        return
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] 写入配置失败：{e}")


# ---------------------------------------------------------------------------
# 系统托盘
# ---------------------------------------------------------------------------
def setup_tray(pet: KuromiPet) -> QSystemTrayIcon:
    icon_path = ASSETS_DIR / "kuromi_idle.png"
    icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()

    tray = QSystemTrayIcon(icon)
    tray.setToolTip("库洛米桌宠 - 双击呼出 / 隐藏")

    menu = QMenu()
    menu.setStyleSheet(MENU_QSS)
    act_show = QAction("显示/隐藏库洛米")
    act_show.triggered.connect(lambda: pet.setVisible(not pet.isVisible()))
    menu.addAction(act_show)

    act_quit = QAction("退出")
    act_quit.triggered.connect(QApplication.quit)
    menu.addAction(act_quit)

    tray.setContextMenu(menu)

    def on_activated(reason):
        if reason == QSystemTrayIcon.DoubleClick:
            pet.setVisible(not pet.isVisible())

    tray.activated.connect(on_activated)
    tray.show()
    pet.tray = tray  # 让 pet 可以发系统通知
    return tray


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    # Windows 上让任务栏图标正确显示
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("kuromi.pet.1.0")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    cfg = load_config()
    pet = KuromiPet(cfg)
    pet.show()
    setup_tray(pet)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
