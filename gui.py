import sys
import os
import matplotlib.font_manager
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton,
                               QLabel, QTextEdit, QFileDialog, QMessageBox, QProgressBar, QSpinBox, QComboBox, QHBoxLayout, QDoubleSpinBox, QGroupBox, QLineEdit)
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QFont
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from video_generator import generate_slideshow
from minimax_client import MinimaxClient

def list_system_fonts():
    """
    Returns a list of tuples (font_name, font_path) available for PIL.
    """
    font_files = matplotlib.font_manager.findSystemFonts(fontpaths=None, fontext='ttf')

    # Include local downloaded fonts (Ensure they are absolute paths)
    local_fonts = ["NotoSansSC-Regular.otf", "NotoSansSC-Regular.ttf", "MaShanZheng-Regular.ttf"]
    for f in local_fonts:
        if os.path.exists(f):
            font_files.append(os.path.abspath(f))

    fonts = []
    # Key Chinese fonts to prioritize
    priority_fonts = []

    for fpath in font_files:
        try:
            prop = matplotlib.font_manager.FontProperties(fname=fpath)
            name = prop.get_name()
            # Only add if name is readable
            if name:
                # Prioritize known Chinese fonts
                lower_name = name.lower()
                is_priority = any(k in lower_name for k in ["noto sans sc", "mashanzheng", "simhei", "microsoft yahei", "pingfang"])

                if is_priority:
                    priority_fonts.append((name, fpath))
                else:
                    fonts.append((name, fpath))
        except:
            pass

    # Sort both lists
    priority_fonts.sort(key=lambda x: x[0])
    fonts.sort(key=lambda x: x[0])

    return priority_fonts + fonts

class VideoWorker(QThread):
    finished = Signal()
    progress_update = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, image_paths, text, output_path, duration=30, font_size=40, font_path=None, bottom_margin=50, zoom_factor=1.2, transition_effect="random", audio_path=None):
        super().__init__()
        self.image_paths = image_paths
        self.text = text
        self.output_path = output_path
        self.duration = duration
        self.font_size = font_size
        self.font_path = font_path
        self.bottom_margin = bottom_margin
        self.zoom_factor = zoom_factor
        self.transition_effect = transition_effect
        self.audio_path = audio_path

    def run(self):
        try:
            generate_slideshow(
                self.image_paths,
                self.text,
                self.output_path,
                duration=self.duration,
                font_size=self.font_size,
                font_path=self.font_path,
                bottom_margin=self.bottom_margin,
                zoom_factor=self.zoom_factor,
                transition_effect=self.transition_effect,
                audio_path=self.audio_path,
                progress_callback=self.progress_update.emit
            )
            self.finished.emit()
        except Exception as e:
            self.error_occurred.emit(str(e))

class AudioWorker(QThread):
    finished = Signal(str) # Emits output_file path
    error_occurred = Signal(str)

    def __init__(self, api_key, text, output_file, voice_id, speed, vol, pitch, tone):
        super().__init__()
        self.api_key = api_key
        self.text = text
        self.output_file = output_file
        self.voice_id = voice_id
        self.speed = speed
        self.vol = vol
        self.pitch = pitch
        self.tone = tone

    def run(self):
        try:
            client = MinimaxClient(self.api_key)
            client.generate_speech(self.text, self.output_file, self.voice_id, self.speed, self.vol, self.pitch, self.tone)
            self.finished.emit(self.output_file)
        except Exception as e:
            self.error_occurred.emit(str(e))

class VoiceListWorker(QThread):
    finished = Signal(list) # Emits list of dicts
    error_occurred = Signal(str)

    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key

    def run(self):
        try:
            client = MinimaxClient(self.api_key)
            voices = client.fetch_voices()
            self.finished.emit(voices)
        except Exception as e:
            self.error_occurred.emit(str(e))

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("幻灯片生成器")
        self.resize(600, 700) # Increased size
        self.selected_images = []
        self.generated_audio_path = None
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

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

        # Font Size & Margin Input
        settings_layout = QHBoxLayout()

        settings_layout.addWidget(QLabel("字幕大小："))
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(10, 200)
        self.spin_font_size.setValue(40)
        self.spin_font_size.valueChanged.connect(self.update_font_preview)
        settings_layout.addWidget(self.spin_font_size)

        settings_layout.addWidget(QLabel("底部距离 (px)："))
        self.spin_margin = QSpinBox()
        self.spin_margin.setRange(0, 500)
        self.spin_margin.setValue(50)
        settings_layout.addWidget(self.spin_margin)

        layout.addLayout(settings_layout)

        # Zoom Scale Input
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("图片放大比例："))
        self.spin_zoom = QDoubleSpinBox()
        self.spin_zoom.setRange(1.0, 5.0)
        self.spin_zoom.setSingleStep(0.1)
        self.spin_zoom.setValue(1.2)
        zoom_layout.addWidget(self.spin_zoom)

        # Transition Effect Selection
        zoom_layout.addWidget(QLabel("转场效果："))
        self.combo_transition = QComboBox()
        self.combo_transition.addItem("随机 (Random)", "random")
        self.combo_transition.addItem("淡入淡出 (Crossfade)", "crossfade")
        self.combo_transition.addItem("向左滑动 (Slide Left)", "slide_left")
        self.combo_transition.addItem("向右滑动 (Slide Right)", "slide_right")
        self.combo_transition.addItem("向上滑动 (Slide Top)", "slide_top")
        self.combo_transition.addItem("向下滑动 (Slide Bottom)", "slide_bottom")
        zoom_layout.addWidget(self.combo_transition)

        # Add a spacer to keep layout tight if needed, but here just adding to layout
        zoom_layout.addStretch()
        layout.addLayout(zoom_layout)

        # Duration Input
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel("视频时长 (秒)："))
        self.spin_duration = QSpinBox()
        self.spin_duration.setRange(5, 600)
        self.spin_duration.setValue(30)
        duration_layout.addWidget(self.spin_duration)
        layout.addLayout(duration_layout)

        # Text Input
        layout.addWidget(QLabel("滚动字幕："))
        self.txt_input = QTextEdit()
        self.txt_input.setPlaceholderText("请输入要在视频下方滚动的文字...")
        layout.addWidget(self.txt_input)

        # Dubbing Section
        dubbing_group = QGroupBox("配音设置")
        dubbing_layout = QVBoxLayout()

        # API Key
        api_layout = QHBoxLayout()
        api_layout.addWidget(QLabel("API Key:"))
        self.txt_api_key = QLineEdit()
        self.txt_api_key.setEchoMode(QLineEdit.Password)
        self.txt_api_key.setPlaceholderText("Enter Minimax API Key")
        api_layout.addWidget(self.txt_api_key)
        dubbing_layout.addLayout(api_layout)

        # Dubbing Text
        dubbing_layout.addWidget(QLabel("配音文本 (Dubbing Text):"))
        self.txt_dubbing_input = QTextEdit()
        self.txt_dubbing_input.setPlaceholderText("请输入要生成的语音文本...")
        self.txt_dubbing_input.setFixedHeight(80)
        dubbing_layout.addWidget(self.txt_dubbing_input)

        # Refresh Voices Button
        self.btn_refresh_voices = QPushButton("刷新/获取音色 (Fetch Voices)")
        self.btn_refresh_voices.clicked.connect(self.fetch_voices)
        api_layout.addWidget(self.btn_refresh_voices)

        # Params (VoiceID, Tone)
        params_layout1 = QHBoxLayout()
        params_layout1.addWidget(QLabel("Voice ID:"))
        # Changed to ComboBox
        self.combo_voice_id = QComboBox()
        self.combo_voice_id.setEditable(True) # Allow custom entry if needed
        self.combo_voice_id.addItem("English_ManWithDeepVoice") # Default
        params_layout1.addWidget(self.combo_voice_id)

        params_layout1.addWidget(QLabel("Tone:"))
        self.txt_tone = QLineEdit("happy")
        params_layout1.addWidget(self.txt_tone)
        dubbing_layout.addLayout(params_layout1)

        # Params (Speed, Vol, Pitch)
        params_layout2 = QHBoxLayout()

        params_layout2.addWidget(QLabel("Speed:"))
        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setRange(0.5, 2.0)
        self.spin_speed.setSingleStep(0.1)
        self.spin_speed.setValue(1.0)
        params_layout2.addWidget(self.spin_speed)

        params_layout2.addWidget(QLabel("Vol:"))
        self.spin_vol = QDoubleSpinBox()
        self.spin_vol.setRange(0.1, 10.0)
        self.spin_vol.setSingleStep(0.1)
        self.spin_vol.setValue(1.0)
        params_layout2.addWidget(self.spin_vol)

        params_layout2.addWidget(QLabel("Pitch:"))
        self.spin_pitch = QDoubleSpinBox()
        self.spin_pitch.setRange(-10.0, 10.0)
        self.spin_pitch.setSingleStep(0.5)
        self.spin_pitch.setValue(0.0)
        params_layout2.addWidget(self.spin_pitch)

        dubbing_layout.addLayout(params_layout2)

        # Action Buttons
        action_layout = QHBoxLayout()
        self.btn_gen_audio = QPushButton("生成音频 (Generate Audio)")
        self.btn_gen_audio.clicked.connect(self.generate_audio)
        action_layout.addWidget(self.btn_gen_audio)

        self.btn_play_audio = QPushButton("预览 (Play)")
        self.btn_play_audio.clicked.connect(self.play_audio)
        self.btn_play_audio.setEnabled(False)
        action_layout.addWidget(self.btn_play_audio)

        self.btn_stop_audio = QPushButton("停止 (Stop)")
        self.btn_stop_audio.clicked.connect(self.stop_audio)
        self.btn_stop_audio.setEnabled(False)
        action_layout.addWidget(self.btn_stop_audio)

        dubbing_layout.addLayout(action_layout)

        self.lbl_audio_status = QLabel("音频未生成")
        dubbing_layout.addWidget(self.lbl_audio_status)

        dubbing_group.setLayout(dubbing_layout)
        layout.addWidget(dubbing_group)

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
        font_size = self.spin_font_size.value()
        font = self.lbl_font_preview.font()
        font.setPointSize(max(10, font_size // 2)) # Scale down a bit for UI
        self.lbl_font_preview.setFont(font)
        pass

    def select_images(self):
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilters(["Images (*.png *.jpg *.jpeg *.bmp)"])
        file_dialog.setFileMode(QFileDialog.ExistingFiles)

        if file_dialog.exec():
            self.selected_images = file_dialog.selectedFiles()
            self.lbl_images.setText(f"已选择 {len(self.selected_images)} 张图片")
            self.lbl_status.setText(f"已选择 {len(self.selected_images)} 个文件。")

    def fetch_voices(self):
        api_key = self.txt_api_key.text().strip()
        if not api_key:
             QMessageBox.warning(self, "警告", "请输入 API Key 才能获取音色列表。")
             return

        self.btn_refresh_voices.setEnabled(False)
        self.lbl_audio_status.setText("正在获取音色列表...")

        self.voice_worker = VoiceListWorker(api_key)
        self.voice_worker.finished.connect(self.on_voices_fetched)
        self.voice_worker.error_occurred.connect(self.on_voices_error)
        self.voice_worker.start()

    def on_voices_fetched(self, voices):
        self.btn_refresh_voices.setEnabled(True)
        self.lbl_audio_status.setText("音色列表获取成功")

        current_text = self.combo_voice_id.currentText()
        self.combo_voice_id.clear()

        for v in voices:
            # Display: "Voice Name (voice_id)"
            display_text = f"{v['voice_name']} ({v['voice_id']})"
            self.combo_voice_id.addItem(display_text, v['voice_id'])

        # Restore previous selection if possible, or select first
        index = self.combo_voice_id.findData(current_text)
        if index == -1:
             # Try to find by text if user typed it
             index = self.combo_voice_id.findText(current_text, Qt.MatchContains)

        if index != -1:
            self.combo_voice_id.setCurrentIndex(index)

        QMessageBox.information(self, "成功", f"成功获取 {len(voices)} 个音色。")

    def on_voices_error(self, err_msg):
        self.btn_refresh_voices.setEnabled(True)
        self.lbl_audio_status.setText("获取音色失败")
        QMessageBox.warning(self, "错误", f"获取音色失败：\n{err_msg}")

    def generate_audio(self):
        api_key = self.txt_api_key.text().strip()
        text = self.txt_dubbing_input.toPlainText().strip()

        if not api_key:
             QMessageBox.warning(self, "警告", "请输入 API Key。")
             return
        if not text:
             QMessageBox.warning(self, "警告", "请输入配音文本。")
             return

        self.btn_gen_audio.setEnabled(False)
        self.lbl_audio_status.setText("正在生成音频...")

        # Get Voice ID from Combo Data (preferred) or Text
        voice_id = self.combo_voice_id.currentData()
        if not voice_id:
             # If user typed a custom ID or the combo has no data (just text)
             voice_id = self.combo_voice_id.currentText()
             # If user picked a loaded item, the text format is "Name (ID)", we might need to parse if data is missing?
             # But currentData() returns the second arg of addItem.
             # If the user typed manually in editable combo, currentData might be None.
             # If user typed "English_ManWithDeepVoice", we use that.

        tone = self.txt_tone.text().strip()
        speed = self.spin_speed.value()
        vol = self.spin_vol.value()
        pitch = self.spin_pitch.value()

        # Save to a temporary file
        output_file = os.path.abspath("generated_audio.mp3")

        self.audio_worker = AudioWorker(api_key, text, output_file, voice_id, speed, vol, pitch, tone)
        self.audio_worker.finished.connect(self.on_audio_finished)
        self.audio_worker.error_occurred.connect(self.on_audio_error)
        self.audio_worker.start()

    def on_audio_finished(self, path):
        self.generated_audio_path = path
        self.btn_gen_audio.setEnabled(True)
        self.btn_play_audio.setEnabled(True)
        self.btn_stop_audio.setEnabled(True)
        self.lbl_audio_status.setText(f"音频已生成: {os.path.basename(path)}")
        QMessageBox.information(self, "成功", "音频生成成功！")

    def on_audio_error(self, err_msg):
        self.btn_gen_audio.setEnabled(True)
        self.lbl_audio_status.setText("音频生成失败")
        QMessageBox.critical(self, "错误", f"音频生成失败：\n{err_msg}")

    def play_audio(self):
        if self.generated_audio_path and os.path.exists(self.generated_audio_path):
            self.player.setSource(QUrl.fromLocalFile(self.generated_audio_path))
            self.player.play()

    def stop_audio(self):
        self.player.stop()

    def generate_video(self):
        if not self.selected_images:
            QMessageBox.warning(self, "警告", "请至少选择一张图片。")
            return

        text = self.txt_input.toPlainText().strip()
        # It's okay if scrolling text is empty, maybe they just want slides + audio?
        # But previous logic required text. Let's keep it required unless user says otherwise.
        if not text:
             QMessageBox.warning(self, "警告", "请输入滚动字幕文字。")
             return

        output_path, _ = QFileDialog.getSaveFileName(self, "保存视频", "output.mp4", "Video (*.mp4)")
        if not output_path:
            return

        self.btn_generate.setEnabled(False)
        self.lbl_status.setText("正在生成...")

        font_size = self.spin_font_size.value()
        font_path = self.combo_font.currentData() # Get path from data
        duration = self.spin_duration.value()
        margin = self.spin_margin.value()
        zoom_factor = self.spin_zoom.value()
        transition_effect = self.combo_transition.currentData()

        # Check if audio is generated and file exists
        audio_path = None
        if self.generated_audio_path and os.path.exists(self.generated_audio_path):
             # Ask user if they want to include the generated audio?
             # Or just include it if it exists. The requirement says:
             # "在生成视频时，如果已经获取了mp3，需要将mp3合并到视频里。"
             audio_path = self.generated_audio_path

        self.worker = VideoWorker(
            self.selected_images,
            text,
            output_path,
            duration=duration,
            font_size=font_size,
            font_path=font_path,
            bottom_margin=margin,
            zoom_factor=zoom_factor,
            transition_effect=transition_effect,
            audio_path=audio_path
        )
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
