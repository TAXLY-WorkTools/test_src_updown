import sys, os, subprocess, webbrowser, json, threading, atexit
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QFileDialog, QMessageBox, QMenu, QToolButton, QInputDialog,
    QDialog, QCheckBox, QLineEdit, QSlider, QDialogButtonBox, QScrollArea
)
from PyQt5.QtCore import Qt, QPoint, QSize, QTimer, QSharedMemory, pyqtSignal, QObject, QEvent
from PyQt5.QtGui import QFont, QIcon, QColor, QPainter, QPixmap, QCursor, QKeySequence
from pynput import keyboard
from pystray import MenuItem as TrayMenuItem, Icon as TrayIcon
from PIL import Image, ImageDraw

# ================================================
# 配色方案
# ================================================
COLORS = {
    'primary':            '#404040',
    'primary_hover':      '#606060',
    'primary_light':      '#D0D0D0',
    'bg_page':            '#C0C0C0',
    'bg_card':            '#FFFFFF',
    'bg_hover':           '#E0E0E0',
    'text_main':          '#000000',
    'text_secondary':     '#404040',
    'text_disabled':      '#808080',
    'border':             '#808080',
    'button_face':        '#C0C0C0',
    'button_light':       '#FFFFFF',
    'button_dark':        '#808080',
    'button_pressed':     '#A0A0A0',
    'placeholder_hover':  '#404040',
    'placeholder_bg':     '#E8E8E8',
    'menu_bg':            '#FFFFFF',
    'menu_text':          '#000000',
    'menu_selected_bg':   '#C0C0C0',
    'drag_highlight_bg':  '#A0A0A0',
    'toast_green':        '#5C7A5C',
    'toast_orange':       '#D98C2E',
    'toast_gray':         '#808080',
}

# ================================================
# 数据文件路径
# ================================================
DATA_DIR = os.path.join(os.path.expanduser("~"), "Documents", "aHA小助")
os.makedirs(DATA_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(DATA_DIR, "quick_panel.json")

DEFAULT_TOOLS = [
    {"name": "计算器", "path": "calc.exe", "type": "程序", "description": "Windows 计算器",
     "icon_path": "", "display_name": "计算器", "removable": False},
    {"name": "记事本", "path": "notepad.exe", "type": "程序", "description": "Windows 记事本",
     "icon_path": "", "display_name": "记事本", "removable": False},
    {"name": "截图", "path": "ms-screenclip:", "type": "命令", "description": "系统截图",
     "icon_path": "", "display_name": "截图", "removable": False},
]

TOOLS_SLOTS = [None] * 8
APPS_SLOTS = [None] * 16
ALL_ITEMS = []

SETTINGS = {
    "hotkey": "Ctrl+Shift+A",
    "auto_start": False,
    "button_size": 72,
    "grid_spacing": 4,
    "always_on_top": True,
}

def load_config():
    global ALL_ITEMS, TOOLS_SLOTS, APPS_SLOTS, SETTINGS
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "all_items" in data: ALL_ITEMS = data["all_items"]
        else: ALL_ITEMS = []
        for dt in DEFAULT_TOOLS:
            if dt not in ALL_ITEMS: ALL_ITEMS.append(dt)

        if "tools_slots" in data:
            for i, name in enumerate(data["tools_slots"]):
                if name:
                    for item in ALL_ITEMS:
                        if item["name"] == name:
                            TOOLS_SLOTS[i] = item
                            break
        for dt in DEFAULT_TOOLS:
            if dt not in TOOLS_SLOTS:
                for i in range(8):
                    if TOOLS_SLOTS[i] is None:
                        TOOLS_SLOTS[i] = dt
                        break

        if "apps_slots" in data:
            for i, name in enumerate(data["apps_slots"]):
                if name:
                    for item in ALL_ITEMS:
                        if item["name"] == name:
                            APPS_SLOTS[i] = item
                            break
        if "settings" in data: SETTINGS.update(data["settings"])
    except:
        TOOLS_SLOTS = [None] * 8; APPS_SLOTS = [None] * 16
        ALL_ITEMS = DEFAULT_TOOLS.copy()
        for i, tool in enumerate(DEFAULT_TOOLS):
            TOOLS_SLOTS[i] = tool

def save_config():
    data = {
        "all_items": ALL_ITEMS,
        "tools_slots": [item["name"] if item else None for item in TOOLS_SLOTS],
        "apps_slots": [item["name"] if item else None for item in APPS_SLOTS],
        "settings": SETTINGS,
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

load_config()

# ================================================
# Toast 提示
# ================================================
class ToastWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.label_layout = QVBoxLayout(self)
        self.label_layout.setAlignment(Qt.AlignCenter)
        self.label_layout.setContentsMargins(0,0,0,0)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.hide)

    def show_message(self, text, bg_color="green", duration=2000):
        while self.label_layout.count():
            child = self.label_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        self.label_layout.addWidget(lbl)
        self.setStyleSheet(f"background: {bg_color}; border-radius: 8px; padding: 10px 20px;")
        self.adjustSize()
        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, screen.height() - 120)
        self.show()
        self.timer.start(duration)

# ================================================
# 全局快捷键信号通信器
# ================================================
class HotkeyBridge(QObject):
    show_panel = pyqtSignal()
    show_toast = pyqtSignal(str, str)
    settings_changed = pyqtSignal()

# ================================================
# 自定义按钮
# ================================================
class SlotButton(QToolButton):
    def __init__(self, slot_index, region, parent_panel):
        super().__init__()
        self.slot_index = slot_index; self.region = region; self.parent_panel = parent_panel
        self.item_data = None; self.is_placeholder = True
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setIconSize(QSize(32, 32))
        size = SETTINGS.get("button_size", 72)
        self.setFixedSize(size, size)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_right_menu)

        self._press_timer = QTimer(self); self._press_timer.setSingleShot(True)
        self._press_timer.timeout.connect(self._on_long_press)
        self._drag_intent = False; self._press_pos = None
        self.update_slot_data()

    def update_slot_data(self):
        if self.region == 'tools': self.item_data = TOOLS_SLOTS[self.slot_index]
        else: self.item_data = APPS_SLOTS[self.slot_index]
        self.is_placeholder = (self.item_data is None)
        self._refresh_appearance()

    def _refresh_appearance(self):
        if self.is_placeholder:
            self.setText(""); self.setIcon(QIcon())
            self.setStyleSheet("background: transparent; border: none;")
        else:
            display = self.item_data.get('display_name', self.item_data['name'])
            max_chars = max(2, self.parent_panel.button_size() // 12)
            if len(display) > max_chars: display = display[:max_chars-2] + ".."
            self.setText(display)
            self.setStyleSheet(self._normal_style())
            if self.item_data.get('icon_path') and os.path.exists(self.item_data['icon_path']):
                pixmap = QPixmap(self.item_data['icon_path'])
                if not pixmap.isNull():
                    self.setIcon(QIcon(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
                    return
            typ = self.item_data.get('type', '程序')
            icon_map = {'程序': '🖥️', '文件夹': '📁', '网页': '🌐', '命令': '⚡'}
            pixmap = self._text_icon(icon_map.get(typ, '📄'), COLORS['primary'])
            self.setIcon(QIcon(pixmap))

    def _normal_style(self):
        size = SETTINGS.get("button_size", 72)
        return f"""
            QToolButton {{
                background: {COLORS['button_face']}; color: black;
                border-top: 1px solid {COLORS['button_light']}; border-left: 1px solid {COLORS['button_light']};
                border-right: 1px solid {COLORS['button_dark']}; border-bottom: 1px solid {COLORS['button_dark']};
                padding: 4px; font-size: {max(8, size//6)}px;
            }}
            QToolButton:hover {{ background: {COLORS['bg_hover']}; }}
        """

    def _text_icon(self, char, color):
        pixmap = QPixmap(32, 32); pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap); painter.setPen(QColor(color))
        painter.setFont(QFont("Microsoft Sans Serif", 18))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, char); painter.end()
        return pixmap

    def enterEvent(self, event):
        if self.is_placeholder:
            self.setStyleSheet(f"background: {COLORS['placeholder_bg']}; border: 1px dashed {COLORS['border']};")
            self.setIcon(QIcon(self._text_icon('＋', COLORS['placeholder_hover'])))
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.is_placeholder:
            self.setStyleSheet("background: transparent; border: none;"); self.setIcon(QIcon())
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.is_placeholder: self.show_right_menu(QPoint(0,0)); return
            self._press_pos = event.pos(); self._drag_intent = False; self._press_timer.start(300)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press_pos is not None and (event.pos() - self._press_pos).manhattanLength() > 5:
            self._press_timer.stop(); self._drag_intent = True; self.parent_panel._on_button_drag_start(self)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_timer.stop()
            if not self._drag_intent and not self.is_placeholder: self.parent_panel.execute_item(self.item_data)
            self._press_pos = None; self._drag_intent = False; self.parent_panel._on_button_drag_end()
        super().mouseReleaseEvent(event)

    def _on_long_press(self):
        self._drag_intent = True; self.parent_panel._on_button_drag_start(self)

    def show_right_menu(self, pos):
        if self.parent_panel.is_locked: return
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background: {COLORS['menu_bg']}; color: {COLORS['menu_text']}; border: 1px solid {COLORS['border']}; }}
            QMenu::item:selected {{ background: {COLORS['menu_selected_bg']}; }}
        """)
        if self.is_placeholder:
            menu.addAction("添加程序", lambda: self.parent_panel._set_pending('add', self.region, self.slot_index, '程序'))
            menu.addAction("添加文件夹", lambda: self.parent_panel._set_pending('add', self.region, self.slot_index, '文件夹'))
            menu.addAction("添加网址", lambda: self.parent_panel._set_pending('add', self.region, self.slot_index, '网页'))
            menu.addAction("添加命令", lambda: self.parent_panel._set_pending('add', self.region, self.slot_index, '命令'))
        else:
            menu.addAction("打开", lambda: self.parent_panel.execute_item(self.item_data))
            menu.addAction("重命名", lambda: self.parent_panel._set_pending('rename', self.region, self.slot_index))
            menu.addAction("打开原始路径", lambda: subprocess.Popen(['explorer', '/select,', os.path.normpath(self.item_data['path'])]))
            if self.item_data.get('removable', True):
                menu.addAction("从面板移除", lambda: self.parent_panel._set_pending('remove', self.region, self.slot_index))
        menu.aboutToHide.connect(self.parent_panel._schedule_operation)
        menu.exec_(QCursor.pos())

# ================================================
# 设置对话框（非模态）
# ================================================
class SettingsDialog(QDialog):
    settings_saved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setMinimumSize(420, 380)
        self.setStyleSheet(f"background: {COLORS['bg_page']}; border: 1px solid {COLORS['border']};")
        self._drag_pos = None

        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0)

        title = QFrame(); title.setFixedHeight(28)
        title.setStyleSheet(f"background: {COLORS['primary']}; color: white; border: none;")
        tl = QHBoxLayout(title); tl.setContentsMargins(6,0,6,0)
        tl.addWidget(QLabel("设置")); tl.addStretch()
        close_btn = QPushButton("✕"); close_btn.setFlat(True); close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet("color: white; border: none; font-size: 12px;"); tl.addWidget(close_btn)
        layout.addWidget(title)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        content = QFrame(); content.setStyleSheet(f"background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};")
        clayout = QVBoxLayout(content); clayout.setSpacing(10)

        clayout.addWidget(QLabel("快捷键:"))
        hk_layout = QHBoxLayout()
        self.hotkey_edit = QLineEdit(SETTINGS.get("hotkey", "Ctrl+Shift+A"))
        self.hotkey_edit.setReadOnly(True)
        self.record_btn = QPushButton("🔴 录制")
        self.record_btn.clicked.connect(self.start_recording)
        hk_layout.addWidget(self.hotkey_edit)
        hk_layout.addWidget(self.record_btn)
        clayout.addLayout(hk_layout)

        self.auto_start_cb = QCheckBox("开机自启动"); self.auto_start_cb.setChecked(SETTINGS.get("auto_start", False))
        clayout.addWidget(self.auto_start_cb)

        clayout.addWidget(QLabel("按钮大小:")); size_layout = QHBoxLayout()
        self.size_slider = QSlider(Qt.Horizontal); self.size_slider.setRange(48, 120); self.size_slider.setValue(SETTINGS.get("button_size", 72))
        self.size_label = QLabel(str(self.size_slider.value())); self.size_slider.valueChanged.connect(lambda v: self.size_label.setText(str(v)))
        size_layout.addWidget(self.size_slider); size_layout.addWidget(self.size_label); clayout.addLayout(size_layout)

        clayout.addWidget(QLabel("网格间距:")); gap_layout = QHBoxLayout()
        self.gap_slider = QSlider(Qt.Horizontal); self.gap_slider.setRange(0, 12); self.gap_slider.setValue(SETTINGS.get("grid_spacing", 4))
        self.gap_label = QLabel(str(self.gap_slider.value())); self.gap_slider.valueChanged.connect(lambda v: self.gap_label.setText(str(v)))
        gap_layout.addWidget(self.gap_slider); gap_layout.addWidget(self.gap_label); clayout.addLayout(gap_layout)

        restore_btn = QPushButton("恢复默认工具"); restore_btn.clicked.connect(self.restore_defaults); clayout.addWidget(restore_btn)

        btn_box = QHBoxLayout()
        save_btn = QPushButton("保存"); save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("取消"); cancel_btn.clicked.connect(self.close)
        btn_box.addWidget(save_btn); btn_box.addWidget(cancel_btn); clayout.addLayout(btn_box)

        scroll.setWidget(content); layout.addWidget(scroll)

    def start_recording(self):
        self.record_btn.setText("⏺ 按下组合键...")
        self.record_btn.setEnabled(False)
        self.setFocus()
        self.recording_keys = []
        self.recording = True

    def keyPressEvent(self, event):
        if hasattr(self, 'recording') and self.recording:
            key = event.key()
            modifiers = event.modifiers()
            parts = []
            if modifiers & Qt.ControlModifier: parts.append("Ctrl")
            if modifiers & Qt.AltModifier: parts.append("Alt")
            if modifiers & Qt.ShiftModifier: parts.append("Shift")
            if key not in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta):
                key_str = QKeySequence(key).toString()
                if key_str:
                    parts.append(key_str)
                    shortcut = "+".join(parts)
                    self.hotkey_edit.setText(shortcut)
                    self.recording = False
                    self.record_btn.setText("🔴 录制")
                    self.record_btn.setEnabled(True)
        else:
            super().keyPressEvent(event)

    def save_settings(self):
        SETTINGS["hotkey"] = self.hotkey_edit.text()
        SETTINGS["auto_start"] = self.auto_start_cb.isChecked()
        SETTINGS["button_size"] = self.size_slider.value()
        SETTINGS["grid_spacing"] = self.gap_slider.value()
        save_config()
        self.settings_saved.emit()
        self.close()

    def restore_defaults(self):
        global ALL_ITEMS, TOOLS_SLOTS
        for dt in DEFAULT_TOOLS:
            if dt not in ALL_ITEMS: ALL_ITEMS.append(dt)
        for i, dt in enumerate(DEFAULT_TOOLS):
            if i < 8: TOOLS_SLOTS[i] = dt
        save_config()
        if self.parent() and hasattr(self.parent(), 'refresh_all_slots'): self.parent().refresh_all_slots()
        QMessageBox.information(self, "提示", "默认工具已恢复。")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.pos().y() <= 28: self._drag_pos = event.globalPos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            delta = event.globalPos() - self._drag_pos; self.move(self.pos() + delta); self._drag_pos = event.globalPos()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None; super().mouseReleaseEvent(event)

    def closeEvent(self, event):
        self.hide()
        event.ignore()

# ================================================
# 主窗口（使用 Qt.Tool 避免 Popup 冲突）
# ================================================
class QuickPanel(QWidget):
    def __init__(self, toast, bridge):
        super().__init__()
        self.toast = toast; self.bridge = bridge
        self.is_locked = False; self.is_paused = False
        self.always_on_top = SETTINGS.get("always_on_top", True)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        if self.always_on_top: self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setMouseTracking(True)
        self.setStyleSheet(f"background: {COLORS['bg_page']}; border: 1px solid {COLORS['border']};")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(4,4,4,4)
        self.main_layout.setSpacing(SETTINGS.get("grid_spacing", 4))

        self.title_bar = QFrame(); self.title_bar.setFixedHeight(28)
        self.title_bar.setStyleSheet(f"background: {COLORS['primary']}; color: white; border: none;")
        title_layout = QHBoxLayout(self.title_bar); title_layout.setContentsMargins(6,0,6,0)
        lbl = QLabel("aHA Quick Panel"); lbl.setStyleSheet("color: white; font-weight: bold; font-size: 12px;")
        title_layout.addWidget(lbl); title_layout.addStretch()
        self.settings_btn = QPushButton("⚙️"); self.settings_btn.setFlat(True); self.settings_btn.setStyleSheet("color: white; border: none; font-size: 12px;")
        self.settings_btn.clicked.connect(self.open_settings); title_layout.addWidget(self.settings_btn)
        self.pin_btn = QPushButton("📌"); self.pin_btn.setCheckable(True); self.pin_btn.setChecked(self.always_on_top)
        self.pin_btn.setFlat(True); self.pin_btn.setStyleSheet("color: white; border: none; font-size: 12px;")
        self.pin_btn.clicked.connect(self.toggle_on_top); title_layout.addWidget(self.pin_btn)
        self.lock_btn = QPushButton("🔒"); self.lock_btn.setCheckable(True); self.lock_btn.setFlat(True)
        self.lock_btn.setStyleSheet("color: white; border: none; font-size: 12px;"); self.lock_btn.clicked.connect(self.toggle_lock)
        title_layout.addWidget(self.lock_btn)
        self.close_btn = QPushButton("✕"); self.close_btn.setFlat(True); self.close_btn.setStyleSheet("color: white; border: none; font-size: 12px;")
        self.close_btn.clicked.connect(self.hide); title_layout.addWidget(self.close_btn)
        self.main_layout.addWidget(self.title_bar)

        tools_label = QLabel("  工具"); tools_label.setStyleSheet(f"background: {COLORS['button_face']}; color: black; font-weight: bold; border: 1px solid {COLORS['border']}; padding: 2px;")
        self.main_layout.addWidget(tools_label)
        self.tools_grid = QGridLayout(); self.tools_grid.setSpacing(SETTINGS.get("grid_spacing", 4)); self.main_layout.addLayout(self.tools_grid)
        self.tool_buttons = []

        apps_label = QLabel("  小程序"); apps_label.setStyleSheet(f"background: {COLORS['button_face']}; color: black; font-weight: bold; border: 1px solid {COLORS['border']}; padding: 2px;")
        self.main_layout.addWidget(apps_label)
        self.apps_grid = QGridLayout(); self.apps_grid.setSpacing(SETTINGS.get("grid_spacing", 4)); self.main_layout.addLayout(self.apps_grid)
        self.app_buttons = []

        self._drag_source_button = None; self._drag_target_button = None; self._is_dragging = False; self._window_drag_pos = None
        self.settings_dialog = None
        self._pending_op = None

        # 用于控制失焦隐藏
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._delayed_hide)

        self.build_grid()

    def button_size(self): return SETTINGS.get("button_size", 72)

    def build_grid(self):
        for i in reversed(range(self.tools_grid.count())):
            w = self.tools_grid.itemAt(i).widget()
            if w: w.deleteLater()
        self.tool_buttons.clear()
        for i in range(8):
            btn = SlotButton(i, 'tools', self)
            self.tools_grid.addWidget(btn, i // 4, i % 4)
            self.tool_buttons.append(btn)

        for i in reversed(range(self.apps_grid.count())):
            w = self.apps_grid.itemAt(i).widget()
            if w: w.deleteLater()
        self.app_buttons.clear()
        for i in range(16):
            btn = SlotButton(i, 'apps', self)
            self.apps_grid.addWidget(btn, i // 4, i % 4)
            self.app_buttons.append(btn)

    def refresh_all_slots(self):
        new_size = SETTINGS.get("button_size", 72); new_spacing = SETTINGS.get("grid_spacing", 4)
        for btn in self.tool_buttons + self.app_buttons:
            btn.setFixedSize(new_size, new_size); btn.update_slot_data()
        self.tools_grid.setSpacing(new_spacing); self.apps_grid.setSpacing(new_spacing)
        self.adjustSize()

    def _get_button(self, region, index):
        if region == 'tools' and 0 <= index < len(self.tool_buttons):
            return self.tool_buttons[index]
        elif region == 'apps' and 0 <= index < len(self.app_buttons):
            return self.app_buttons[index]
        return None

    # ---------- 待处理操作与安全延迟执行 ----------
    def _set_pending(self, op_type, region, index, item_type=None):
        self._pending_op = (op_type, region, index, item_type)

    def _schedule_operation(self):
        if self._pending_op:
            QTimer.singleShot(0, self._execute_pending)

    def _execute_pending(self):
        if not self._pending_op: return
        op_type, region, index, item_type = self._pending_op
        self._pending_op = None
        if op_type == 'add':
            self._do_add_item(region, index, item_type)
        elif op_type == 'remove':
            self._do_remove_item(region, index)
        elif op_type == 'rename':
            self._do_rename_item(region, index)

    def _do_add_item(self, region, index, item_type):
        if item_type == '程序':
            file_path, _ = QFileDialog.getOpenFileName(self, "选择程序", "", "所有文件 (*.*)")
            if not file_path: return
            name = os.path.splitext(os.path.basename(file_path))[0]; path = file_path; typ = '程序'
        elif item_type == '文件夹':
            folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
            if not folder: return
            name = os.path.basename(folder); path = folder; typ = '文件夹'
        elif item_type == '网页':
            url, ok = QInputDialog.getText(self, "添加网址", "请输入网址（含http/https）:")
            if not ok or not url.strip(): return
            url = url.strip()
            if not url.startswith(('http://', 'https://')): url = 'https://' + url
            name = url.split('//')[-1][:10]; path = url; typ = '网页'
        elif item_type == '命令':
            cmd, ok = QInputDialog.getText(self, "添加命令", "请输入命令或程序路径（如 cmd /c dir）:")
            if not ok or not cmd.strip(): return
            path = cmd.strip(); name = path.split()[0] if ' ' in path else path; typ = '命令'
        else: return

        new_item = {"name": name, "path": path, "type": typ, "description": "", "icon_path": "", "display_name": name, "removable": True}
        if new_item not in ALL_ITEMS: ALL_ITEMS.append(new_item)
        if region == 'tools': TOOLS_SLOTS[index] = new_item
        else: APPS_SLOTS[index] = new_item
        save_config()
        btn = self._get_button(region, index)
        if btn: btn.update_slot_data()

    def _do_remove_item(self, region, index):
        if region == 'tools': TOOLS_SLOTS[index] = None
        else: APPS_SLOTS[index] = None
        save_config()
        btn = self._get_button(region, index)
        if btn: btn.update_slot_data()

    def _do_rename_item(self, region, index):
        btn = self._get_button(region, index)
        if not btn or btn.is_placeholder: return
        new_name, ok = QInputDialog.getText(self, "重命名", "请输入显示名称:", text=btn.item_data.get('display_name', btn.item_data['name']))
        if ok and new_name.strip():
            btn.item_data['display_name'] = new_name.strip()
            save_config()
            btn.update_slot_data()

    # ---------- 窗口自动隐藏（失焦时延迟关闭） ----------
    def focusOutEvent(self, event):
        # 如果子控件获得焦点则不隐藏
        if self.isAncestorOf(QApplication.focusWidget()):
            super().focusOutEvent(event)
            return
        self._hide_timer.start(150)  # 150ms后隐藏，避免菜单、对话框关闭时误关
        super().focusOutEvent(event)

    def showEvent(self, event):
        self._hide_timer.stop()
        super().showEvent(event)

    def _delayed_hide(self):
        if not self.isActiveWindow():
            self.hide()

    # ---------- 其余方法 ----------
    def open_settings(self):
        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(self)
            self.settings_dialog.settings_saved.connect(self.on_settings_saved)
        self.settings_dialog.show()

    def on_settings_saved(self):
        self.refresh_all_slots()
        restart_hotkey_listener(self)
        try:
            import winshell
            startup = winshell.startup()
            shortcut = os.path.join(startup, "aHA_QuickPanel.lnk")
            if SETTINGS.get("auto_start", False):
                target = sys.argv[0]
                with winshell.shortcut(shortcut) as s: s.path = target; s.description = "aHA Quick Panel"
            else:
                if os.path.exists(shortcut): os.remove(shortcut)
        except: pass

    def toggle_on_top(self):
        self.always_on_top = not self.always_on_top
        SETTINGS["always_on_top"] = self.always_on_top
        save_config()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.always_on_top)
        self.hide(); self.show()
        self.pin_btn.setChecked(self.always_on_top)
        self.pin_btn.setText("📌" if self.always_on_top else "📍")

    def _on_button_drag_start(self, button): self._drag_source_button = button; self._is_dragging = True
    def _on_button_drag_end(self):
        if self._is_dragging and self._drag_target_button:
            self.swap_slots(self._drag_source_button.region, self._drag_source_button.slot_index,
                            self._drag_target_button.region, self._drag_target_button.slot_index)
        if self._drag_target_button:
            self._drag_target_button.setStyleSheet(self._drag_target_button._normal_style() if not self._drag_target_button.is_placeholder else "background: transparent; border: none;")
        self._drag_source_button = None; self._drag_target_button = None; self._is_dragging = False

    def mouseMoveEvent(self, event):
        if self._window_drag_pos is not None and event.buttons() & Qt.LeftButton:
            delta = event.globalPos() - self._window_drag_pos; self.move(self.pos() + delta); self._window_drag_pos = event.globalPos(); return
        if self._is_dragging and self._drag_source_button is not None:
            if self._drag_target_button:
                self._drag_target_button.setStyleSheet(self._drag_target_button._normal_style() if not self._drag_target_button.is_placeholder else "background: transparent; border: none;")
            target = self._button_at(event.pos())
            if target and target != self._drag_source_button:
                self._drag_target_button = target; self._drag_target_button.setStyleSheet(f"background: {COLORS['drag_highlight_bg']};")
            else: self._drag_target_button = None
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.title_bar.geometry().contains(event.pos()): self._window_drag_pos = event.globalPos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._window_drag_pos = None; super().mouseReleaseEvent(event)

    def _button_at(self, pos):
        for btn in self.tool_buttons + self.app_buttons:
            if btn.geometry().contains(pos): return btn
        return None

    def swap_slots(self, src_region, src_index, tgt_region, tgt_index):
        src_list = TOOLS_SLOTS if src_region == 'tools' else APPS_SLOTS
        tgt_list = TOOLS_SLOTS if tgt_region == 'tools' else APPS_SLOTS
        src_list[src_index], tgt_list[tgt_index] = tgt_list[tgt_index], src_list[src_index]
        save_config()
        src_btn = self._get_button(src_region, src_index)
        if src_btn: src_btn.update_slot_data()
        tgt_btn = self._get_button(tgt_region, tgt_index)
        if tgt_btn: tgt_btn.update_slot_data()

    def execute_item(self, item):
        if not item or not item.get('path'):
            QMessageBox.warning(self, "错误", "项目路径无效")
            return
        try:
            typ = item.get('type', '程序')
            if typ == '网页': webbrowser.open(item['path'])
            elif typ == '命令':
                if item['path'].startswith('ms-screenclip:'): subprocess.Popen('explorer ms-screenclip:', shell=True)
                else: subprocess.Popen(item['path'], shell=True)
            else: os.startfile(item['path'])
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法打开项目: {e}")

    def toggle_lock(self):
        self.is_locked = self.lock_btn.isChecked()
        self.lock_btn.setText("🔓" if self.is_locked else "🔒")

    def show_at_mouse(self, pos=None):
        if self.is_paused: return
        if pos is None: pos = QCursor.pos()
        self.adjustSize()
        screen = QApplication.primaryScreen().availableGeometry()
        w, h = self.width(), self.height()
        x = pos.x() + 20; y = pos.y() + 20
        if x + w > screen.right() - 20: x = screen.right() - 20 - w
        if y + h > screen.bottom() - 20: y = screen.bottom() - 20 - h
        if x < screen.left() + 20: x = screen.left() + 20
        if y < screen.top() + 20: y = screen.top() + 20
        self.move(x, y); self.show(); self.activateWindow()

# ================================================
# 托盘图标与全局热键管理
# ================================================
tray_icon = None
current_listener = None

def create_tray_image(color="#5C7A5C"):
    img = Image.new('RGBA', (64, 64), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    lightning = [(28,4), (20,28), (32,28), (24,56), (44,26), (32,26), (38,4)]
    draw.polygon(lightning, fill=color)
    return img

def convert_hotkey_to_pynput(hotkey_str):
    parts = hotkey_str.split('+')
    converted = []
    for p in parts:
        p = p.strip()
        if p.lower() in ('ctrl', 'control'): converted.append('<ctrl>')
        elif p.lower() == 'alt': converted.append('<alt>')
        elif p.lower() == 'shift': converted.append('<shift>')
        else: converted.append(p.lower())
    return '+'.join(converted)

def start_hotkey_listener(panel):
    global current_listener
    if current_listener:
        current_listener.stop()
    hotkey_str = SETTINGS.get("hotkey", "Ctrl+Shift+A")
    pynput_hotkey = convert_hotkey_to_pynput(hotkey_str)
    try:
        current_listener = keyboard.GlobalHotKeys({pynput_hotkey: lambda: panel.bridge.show_panel.emit()})
        threading.Thread(target=current_listener.run, daemon=True).start()
    except Exception as e:
        print(f"热键注册失败: {e}")

def restart_hotkey_listener(panel):
    start_hotkey_listener(panel)

def setup_tray(app, panel, toast, shared_mem):
    global tray_icon
    def show_panel(icon, item):
        panel.show_at_mouse()
    def quit_app(icon, item):
        if current_listener: current_listener.stop()
        panel.hide()
        tray_icon.stop()
        shared_mem.detach()
        toast.show_message("aHA Quick Panel 已退出", COLORS['toast_orange'])
        QTimer.singleShot(0, app.quit)
    def toggle_pause(icon, item):
        panel.is_paused = not panel.is_paused
        if panel.is_paused:
            tray_icon.icon = create_tray_image("#808080")
            panel.bridge.show_toast.emit("aHA Quick Panel 已暂停", COLORS['toast_gray'])
        else:
            tray_icon.icon = create_tray_image("#5C7A5C")
            panel.bridge.show_toast.emit("aHA Quick Panel 已恢复", COLORS['toast_green'])

    image = create_tray_image("#5C7A5C")
    menu = (
        TrayMenuItem('显示面板', show_panel),
        TrayMenuItem('暂停/恢复', toggle_pause),
        TrayMenuItem('退出', quit_app),
    )
    tray_icon = TrayIcon("aHA Quick Panel", image, "aHA Quick Panel", menu)
    tray_icon.on_double_click = toggle_pause
    threading.Thread(target=tray_icon.run, daemon=True).start()

if __name__ == "__main__":
    shared_memory = QSharedMemory("aHA_QuickPanel_Instance")
    if not shared_memory.create(1):
        app = QApplication(sys.argv)
        toast = ToastWidget()
        toast.show_message("aHA Quick Panel 已打开，请勿重复启动", COLORS['toast_orange'])
        sys.exit(app.exec_())

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon())
    toast = ToastWidget()
    bridge = HotkeyBridge()
    panel = QuickPanel(toast, bridge)

    bridge.show_toast.connect(lambda msg, color: toast.show_message(msg, color))
    bridge.show_panel.connect(lambda: panel.show_at_mouse())

    start_hotkey_listener(panel)

    def cleanup():
        if current_listener: current_listener.stop()
        if shared_memory.isAttached(): shared_memory.detach()
    atexit.register(cleanup)

    setup_tray(app, panel, toast, shared_memory)
    toast.show_message("aHA Quick Panel 已启动 😊", COLORS['toast_green'])
    panel.show_at_mouse()
    sys.exit(app.exec_())