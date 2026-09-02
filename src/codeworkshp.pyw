import sys, os, subprocess, webbrowser, tempfile, json, shutil, requests, threading
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QSplitter,
    QStackedWidget, QLabel, QLineEdit, QFrame, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QPlainTextEdit, QDialog, QDialogButtonBox, QCheckBox, QMessageBox,
    QTabWidget, QToolButton, QShortcut, QTextEdit, QTabBar, QInputDialog, QMenu,
    QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt, QRect, QSize, QProcess, QMimeData, pyqtSignal, QObject, QThread, QTimer
from PyQt5.QtGui import (
    QFont, QIcon, QKeySequence, QPainter, QColor, QTextFormat, QPen, QKeyEvent
)

# ================================================
# 复古 Win9x 配色
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
    'line_number_bg':     '#D0D0D0',
    'line_number_fg':     '#404040',
    'indent_guide':       '#808080',
    'button_face':        '#C0C0C0',
    'button_light':       '#FFFFFF',
    'button_dark':        '#808080',
    'button_pressed':     '#A0A0A0',
    'editor_bg':          '#FFFFFF',
    'editor_text':        '#000000',
    'code_bg':            '#1E1E1E',
    'code_fg':            '#DCDCDC',
}

# ================================================
# 数据文件
# ================================================
DATA_DIR = os.path.join(os.path.expanduser("~"), "Documents", "aHA代码工坊")
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, "workshop_data.json")
AI_CONFIG_FILE = os.path.join(DATA_DIR, "ai_config.json")
AI_SESSIONS_FILE = os.path.join(DATA_DIR, "ai_sessions.json")

DRAFTS = []
DRAFT_RECYCLE_BIN = []
AI_CONFIG = {"api_key": "", "model": "gpt-3.5-turbo", "endpoint": "https://api.openai.com/v1/chat/completions"}
AI_SESSIONS = {}

def save_data():
    data = {
        "drafts": [{"name": d["name"], "path": d["path"], "content": d["content"],
                    "time": d["time"], "description": d["description"]} for d in DRAFTS],
        "draft_recycle_bin": [{"item": {"name": e["item"]["name"], "path": e["item"]["path"],
                                        "content": e["item"]["content"], "time": e["item"]["time"],
                                        "description": e["item"]["description"]},
                               "delete_time": e["delete_time"].strftime("%Y-%m-%d %H:%M:%S"),
                               "expire_time": e["expire_time"].strftime("%Y-%m-%d %H:%M:%S")} for e in DRAFT_RECYCLE_BIN]
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_data():
    global DRAFTS, DRAFT_RECYCLE_BIN
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "drafts" in data: DRAFTS = data["drafts"]
        if "draft_recycle_bin" in data:
            DRAFT_RECYCLE_BIN = [
                {"item": e["item"], "delete_time": datetime.strptime(e["delete_time"], "%Y-%m-%d %H:%M:%S"),
                 "expire_time": datetime.strptime(e["expire_time"], "%Y-%m-%d %H:%M:%S")} for e in data["draft_recycle_bin"]
            ]
    except:
        DRAFTS.clear(); DRAFT_RECYCLE_BIN.clear()

def save_ai_config():
    with open(AI_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(AI_CONFIG, f, indent=2)

def load_ai_config():
    global AI_CONFIG
    try:
        with open(AI_CONFIG_FILE, "r", encoding="utf-8") as f:
            AI_CONFIG.update(json.load(f))
    except:
        pass

def save_ai_sessions():
    with open(AI_SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(AI_SESSIONS, f, indent=2)

def load_ai_sessions():
    global AI_SESSIONS
    try:
        with open(AI_SESSIONS_FILE, "r", encoding="utf-8") as f:
            AI_SESSIONS = json.load(f)
    except:
        AI_SESSIONS = {}

load_data(); load_ai_config(); load_ai_sessions()

# ================================================
# AI 工作线程
# ================================================
class AIWorker(QObject):
    finished = pyqtSignal(str, bool)
    def __init__(self, messages, model, api_key, endpoint):
        super().__init__()
        self.messages = messages; self.model = model; self.api_key = api_key; self.endpoint = endpoint
    def run(self):
        try:
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            payload = {"model": self.model, "messages": self.messages, "temperature": 0.7}
            resp = requests.post(self.endpoint, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                reply = resp.json()["choices"][0]["message"]["content"]
                self.finished.emit(reply, True)
            else:
                self.finished.emit(f"API请求失败：{resp.status_code} {resp.text}", False)
        except Exception as e:
            self.finished.emit(f"请求异常：{str(e)}", False)

# ================================================
# 复古风格 AI 聊天面板
# ================================================
class AIChatPanel(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.current_session_id = None
        self.setMinimumWidth(300); self.setMaximumWidth(650)
        self.setStyleSheet(f"background-color: {COLORS['bg_page']}; border: 1px solid {COLORS['border']};")
        layout = QVBoxLayout(self); layout.setContentsMargins(2,2,2,2); layout.setSpacing(3)

        title = QFrame(); title.setFixedHeight(32)
        title.setStyleSheet(f"background: {COLORS['primary']}; color: white; padding: 2px; border: none;")
        title_layout = QHBoxLayout(title); title_layout.setContentsMargins(4,0,4,0)
        lbl = QLabel("🤖 AI 助手")
        lbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        title_layout.addWidget(lbl); title_layout.addStretch()
        for text, slot in [("🗑️", self.clear_current_session), ("⚙", self.open_settings), ("✕", self.hide_panel)]:
            btn = QPushButton(text); btn.setFlat(True)
            btn.setStyleSheet("color: white; border: none; font-size: 14px;")
            btn.clicked.connect(slot); title_layout.addWidget(btn)
        layout.addWidget(title)

        self.chat_area = QScrollArea(); self.chat_area.setWidgetResizable(True)
        self.chat_area.setStyleSheet("QScrollArea { border: 1px solid #808080; background: white; }")
        self.chat_content = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_content); self.chat_layout.setAlignment(Qt.AlignTop)
        self.chat_layout.setSpacing(6); self.chat_layout.setContentsMargins(6,6,6,6)
        self.chat_area.setWidget(self.chat_content); layout.addWidget(self.chat_area, 1)

        input_frame = QFrame()
        input_frame.setStyleSheet(f"background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};")
        input_layout = QVBoxLayout(input_frame); input_layout.setContentsMargins(6,6,6,6)
        self.input_text = QPlainTextEdit()
        self.input_text.setPlaceholderText("输入问题... (Enter发送，Ctrl+Enter换行)")
        self.input_text.setMaximumHeight(80)
        self.input_text.setStyleSheet("font-size: 12px; border: 1px solid #808080; background: white;")
        self.input_text.installEventFilter(self)
        self.cb_context = QCheckBox("附带当前编辑器代码")
        self.cb_context.setStyleSheet("font-size: 12px;")
        input_layout.addWidget(self.input_text); input_layout.addWidget(self.cb_context)
        layout.addWidget(input_frame)

        self.btn_send = QPushButton("发送")
        self.btn_send.setStyleSheet(self._button_style()); self.btn_send.clicked.connect(self.send_message)
        layout.addWidget(self.btn_send)

        self.worker = None; self.thread = None

    def _button_style(self):
        return f"""
            QPushButton {{
                border-top: 1px solid {COLORS['button_light']}; border-left: 1px solid {COLORS['button_light']};
                border-right: 1px solid {COLORS['button_dark']}; border-bottom: 1px solid {COLORS['button_dark']};
                background: {COLORS['button_face']}; color: black; padding: 8px 20px; font-size: 14px;
            }}
            QPushButton:pressed {{
                border-top: 1px solid {COLORS['button_dark']}; border-left: 1px solid {COLORS['button_dark']};
                border-right: 1px solid {COLORS['button_light']}; border-bottom: 1px solid {COLORS['button_light']};
                background: {COLORS['button_pressed']};
            }}
        """

    def eventFilter(self, obj, event):
        if obj == self.input_text and event.type() == QKeyEvent.KeyPress:
            if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ControlModifier):
                self.send_message(); return True
        return super().eventFilter(obj, event)

    def hide_panel(self): self.main.toggle_ai_panel(False)
    def clear_current_session(self):
        if self.current_session_id and self.current_session_id in AI_SESSIONS:
            AI_SESSIONS[self.current_session_id] = []; save_ai_sessions(); self.refresh_messages()

    def open_settings(self):
        dialog = QDialog(self); dialog.setWindowTitle("AI 设置")
        layout = QVBoxLayout(dialog)
        for label, attr in [("API Key:", "api_key"), ("模型:", "model"), ("API端点:", "endpoint")]:
            layout.addWidget(QLabel(label))
            edit = QLineEdit(AI_CONFIG.get(attr, ""))
            if attr == "api_key": edit.setEchoMode(QLineEdit.Password)
            layout.addWidget(edit)
            setattr(self, f"edit_{attr}", edit)
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dialog.accept); btn_box.rejected.connect(dialog.reject); layout.addWidget(btn_box)
        if dialog.exec_() == QDialog.Accepted:
            AI_CONFIG["api_key"] = self.edit_api_key.text().strip()
            AI_CONFIG["model"] = self.edit_model.text().strip()
            AI_CONFIG["endpoint"] = self.edit_endpoint.text().strip()
            save_ai_config(); QMessageBox.information(self, "设置", "AI配置已保存")

    def set_current_session(self, session_id):
        if self.current_session_id != session_id:
            self.current_session_id = session_id
            if session_id not in AI_SESSIONS: AI_SESSIONS[session_id] = []
            self.refresh_messages()

    def get_session_messages(self):
        return AI_SESSIONS.get(self.current_session_id, []) if self.current_session_id else []

    def refresh_messages(self):
        while self.chat_layout.count():
            item = self.chat_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for msg in self.get_session_messages():
            self._add_message_widget(msg["role"], msg["content"])

    def send_message(self):
        user_text = self.input_text.toPlainText().strip()
        if not user_text: return
        if not AI_CONFIG.get("api_key"): QMessageBox.warning(self, "提示", "请先设置API Key"); return
        if not self.current_session_id: self.current_session_id = "default"
        if self.current_session_id not in AI_SESSIONS: AI_SESSIONS[self.current_session_id] = []
        messages = [{"role": "system", "content": "你是一个编程助手，请用中文回答，代码部分使用Markdown代码块包裹。"}]
        if self.cb_context.isChecked():
            editor = self.main.get_current_editor()
            if editor:
                code = editor.toPlainText()
                if code.strip(): user_text = f"以下是当前代码：\n```\n{code}\n```\n\n{user_text}"
        messages.extend(self.get_session_messages()); messages.append({"role": "user", "content": user_text})
        self._add_message_widget("user", user_text)
        AI_SESSIONS[self.current_session_id].append({"role": "user", "content": user_text}); save_ai_sessions()
        self.input_text.clear()
        self._add_message_widget("assistant", "思考中...", is_placeholder=True)
        self.run_ai(messages)

    def run_ai(self, messages):
        self.thread = QThread()
        self.worker = AIWorker(messages, AI_CONFIG["model"], AI_CONFIG["api_key"], AI_CONFIG["endpoint"])
        self.worker.moveToThread(self.thread); self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_ai_reply); self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater); self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def on_ai_reply(self, text, success):
        for i in range(self.chat_layout.count()-1, -1, -1):
            w = self.chat_layout.itemAt(i).widget()
            if w and hasattr(w, 'is_placeholder'): w.deleteLater(); break
        self._add_message_widget("assistant", text)
        if self.current_session_id not in AI_SESSIONS: AI_SESSIONS[self.current_session_id] = []
        AI_SESSIONS[self.current_session_id].append({"role": "assistant", "content": text}); save_ai_sessions()

    def _add_message_widget(self, role, content, is_placeholder=False):
        frame = QFrame(); frame.setStyleSheet("background: transparent;")
        if is_placeholder: frame.is_placeholder = True
        h_layout = QHBoxLayout(frame); h_layout.setContentsMargins(0,0,0,0); h_layout.setSpacing(6)
        avatar = QLabel(); avatar.setFixedSize(28,28); avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"background: {COLORS['primary']}; color: white; font-size: 14px; border: 1px solid #808080;")
        avatar.setText("🤖" if role == "assistant" else "🧑")
        bubble = QFrame()
        bg_color = COLORS['bg_card'] if role == 'assistant' else '#E0E0E0'
        bubble.setStyleSheet(f"background: {bg_color}; border: 1px solid {COLORS['border']};")
        bubble_layout = QVBoxLayout(bubble); bubble_layout.setContentsMargins(6,4,6,4)
        if "```" in content:
            parts = content.split("```")
            for i, part in enumerate(parts):
                if i % 2 == 1:
                    code_text = part.strip()
                    code_container = QFrame(); code_container.setStyleSheet("background: #1E1E1E; border: 1px solid #808080;")
                    code_layout = QVBoxLayout(code_container); code_layout.setContentsMargins(4,4,4,4)
                    top_bar = QHBoxLayout()
                    lang_label = QLabel("Code"); lang_label.setStyleSheet("color: #A0A0A0; font-size: 11px;")
                    top_bar.addWidget(lang_label); top_bar.addStretch()
                    for act, text in [("复制", self.copy_code), ("下载", self.download_code)]:
                        btn = QPushButton(text); btn.setStyleSheet(self._mini_button_style())
                        btn.clicked.connect(lambda checked, t=code_text, a=act: a(t)); top_bar.addWidget(btn)
                    code_layout.addLayout(top_bar)
                    code_lbl = QLabel(code_text); code_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
                    code_lbl.setWordWrap(True); code_lbl.setStyleSheet("color: #DCDCDC; font-family: Consolas; font-size: 11px; padding: 2px;")
                    code_layout.addWidget(code_lbl); bubble_layout.addWidget(code_container)
                else:
                    if part.strip():
                        text_lbl = QLabel(part.strip()); text_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
                        text_lbl.setWordWrap(True); text_lbl.setStyleSheet("color: black; font-size: 12px;")
                        bubble_layout.addWidget(text_lbl)
        else:
            text_lbl = QLabel(content); text_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            text_lbl.setWordWrap(True); text_lbl.setStyleSheet("color: black; font-size: 12px;")
            bubble_layout.addWidget(text_lbl)
        if role == "user": h_layout.addStretch(); h_layout.addWidget(bubble); h_layout.addWidget(avatar)
        else: h_layout.addWidget(avatar); h_layout.addWidget(bubble); h_layout.addStretch()
        self.chat_layout.addWidget(frame)
        QTimer.singleShot(50, lambda: self.chat_area.verticalScrollBar().setValue(self.chat_area.verticalScrollBar().maximum()))

    def _mini_button_style(self):
        return f"QPushButton {{ border: 1px solid {COLORS['button_dark']}; background: {COLORS['button_face']}; color: black; font-size: 11px; padding: 2px 6px; }} QPushButton:pressed {{ background: {COLORS['button_pressed']}; }}"

    def copy_code(self, text): QApplication.clipboard().setText(text); QMessageBox.information(self, "复制成功", "代码已复制到剪贴板。")
    def download_code(self, text):
        path, _ = QFileDialog.getSaveFileName(self, "下载代码", "code", "Python (*.py);;HTML (*.html);;Text (*.txt);;All Files (*)")
        if path:
            with open(path, "w", encoding="utf-8") as f: f.write(text)
            QMessageBox.information(self, "下载成功", f"代码已保存到 {path}")

# ================================================
# 带行号的编辑器
# ================================================
class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.update_line_number_area_width(0); self.highlight_current_line()
        self.setFont(QFont("Consolas", 11))
    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        return 3 + self.fontMetrics().horizontalAdvance('9') * digits + 12
    def update_line_number_area_width(self, _): self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
    def update_line_number_area(self, rect, dy):
        if dy: self.line_number_area.scroll(0, dy)
        else: self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()): self.update_line_number_area_width(0)
    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect(); self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))
    def highlight_current_line(self):
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor("#C0C0C0")); selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor(); selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)
    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area); painter.fillRect(event.rect(), QColor(COLORS['line_number_bg']))
        block = self.firstVisibleBlock(); block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor(COLORS['line_number_fg']))
                painter.drawText(0, top, self.line_number_area.width()-5, self.fontMetrics().height(), Qt.AlignRight, str(block_number+1))
                text = block.text()
                if text.strip():
                    indent = len(text) - len(text.lstrip())
                    if indent > 0:
                        tab_width = self.fontMetrics().horizontalAdvance(' ') * 4
                        x = self.line_number_area.width() + (indent // 4) * tab_width
                        painter.setPen(QPen(QColor(COLORS['indent_guide']), 1, Qt.DotLine)); painter.drawLine(x, top, x, bottom)
            block = block.next(); top = bottom; bottom = top + round(self.blockBoundingRect(block).height()); block_number += 1

class LineNumberArea(QWidget):
    def __init__(self, editor): super().__init__(editor); self.code_editor = editor
    def sizeHint(self): return QSize(self.code_editor.line_number_area_width(), 0)
    def paintEvent(self, event): self.code_editor.line_number_area_paint_event(event)

# ================================================
# 欢迎页
# ================================================
class WelcomePage(QWidget):
    def __init__(self, open_file_callback):
        super().__init__(); self.open_file_callback = open_file_callback; self.setAcceptDrops(True)
        layout = QVBoxLayout(self); layout.setAlignment(Qt.AlignCenter)
        title = QLabel("代码工坊"); title.setFont(QFont("Microsoft Sans Serif", 28, QFont.Bold)); title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("请创建或导入代码"); subtitle.setFont(QFont("Microsoft Sans Serif", 16)); subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(title); layout.addWidget(subtitle)
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path): self.open_file_callback(path)

# ================================================
# 拖拽排序表格
# ================================================
class DragDropTableWidget(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True); self.setAcceptDrops(True); self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction); self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet(f"QTableWidget {{ border: 1px solid {COLORS['border']}; background: white; gridline-color: {COLORS['border']}; }} QTableWidget::item:selected {{ background: {COLORS['primary']}; color: white; }} QHeaderView::section {{ background: {COLORS['button_face']}; border: 1px solid {COLORS['border']}; padding: 4px; font-size: 12px; }}")
    def startDrag(self, supportedActions):
        indexes = self.selectedIndexes()
        if not indexes: return
        mime = QMimeData(); mime.setData("application/x-aha-internal", b"move"); super().startDrag(supportedActions)
    def dropEvent(self, event):
        if event.source() == self and event.mimeData().hasFormat("application/x-aha-internal"):
            super().dropEvent(event)
            if hasattr(self.parent(), 'update_draft_order'): self.parent().update_draft_order()
            elif hasattr(self.parent(), 'update_recycle_order'): self.parent().update_recycle_order()
        else: event.ignore()

# ================================================
# 主窗口（增大活动栏图标）
# ================================================
class CodeWorkshop(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("aHA 代码工坊"); self.setMinimumSize(1100,750); self.resize(1300,850)
        self.center_on_screen()
        self.current_view = 0; self.editors = {}; self.editor_paths = {}; self.ai_panel = None
        self.setStyleSheet(f"background: {COLORS['bg_page']}; font-family: 'Microsoft Sans Serif'; font-size: 12px;")
        self.setup_ui(); self.setup_shortcuts(); self.update_welcome_page()

    def center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width()-1300)//2, (screen.height()-850)//2)

    def setup_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        main_layout = QHBoxLayout(central); main_layout.setContentsMargins(0,0,0,0); main_layout.setSpacing(0)

        # 加宽活动栏并增大图标
        self.activity_bar = QFrame(); self.activity_bar.setFixedWidth(60)
        self.activity_bar.setStyleSheet(f"background: {COLORS['primary']}; border-right: 1px solid #000;")
        activity_layout = QVBoxLayout(self.activity_bar); activity_layout.setContentsMargins(0,12,0,0); activity_layout.setSpacing(10)

        self.btn_editor = self.create_activity_button("📝", "编辑器"); self.btn_editor.setChecked(True); self.btn_editor.clicked.connect(lambda: self.switch_view(0))
        self.btn_drafts = self.create_activity_button("📂", "草稿箱"); self.btn_drafts.clicked.connect(lambda: self.switch_view(1))
        self.btn_recycle = self.create_activity_button("🗑️", "垃圾箱"); self.btn_recycle.clicked.connect(lambda: self.switch_view(2))
        self.btn_ai = self.create_activity_button("🤖", "AI助手"); self.btn_ai.setCheckable(True)
        self.btn_ai.clicked.connect(lambda: self.toggle_ai_panel(not self.ai_panel.isVisible() if self.ai_panel else True))
        for btn in [self.btn_editor, self.btn_drafts, self.btn_recycle, self.btn_ai]: activity_layout.addWidget(btn)
        activity_layout.addStretch(); main_layout.addWidget(self.activity_bar)

        self.right_splitter = QSplitter(Qt.Horizontal); self.right_splitter.setStyleSheet("QSplitter::handle { background: #808080; }")
        self.left_panel = QStackedWidget()
        self.left_panel.addWidget(self.create_editor_view()); self.left_panel.addWidget(self.create_drafts_view()); self.left_panel.addWidget(self.create_recycle_view())
        self.right_splitter.addWidget(self.left_panel)

        self.ai_panel = AIChatPanel(self); self.ai_panel.hide(); self.right_splitter.addWidget(self.ai_panel)
        self.right_splitter.setSizes([850,0]); main_layout.addWidget(self.right_splitter)

        self.statusBar().setStyleSheet(f"background: {COLORS['button_face']}; border-top: 1px solid #808080; color: black; font-size: 12px;")
        self.statusBar().showMessage("就绪")

    def create_activity_button(self, icon_text, tooltip):
        btn = QToolButton(); btn.setText(icon_text); btn.setToolTip(tooltip); btn.setCheckable(True); btn.setFixedSize(44,44)
        btn.setFont(QFont("Microsoft Sans Serif", 16))
        btn.setStyleSheet(f"QToolButton {{ color: white; border: 1px solid transparent; background: transparent; }} QToolButton:hover {{ background: {COLORS['primary_hover']}; }} QToolButton:checked {{ background: {COLORS['primary_light']}; color: black; }}")
        return btn

    def switch_view(self, index):
        self.current_view = index; self.left_panel.setCurrentIndex(index)
        for btn in [self.btn_editor, self.btn_drafts, self.btn_recycle]: btn.setChecked(False)
        if index == 0: self.btn_editor.setChecked(True)
        elif index == 1: self.btn_drafts.setChecked(True)
        elif index == 2: self.btn_recycle.setChecked(True)

    def toggle_ai_panel(self, show):
        if show: self.ai_panel.show(); self.btn_ai.setChecked(True); self.right_splitter.setSizes([650,400])
        else: self.ai_panel.hide(); self.btn_ai.setChecked(False); self.right_splitter.setSizes([850,0])

    # 大按钮样式
    def _button_style(self):
        return f"""
            QPushButton {{
                border-top: 1px solid {COLORS['button_light']}; border-left: 1px solid {COLORS['button_light']};
                border-right: 1px solid {COLORS['button_dark']}; border-bottom: 1px solid {COLORS['button_dark']};
                background: {COLORS['button_face']}; color: black; padding: 8px 20px; font-size: 14px;
            }}
            QPushButton:pressed {{
                border-top: 1px solid {COLORS['button_dark']}; border-left: 1px solid {COLORS['button_dark']};
                border-right: 1px solid {COLORS['button_light']}; border-bottom: 1px solid {COLORS['button_light']};
                background: {COLORS['button_pressed']};
            }}
        """

    # ---------- 编辑器视图 ----------
    def create_editor_view(self):
        widget = QWidget(); layout = QVBoxLayout(widget); layout.setContentsMargins(0,0,0,0)
        toolbar = QHBoxLayout(); toolbar.setContentsMargins(4,4,4,4); toolbar.setSpacing(4)
        for txt, slot in [("📄 新建", self.new_tab), ("📂 打开", self.open_file), ("📑 存草稿", self.save_current_as_draft), ("📋 另存为", self.save_as_current_file)]:
            btn = QPushButton(txt); btn.setStyleSheet(self._button_style()); btn.clicked.connect(lambda checked, s=slot: s())
            toolbar.addWidget(btn)
        toolbar.addStretch()
        for txt, slot in [("▶ Python", self.run_python), ("🌐 HTML", self.run_html), ("📦 库", self.install_lib)]:
            btn = QPushButton(txt); btn.setStyleSheet(self._button_style()); btn.clicked.connect(lambda checked, s=slot: s())
            toolbar.addWidget(btn)
        layout.addLayout(toolbar)

        self.editor_stack = QStackedWidget()
        self.welcome_page = WelcomePage(self.open_file); self.editor_stack.addWidget(self.welcome_page)
        self.tab_widget = QTabWidget(); self.tab_widget.setTabsClosable(True); self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.tab_widget.tabBar().setContextMenuPolicy(Qt.CustomContextMenu); self.tab_widget.tabBar().customContextMenuRequested.connect(self.on_tab_context_menu)
        self.tab_widget.tabBar().tabBarDoubleClicked.connect(self.on_tab_double_click)
        self.tab_widget.setStyleSheet(f"QTabWidget::pane {{ border: 1px solid #808080; top: -1px; }} QTabBar::tab {{ background: {COLORS['button_face']}; border: 1px solid #808080; padding: 6px 14px; color: black; font-size: 13px; margin-right: -1px; }} QTabBar::tab:selected {{ background: white; border-bottom: 1px solid white; }}")
        self.editor_stack.addWidget(self.tab_widget); layout.addWidget(self.editor_stack)
        self.editor_stack.setCurrentIndex(0)
        return widget

    def update_welcome_page(self):
        if self.tab_widget.count() == 0: self.editor_stack.setCurrentIndex(0)
        else: self.editor_stack.setCurrentIndex(1)

    def new_tab(self, content="", file_path=None):
        try:
            editor = CodeEditor(); editor.setPlaceholderText("请输入代码...")
            editor.setStyleSheet(f"background: white; color: {COLORS['editor_text']}; font-size: 12px;")
            editor.setAcceptDrops(True); editor.dropEvent = lambda event, e=editor: self.editor_drop_event(event, e)
            editor.cursorPositionChanged.connect(lambda e=editor: self._safe_update_cursor(e))
            index = self.tab_widget.addTab(editor, "未命名"); self.tab_widget.setCurrentIndex(index)
            self.editors[index] = editor
            if file_path: self.editor_paths[index] = file_path; self.tab_widget.setTabText(index, os.path.basename(file_path))
            else: self.editor_paths[index] = None
            editor.setPlainText(content); self.update_welcome_page()
            return index
        except Exception as e: QMessageBox.critical(self, "错误", f"新建标签失败: {e}"); return -1

    def _safe_update_cursor(self, editor):
        try:
            if editor and editor.isVisible():
                cursor = editor.textCursor()
                self.statusBar().showMessage(f"行: {cursor.blockNumber()+1}, 列: {cursor.columnNumber()+1}")
        except: pass

    def open_file(self, path=None):
        if not path: path, _ = QFileDialog.getOpenFileName(self, "打开文件", "", "代码文件 (*.py *.html *.txt *.css *.js *.json *.md);;所有文件 (*.*)")
        if path:
            for idx, p in self.editor_paths.items():
                if p == path: self.tab_widget.setCurrentIndex(idx); return
            try:
                with open(path, 'r', encoding='utf-8') as f: content = f.read()
                self.new_tab(content, path)
            except Exception as e: QMessageBox.warning(self, "错误", f"无法打开文件: {e}")

    def editor_drop_event(self, event, editor):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if os.path.isfile(path): self.open_file(path)

    def close_tab(self, index):
        editor = self.editors.get(index)
        if editor and editor.document().isModified():
            reply = QMessageBox.question(self, "关闭", "文件已修改，是否存入草稿？", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if reply == QMessageBox.Save: self.save_draft_from_editor(index)
            elif reply == QMessageBox.Cancel: return
        self.tab_widget.removeTab(index)
        if index in self.editors: del self.editors[index]
        if index in self.editor_paths: del self.editor_paths[index]
        self.update_welcome_page()

    def on_tab_context_menu(self, pos):
        tab_bar = self.tab_widget.tabBar(); index = tab_bar.tabAt(pos)
        if index < 0: return
        menu = QMenu(self)
        for action_text, slot in [("复制", lambda: self.copy_tab_content(index)), ("存草稿", lambda: self.save_draft_from_editor(index)),
                                  ("另存为", lambda: self.save_as_file(index)), ("重命名", lambda: self.rename_tab(index)), ("删除", lambda: self.close_tab(index))]:
            menu.addAction(action_text).triggered.connect(slot)
        menu.exec_(tab_bar.mapToGlobal(pos))

    def copy_tab_content(self, index):
        editor = self.editors.get(index)
        if editor: QApplication.clipboard().setText(editor.toPlainText()); self.statusBar().showMessage("内容已复制", 2000)

    def rename_tab(self, index):
        old_name = self.tab_widget.tabText(index)
        new_name, ok = QInputDialog.getText(self, "重命名", "新名称:", text=old_name)
        if ok and new_name.strip():
            new_name = new_name.strip(); self.tab_widget.setTabText(index, new_name)
            old_path = self.editor_paths.get(index)
            if old_path: self.editor_paths[index] = os.path.join(os.path.dirname(old_path), new_name)
            else: self.editor_paths[index] = os.path.join(tempfile.gettempdir(), new_name)

    def on_tab_double_click(self, index):
        if index >= 0: self.rename_tab(index)

    def save_draft_from_editor(self, index):
        content = self.editors[index].toPlainText().strip()
        if not content: return
        name = self.editor_paths.get(index)
        name = os.path.splitext(os.path.basename(name))[0] if name else f"草稿_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        path = os.path.join(tempfile.gettempdir(), f"{name}.txt")
        with open(path, "w", encoding="utf-8") as f: f.write(content)
        DRAFTS.append({"name": name, "path": path, "content": content, "time": datetime.now().strftime("%Y/%m/%d %H:%M:%S"), "description": ""})
        save_data(); self.refresh_drafts_table(); self.statusBar().showMessage(f"草稿已保存: {name}", 3000)

    def save_current_as_draft(self):
        idx = self.tab_widget.currentIndex()
        if idx >= 0: self.save_draft_from_editor(idx); QMessageBox.information(self, "存草稿", "当前内容已存入草稿箱。")

    def save_file(self, index):
        path = self.editor_paths.get(index)
        if not path: return self.save_as_file(index)
        try:
            with open(path, 'w', encoding='utf-8') as f: f.write(self.editors[index].toPlainText())
            self.editors[index].document().setModified(False); self.statusBar().showMessage(f"已保存: {path}", 3000)
            return True
        except Exception as e: QMessageBox.warning(self, "错误", f"保存失败: {e}"); return False

    def save_as_file(self, index):
        path, _ = QFileDialog.getSaveFileName(self, "另存为", "", "Python (*.py);;HTML (*.html);;所有文件 (*.*)")
        if path: self.editor_paths[index] = path; self.tab_widget.setTabText(index, os.path.basename(path)); return self.save_file(index)
        return False

    def save_as_current_file(self):
        idx = self.tab_widget.currentIndex()
        if idx >= 0: self.save_as_file(idx)

    def on_tab_changed(self, index):
        if index >= 0 and index in self.editors:
            path = self.editor_paths.get(index, "未命名")
            self.statusBar().showMessage(f"当前文件: {path}")
            if self.ai_panel: self.ai_panel.set_current_session(path if path else f"unsaved_{index}")

    # ---------- 运行与安装 ----------
    def run_python(self):
        editor = self.get_current_editor()
        if not editor: return
        content = editor.toPlainText().strip()
        if not content: QMessageBox.warning(self, "提示", "没有代码"); return
        tmp = os.path.join(tempfile.gettempdir(), f"aHA_temp_{datetime.now().strftime('%H%M%S')}.py")
        with open(tmp, "w", encoding="utf-8") as f: f.write(content)
        subprocess.Popen(f'start cmd /k python "{tmp}"', shell=True)

    def run_html(self):
        editor = self.get_current_editor()
        if not editor: return
        content = editor.toPlainText().strip()
        if not content: return
        tmp = os.path.join(tempfile.gettempdir(), f"aHA_temp_{datetime.now().strftime('%H%M%S')}.html")
        with open(tmp, "w", encoding="utf-8") as f: f.write(content)
        webbrowser.open(f"file://{tmp}")

    def get_current_editor(self):
        idx = self.tab_widget.currentIndex(); return self.editors.get(idx)

    def install_lib(self):
        dialog = QDialog(self); dialog.setWindowTitle("安装"); dlg_layout = QVBoxLayout(dialog)
        dlg_layout.addWidget(QLabel("请输入pip安装代码")); input_line = QLineEdit(); input_line.setPlaceholderText("pip install ...")
        mirror_cb = QCheckBox("自动补充镜像"); mirror_edit = QLineEdit("https://pypi.tuna.tsinghua.edu.cn/simple"); mirror_edit.setEnabled(False)
        mirror_cb.toggled.connect(mirror_edit.setEnabled)
        dlg_layout.addWidget(input_line); dlg_layout.addWidget(mirror_cb); dlg_layout.addWidget(mirror_edit)
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); btn_box.accepted.connect(dialog.accept); btn_box.rejected.connect(dialog.reject)
        dlg_layout.addWidget(btn_box)
        if dialog.exec_() == QDialog.Accepted and input_line.text().strip():
            code = input_line.text().strip()
            if mirror_cb.isChecked() and "-i" not in code: code += f" -i {mirror_edit.text()}"
            subprocess.Popen(f'start cmd /k "{code}"', shell=True)

    # ---------- 草稿箱 ----------
    def create_drafts_view(self):
        widget = QWidget(); layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("#草稿箱"))
        self.drafts_table = DragDropTableWidget(); self.drafts_table.setColumnCount(4)
        self.drafts_table.setHorizontalHeaderLabels(["名称", "时间", "描述", "操作"])
        header = self.drafts_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive); header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Stretch); header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.drafts_table.setColumnWidth(0, 180); self.drafts_table.setColumnWidth(1, 160); self.drafts_table.setColumnWidth(3, 160)
        header.setMinimumSectionSize(60)
        self.drafts_table.setContextMenuPolicy(Qt.CustomContextMenu); self.drafts_table.customContextMenuRequested.connect(self.on_drafts_context_menu)
        layout.addWidget(self.drafts_table)
        btn_new = QPushButton("+ 创建新的草稿"); btn_new.setStyleSheet(self._button_style()); btn_new.clicked.connect(lambda: self.switch_view(0)); layout.addWidget(btn_new)
        self.refresh_drafts_table()
        return widget

    def on_drafts_context_menu(self, pos):
        table = self.drafts_table; row = table.rowAt(pos.y())
        if row < 0 or row >= len(DRAFTS): return
        draft = DRAFTS[row]; menu = QMenu(self)
        for text, slot in [("🤚 编辑", lambda: self.edit_draft(draft)), ("💾 另存为", lambda: self.saveas_draft(draft)),
                           ("📄 复制内容", lambda: QApplication.clipboard().setText(draft['content'])),
                           ("✏️ 重命名", lambda: self.rename_draft(row, draft)), ("❌ 删除", lambda: self.delete_draft(draft))]:
            menu.addAction(text).triggered.connect(slot)
        menu.exec_(table.viewport().mapToGlobal(pos))

    def rename_draft(self, row, draft):
        new_name, ok = QInputDialog.getText(self, "重命名草稿", "新名称:", text=draft['name'])
        if ok and new_name.strip():
            draft['name'] = new_name.strip(); self.drafts_table.item(row, 0).setText(new_name); save_data()

    def refresh_drafts_table(self):
        self.drafts_table.setRowCount(len(DRAFTS))
        for i, draft in enumerate(DRAFTS):
            name_item = QTableWidgetItem(draft['name']); name_item.setData(Qt.UserRole, draft)
            self.drafts_table.setItem(i, 0, name_item); self.drafts_table.setItem(i, 1, QTableWidgetItem(draft['time']))
            self.drafts_table.setItem(i, 2, QTableWidgetItem(draft.get('description', '')))
            w = QWidget(); hb = QHBoxLayout(w)
            for icon, slot in [("🤚", lambda d=draft: self.edit_draft(d)), ("💾", lambda d=draft: self.saveas_draft(d)), ("❌️", lambda d=draft: self.delete_draft(d))]:
                btn = QPushButton(icon); btn.setToolTip("编辑" if icon=="🤚" else "另存为" if icon=="💾" else "删除")
                btn.clicked.connect(slot); btn.setStyleSheet("QPushButton { font-size: 16px; padding: 4px 8px; border: none; background: transparent; } QPushButton:hover { background: #E8EDF5; }")
                hb.addWidget(btn)
            hb.setContentsMargins(0,0,0,0); self.drafts_table.setCellWidget(i, 3, w)

    def edit_draft(self, draft): self.switch_view(0); self.new_tab(draft['content'], draft['path'])
    def saveas_draft(self, draft):
        path, _ = QFileDialog.getSaveFileName(self, "另存为草稿", draft['name'], "Python (*.py);;HTML (*.html);;所有文件 (*.*)")
        if path:
            try: shutil.copy2(draft['path'], path); QMessageBox.information(self, "完成", f"草稿已保存至 {path}")
            except Exception as e: QMessageBox.warning(self, "错误", f"另存失败: {e}")
    def delete_draft(self, draft):
        reply = QMessageBox.question(self, "删除草稿", "确定？", QMessageBox.Yes|QMessageBox.No)
        if reply == QMessageBox.Yes:
            DRAFTS.remove(draft); DRAFT_RECYCLE_BIN.append({"item":draft,"delete_time":datetime.now(),"expire_time":datetime.now()+timedelta(days=7)})
            save_data(); self.refresh_drafts_table(); self.refresh_recycle_table()
    def update_draft_order(self):
        new_order = []
        for row in range(self.drafts_table.rowCount()):
            item = self.drafts_table.item(row, 0)
            if item:
                draft = item.data(Qt.UserRole)
                if draft: new_order.append(draft)
        if new_order: DRAFTS.clear(); DRAFTS.extend(new_order); save_data()

    # ---------- 垃圾箱 ----------
    def create_recycle_view(self):
        widget = QWidget(); layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("#草稿垃圾箱（保留7天）"))
        self.draft_recycle_table = DragDropTableWidget(); self.draft_recycle_table.setColumnCount(3)
        self.draft_recycle_table.setHorizontalHeaderLabels(["名称", "删除时间", "操作"])
        header = self.draft_recycle_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch); header.setSectionResizeMode(1, QHeaderView.Interactive); header.setSectionResizeMode(2, QHeaderView.Fixed)
        self.draft_recycle_table.setColumnWidth(1, 180); self.draft_recycle_table.setColumnWidth(2, 120); header.setMinimumSectionSize(60)
        self.draft_recycle_table.setContextMenuPolicy(Qt.CustomContextMenu); self.draft_recycle_table.customContextMenuRequested.connect(self.on_recycle_context_menu)
        layout.addWidget(self.draft_recycle_table); self.refresh_recycle_table()
        return widget

    def on_recycle_context_menu(self, pos):
        table = self.draft_recycle_table; row = table.rowAt(pos.y())
        if row < 0 or row >= len(DRAFT_RECYCLE_BIN): return
        entry = DRAFT_RECYCLE_BIN[row]; menu = QMenu(self)
        for text, slot in [("↩️ 恢复", lambda: self.restore_draft(entry)), ("❌ 永久删除", lambda: self.delete_draft_forever(entry))]:
            menu.addAction(text).triggered.connect(slot)
        menu.exec_(table.viewport().mapToGlobal(pos))

    def refresh_recycle_table(self):
        now = datetime.now()
        for e in DRAFT_RECYCLE_BIN[:]:
            if now >= e['expire_time']: DRAFT_RECYCLE_BIN.remove(e)
        self.draft_recycle_table.setRowCount(len(DRAFT_RECYCLE_BIN))
        for i, entry in enumerate(DRAFT_RECYCLE_BIN):
            item = entry['item']
            name_item = QTableWidgetItem(item['name']); name_item.setData(Qt.UserRole, entry)
            self.draft_recycle_table.setItem(i, 0, name_item); self.draft_recycle_table.setItem(i, 1, QTableWidgetItem(entry['delete_time'].strftime("%Y/%m/%d %H:%M:%S")))
            w = QWidget(); hb = QHBoxLayout(w)
            for icon, slot in [("↩️", lambda e=entry: self.restore_draft(e)), ("❌️", lambda e=entry: self.delete_draft_forever(e))]:
                btn = QPushButton(icon); btn.setToolTip("恢复" if icon=="↩️" else "永久删除")
                btn.clicked.connect(slot); btn.setStyleSheet("QPushButton { font-size: 16px; padding: 4px 8px; border: none; background: transparent; } QPushButton:hover { background: #E8EDF5; }")
                hb.addWidget(btn)
            hb.setContentsMargins(0,0,0,0); self.draft_recycle_table.setCellWidget(i, 2, w)

    def update_recycle_order(self):
        new_order = []
        for row in range(self.draft_recycle_table.rowCount()):
            item = self.draft_recycle_table.item(row, 0)
            if item:
                entry = item.data(Qt.UserRole)
                if entry: new_order.append(entry)
        if new_order: DRAFT_RECYCLE_BIN.clear(); DRAFT_RECYCLE_BIN.extend(new_order); save_data()

    def restore_draft(self, entry): DRAFTS.append(entry['item']); DRAFT_RECYCLE_BIN.remove(entry); save_data(); self.refresh_drafts_table(); self.refresh_recycle_table()
    def delete_draft_forever(self, entry):
        reply = QMessageBox.question(self, "永久删除", "确定？", QMessageBox.Yes|QMessageBox.No)
        if reply == QMessageBox.Yes:
            DRAFT_RECYCLE_BIN.remove(entry)
            if os.path.exists(entry['item']['path']):
                try: os.remove(entry['item']['path'])
                except: pass
            save_data(); self.refresh_recycle_table()

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(lambda: self.new_tab())
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(lambda: self.open_file())
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self.save_current_as_draft)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(self.save_as_current_file)

    def closeEvent(self, event):
        for idx in list(self.editors.keys()):
            if self.editors[idx].document().isModified():
                reply = QMessageBox.question(self, "退出", "还有未保存内容，存入草稿？", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
                if reply == QMessageBox.Save: self.save_draft_from_editor(idx)
                elif reply == QMessageBox.Cancel: event.ignore(); return
        save_data(); event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setWindowIcon(QIcon())
    window = CodeWorkshop(); window.show()
    sys.exit(app.exec_())