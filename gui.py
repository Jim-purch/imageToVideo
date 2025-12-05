import sys
import os
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton,
                               QLabel, QTextEdit, QFileDialog, QMessageBox, QProgressBar, QSpinBox)
from PySide6.QtCore import Qt, QThread, Signal

from video_generator import generate_slideshow

class VideoWorker(QThread):
    finished = Signal()
    progress_update = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, image_paths, text, output_path, font_size=40):
        super().__init__()
        self.image_paths = image_paths
        self.text = text
        self.output_path = output_path
        self.font_size = font_size

    def run(self):
        try:
            generate_slideshow(
                self.image_paths,
                self.text,
                self.output_path,
                font_size=self.font_size,
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

        # Font Size Input
        layout.addWidget(QLabel("字幕大小："))
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(10, 200)
        self.spin_font_size.setValue(40)
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
        self.worker = VideoWorker(self.selected_images, text, output_path, font_size=font_size)
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
