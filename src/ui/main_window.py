from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLineEdit, 
                               QProgressBar, QTextEdit, QComboBox,
                               QFileDialog, QMenuBar, QMenu, QLabel)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QAction, QIcon
from core.apk_processor import ApkProcessor
from core.config_manager import ConfigManager
from PyQt6.QtGui import QDesktopServices
import os
import json

class PasswordLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEchoMode(QLineEdit.EchoMode.Password)
        
        # 加载图标
        self.eye_on = QIcon(os.path.join(os.path.dirname(__file__), 'resources', 'eye-on.svg'))
        self.eye_off = QIcon(os.path.join(os.path.dirname(__file__), 'resources', 'eye-off.svg'))
        
        # 创建显示/隐藏按钮
        self.toggle_button = QPushButton(self)
        self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_button.setFixedSize(30, 30)
        
        # 连接信号
        self.toggle_button.clicked.connect(self.toggle_password_visible)
        
        # 初始化按钮图标
        self.update_toggle_button()
    
    def toggle_password_visible(self):
        if self.echoMode() == QLineEdit.EchoMode.Password:
            self.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.setEchoMode(QLineEdit.EchoMode.Password)
        self.update_toggle_button()
    
    def update_toggle_button(self):
        icon = self.eye_on if self.echoMode() == QLineEdit.EchoMode.Normal else self.eye_off
        self.toggle_button.setIcon(icon)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 更新按钮位置
        padding = 5
        self.toggle_button.move(self.width() - self.toggle_button.width() - padding,
                              (self.height() - self.toggle_button.height()) // 2)

class ProcessThread(QThread):
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, config_manager, apk_path, cert_path, cert_password, key_alias, key_password):
        super().__init__()
        self.apk_path = apk_path
        self.cert_path = cert_path
        self.cert_password = cert_password
        self.key_alias = key_alias
        self.key_password = key_password
        self.processor = ApkProcessor(config_manager, logger=self.log_message)
        self.is_cancelled = False

    def run(self):
        try:
            success, message = self.processor.process_apk(
                self.apk_path,
                self.cert_path,
                self.cert_password,
                self.key_alias,
                self.key_password,
                self.progress_callback
            )
            if not self.is_cancelled:
                self.finished_signal.emit(success, message)
        except Exception as e:
            if not self.is_cancelled:
                self.finished_signal.emit(False, str(e))

    def progress_callback(self, message):
        if not self.is_cancelled:
            self.progress_signal.emit(message)

    def cancel(self):
        """取消处理"""
        self.is_cancelled = True
        if hasattr(self, 'processor'):
            # 确保清理临时文件
            self.processor.cleanup()

    def log_message(self, message):
        """Logger callback that emits the progress signal"""
        if not self.is_cancelled:
            self.progress_signal.emit(str(message))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.setWindowTitle("安卓应用修改器")
        self.setAcceptDrops(True)
        
        # 设置程序图标
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), 'resources', 'app_icon.svg')))
        
        # 创建菜单栏
        self.create_menu_bar()
        
        # 初始化UI（包含创建log_text）
        self.init_ui()
        
        # 初始化完成后再加载和设置其他内容
        self.init_default_values()

    def init_default_values(self):
        """初始化默认值和加载保存的配置"""
        # 加载上次的APK和证书路径及相关信息
        self.load_last_paths()

    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # 选项菜单
        options_menu = menubar.addMenu('选项')
        
        # Zipalign选项
        self.zipalign_action = QAction('启用Zipalign优化', self)
        self.zipalign_action.setCheckable(True)
        self.zipalign_action.setChecked(self.config_manager.get_value('zipalign_enabled', False))
        self.zipalign_action.triggered.connect(self.toggle_zipalign)
        options_menu.addAction(self.zipalign_action)
        
        # 添加可调试选项
        self.debuggable_action = QAction('启用APK调试', self)
        self.debuggable_action.setCheckable(True)
        self.debuggable_action.setChecked(self.config_manager.get_value('debuggable_enabled', False))
        self.debuggable_action.triggered.connect(self.toggle_debuggable)
        options_menu.addAction(self.debuggable_action)

    def toggle_zipalign(self):
        enabled = self.zipalign_action.isChecked()
        self.config_manager.set_value('zipalign_enabled', enabled)

    def toggle_debuggable(self):
        enabled = self.debuggable_action.isChecked()
        self.config_manager.set_value('debuggable_enabled', enabled)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 进度条（不显示文字）
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)  # 隐藏进度条文字
        layout.addWidget(self.progress_bar)

        # 文件输入区域
        self.create_file_input_section(layout)
        
        # 证书配置区域
        self.create_certificate_section(layout)
        
        # 操作按钮区域（三等分布局）
        button_layout = QHBoxLayout()
        self.process_button = QPushButton("处理")
        self.cancel_button = QPushButton("取消")
        self.open_output_button = QPushButton("打开输出目录")
        
        for button in [self.process_button, self.cancel_button, self.open_output_button]:
            button.setMinimumWidth(150)
            button_layout.addWidget(button)
        
        self.process_button.clicked.connect(self.start_processing)
        self.cancel_button.clicked.connect(self.cancel_processing)
        self.open_output_button.clicked.connect(self.open_output_directory)
        self.cancel_button.setEnabled(False)
        
        layout.addLayout(button_layout)

        # 创建日志区域容器
        self.log_container = QWidget()
        log_container_layout = QVBoxLayout(self.log_container)
        log_container_layout.setContentsMargins(0, 0, 0, 0)  # 移除边距
        log_container_layout.setSpacing(0)  # 移除间距
        
        # 创建日志区域的折叠控制
        log_header = QWidget()  # 创建标题栏容器
        log_header.setStyleSheet("""
            QWidget {
                background-color: #f0f0f0;
                border-bottom: 1px solid #cccccc;
            }
        """)
        log_header_layout = QHBoxLayout(log_header)
        log_header_layout.setContentsMargins(5, 2, 5, 2)  # 减小上下边距
        log_label = QLabel("处理日志")
        self.toggle_log_button = QPushButton("展开")  # 默认为收起状态
        self.toggle_log_button.setFixedWidth(60)
        self.toggle_log_button.clicked.connect(self.toggle_log_area)
        log_header_layout.addWidget(log_label)
        log_header_layout.addStretch()
        log_header_layout.addWidget(self.toggle_log_button)
        log_container_layout.addWidget(log_header)

        # 创建日志文本区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(200)  # 设置展开时的最小高度
        self.log_text.setMaximumHeight(50)  # 默认收起状态
        self.log_text.setStyleSheet("""
            QTextEdit { 
                border: none;
                background-color: #ffffff;
                padding: 2px 5px;
            }
        """)
        log_container_layout.addWidget(self.log_text)
        
        # 存储完整日志
        self.full_log = []
        
        # 添加初始提示信息
        self.update_progress("等待开始处理...")
        
        layout.addWidget(self.log_container)
        
        # 保存原始窗口大小
        self.expanded_height = None
        
        # 设置初始窗口大小
        self.setMinimumSize(600, 400)
        
        # 初始化为收起状态
        QTimer.singleShot(0, lambda: self.toggle_log_area(initial=True))

    def create_file_input_section(self, parent_layout):
        group_layout = QVBoxLayout()
        
        # APK文件选择
        apk_layout = QHBoxLayout()
        apk_label = QLabel("APK文件：")
        self.apk_path = QLineEdit()
        self.apk_path.setPlaceholderText("拖放APK文件到这里或点击选择")
        self.apk_path.setReadOnly(True)
        apk_button = QPushButton("选择APK")
        apk_button.clicked.connect(self.select_apk_file)  # 重新连接信号
        apk_layout.addWidget(apk_label)
        apk_layout.addWidget(self.apk_path)
        apk_layout.addWidget(apk_button)
        
        # 证书文件选择
        cert_layout = QHBoxLayout()
        cert_label = QLabel("证书文件：")
        self.cert_path = QLineEdit()
        self.cert_path.setPlaceholderText("拖放证书文件到这里或点击选择")
        self.cert_path.setReadOnly(True)
        cert_button = QPushButton("选择证书")
        cert_button.clicked.connect(self.select_cert_file)  # 重新连接信号
        cert_layout.addWidget(cert_label)
        cert_layout.addWidget(self.cert_path)
        cert_layout.addWidget(cert_button)
        
        group_layout.addLayout(apk_layout)
        group_layout.addLayout(cert_layout)
        parent_layout.addLayout(group_layout)

    def create_certificate_section(self, parent_layout):
        group_layout = QVBoxLayout()
        
        # 证书密码
        cert_pass_layout = QHBoxLayout()
        cert_pass_label = QLabel("证书密码：")
        self.cert_password = PasswordLineEdit()
        self.cert_password.setPlaceholderText("证书密码")
        cert_pass_layout.addWidget(cert_pass_label)
        cert_pass_layout.addWidget(self.cert_password)
        
        # 密钥别名
        key_alias_layout = QHBoxLayout()
        key_alias_label = QLabel("密钥别名：")
        self.key_alias = QComboBox()
        self.key_alias.setEditable(True)
        self.key_alias.setPlaceholderText("密钥别名")
        key_alias_layout.addWidget(key_alias_label)
        key_alias_layout.addWidget(self.key_alias, 1)  # 设置拉伸因子为1
        
        # 密钥密码
        key_pass_layout = QHBoxLayout()
        key_pass_label = QLabel("密钥密码：")
        self.key_password = PasswordLineEdit()
        self.key_password.setPlaceholderText("密钥密码")
        key_pass_layout.addWidget(key_pass_label)
        key_pass_layout.addWidget(self.key_password)
        
        group_layout.addLayout(cert_pass_layout)
        group_layout.addLayout(key_alias_layout)
        group_layout.addLayout(key_pass_layout)
        parent_layout.addLayout(group_layout)

    def start_processing(self):
        if not self.validate_inputs():
            return
        self.log_text.clear()  # 每次运行前清空日志

        self.process_thread = ProcessThread(
            self.config_manager,
            self.apk_path.text(),
            self.cert_path.text(),
            self.cert_password.text(),
            self.key_alias.currentText(),
            self.key_password.text()
        )

        self.process_thread.progress_signal.connect(self.update_progress)
        self.process_thread.finished_signal.connect(self.process_finished)

        self.process_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setRange(0, 0)
        self.log_text.append("开始处理APK文件...")

        self.process_thread.start()

    def cancel_processing(self):
        """取消处理"""
        if hasattr(self, 'process_thread') and self.process_thread.isRunning():
            # 设置进度条为加载状态
            self.progress_bar.setRange(0, 0)
            
            self.process_thread.cancel()
            self.process_thread.wait()  # 等待线程结束
            
            # 恢复进度条和按钮状态
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.process_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            
            self.update_progress("已取消处理")

    def update_progress(self, message):
        """更新进度信息"""
        # 保存到完整日志
        self.full_log.append(message)
        
        # 如果是收起状态，只显示最新消息
        if self.toggle_log_button.text() == "展开":
            self.log_text.setPlainText(message)
        else:
            # 展开状态，显示所有日志
            self.log_text.append(message)
        
        # 确保日志始终滚动到最新内容
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def process_finished(self, success, message):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100 if success else 0)
        self.process_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        
        status = "成功" if success else "失败"
        self.log_text.append(f"处理{status}：{message}")

    def validate_inputs(self):
        if not self.apk_path.text():
            self.log_text.append("错误：请选择APK文件")
            return False
        if not self.cert_path.text():
            self.log_text.append("错误：请选择证书文件")
            return False
        if not self.cert_password.text():
            self.log_text.append("错误：请输入证书密码")
            return False
        if not self.key_alias.currentText():
            self.log_text.append("错误：请输入密钥别名")
            return False
        if not self.key_password.text():
            self.log_text.append("错误：请输入密钥密码")
            return False
        return True

    def create_status_section(self, parent_layout):
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        parent_layout.addWidget(self.log_text)

    def select_apk_file(self):
        # 获取当前APK路径的目录
        current_dir = os.path.dirname(self.apk_path.text()) if self.apk_path.text() else ""
        
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "选择APK文件",
            current_dir,  # 使用当前APK路径的目录
            "APK文件 (*.apk)"
        )
        if file_name:
            self.apk_path.setText(file_name)
            self.log_text.append(f"已选择APK文件：{file_name}")
            self.save_last_paths()  # 保存路径

    def select_cert_file(self):
        # 获取当前证书路径的目录
        current_dir = os.path.dirname(self.cert_path.text()) if self.cert_path.text() else ""
        
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "选择证书文件",
            current_dir,  # 使用当前证书路径的目录
            "证书文件 (*.keystore *.jks)"
        )
        if file_name:
            self.cert_path.setText(file_name)
            self.log_text.append(f"已选择证书文件：{file_name}")
            self.save_last_paths()  # 保存路径

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if not urls:
            return

        file_path = urls[0].toLocalFile()
        if file_path.lower().endswith('.apk'):
            self.apk_path.setText(file_path)
            self.log_text.append(f"已拖放APK文件：{file_path}")
            self.save_last_paths()  # 保存路径
        elif file_path.lower().endswith(('.keystore', '.jks')):
            self.cert_path.setText(file_path)
            self.log_text.append(f"已拖放证书文件：{file_path}")
            self.save_last_paths()  # 保存路径

    def save_last_paths(self):
        """保存APK、证书路径和证书相关信息"""
        try:
            with open("last_paths.json", "w", encoding="utf-8") as f:
                json.dump({
                    'apk_path': self.apk_path.text(),
                    'cert_path': self.cert_path.text(),
                    'cert_password': self.cert_password.text(),
                    'key_alias': self.key_alias.currentText(),
                    'key_password': self.key_password.text()
                }, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存配置失败：{str(e)}")

    def load_last_paths(self):
        """加载上次使用的APK、证书路径和证书相关信息"""
        try:
            if os.path.exists("last_paths.json"):
                with open("last_paths.json", "r", encoding="utf-8") as f:
                    paths = json.load(f)
                    
                    # 加载APK路径
                    if 'apk_path' in paths and os.path.exists(paths['apk_path']):
                        self.apk_path.setText(paths['apk_path'])
                        self.log_text.append(f"已加载上次的APK文件路径：{paths['apk_path']}")
                    
                    # 加载证书路径
                    if 'cert_path' in paths and os.path.exists(paths['cert_path']):
                        self.cert_path.setText(paths['cert_path'])
                        self.log_text.append(f"已加载上次的证书文件路径：{paths['cert_path']}")
                    
                    # 加载证书密码
                    if 'cert_password' in paths:
                        self.cert_password.setText(paths['cert_password'])
                    
                    # 加载密钥别名
                    if 'key_alias' in paths:
                        self.key_alias.clear()  # 清除现有项
                        self.key_alias.addItem(paths['key_alias'])
                        self.key_alias.setCurrentText(paths['key_alias'])
                    
                    # 加载密钥密码
                    if 'key_password' in paths:
                        self.key_password.setText(paths['key_password'])
        except Exception as e:
            print(f"加载配置失败：{str(e)}")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def open_output_directory(self):
        output_dir = self.config_manager.get_value('output_dir', 'output')
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(output_dir)))

    def toggle_log_area(self, initial=False):
        """切换日志区域的展开/收起状态"""
        if self.toggle_log_button.text() == "收起" or initial:
            # 保存当前窗口高度
            if not self.expanded_height and not initial:
                self.expanded_height = self.height()
            
            # 设置为最小高度显示
            self.log_text.setMaximumHeight(19)  # 减小高度，刚好显示一行
            self.log_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # 隐藏滚动条
            self.toggle_log_button.setText("展开")
            
            # 调整窗口高度
            if not initial:
                new_height = self.height() - self.log_text.height() + 19
                self.resize(self.width(), new_height)
            
            # 只显示最新的一条消息
            if self.full_log:
                self.log_text.setPlainText(self.full_log[-1])
            
        else:
            # 恢复原始高度
            self.log_text.setMaximumHeight(16777215)  # 设置为 Qt 的最大值
            self.log_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # 恢复滚动条
            self.toggle_log_button.setText("收起")
            
            # 恢复显示完整日志
            self.log_text.setPlainText("")  # 清空当前显示
            for msg in self.full_log:
                self.log_text.append(msg)
            
            if self.expanded_height:
                self.resize(self.width(), self.expanded_height)
