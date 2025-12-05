import sys
import os
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton,
                               QLabel, QTextEdit, QFileDialog, QMessageBox, QProgressBar)
from PySide6.QtCore import Qt, QThread, Signal

from video_generator import generate_slideshow

class VideoWorker(QThread):
    finished = Signal()
    progress_update = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, image_paths, text, output_path):
        super().__init__()
        self.image_paths = image_paths
        self.text = text
        self.output_path = output_path

    def run(self):
        try:
            generate_slideshow(
                self.image_paths,
                self.text,
                self.output_path,
                progress_callback=self.progress_update.emit
            )
            self.finished.emit()
        except Exception as e:
            self.error_occurred.emit(str(e))

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Slideshow Generator")
        self.resize(500, 400)
        self.selected_images = []

        layout = QVBoxLayout()

        # Image Selection
        self.btn_select_images = QPushButton("Select Images")
        self.btn_select_images.clicked.connect(self.select_images)
        layout.addWidget(self.btn_select_images)

        self.lbl_images = QLabel("No images selected")
        layout.addWidget(self.lbl_images)

        # Text Input
        layout.addWidget(QLabel("Scrolling Text:"))
        self.txt_input = QTextEdit()
        self.txt_input.setPlaceholderText("Enter the text to display...")
        layout.addWidget(self.txt_input)

        # Generate Button
        self.btn_generate = QPushButton("Generate Video")
        self.btn_generate.clicked.connect(self.generate_video)
        layout.addWidget(self.btn_generate)

        # Status
        self.lbl_status = QLabel("Ready")
        layout.addWidget(self.lbl_status)

        self.setLayout(layout)

    def select_images(self):
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilters(["Images (*.png *.jpg *.jpeg *.bmp)"])
        file_dialog.setFileMode(QFileDialog.ExistingFiles)

        if file_dialog.exec():
            self.selected_images = file_dialog.selectedFiles()
            self.lbl_images.setText(f"{len(self.selected_images)} images selected")
            self.lbl_status.setText(f"Selected {len(self.selected_images)} files.")

    def generate_video(self):
        if not self.selected_images:
            QMessageBox.warning(self, "Warning", "Please select at least one image.")
            return

        text = self.txt_input.toPlainText().strip()
        if not text:
             QMessageBox.warning(self, "Warning", "Please enter some text.")
             return

        output_path, _ = QFileDialog.getSaveFileName(self, "Save Video", "output.mp4", "Video (*.mp4)")
        if not output_path:
            return

        self.btn_generate.setEnabled(False)
        self.lbl_status.setText("Generating...")

        self.worker = VideoWorker(self.selected_images, text, output_path)
        self.worker.progress_update.connect(self.update_status)
        self.worker.finished.connect(self.on_finished)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()

    def update_status(self, msg):
        self.lbl_status.setText(msg)

    def on_finished(self):
        self.btn_generate.setEnabled(True)
        self.lbl_status.setText("Generation Complete!")
        QMessageBox.information(self, "Success", "Video generated successfully!")

    def on_error(self, err_msg):
        self.btn_generate.setEnabled(True)
        self.lbl_status.setText("Error occurred.")
        QMessageBox.critical(self, "Error", f"An error occurred:\n{err_msg}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
