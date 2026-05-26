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
    QPixmap, QPainter, QColor, QFont, QAction, QIcon,
    QPainterPath, QPen, QCursor, QMouseEvent
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QMenu, QSystemTrayIcon,
    QVBoxLayout, QHBoxLayout, QMessageBox, QDialog, QLineEdit,
    QTimeEdit, QPushButton, QFormLayout
)
from PySide6.QtCore import QTime


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
QDialog {
    background-color: #3a1f4d;
    color: #f5e6ff;
    font-family: 'Microsoft YaHei', 'Segoe UI';
    font-size: 12px;
}
QLabel {
    color: #f5e6ff;
    font-size: 12px;
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
    padding: 6px 18px;
    font-weight: bold;
    min-width: 60px;
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
        self.setFixedWidth(340)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：吃早餐")

        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(QTime.currentTime())

        self.msg_edit = QLineEdit()
        self.msg_edit.setPlaceholderText("提醒时库洛米要说的话~")

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
            QMessageBox.warning(self, "提示", "请填写提醒名称~")
            return
        if not self.msg_edit.text().strip():
            QMessageBox.warning(self, "提示", "请填写提醒内容~")
            return
        self.accept()

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
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_text(self, text: str, duration_ms: int = 6000):
        """只更新文字与尺寸，不在此处 show，避免使用旧坐标先闪一下。
        调用方应在 resize 后 move() 到正确位置，再调用 reveal()。
        """
        self.text = text
        fm = self.fontMetrics()
        # 自动换行计算
        rect = fm.boundingRect(
            0, 0, self.max_width - self.padding * 2, 0,
            Qt.TextWordWrap, text
        )
        w = rect.width() + self.padding * 2
        h = rect.height() + self.padding * 2 + 10  # +尾巴
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
        body_h = h - 10  # 减去尾巴

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

        # 文字
        p.setPen(QColor(60, 30, 80))
        font = QFont("Microsoft YaHei", 10)
        font.setBold(True)
        p.setFont(font)
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
                     duration=4000)

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
        msg = f"⏰ {reminder['name']}\n{reminder['message']}"
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
            if "angry" in self.frames:
                self._temp_set_state("angry", 4000)
            self.say("哼！别摸我啦~(>﹏<)", happy=False, duration=4000)

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

        menu.addSeparator()

        # 状态切换子菜单
        state_menu = menu.addMenu(
            f"🎭 切换状态（当前：{STATE_LABELS.get(self.current_state, self.current_state)}）"
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
        rem_menu = menu.addMenu("⏰ 今日提醒")
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
    # 首次运行：把打包内置的默认 config.json 复制到 exe 旁边
    if not CONFIG_PATH.exists():
        try:
            if DEFAULT_CONFIG_PATH.exists() and DEFAULT_CONFIG_PATH != CONFIG_PATH:
                import shutil
                shutil.copyfile(DEFAULT_CONFIG_PATH, CONFIG_PATH)
        except Exception as e:
            print(f"[WARN] 复制默认配置失败：{e}")

    if not CONFIG_PATH.exists():
        return {"pet": {"size": 180, "always_on_top": True}, "reminders": []}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


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
