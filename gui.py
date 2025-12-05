import sys
import os
import matplotlib.font_manager
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton,
                               QLabel, QTextEdit, QFileDialog, QMessageBox, QProgressBar, QSpinBox, QComboBox, QHBoxLayout)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from video_generator import generate_slideshow

def list_system_fonts():
    """
    Returns a list of tuples (font_name, font_path) available for PIL.
    """
    font_files = matplotlib.font_manager.findSystemFonts(fontpaths=None, fontext='ttf')

    # Include local downloaded fonts
    local_fonts = ["NotoSansSC-Regular.otf", "NotoSansSC-Regular.ttf", "MaShanZheng-Regular.ttf"]
    for f in local_fonts:
        if os.path.exists(f):
            font_files.append(os.path.abspath(f))

    fonts = []
    for fpath in font_files:
        try:
            prop = matplotlib.font_manager.FontProperties(fname=fpath)
            name = prop.get_name()
            # Only add if name is readable
            if name:
                fonts.append((name, fpath))
        except:
            pass

    fonts.sort(key=lambda x: x[0])
    return fonts

class VideoWorker(QThread):
    finished = Signal()
    progress_update = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, image_paths, text, output_path, font_size=40, font_path=None):
        super().__init__()
        self.image_paths = image_paths
        self.text = text
        self.output_path = output_path
        self.font_size = font_size
        self.font_path = font_path

    def run(self):
        try:
            generate_slideshow(
                self.image_paths,
                self.text,
                self.output_path,
                font_size=self.font_size,
                font_path=self.font_path,
                progress_callback=self.progress_update.emit
            )
            self.finished.emit()
        except Exception as e:
            self.error_occurred.emit(str(e))

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("幻灯片生成器")
        self.resize(500, 400)
        self.selected_images = []

        layout = QVBoxLayout()

        # Image Selection
        self.btn_select_images = QPushButton("选择图片")
        self.btn_select_images.clicked.connect(self.select_images)
        layout.addWidget(self.btn_select_images)

        self.lbl_images = QLabel("未选择图片")
        layout.addWidget(self.lbl_images)

        # Font Selection
        layout.addWidget(QLabel("选择字体："))
        font_layout = QHBoxLayout()

        self.combo_font = QComboBox()
        self.fonts = list_system_fonts()

        # Add a default option
        self.combo_font.addItem("默认 (Default)", None)

        for name, path in self.fonts:
            self.combo_font.addItem(name, path)

        self.combo_font.currentIndexChanged.connect(self.update_font_preview)
        font_layout.addWidget(self.combo_font)

        # Font Preview Label
        self.lbl_font_preview = QLabel("字体预览 Sample")
        self.lbl_font_preview.setStyleSheet("border: 1px solid gray; padding: 5px;")
        self.lbl_font_preview.setFixedHeight(50)
        font_layout.addWidget(self.lbl_font_preview)

        layout.addLayout(font_layout)

        # Font Size Input
        layout.addWidget(QLabel("字幕大小："))
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(10, 200)
        self.spin_font_size.setValue(40)
        self.spin_font_size.valueChanged.connect(self.update_font_preview)
        layout.addWidget(self.spin_font_size)

        # Text Input
        layout.addWidget(QLabel("滚动字幕："))
        self.txt_input = QTextEdit()
        self.txt_input.setPlaceholderText("请输入要在视频下方滚动的文字...")
        layout.addWidget(self.txt_input)

        # Generate Button
        self.btn_generate = QPushButton("生成视频")
        self.btn_generate.clicked.connect(self.generate_video)
        layout.addWidget(self.btn_generate)

        # Status
        self.lbl_status = QLabel("就绪")
        layout.addWidget(self.lbl_status)

        self.setLayout(layout)

    def update_font_preview(self):
        # Update preview label font
        # Note: Set QFont on QLabel uses system fonts rendering,
        # which might not perfectly match PIL if PIL loads a custom file not installed.
        # But we can try to set the font family if it's installed.
        # For non-installed files (local), QFontDatabase.addApplicationFont might be needed.
        # For now, we just update size.

        font_size = self.spin_font_size.value()
        # We can't easily preview the exact TTF file in QLabel without loading it into Qt.
        # But we can update size.
        font = self.lbl_font_preview.font()
        font.setPointSize(max(10, font_size // 2)) # Scale down a bit for UI
        self.lbl_font_preview.setFont(font)

        # If user selected a specific font, maybe we can show its name?
        # Implementing full WYSIWYG preview for raw TTF files in PySide needs font loading.
        pass

    def select_images(self):
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilters(["Images (*.png *.jpg *.jpeg *.bmp)"])
        file_dialog.setFileMode(QFileDialog.ExistingFiles)

        if file_dialog.exec():
            self.selected_images = file_dialog.selectedFiles()
            self.lbl_images.setText(f"已选择 {len(self.selected_images)} 张图片")
            self.lbl_status.setText(f"已选择 {len(self.selected_images)} 个文件。")

    def generate_video(self):
        if not self.selected_images:
            QMessageBox.warning(self, "警告", "请至少选择一张图片。")
            return

        text = self.txt_input.toPlainText().strip()
        if not text:
             QMessageBox.warning(self, "警告", "请输入文字。")
             return

        output_path, _ = QFileDialog.getSaveFileName(self, "保存视频", "output.mp4", "Video (*.mp4)")
        if not output_path:
            return

        self.btn_generate.setEnabled(False)
        self.lbl_status.setText("正在生成...")

        font_size = self.spin_font_size.value()
        font_path = self.combo_font.currentData() # Get path from data

        self.worker = VideoWorker(self.selected_images, text, output_path, font_size=font_size, font_path=font_path)
        self.worker.progress_update.connect(self.update_status)
        self.worker.finished.connect(self.on_finished)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()

    def update_status(self, msg):
        self.lbl_status.setText(msg)

    def on_finished(self):
        self.btn_generate.setEnabled(True)
        self.lbl_status.setText("生成完成！")
        QMessageBox.information(self, "成功", "视频生成成功！")

    def on_error(self, err_msg):
        self.btn_generate.setEnabled(True)
        self.lbl_status.setText("发生错误。")
        QMessageBox.critical(self, "错误", f"发生错误：\n{err_msg}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
