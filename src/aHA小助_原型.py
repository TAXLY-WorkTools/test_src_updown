import sys, os, threading, subprocess, webbrowser, tempfile, json, shutil
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout,
    QSystemTrayIcon, QMenu, QAction, QMessageBox, QLabel,
    QListWidget, QStackedWidget, QCheckBox, QLineEdit,
    QFrame, QFileDialog, QSlider, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QPlainTextEdit, QDialog, QDialogButtonBox,
    QToolTip, QSizePolicy, QInputDialog, QSizeGrip, QToolButton
)
from PyQt5.QtCore import (
    Qt, QPoint, pyqtSignal, QObject, QTimer, QMimeData, QSize, QUrl, QRect
)
from PyQt5.QtGui import (
    QFont, QIcon, QCursor, QColor, QDrag, QPixmap, QPainter, QKeyEvent
)
from pynput import keyboard, mouse
from pystray import MenuItem as TrayMenuItem, Icon as TrayIcon
from PIL import Image, ImageDraw

# ================================================
# 配色方案
# ================================================
COLORS = {
    'bg_page': '#F2F4F8',
    'bg_card': '#FFFFFF',
    'bg_hover': '#E8EDF5',
    'primary': '#0052D9',
    'primary_hover': '#003D99',
    'primary_light': '#E0E9FF',
    'text_main': '#1A2634',
    'text_secondary': '#5A6878',
    'text_disabled': '#A8B5C5',
    'border': '#D6DEE8',
    'white_soft': '#F8FAFC',
    'panel_tool_bg': '#F4F6F9',
    'panel_app_bg': '#FFFFFF',
}

# ================================================
# 数据与设置
# ================================================
DATA_DIR = os.path.join(os.path.expanduser("~"), "Documents", "aHA小助")
os.makedirs(DATA_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(DATA_DIR, "aha_config.json")

DEFAULT_TOOLS = [
    {"name": "计算器", "path": "calc.exe", "type": "程序", "description": "Windows 计算器",
     "time": datetime.now().strftime("%Y/%m/%d"), "is_self_made": False, "removable": False,
     "icon_path": "", "display_name": "计算器"},
    {"name": "记事本", "path": "notepad.exe", "type": "程序", "description": "Windows 记事本",
     "time": datetime.now().strftime("%Y/%m/%d"), "is_self_made": False, "removable": False,
     "icon_path": "", "display_name": "记事本"},
]

ALL_ITEMS = []
PANEL_ITEMS = []
RECYCLE_BIN = []
DRAFTS = []
DRAFT_RECYCLE_BIN = []

SETTINGS = {
    "auto_start": False,
    "show_startup_tip": True,
    "hotkeys": {"panel_show_1": "Ctrl+Shift+A", "panel_show_2": "", "search": ""},
    "paths": {"new_program_save": os.path.expanduser("~/Documents/aHA小助/新建程序"),
              "import_save": os.path.expanduser("~/Documents/aHA小助/导入程序")},
    "appearance": {"allow_custom_size": False, "button_size": 50, "button_gap": 8,
                   "button_radius": 8, "auto_shrink_text": True, "hover_enlarge": True},
    "hover_delay": 1000,
    "delete_countdown": 3
}

def save_data():
    data = {
        "settings": SETTINGS, "all_items": ALL_ITEMS,
        "panel_items": [item['name'] for item in PANEL_ITEMS],
        "recycle_bin": [{"item": e["item"], "delete_time": e["delete_time"].strftime("%Y-%m-%d %H:%M:%S"),
                         "expire_time": e["expire_time"].strftime("%Y-%m-%d %H:%M:%S")} for e in RECYCLE_BIN],
        "drafts": [{"name": d["name"], "path": d["path"], "content": d["content"],
                    "time": d["time"], "description": d["description"]} for d in DRAFTS],
        "draft_recycle_bin": [{"item": {"name": e["item"]["name"], "path": e["item"]["path"],
                                        "content": e["item"]["content"], "time": e["item"]["time"],
                                        "description": e["item"]["description"]},
                               "delete_time": e["delete_time"].strftime("%Y-%m-%d %H:%M:%S"),
                               "expire_time": e["expire_time"].strftime("%Y-%m-%d %H:%M:%S")} for e in DRAFT_RECYCLE_BIN]
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_data():
    global ALL_ITEMS, PANEL_ITEMS, RECYCLE_BIN, DRAFTS, DRAFT_RECYCLE_BIN, SETTINGS
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "settings" in data: SETTINGS.update(data["settings"])
        if "all_items" in data:
            ALL_ITEMS = data["all_items"]
            default_names = {t['name'] for t in DEFAULT_TOOLS}
            for dt in DEFAULT_TOOLS:
                if dt['name'] not in {t['name'] for t in ALL_ITEMS}:
                    ALL_ITEMS.append(dt)
        else: ALL_ITEMS = DEFAULT_TOOLS.copy()
        panel_names = data.get("panel_items", [])
        PANEL_ITEMS = [item for name in panel_names for item in ALL_ITEMS if item['name'] == name]
        if "recycle_bin" in data:
            RECYCLE_BIN = [{"item": e["item"], "delete_time": datetime.strptime(e["delete_time"], "%Y-%m-%d %H:%M:%S"),
                            "expire_time": datetime.strptime(e["expire_time"], "%Y-%m-%d %H:%M:%S")} for e in data["recycle_bin"]]
        if "drafts" in data: DRAFTS = data["drafts"]
        if "draft_recycle_bin" in data:
            DRAFT_RECYCLE_BIN = [{"item": e["item"], "delete_time": datetime.strptime(e["delete_time"], "%Y-%m-%d %H:%M:%S"),
                                  "expire_time": datetime.strptime(e["expire_time"], "%Y-%m-%d %H:%M:%S")} for e in data["draft_recycle_bin"]]
    except:
        ALL_ITEMS = DEFAULT_TOOLS.copy(); PANEL_ITEMS = DEFAULT_TOOLS.copy()
        RECYCLE_BIN.clear(); DRAFTS.clear(); DRAFT_RECYCLE_BIN.clear()

load_data()

# ------------------------------------------------
# 信号通信器
# ------------------------------------------------
class Communicator(QObject):
    show_panel_signal = pyqtSignal(bool)
    show_startup_toast = pyqtSignal(str, str)
    toggle_pause_signal = pyqtSignal()
    show_settings_signal = pyqtSignal()
    quit_app_signal = pyqtSignal()
    data_updated = pyqtSignal()
    open_tools_config = pyqtSignal()
    open_editor_with_file = pyqtSignal(str)
    appearance_changed = pyqtSignal()

# ------------------------------------------------
# Toast 提示
# ------------------------------------------------
class ToastWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.label_layout = QVBoxLayout(); self.label_layout.setAlignment(Qt.AlignCenter); self.setLayout(self.label_layout)
        self.timer = QTimer(self); self.timer.timeout.connect(self.hide)

    def show_message(self, text, bg_color="green"):
        self.setStyleSheet(f"background: {bg_color}; border-radius: 8px; padding: 8px 16px;")
        while self.label_layout.count():
            child = self.label_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        lbl = QLabel(text); lbl.setAlignment(Qt.AlignCenter); lbl.setStyleSheet("color: white; font-size: 14px;")
        self.label_layout.addWidget(lbl)
        self.adjustSize()
        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2, screen.height() - 100)
        self.show(); self.timer.start(1000)

# ================================================
# 外观编辑对话框
# ================================================
class AppearanceDialog(QDialog):
    def __init__(self, item=None, parent=None):
        super().__init__(parent)
        self.item = item
        self.selected_icon_path = item.get('icon_path', '') if item else ''
        self.setWindowTitle("自定义外观"); self.setMinimumWidth(420)
        self.setStyleSheet(f"background: {COLORS['bg_card']};")
        main_layout = QHBoxLayout(self); left_layout = QVBoxLayout(); right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("图标:"))
        self.icon_label = QLabel(); self.icon_label.setFixedSize(64, 64)
        self.icon_label.setStyleSheet(f"border: 1px solid {COLORS['border']}; background: {COLORS['bg_page']};")
        self.icon_btn = QPushButton("选择图标..."); self.icon_btn.clicked.connect(self.choose_icon)
        right_layout.addWidget(self.icon_label); right_layout.addWidget(self.icon_btn)
        right_layout.addWidget(QLabel("标题:"))
        self.title_edit = QLineEdit(); self.title_edit.setPlaceholderText("显示名称")
        right_layout.addWidget(self.title_edit)
        right_layout.addWidget(QLabel("用途说明:"))
        self.desc_edit = QLineEdit(); self.desc_edit.setPlaceholderText("鼠标悬浮提示")
        right_layout.addWidget(self.desc_edit)

        if item:
            self.title_edit.setText(item.get('display_name', item['name']))
            self.desc_edit.setText(item.get('description', ''))
            if item.get('icon_path'):
                pixmap = QPixmap(item['icon_path'])
                if not pixmap.isNull(): self.icon_label.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存"); save_btn.setStyleSheet(f"background: {COLORS['primary']}; color: white; padding: 6px 16px; border-radius: 4px;")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消"); cancel_btn.setStyleSheet(f"background: {COLORS['bg_hover']}; padding: 6px 16px; border-radius: 4px;")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn); btn_layout.addWidget(cancel_btn)
        left_layout.addLayout(btn_layout)
        main_layout.addLayout(left_layout); main_layout.addLayout(right_layout)

    def choose_icon(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择图标", "", "图片文件 (*.png *.jpg *.jpeg *.ico)")
        if file_path:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                self.icon_label.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.selected_icon_path = file_path

    def get_result(self):
        return {'icon_path': self.selected_icon_path, 'display_name': self.title_edit.text().strip(),
                'description': self.desc_edit.text().strip()}

# ================================================
# 面板按钮（QToolButton 风格，图标上文字下，单击菜单，双击启动）
# ================================================
class PanelButton(QToolButton):
    def __init__(self, text, item_data, parent_panel):
        super().__init__()
        self.item_data = item_data
        self.parent_panel = parent_panel
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setIconSize(QSize(32, 32))
        self.setText(text if text else "＋")
        self.setPopupMode(QToolButton.InstantPopup)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self._refresh_icon()
        self.clicked.connect(self.on_click)

    def _refresh_icon(self):
        if self.item_data and self.item_data.get('icon_path'):
            pixmap = QPixmap(self.item_data['icon_path'])
            if not pixmap.isNull():
                self.setIcon(QIcon(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
                return
        if self.item_data:
            typ = self.item_data.get('type', '程序')
            icon_map = {'程序': '🖥️', '文件夹': '📁', '网页': '🌐'}
            self.setIcon(self._text_icon(icon_map.get(typ, '📄')))
        else:
            self.setIcon(self._text_icon('＋'))

    def _text_icon(self, char):
        pixmap = QPixmap(32, 32); pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap); painter.setPen(QColor(COLORS['primary']))
        painter.setFont(QFont("Segoe UI", 18)); painter.drawText(pixmap.rect(), Qt.AlignCenter, char); painter.end()
        return QIcon(pixmap)

    def on_click(self, checked=None):
        # 单击弹出菜单
        self.show_menu()

    def mouseDoubleClickEvent(self, event):
        # 双击启动程序（只对已配置按钮有效）
        if self.item_data:
            self.parent_panel.execute_item(self.item_data)
        else:
            # 空白按钮双击不做操作或弹出新建菜单（此处不做操作）
            pass
        super().mouseDoubleClickEvent(event)

    def show_menu(self):
        if self.parent_panel.is_locked: return
        menu = QMenu(self)
        if self.item_data:
            menu.addAction("修改程序", lambda: self.parent_panel.app.comm.open_editor_with_file.emit(self.item_data['path']))
            menu.addAction("另存为", lambda: self.parent_panel._save_as(self.item_data))
            menu.addAction("打开原始路径", lambda: subprocess.Popen(['explorer', '/select,', os.path.normpath(self.item_data['path'])]))
            if self.item_data.get('removable', True): menu.addAction("从面板移除", lambda: self.parent_panel._remove_from_panel(self.item_data))
            menu.addAction("自定义外观", lambda: self.parent_panel.customize_appearance(self.item_data))
        else:
            menu.addAction("新建", lambda: self.parent_panel.app.comm.open_tools_config.emit())
            menu.addAction("配置按键", lambda: self.parent_panel.app.comm.open_tools_config.emit())
            menu.addAction("自定义导入程序", lambda: self.parent_panel._import_file())
            menu.addAction("自定义文件夹路径", lambda: self.parent_panel._add_folder())
            menu.addAction("自定义网址", lambda: self.parent_panel._add_url())
        menu.exec_(self.mapToGlobal(QPoint(0, self.height())))

# ================================================
# 面板 B（全新视觉）
# ================================================
class PanelWidget(QWidget):
    def __init__(self, app_controller):
        super().__init__()
        self.app = app_controller
        self.is_locked = False
        self.is_pinned = True
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(f"background: {COLORS['bg_card']}; border-radius: 12px;")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(6)

        # 标题栏
        title_bar = QFrame()
        title_bar.setFixedHeight(32)
        title_bar.setStyleSheet("background: transparent;")
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(8, 0, 8, 0)
        self.title_label = QLabel("aHA小助")
        self.title_label.setStyleSheet(f"color: {COLORS['text_main']}; font-size: 14px; font-weight: bold;")
        self.pin_btn = QPushButton("📌")
        self.pin_btn.setCheckable(True); self.pin_btn.setChecked(self.is_pinned); self.pin_btn.setFixedSize(24, 24)
        self.pin_btn.clicked.connect(self.toggle_pin)
        self.close_btn = QPushButton("✕"); self.close_btn.setFixedSize(24, 24); self.close_btn.clicked.connect(self.hide)
        for btn in (self.pin_btn, self.close_btn):
            btn.setStyleSheet("QPushButton { border: none; color: #5A6878; } QPushButton:hover { background: #E8EDF5; border-radius: 4px; }")
        tb_layout.addWidget(self.title_label); tb_layout.addStretch()
        tb_layout.addWidget(self.pin_btn); tb_layout.addWidget(self.close_btn)
        self.main_layout.addWidget(title_bar)

        # 工具区
        self.tools_section = QFrame()
        self.tools_section.setStyleSheet(f"background: {COLORS['panel_tool_bg']}; border-radius: 8px;")
        tools_layout = QVBoxLayout(self.tools_section); tools_layout.setContentsMargins(8, 8, 8, 8); tools_layout.setSpacing(4)
        tools_header = QHBoxLayout()
        tools_label = QLabel("工具"); tools_label.setStyleSheet(f"color: {COLORS['text_main']}; font-weight: bold; font-size: 13px;")
        tools_desc = QLabel("#日常工具"); tools_desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        self.tools_prev_btn = QPushButton("←"); self.tools_next_btn = QPushButton("→"); self.tools_page_label = QLabel("1/1")
        for btn in (self.tools_prev_btn, self.tools_next_btn): btn.setFixedWidth(24); btn.setStyleSheet(f"border: none; color: {COLORS['primary']};")
        self.tools_page_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        self.tools_prev_btn.clicked.connect(self.prev_tools_page); self.tools_next_btn.clicked.connect(self.next_tools_page)
        tools_header.addWidget(tools_label); tools_header.addWidget(tools_desc); tools_header.addStretch()
        tools_header.addWidget(self.tools_prev_btn); tools_header.addWidget(self.tools_page_label); tools_header.addWidget(self.tools_next_btn)
        tools_layout.addLayout(tools_header)
        self.tools_pages = QStackedWidget(); tools_layout.addWidget(self.tools_pages)
        self.main_layout.addWidget(self.tools_section)

        # 小程序区
        self.apps_section = QFrame()
        self.apps_section.setStyleSheet(f"background: {COLORS['panel_app_bg']}; border-radius: 8px;")
        apps_layout = QVBoxLayout(self.apps_section); apps_layout.setContentsMargins(8, 8, 8, 8); apps_layout.setSpacing(4)
        apps_header = QHBoxLayout()
        apps_label = QLabel("小程序"); apps_label.setStyleSheet(f"color: {COLORS['text_main']}; font-weight: bold; font-size: 13px;")
        apps_desc = QLabel("#自制或来自分享"); apps_desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        self.lock_btn = QPushButton("🔒"); self.lock_btn.setCheckable(True); self.lock_btn.setFixedSize(24, 24); self.lock_btn.clicked.connect(self.toggle_lock)
        self.config_btn = QPushButton("⚙️"); self.config_btn.setFixedSize(24, 24); self.config_btn.clicked.connect(self.open_tools_config)
        self.apps_prev_btn = QPushButton("←"); self.apps_next_btn = QPushButton("→"); self.apps_page_label = QLabel("1/1")
        for btn in (self.apps_prev_btn, self.apps_next_btn, self.lock_btn, self.config_btn): btn.setStyleSheet(f"border: none; color: {COLORS['primary']};")
        self.apps_page_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        self.apps_prev_btn.clicked.connect(self.prev_apps_page); self.apps_next_btn.clicked.connect(self.next_apps_page)
        apps_header.addWidget(apps_label); apps_header.addWidget(apps_desc); apps_header.addStretch()
        apps_header.addWidget(self.lock_btn); apps_header.addWidget(self.config_btn)
        apps_header.addWidget(self.apps_prev_btn); apps_header.addWidget(self.apps_page_label); apps_header.addWidget(self.apps_next_btn)
        apps_layout.addLayout(apps_header)
        self.apps_pages = QStackedWidget(); apps_layout.addWidget(self.apps_pages)
        self.main_layout.addWidget(self.apps_section)

        self.current_tools_page = 0; self.current_apps_page = 0
        self.app.comm.appearance_changed.connect(self.update_appearance)
        self.drag_pos = None
        self.refresh_buttons()

    def toggle_pin(self):
        self.is_pinned = not self.is_pinned
        self.pin_btn.setChecked(self.is_pinned)
        flags = Qt.Popup | Qt.FramelessWindowHint
        if self.is_pinned: flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags); self.hide(); self.show()

    def toggle_lock(self):
        self.is_locked = self.lock_btn.isChecked()
        self.lock_btn.setText("🔓" if self.is_locked else "🔒")

    def open_tools_config(self):
        self.app.comm.open_tools_config.emit(); self.hide()

    def show_centered(self):
        self.refresh_buttons()
        screen = QApplication.primaryScreen().availableGeometry()
        self.adjustSize()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y); self.show(); self.activateWindow()

    def show_at_mouse(self, pos=None):
        if pos is None: pos = QCursor.pos()
        self.refresh_buttons()
        self.adjustSize()
        screen = QApplication.primaryScreen().availableGeometry()
        w, h = self.width(), self.height()
        x = pos.x() + 20
        y = pos.y() + 20
        if x + w > screen.right() - 20: x = screen.right() - 20 - w
        if y + h > screen.bottom() - 20: y = screen.bottom() - 20 - h
        if x < screen.left() + 20: x = screen.left() + 20
        if y < screen.top() + 20: y = screen.top() + 20
        self.move(x, y); self.show(); self.activateWindow()

    def update_appearance(self): self.refresh_buttons()

    def get_tools_list(self):
        return [item for item in PANEL_ITEMS if not item.get('removable', True)]

    def get_apps_list(self):
        return [item for item in PANEL_ITEMS if item.get('removable', True)]

    def prev_tools_page(self):
        if self.current_tools_page > 0: self.current_tools_page -= 1; self.refresh_buttons()

    def next_tools_page(self):
        tools = self.get_tools_list()
        max_page = max(0, (len(tools) - 1) // 8)
        if self.current_tools_page < max_page: self.current_tools_page += 1; self.refresh_buttons()

    def prev_apps_page(self):
        if self.current_apps_page > 0: self.current_apps_page -= 1; self.refresh_buttons()

    def next_apps_page(self):
        apps = self.get_apps_list()
        max_page = max(0, (len(apps) - 1) // 16)
        if self.current_apps_page < max_page: self.current_apps_page += 1; self.refresh_buttons()

    def refresh_buttons(self):
        self._clear_pages()
        tools = self.get_tools_list()
        apps = self.get_apps_list()
        size = SETTINGS['appearance']['button_size']
        gap = SETTINGS['appearance']['button_gap']

        tools_per_page = 8
        total_tools_pages = max(1, (len(tools) + tools_per_page - 1) // tools_per_page)
        for page in range(total_tools_pages):
            page_widget = QWidget()
            grid = QGridLayout(); grid.setSpacing(gap)
            start = page * tools_per_page
            page_items = tools[start:start + tools_per_page]
            for i in range(tools_per_page):
                row, col = i // 4, i % 4
                if i < len(page_items):
                    btn = PanelButton(page_items[i].get('display_name', page_items[i]['name']), page_items[i], self)
                    btn.setStyleSheet(self.button_style())
                    grid.addWidget(btn, row, col)
                else:
                    placeholder = PanelButton("＋", None, self)
                    placeholder.setStyleSheet(f"color: {COLORS['text_disabled']}; font-size: 24px; background: transparent;")
                    placeholder.setFixedSize(size, size + 20)
                    grid.addWidget(placeholder, row, col)
            page_widget.setLayout(grid)
            self.tools_pages.addWidget(page_widget)

        if self.current_tools_page >= total_tools_pages: self.current_tools_page = total_tools_pages - 1
        self.tools_pages.setCurrentIndex(self.current_tools_page)
        self.tools_page_label.setText(f"{self.current_tools_page+1}/{total_tools_pages}")
        self.tools_prev_btn.setEnabled(self.current_tools_page > 0)
        self.tools_next_btn.setEnabled(self.current_tools_page < total_tools_pages - 1)

        apps_per_page = 16
        total_apps_pages = max(1, (len(apps) + apps_per_page - 1) // apps_per_page)
        for page in range(total_apps_pages):
            page_widget = QWidget()
            grid = QGridLayout(); grid.setSpacing(gap)
            start = page * apps_per_page
            page_items = apps[start:start + apps_per_page]
            for i in range(apps_per_page):
                row, col = i // 4, i % 4
                if i < len(page_items):
                    btn = PanelButton(page_items[i].get('display_name', page_items[i]['name']), page_items[i], self)
                    btn.setStyleSheet(self.button_style())
                    grid.addWidget(btn, row, col)
                else:
                    placeholder = PanelButton("＋", None, self)
                    placeholder.setStyleSheet(f"color: {COLORS['text_disabled']}; font-size: 24px; background: transparent;")
                    placeholder.setFixedSize(size, size + 20)
                    grid.addWidget(placeholder, row, col)
            page_widget.setLayout(grid)
            self.apps_pages.addWidget(page_widget)

        if self.current_apps_page >= total_apps_pages: self.current_apps_page = total_apps_pages - 1
        self.apps_pages.setCurrentIndex(self.current_apps_page)
        self.apps_page_label.setText(f"{self.current_apps_page+1}/{total_apps_pages}")
        self.apps_prev_btn.setEnabled(self.current_apps_page > 0)
        self.apps_next_btn.setEnabled(self.current_apps_page < total_apps_pages - 1)

        self.adjustSize()

    def _clear_pages(self):
        for pages in (self.tools_pages, self.apps_pages):
            while pages.count():
                widget = pages.widget(0); pages.removeWidget(widget); widget.deleteLater()

    def button_style(self):
        size = SETTINGS['appearance']['button_size']
        return f"""
            QToolButton {{
                background: transparent; color: {COLORS['text_main']};
                min-width: {size}px; min-height: {size+20}px; max-width: {size}px; max-height: {size+20}px;
                font-size: 11px; border: none;
            }}
            QToolButton:hover {{
                background: {COLORS['bg_hover']}; border-radius: {SETTINGS['appearance']['button_radius']}px;
            }}
        """

    def execute_item(self, item):
        if item['type'] == '网页': webbrowser.open(item['path'])
        else: os.startfile(item['path'])

    def _save_as(self, data):
        file_path, _ = QFileDialog.getSaveFileName(self, "另存为", data.get('name',''), "所有文件 (*.*)")
        if file_path:
            try:
                shutil.copy2(data['path'], file_path); QMessageBox.information(self, "完成", f"已保存副本至 {file_path}")
            except Exception as e: QMessageBox.warning(self, "错误", str(e))

    def _remove_from_panel(self, data):
        if data in PANEL_ITEMS: PANEL_ITEMS.remove(data); save_data(); self.refresh_buttons()

    def _import_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择程序", "", "所有文件 (*.*)")
        if file_path:
            name = os.path.splitext(os.path.basename(file_path))[0]
            new_item = {"name": name, "path": file_path, "type": "程序", "description": "",
                        "time": datetime.now().strftime("%Y/%m/%d"), "is_self_made": False, "removable": True,
                        "icon_path": "", "display_name": name}
            ALL_ITEMS.append(new_item); PANEL_ITEMS.append(new_item); save_data(); self.refresh_buttons()

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            dlg = AppearanceDialog(); dlg.setWindowTitle("添加文件夹")
            if dlg.exec_() == QDialog.Accepted:
                res = dlg.get_result()
                name = res['display_name'] or os.path.basename(folder)
                new_item = {"name": name, "path": folder, "type": "文件夹", "description": res['description'],
                            "time": datetime.now().strftime("%Y/%m/%d"), "is_self_made": False, "removable": True,
                            "icon_path": res['icon_path'], "display_name": res['display_name']}
                ALL_ITEMS.append(new_item); PANEL_ITEMS.append(new_item); save_data(); self.refresh_buttons()

    def _add_url(self):
        text, ok = QInputDialog.getText(self, "添加网址", "请输入网址 (http/https):")
        if ok and text.strip():
            url = text.strip()
            if not url.startswith(('http://', 'https://')): url = 'https://' + url
            dlg = AppearanceDialog(); dlg.setWindowTitle("添加网页")
            if dlg.exec_() == QDialog.Accepted:
                res = dlg.get_result()
                new_item = {"name": res['display_name'] or url, "path": url, "type": "网页",
                            "description": res['description'], "time": datetime.now().strftime("%Y/%m/%d"),
                            "is_self_made": False, "removable": True, "icon_path": res['icon_path'],
                            "display_name": res['display_name']}
                ALL_ITEMS.append(new_item); PANEL_ITEMS.append(new_item); save_data(); self.refresh_buttons()

    def customize_appearance(self, item):
        dlg = AppearanceDialog(item)
        if dlg.exec_() == QDialog.Accepted:
            res = dlg.get_result()
            item['icon_path'] = res['icon_path']; item['display_name'] = res['display_name']; item['description'] = res['description']
            save_data(); self.refresh_buttons()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.title_label.geometry().contains(event.pos()):
            self.drag_pos = event.globalPos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_pos is not None and event.buttons() & Qt.LeftButton:
            delta = event.globalPos() - self.drag_pos; self.move(self.pos() + delta); self.drag_pos = event.globalPos()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None
        super().mouseReleaseEvent(event)

# ------------------------------------------------
# 快捷键录制
# ------------------------------------------------
class HotkeyLineEdit(QLineEdit):
    hotkeyRecorded = pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True); self.setPlaceholderText("点击后按下组合键"); self.is_recording = False
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self and event.type() == event.MouseButtonPress:
            self.start_recording(); return True
        return super().eventFilter(obj, event)

    def start_recording(self):
        self.is_recording = True; self.setText("")
        self.setStyleSheet("background: #ffffcc; border: 2px solid #f39c12; border-radius: 4px;")
        self.setFocus()

    def stop_recording(self):
        self.is_recording = False; self.setStyleSheet("")

    def keyPressEvent(self, event):
        if not self.is_recording: return
        key = event.key(); modifiers = event.modifiers()
        parts = []
        if modifiers & Qt.ControlModifier: parts.append("ctrl")
        if modifiers & Qt.AltModifier: parts.append("alt")
        if modifiers & Qt.ShiftModifier: parts.append("shift")
        if key not in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta):
            key_text = event.text()
            if key_text: parts.append(key_text.lower())
            else:
                key_map = {Qt.Key_Space: "space", Qt.Key_Enter: "enter", Qt.Key_Return: "enter",
                           Qt.Key_Tab: "tab", Qt.Key_Backspace: "backspace", Qt.Key_Escape: "esc",
                           Qt.Key_Up: "up", Qt.Key_Down: "down", Qt.Key_Left: "left", Qt.Key_Right: "right"}
                parts.append(key_map.get(key, f"key{key}"))
            shortcut = "+".join(parts)
            self.setText(shortcut); self.stop_recording(); self.hotkeyRecorded.emit(shortcut)

# ================================================
# 可粘贴表格控件
# ================================================
class PasteTableWidget(QTableWidget):
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_V and (event.modifiers() & Qt.ControlModifier):
            self._paste_from_clipboard()
        elif event.key() == Qt.Key_C and (event.modifiers() & Qt.ControlModifier):
            self._copy_selected()
        else:
            super().keyPressEvent(event)

    def _paste_from_clipboard(self):
        clipboard = QApplication.clipboard(); mime = clipboard.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                path = url.toLocalFile()
                if os.path.isdir(path): self.window()._add_item(path, "文件夹")
                elif os.path.isfile(path): self.window()._add_item(path, "程序")
        elif mime.hasText():
            text = mime.text().strip()
            if text.startswith("http://") or text.startswith("https://"):
                reply = QMessageBox.question(self, "粘贴", f"是否添加网页：{text}?", QMessageBox.Yes|QMessageBox.No)
                if reply == QMessageBox.Yes: self.window()._add_item(text, "网页")

    def _copy_selected(self):
        rows = set()
        for item in self.selectedItems(): rows.add(item.row())
        if not rows: return
        names = []
        for row in rows:
            name_item = self.item(row, 3) if self.columnCount() > 3 else self.item(row, 0)
            if name_item:
                data = name_item.data(Qt.UserRole)
                if data: names.append(data['path'])
        if names: QApplication.clipboard().setText('\n'.join(names))

# ================================================
# 设置窗口 A（配色适配）
# ================================================
class SettingsWindow(QWidget):
    def __init__(self, app_controller):
        super().__init__()
        self.app = app_controller
        self.current_edit_file = None
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setMinimumSize(800, 500); self.resize(1000, 700)
        self.center_on_screen()
        self.drag_pos = None

        main_layout = QVBoxLayout(self); main_layout.setContentsMargins(2,2,2,2); main_layout.setSpacing(0)

        # 标题栏
        title_bar = QFrame(); title_bar.setFixedHeight(40)
        title_bar.setStyleSheet(f"background: {COLORS['primary']}; border-top-left-radius: 12px; border-top-right-radius: 12px;")
        tb_layout = QHBoxLayout(title_bar); tb_layout.setContentsMargins(20,0,10,0)
        tb_layout.addWidget(QLabel("aHA小助 设置")); tb_layout.addStretch()
        self.btn_pin = QPushButton("📌"); self.btn_pin.setCheckable(True); self.btn_pin.setFixedSize(26,26); self.btn_pin.clicked.connect(self.toggle_pin)
        self.btn_min = QPushButton("─"); self.btn_min.setFixedSize(26,26); self.btn_min.clicked.connect(self.showMinimized)
        self.btn_max = QPushButton("🗖"); self.btn_max.setFixedSize(26,26); self.btn_max.clicked.connect(self.toggle_maximize)
        self.btn_close = QPushButton("✕"); self.btn_close.setFixedSize(26,26); self.btn_close.clicked.connect(self.hide_window)
        for btn in (self.btn_pin, self.btn_min, self.btn_max, self.btn_close):
            btn.setStyleSheet("QPushButton { background: transparent; color: white; border: none; font-size: 14px; } QPushButton:hover { background: rgba(255,255,255,0.2); border-radius: 4px; }")
        tb_layout.addWidget(self.btn_pin); tb_layout.addWidget(self.btn_min); tb_layout.addWidget(self.btn_max); tb_layout.addWidget(self.btn_close)
        main_layout.addWidget(title_bar)

        content = QWidget(); content.setStyleSheet(f"background: {COLORS['bg_page']};")
        content_layout = QHBoxLayout(content); content_layout.setContentsMargins(0,0,0,0)

        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(180)
        self.nav_list.addItem("基础设置"); self.nav_list.addItem("工具配置"); self.nav_list.addItem("代码工坊"); self.nav_list.addItem("查找小程序")
        self.nav_list.currentRowChanged.connect(self.switch_page)
        self.nav_list.setStyleSheet(f"""
            QListWidget {{ background: {COLORS['white_soft']}; color: {COLORS['text_main']}; border: none; }}
            QListWidget::item {{ padding: 16px 24px; border-bottom: 1px solid {COLORS['border']}; }}
            QListWidget::item:selected {{ background: {COLORS['primary']}; color: white; }}
        """)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.create_basic_page())
        self.stack.addWidget(self.create_tools_page())
        self.stack.addWidget(self.create_editor_page())
        self.stack.addWidget(self.create_placeholder_page("查找小程序（敬请期待）"))
        content_layout.addWidget(self.nav_list); content_layout.addWidget(self.stack)
        main_layout.addWidget(content)

        self.size_grip = QSizeGrip(self)
        main_layout.addWidget(self.size_grip, 0, Qt.AlignBottom | Qt.AlignRight)
        self.nav_list.setCurrentRow(0)

    def center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def switch_page(self, index): self.stack.setCurrentIndex(index)

    def toggle_pin(self):
        flags = self.windowFlags()
        if self.btn_pin.isChecked(): flags |= Qt.WindowStaysOnTopHint
        else: flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags); self.show()

    def toggle_maximize(self):
        if self.isMaximized(): self.showNormal(); self.btn_max.setText("🗖")
        else: self.showMaximized(); self.btn_max.setText("🗗")

    def hide_window(self): self.hide()

    def closeEvent(self, event): event.ignore(); self.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.pos().y() <= 40:
            self.drag_pos = event.globalPos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_pos is not None and event.buttons() & Qt.LeftButton:
            delta = event.globalPos() - self.drag_pos; self.move(self.pos() + delta); self.drag_pos = event.globalPos()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event): self.drag_pos = None; super().mouseReleaseEvent(event)

    def create_placeholder_page(self, text):
        page = QWidget(); layout = QVBoxLayout(page)
        lbl = QLabel(text); lbl.setAlignment(Qt.AlignCenter); lbl.setStyleSheet(f"color: {COLORS['text_secondary']};"); layout.addWidget(lbl)
        return page

    # ----------------- 基础设置（简化示例，保留原有功能） -----------------
    def create_basic_page(self):
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(30,20,30,20); layout.setSpacing(20)
        title = QLabel("基础设置"); title.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {COLORS['text_main']};")
        layout.addWidget(title)

        startup_group = QFrame(); startup_group.setFrameShape(QFrame.StyledPanel)
        startup_group.setStyleSheet(f"background: {COLORS['bg_card']}; border-radius: 8px; padding: 16px;")
        slayout = QVBoxLayout(startup_group)
        slayout.addWidget(QLabel("启动项"))
        self.auto_start_cb = QCheckBox("开机自启动 aHA小助"); self.auto_start_cb.setChecked(SETTINGS.get("auto_start", False))
        self.startup_tip_cb = QCheckBox("显示启动完成提示"); self.startup_tip_cb.setChecked(SETTINGS.get("show_startup_tip", True))
        self.auto_start_cb.stateChanged.connect(self.toggle_auto_start)
        slayout.addWidget(self.auto_start_cb); slayout.addWidget(self.startup_tip_cb)
        layout.addWidget(startup_group)

        hotkey_group = QFrame(); hotkey_group.setFrameShape(QFrame.StyledPanel)
        hotkey_group.setStyleSheet(f"background: {COLORS['bg_card']}; border-radius: 8px; padding: 16px;")
        hlayout = QVBoxLayout(hotkey_group); hlayout.addWidget(QLabel("快捷键设置"))
        self.hotkey1_edit = HotkeyLineEdit(); self.hotkey1_edit.setText(SETTINGS["hotkeys"]["panel_show_1"])
        self.hotkey2_edit = HotkeyLineEdit(); self.hotkey2_edit.setText(SETTINGS["hotkeys"]["panel_show_2"])
        hlayout.addLayout(self._hk_line("呼出面板快捷键 1:", self.hotkey1_edit, "panel_show_1"))
        hlayout.addLayout(self._hk_line("呼出面板快捷键 2:", self.hotkey2_edit, "panel_show_2"))
        btn_line = QHBoxLayout()
        restore_btn = QPushButton("恢复默认"); restore_btn.clicked.connect(self.restore_default_hotkeys)
        clear_btn = QPushButton("清除"); clear_btn.clicked.connect(self.clear_all_hotkeys)
        btn_line.addWidget(restore_btn); btn_line.addWidget(clear_btn); btn_line.addStretch()
        hlayout.addLayout(btn_line); layout.addWidget(hotkey_group)

        path_group = QFrame(); path_group.setFrameShape(QFrame.StyledPanel)
        path_group.setStyleSheet(f"background: {COLORS['bg_card']}; border-radius: 8px; padding: 16px;")
        playout = QVBoxLayout(path_group); playout.addWidget(QLabel("文件保存路径"))
        self.new_path_edit = QLineEdit(SETTINGS["paths"]["new_program_save"])
        self.import_path_edit = QLineEdit(SETTINGS["paths"]["import_save"])
        playout.addLayout(self._path_line("新建默认保存:", self.new_path_edit, "new_program_save"))
        playout.addLayout(self._path_line("导入保存:", self.import_path_edit, "import_save"))
        layout.addWidget(path_group)

        appearance_group = QFrame(); appearance_group.setFrameShape(QFrame.StyledPanel)
        appearance_group.setStyleSheet(f"background: {COLORS['bg_card']}; border-radius: 8px; padding: 16px;")
        alayout = QVBoxLayout(appearance_group); alayout.addWidget(QLabel("外观"))
        self.allow_custom_cb = QCheckBox("允许设置按钮尺寸"); self.allow_custom_cb.setChecked(SETTINGS['appearance']['allow_custom_size'])
        alayout.addWidget(self.allow_custom_cb)
        self.size_slider = self._slider_line("按钮大小:", 20,100, SETTINGS['appearance']['button_size'], 'button_size')
        self.gap_slider = self._slider_line("间隙:", 0,30, SETTINGS['appearance']['button_gap'], 'button_gap')
        self.radius_slider = self._slider_line("圆角:", 0,20, SETTINGS['appearance']['button_radius'], 'button_radius')
        alayout.addLayout(self.size_slider); alayout.addLayout(self.gap_slider); alayout.addLayout(self.radius_slider)
        layout.addWidget(appearance_group)

        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    def _hk_line(self, label, edit, key):
        layout = QHBoxLayout(); layout.addWidget(QLabel(label)); layout.addWidget(edit)
        btn = QPushButton("✕"); btn.setFixedWidth(30); btn.clicked.connect(lambda: edit.clear())
        layout.addWidget(btn); edit.hotkeyRecorded.connect(lambda s: self.update_hotkey(key, s))
        return layout

    def _path_line(self, label, edit, key):
        layout = QHBoxLayout(); layout.addWidget(QLabel(label)); layout.addWidget(edit)
        btn = QPushButton("自定义"); btn.clicked.connect(lambda: self.browse_folder(edit))
        layout.addWidget(btn); edit.textChanged.connect(lambda: self.update_path(key, edit.text()))
        return layout

    def _slider_line(self, label, rmin, rmax, val, key):
        layout = QHBoxLayout(); layout.addWidget(QLabel(label))
        slider = QSlider(Qt.Horizontal); slider.setRange(rmin, rmax); slider.setValue(val)
        lbl = QLabel(str(val)); slider.valueChanged.connect(lambda v: (lbl.setText(str(v)), self.update_appearance(key, v)))
        layout.addWidget(slider); layout.addWidget(lbl)
        return layout

    def toggle_auto_start(self, state):
        try:
            import winshell
            startup_folder = winshell.startup()
            shortcut_path = os.path.join(startup_folder, "aHA小助.lnk")
            if state == Qt.Checked:
                target = sys.argv[0]
                with winshell.shortcut(shortcut_path) as s: s.path = target; s.description = "aHA小助"
            else:
                if os.path.exists(shortcut_path): os.remove(shortcut_path)
            SETTINGS["auto_start"] = (state == Qt.Checked); save_data()
        except ImportError:
            QMessageBox.warning(self, "错误", "请安装 winshell 库"); self.auto_start_cb.setChecked(False)
        except Exception as e: QMessageBox.warning(self, "错误", str(e))

    def browse_folder(self, edit):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder: edit.setText(folder)

    def update_hotkey(self, key, value): SETTINGS["hotkeys"][key] = value; save_data()
    def update_path(self, key, value): SETTINGS["paths"][key] = value; save_data()
    def update_appearance(self, key, value): SETTINGS['appearance'][key] = value; save_data(); self.app.comm.appearance_changed.emit()
    def restore_default_hotkeys(self):
        self.hotkey1_edit.setText("Ctrl+Shift+A"); self.hotkey2_edit.clear()
        SETTINGS["hotkeys"] = {"panel_show_1": "Ctrl+Shift+A", "panel_show_2": "", "search": ""}; save_data()
    def clear_all_hotkeys(self):
        self.hotkey1_edit.clear(); self.hotkey2_edit.clear()
        SETTINGS["hotkeys"] = {"panel_show_1": "", "panel_show_2": "", "search": ""}; save_data()

    # ----------------- 工具配置页 -----------------
    def create_tools_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(0,0,0,0)
        sub_nav = QHBoxLayout()
        self.btn_panel = QPushButton("面板窗口配置"); self.btn_tools = QPushButton("工具&小程序配置"); self.btn_recycle = QPushButton("配置回收站")
        for btn in (self.btn_panel, self.btn_tools, self.btn_recycle):
            btn.setCheckable(True); btn.setFlat(True)
            btn.setStyleSheet(f"QPushButton {{ padding: 8px 16px; background: transparent; color: {COLORS['text_main']}; }} QPushButton:checked {{ background: {COLORS['primary']}; color: white; }}")
            sub_nav.addWidget(btn)
        sub_nav.addStretch(); layout.addLayout(sub_nav)

        self.tools_stack = QStackedWidget()
        self.tools_stack.addWidget(self.create_panel_config_page())
        self.tools_stack.addWidget(self.create_library_page())
        self.tools_stack.addWidget(self.create_recycle_page())
        layout.addWidget(self.tools_stack)
        self.btn_panel.clicked.connect(lambda: (self.tools_stack.setCurrentIndex(0), self.refresh_panel_config()))
        self.btn_tools.clicked.connect(lambda: (self.tools_stack.setCurrentIndex(1), self.refresh_library_table()))
        self.btn_recycle.clicked.connect(lambda: (self.tools_stack.setCurrentIndex(2), self.refresh_recycle_table()))
        self.btn_tools.setChecked(True); self.tools_stack.setCurrentIndex(1)
        return page

    def create_panel_config_page(self):
        widget = QWidget(); layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("#勾选将在面板中显示的程序"))
        self.panel_table = PasteTableWidget(); self.panel_table.setColumnCount(5)
        self.panel_table.setHorizontalHeaderLabels(["全选", "💡", "显示", "名称", "路径"])
        self.panel_table.horizontalHeader().setStretchLastSection(True)
        self.panel_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.panel_table.cellDoubleClicked.connect(lambda row, col: self._execute_item_from_table(self.panel_table, row))
        layout.addWidget(self.panel_table); self.refresh_panel_config()
        return widget

    def _execute_item_from_table(self, table, row):
        name_col = 3 if table is self.panel_table else 2
        name_item = table.item(row, name_col)
        if name_item:
            data = name_item.data(Qt.UserRole)
            if data:
                if data['type'] == '网页': webbrowser.open(data['path'])
                else: os.startfile(data['path'])

    def _add_item(self, path, typ):
        name = os.path.splitext(os.path.basename(path))[0] if typ != "网页" else path.split("//")[-1][:20]
        new_item = {"name": name, "path": path, "type": typ, "description": "",
                    "time": datetime.now().strftime("%Y/%m/%d"), "is_self_made": False, "removable": True,
                    "icon_path": "", "display_name": name}
        ALL_ITEMS.append(new_item); PANEL_ITEMS.append(new_item)
        save_data(); self.refresh_panel_config(); self.refresh_library_table()
        self.app.comm.data_updated.emit()

    def refresh_panel_config(self):
        table = self.panel_table; table.setRowCount(len(ALL_ITEMS))
        for i, item in enumerate(ALL_ITEMS):
            cb = QCheckBox(); cb.setChecked(item in PANEL_ITEMS)
            idx = i
            cb.stateChanged.connect(lambda state, idx=idx: self.toggle_panel_item(idx, state))
            table.setCellWidget(i, 0, cb)
            bulb = QLabel("💡" if item.get('is_self_made', False) else "💡"); bulb.setAlignment(Qt.AlignCenter)
            if not item.get('is_self_made', False): bulb.setStyleSheet("color: gray;")
            table.setCellWidget(i, 1, bulb)
            table.setItem(i, 2, QTableWidgetItem(""))
            name_item = QTableWidgetItem(item.get('display_name', item['name'])); name_item.setData(Qt.UserRole, item)
            table.setItem(i, 3, name_item); table.setItem(i, 4, QTableWidgetItem(item['path']))
        table.setColumnWidth(1, 30); table.setColumnWidth(2, 30)

    def toggle_panel_item(self, idx, state):
        item = ALL_ITEMS[idx]
        if state == Qt.Checked:
            if item not in PANEL_ITEMS: PANEL_ITEMS.append(item)
        else:
            if item in PANEL_ITEMS: PANEL_ITEMS.remove(item)
        save_data(); self.app.comm.data_updated.emit()

    def create_library_page(self):
        widget = QWidget(); layout = QVBoxLayout(widget)
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit(); self.search_edit.setPlaceholderText("搜索..."); search_layout.addWidget(self.search_edit)
        search_btn = QPushButton("搜索"); search_btn.clicked.connect(self.refresh_library_table); search_layout.addWidget(search_btn)
        layout.addLayout(search_layout)
        self.library_table = PasteTableWidget(); self.library_table.setColumnCount(8)
        self.library_table.setHorizontalHeaderLabels(["全选", "💡", "名称", "类型", "路径", "描述", "自制", "操作"])
        self.library_table.horizontalHeader().setStretchLastSection(True)
        self.library_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.library_table.cellDoubleClicked.connect(lambda row, col: self._execute_item_from_table(self.library_table, row))
        layout.addWidget(self.library_table)
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(QPushButton("+ 添加程序", clicked=self.add_program_dialog))
        btn_layout.addWidget(QPushButton("+ 添加文件夹", clicked=self.add_folder_dialog))
        btn_layout.addWidget(QPushButton("+ 添加网页", clicked=self.add_url_dialog))
        btn_layout.addStretch(); layout.addLayout(btn_layout)
        self.refresh_library_table()
        return widget

    def refresh_library_table(self):
        keyword = self.search_edit.text().lower()
        filtered = [it for it in ALL_ITEMS if keyword in it['name'].lower() or keyword in it['path'].lower()]
        table = self.library_table; table.setRowCount(len(filtered))
        for i, item in enumerate(filtered):
            cb = QCheckBox(); table.setCellWidget(i, 0, cb)
            bulb = QLabel("💡" if item.get('is_self_made', False) else "💡"); bulb.setAlignment(Qt.AlignCenter)
            if not item.get('is_self_made', False): bulb.setStyleSheet("color: gray;")
            table.setCellWidget(i, 1, bulb)
            name_item = QTableWidgetItem(item.get('display_name', item['name'])); name_item.setData(Qt.UserRole, item)
            table.setItem(i, 2, name_item)
            table.setItem(i, 3, QTableWidgetItem(item['type'])); table.setItem(i, 4, QTableWidgetItem(item['path']))
            desc = QTableWidgetItem(item.get('description', '')); desc.setFlags(desc.flags()|Qt.ItemIsEditable); table.setItem(i, 5, desc)
            table.setItem(i, 6, QTableWidgetItem("是" if item.get('is_self_made', False) else "否"))
            w = QWidget(); hb = QHBoxLayout(w)
            edit_btn = QPushButton("编辑"); edit_btn.clicked.connect(lambda checked, it=item: self.app.comm.open_editor_with_file.emit(it['path']))
            del_btn = QPushButton("删除") if item.get('removable', True) else QLabel("内置")
            if isinstance(del_btn, QPushButton): del_btn.clicked.connect(lambda checked, it=item: self._move_to_recycle(it))
            hb.addWidget(edit_btn); hb.addWidget(del_btn); hb.setContentsMargins(0,0,0,0)
            table.setCellWidget(i, 7, w)
        table.setColumnWidth(1, 30)

    def _move_to_recycle(self, data):
        if data.get('removable', True):
            ALL_ITEMS.remove(data)
            if data in PANEL_ITEMS: PANEL_ITEMS.remove(data)
            RECYCLE_BIN.append({"item": data, "delete_time": datetime.now(), "expire_time": datetime.now()+timedelta(days=7)})
            save_data(); self.refresh_library_table(); self.refresh_recycle_table(); self.app.comm.data_updated.emit()

    def add_program_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择程序", "", "所有文件 (*.*)")
        if file_path: self._add_item(file_path, "程序")

    def add_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder: self._add_item(folder, "文件夹")

    def add_url_dialog(self):
        text, ok = QInputDialog.getText(self, "添加网页", "请输入网址 (http/https):")
        if ok and text.strip():
            url = text.strip()
            if not (url.startswith("http://") or url.startswith("https://")): url = "https://" + url
            self._add_item(url, "网页")

    def create_recycle_page(self):
        widget = QWidget(); layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("#被删除的小程序，7天内可恢复"))
        self.recycle_table = QTableWidget(0,5)
        self.recycle_table.setHorizontalHeaderLabels(["名称","路径","删除时间","操作",""])
        self.recycle_table.horizontalHeader().setStretchLastSection(True)
        self.recycle_table.cellDoubleClicked.connect(lambda row, col: self._restore_from_doubleclick(row))
        layout.addWidget(self.recycle_table); self.refresh_recycle_table()
        return widget

    def _restore_from_doubleclick(self, row):
        if row < len(RECYCLE_BIN): self.restore_item(RECYCLE_BIN[row])

    def refresh_recycle_table(self):
        now = datetime.now()
        for e in RECYCLE_BIN[:]:
            if now >= e['expire_time']: RECYCLE_BIN.remove(e)
        self.recycle_table.setRowCount(len(RECYCLE_BIN))
        for i, entry in enumerate(RECYCLE_BIN):
            item = entry['item']
            self.recycle_table.setItem(i,0,QTableWidgetItem(item['name']))
            self.recycle_table.setItem(i,1,QTableWidgetItem(item['path']))
            self.recycle_table.setItem(i,2,QTableWidgetItem(entry['delete_time'].strftime("%Y/%m/%d %H:%M:%S")))
            w = QWidget(); hb = QHBoxLayout(w)
            rest_btn = QPushButton("恢复"); rest_btn.clicked.connect(lambda checked, e=entry: self.restore_item(e))
            del_btn = QPushButton("永久删除"); del_btn.clicked.connect(lambda checked, e=entry: self.delete_recycle_item_forever(e))
            hb.addWidget(rest_btn); hb.addWidget(del_btn); hb.setContentsMargins(0,0,0,0)
            self.recycle_table.setCellWidget(i,3,w)

    def restore_item(self, entry):
        item = entry['item']; ALL_ITEMS.append(item); PANEL_ITEMS.append(item); RECYCLE_BIN.remove(entry)
        save_data(); self.refresh_library_table(); self.refresh_panel_config(); self.refresh_recycle_table()
        self.app.comm.data_updated.emit()

    def delete_recycle_item_forever(self, entry):
        reply = QMessageBox.question(self, "永久删除", "此操作不可恢复，确定？", QMessageBox.Yes|QMessageBox.No)
        if reply == QMessageBox.Yes:
            RECYCLE_BIN.remove(entry); save_data(); self.refresh_recycle_table()

    # ----------------- 代码工坊（保持不变） -----------------
    def create_editor_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(0,0,0,0)
        sub_nav = QHBoxLayout()
        self.btn_new = QPushButton("创建与修改"); self.btn_drafts = QPushButton("草稿箱"); self.btn_draft_recycle = QPushButton("垃圾箱")
        for btn in (self.btn_new, self.btn_drafts, self.btn_draft_recycle):
            btn.setCheckable(True); btn.setFlat(True)
            btn.setStyleSheet(f"QPushButton {{ padding: 8px 16px; background: transparent; color: {COLORS['text_main']}; }} QPushButton:checked {{ background: {COLORS['primary']}; color: white; }}")
            sub_nav.addWidget(btn)
        sub_nav.addStretch(); layout.addLayout(sub_nav)
        self.editor_stack = QStackedWidget()
        self.editor_stack.addWidget(self.create_code_editor_page())
        self.editor_stack.addWidget(self.create_drafts_page())
        self.editor_stack.addWidget(self.create_draft_recycle_page())
        layout.addWidget(self.editor_stack)
        self.btn_new.clicked.connect(lambda: self.goto_editor_new())
        self.btn_drafts.clicked.connect(lambda: (self.editor_stack.setCurrentIndex(1), self.refresh_drafts_table()))
        self.btn_draft_recycle.clicked.connect(lambda: (self.editor_stack.setCurrentIndex(2), self.refresh_draft_recycle_table()))
        self.btn_new.setChecked(True); self.editor_stack.setCurrentIndex(0)
        return page

    def goto_editor_new(self): self.editor_stack.setCurrentIndex(0); self.btn_new.setChecked(True); self.code_editor.clear(); self.current_edit_file = None

    def create_code_editor_page(self):
        widget = QWidget(); layout = QVBoxLayout(widget)
        toolbar = QHBoxLayout(); toolbar.addWidget(QLabel("#用aHA小助创建一个小程序吧！")); toolbar.addStretch()
        btn_install = QPushButton("安装python工具库"); btn_save_draft = QPushButton("存草稿"); btn_clear = QPushButton("删除")
        toolbar.addWidget(btn_install); toolbar.addWidget(btn_save_draft); toolbar.addWidget(btn_clear)
        layout.addLayout(toolbar)
        self.code_editor = QPlainTextEdit(); self.code_editor.setPlaceholderText("请输入代码...")
        self.code_editor.setStyleSheet(f"background: white; color: {COLORS['text_main']}; font-family: Consolas; border: 1px solid {COLORS['border']};")
        self.code_editor.setAcceptDrops(True); self.code_editor.dropEvent = self.editor_drop_event
        layout.addWidget(self.code_editor)
        run_layout = QHBoxLayout()
        btn_run_py = QPushButton("python运行"); btn_run_html = QPushButton("html运行"); btn_save_as = QPushButton("另存为..."); self.btn_save = QPushButton("保存")
        run_layout.addWidget(btn_run_py); run_layout.addWidget(btn_run_html); run_layout.addWidget(btn_save_as); run_layout.addWidget(self.btn_save); run_layout.addStretch()
        layout.addLayout(run_layout)
        btn_install.clicked.connect(self._install_lib); btn_save_draft.clicked.connect(self._save_draft)
        btn_clear.clicked.connect(lambda: self.code_editor.clear()); btn_run_py.clicked.connect(self._run_python)
        btn_run_html.clicked.connect(self._run_html); btn_save_as.clicked.connect(self._save_as_editor); self.btn_save.clicked.connect(self._save_current)
        return widget

    def editor_drop_event(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if os.path.isfile(path):
                    ext = os.path.splitext(path)[1].lower()
                    if ext in ['.txt','.py','.html','.css','.js','.json','.md']:
                        reply = QMessageBox.question(self, "导入文件", f"是否复制该文件代码？\n{os.path.basename(path)}", QMessageBox.Yes|QMessageBox.No)
                        if reply == QMessageBox.Yes:
                            try:
                                with open(path, 'r', encoding='utf-8') as f: self.code_editor.setPlainText(f.read()); self.current_edit_file = path
                            except Exception as e: QMessageBox.warning(self, "错误", str(e))
                        else: self.code_editor.textCursor().insertText(f'"{path}"')
                    else: self.code_editor.textCursor().insertText(f'"{path}"')

    def _install_lib(self):
        dialog = QDialog(self); dialog.setWindowTitle("安装"); dlg_layout = QVBoxLayout(dialog)
        dlg_layout.addWidget(QLabel("请输入pip安装代码")); input_line = QLineEdit(); input_line.setPlaceholderText("pip install ...")
        mirror_cb = QCheckBox("自动补充镜像"); mirror_edit = QLineEdit("https://pypi.tuna.tsinghua.edu.cn/simple"); mirror_edit.setEnabled(False); mirror_cb.toggled.connect(mirror_edit.setEnabled)
        dlg_layout.addWidget(input_line); dlg_layout.addWidget(mirror_cb); dlg_layout.addWidget(mirror_edit)
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); btn_box.accepted.connect(dialog.accept); btn_box.rejected.connect(dialog.reject); dlg_layout.addWidget(btn_box)
        if dialog.exec_() == QDialog.Accepted and input_line.text().strip():
            code = input_line.text().strip()
            if mirror_cb.isChecked() and "-i" not in code: code += f" -i {mirror_edit.text()}"
            subprocess.Popen(f'start cmd /k "{code}"', shell=True)

    def _save_draft(self):
        content = self.code_editor.toPlainText().strip()
        if not content: QMessageBox.warning(self, "提示", "代码为空"); return
        name = f"草稿_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        path = os.path.join(tempfile.gettempdir(), f"{name}.txt")
        with open(path, "w", encoding="utf-8") as f: f.write(content)
        DRAFTS.append({"name":name,"path":path,"content":content,"time":datetime.now().strftime("%Y/%m/%d %H:%M:%S"),"description":""})
        save_data(); self.refresh_drafts_table(); QMessageBox.information(self, "草稿", f"已保存至草稿箱：{name}")

    def _run_python(self):
        content = self.code_editor.toPlainText().strip()
        if not content: return
        tmp = os.path.join(tempfile.gettempdir(), f"aHA_temp_{datetime.now().strftime('%H%M%S')}.py")
        with open(tmp, "w", encoding="utf-8") as f: f.write(content)
        subprocess.Popen(f'python "{tmp}"', shell=True)

    def _run_html(self):
        content = self.code_editor.toPlainText().strip()
        if not content: return
        tmp = os.path.join(tempfile.gettempdir(), f"aHA_temp_{datetime.now().strftime('%H%M%S')}.html")
        with open(tmp, "w", encoding="utf-8") as f: f.write(content)
        webbrowser.open(f"file://{tmp}")

    def _save_as_editor(self):
        content = self.code_editor.toPlainText().strip()
        if not content: return
        file_path, _ = QFileDialog.getSaveFileName(self, "另存为", "", "Python文件 (*.py);;HTML文件 (*.html);;所有文件 (*.*)")
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f: f.write(content)
            self.current_edit_file = file_path; QMessageBox.information(self, "保存", f"已保存至 {file_path}")

    def _save_current(self):
        if not self.current_edit_file: QMessageBox.warning(self, "提示", "没有关联的文件路径"); return
        content = self.code_editor.toPlainText()
        reply = QMessageBox.question(self, "确认修改", f"确定保存对 {os.path.basename(self.current_edit_file)} 的修改？", QMessageBox.Yes|QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                with open(self.current_edit_file, "w", encoding="utf-8") as f: f.write(content)
                QMessageBox.information(self, "保存", "文件已保存。")
            except Exception as e: QMessageBox.warning(self, "错误", str(e))

    def create_drafts_page(self):
        widget = QWidget(); layout = QVBoxLayout(widget); layout.addWidget(QLabel("#草稿箱"))
        self.drafts_table = QTableWidget(0,4); self.drafts_table.setHorizontalHeaderLabels(["名称","时间","描述","操作"])
        self.drafts_table.horizontalHeader().setStretchLastSection(True); layout.addWidget(self.drafts_table)
        btn = QPushButton("+ 创建新的草稿"); btn.clicked.connect(lambda: self.editor_stack.setCurrentIndex(0)); layout.addWidget(btn)
        self.refresh_drafts_table(); return widget

    def refresh_drafts_table(self):
        self.drafts_table.setRowCount(len(DRAFTS))
        for i, draft in enumerate(DRAFTS):
            self.drafts_table.setItem(i,0,QTableWidgetItem(draft['name'])); self.drafts_table.setItem(i,1,QTableWidgetItem(draft['time']))
            self.drafts_table.setItem(i,2,QTableWidgetItem(draft.get('description','')))
            w = QWidget(); hb = QHBoxLayout(w)
            edit_btn = QPushButton("编辑"); edit_btn.clicked.connect(lambda checked, d=draft: self.edit_draft(d))
            del_btn = QPushButton("删除"); del_btn.clicked.connect(lambda checked, d=draft: self.delete_draft(d))
            hb.addWidget(edit_btn); hb.addWidget(del_btn); hb.setContentsMargins(0,0,0,0); self.drafts_table.setCellWidget(i,3,w)

    def edit_draft(self, draft): self.code_editor.setPlainText(draft['content']); self.current_edit_file = draft['path']; self.editor_stack.setCurrentIndex(0); self.btn_new.setChecked(True)

    def delete_draft(self, draft):
        reply = QMessageBox.question(self, "删除草稿", "确定？", QMessageBox.Yes|QMessageBox.No)
        if reply == QMessageBox.Yes:
            DRAFTS.remove(draft); DRAFT_RECYCLE_BIN.append({"item":draft,"delete_time":datetime.now(),"expire_time":datetime.now()+timedelta(days=7)})
            save_data(); self.refresh_drafts_table(); self.refresh_draft_recycle_table()

    def create_draft_recycle_page(self):
        widget = QWidget(); layout = QVBoxLayout(widget); layout.addWidget(QLabel("#草稿垃圾箱"))
        self.draft_recycle_table = QTableWidget(0,3); self.draft_recycle_table.setHorizontalHeaderLabels(["名称","删除时间","操作"])
        self.draft_recycle_table.horizontalHeader().setStretchLastSection(True); layout.addWidget(self.draft_recycle_table); self.refresh_draft_recycle_table(); return widget

    def refresh_draft_recycle_table(self):
        now = datetime.now()
        for e in DRAFT_RECYCLE_BIN[:]:
            if now >= e['expire_time']: DRAFT_RECYCLE_BIN.remove(e)
        self.draft_recycle_table.setRowCount(len(DRAFT_RECYCLE_BIN))
        for i, entry in enumerate(DRAFT_RECYCLE_BIN):
            item = entry['item']
            self.draft_recycle_table.setItem(i,0,QTableWidgetItem(item['name'])); self.draft_recycle_table.setItem(i,1,QTableWidgetItem(entry['delete_time'].strftime("%Y/%m/%d %H:%M:%S")))
            w = QWidget(); hb = QHBoxLayout(w)
            rest = QPushButton("恢复"); rest.clicked.connect(lambda checked, e=entry: self.restore_draft(e))
            del_btn = QPushButton("永久删除"); del_btn.clicked.connect(lambda checked, e=entry: self.delete_draft_forever(e))
            hb.addWidget(rest); hb.addWidget(del_btn); hb.setContentsMargins(0,0,0,0); self.draft_recycle_table.setCellWidget(i,2,w)

    def restore_draft(self, entry): DRAFTS.append(entry['item']); DRAFT_RECYCLE_BIN.remove(entry); save_data(); self.refresh_drafts_table(); self.refresh_draft_recycle_table()

    def delete_draft_forever(self, entry):
        reply = QMessageBox.question(self, "永久删除", "确定？", QMessageBox.Yes|QMessageBox.No)
        if reply == QMessageBox.Yes:
            DRAFT_RECYCLE_BIN.remove(entry)
            if os.path.exists(entry['item']['path']):
                try: os.remove(entry['item']['path'])
                except: pass
            save_data(); self.refresh_draft_recycle_table()

    def jump_to_tools_config(self): self.show(); self.activateWindow(); self.raise_(); self.nav_list.setCurrentRow(1); self.tools_stack.setCurrentIndex(1); self.btn_tools.setChecked(True)

    def jump_to_edit_with_file(self, filepath):
        self.show(); self.activateWindow(); self.raise_(); self.nav_list.setCurrentRow(2); self.editor_stack.setCurrentIndex(0); self.btn_new.setChecked(True)
        try:
            with open(filepath, "r", encoding="utf-8") as f: self.code_editor.setPlainText(f.read()); self.current_edit_file = filepath
        except Exception as e: QMessageBox.warning(self, "错误", str(e))

# ================================================
# 主应用
# ================================================
class AHAApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.comm = Communicator(); self.toast = ToastWidget(); self.panel = PanelWidget(self)
        self.settings_window = None; self.is_paused = False; self.tray_icon = None
        self.init_ui(); self.init_global_hotkeys()
        self.comm.show_panel_signal.connect(self.handle_show_panel)
        self.comm.show_startup_toast.connect(self.show_toast_safe)
        self.comm.toggle_pause_signal.connect(self.toggle_pause)
        self.comm.show_settings_signal.connect(self.show_settings)
        self.comm.quit_app_signal.connect(self.quit_app)
        self.comm.data_updated.connect(lambda: self.panel.refresh_buttons())
        self.comm.open_tools_config.connect(self.open_tools_config_handler)
        self.comm.open_editor_with_file.connect(self.open_editor_with_file_handler)
        self.comm.appearance_changed.connect(lambda: self.panel.update_appearance())
        if SETTINGS.get("show_startup_tip", True): self.comm.show_startup_toast.emit("aHA小助已启动！", "green")

    def init_ui(self): self.setQuitOnLastWindowClosed(False)

    def handle_show_panel(self, follow_cursor=True):
        if self.is_paused: return
        if follow_cursor: self.panel.show_at_mouse()
        else: self.panel.show_centered()

    def show_toast_safe(self, msg, color): self.toast.show_message(msg, color)

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        self.comm.show_startup_toast.emit("aHA小助已暂停..." if self.is_paused else "aHA小助已启动！", "#f39c12" if self.is_paused else "green")

    def show_settings(self):
        if self.settings_window is None: self.settings_window = SettingsWindow(self)
        self.settings_window.show(); self.settings_window.activateWindow(); self.settings_window.raise_()

    def open_tools_config_handler(self):
        self.show_settings()
        if self.settings_window: self.settings_window.jump_to_tools_config()

    def open_editor_with_file_handler(self, path):
        self.show_settings()
        if self.settings_window: self.settings_window.jump_to_edit_with_file(path)

    def init_global_hotkeys(self):
        def show(): self.comm.show_panel_signal.emit(True)
        self.hotkey_listener = keyboard.GlobalHotKeys({'<ctrl>+<shift>+a': show, '<ctrl>+<shift>+A': show})
        self.hotkey_thread = threading.Thread(target=self.hotkey_listener.run, daemon=True); self.hotkey_thread.start()
        def on_click(x,y,button,pressed):
            if button == mouse.Button.middle and pressed and not self.panel.geometry().contains(QPoint(x,y)):
                self.comm.show_panel_signal.emit(True)
        self.mouse_listener = mouse.Listener(on_click=on_click)
        self.mouse_thread = threading.Thread(target=self.mouse_listener.run, daemon=True); self.mouse_thread.start()

    def setup_tray(self):
        image = Image.new('RGBA', (64,64), (0,0,0,0)); draw = ImageDraw.Draw(image)
        draw.ellipse((10,10,54,54), fill=COLORS['primary']); draw.text((20,20), "aHA", fill='white')
        menu = (TrayMenuItem('设置', lambda: self.comm.show_settings_signal.emit()),
                TrayMenuItem('显示面板', lambda: self.comm.show_panel_signal.emit(False)),
                TrayMenuItem('暂停/启动', lambda: self.comm.toggle_pause_signal.emit()),
                TrayMenuItem('退出', self.quit_app))
        self.tray_icon = TrayIcon("aHA小助", image, "aHA小助", menu)
        self.tray_icon.on_double_click = lambda icon, item: self.comm.toggle_pause_signal.emit()
        tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True); tray_thread.start()

    def quit_app(self):
        save_data(); self.hotkey_listener.stop(); self.mouse_listener.stop()
        if self.tray_icon: self.tray_icon.stop(); self.quit()

if __name__ == "__main__":
    app = AHAApp(sys.argv); app.setWindowIcon(QIcon())
    QTimer.singleShot(0, app.setup_tray); sys.exit(app.exec_())