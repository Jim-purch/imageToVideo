import sys
import os
import json
import matplotlib.font_manager
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton,
                               QLabel, QTextEdit, QFileDialog, QMessageBox, QProgressBar, QSpinBox, QComboBox, QHBoxLayout, QDoubleSpinBox, QGroupBox, QLineEdit, QInputDialog, QColorDialog, QStackedWidget)
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QFont, QColor, QPalette
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

    def __init__(self, image_paths, text, output_path, duration=30, resolution=(1000, 1000), font_size=40, font_path=None, bottom_margin=50, zoom_factor=1.2, transition_effect="random", audio_path=None, bg_color=(255, 255, 255)):
        super().__init__()
        self.image_paths = image_paths
        self.text = text
        self.output_path = output_path
        self.duration = duration
        self.resolution = resolution
        self.font_size = font_size
        self.font_path = font_path
        self.bottom_margin = bottom_margin
        self.zoom_factor = zoom_factor
        self.transition_effect = transition_effect
        self.audio_path = audio_path
        self.bg_color = bg_color

    def run(self):
        try:
            generate_slideshow(
                self.image_paths,
                self.text,
                self.output_path,
                duration=self.duration,
                resolution=self.resolution,
                font_size=self.font_size,
                font_path=self.font_path,
                bottom_margin=self.bottom_margin,
                zoom_factor=self.zoom_factor,
                transition_effect=self.transition_effect,
                audio_path=self.audio_path,
                bg_color=self.bg_color,
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
        self.resize(900, 750)
        self.selected_images = []
        self.generated_audio_path = None
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.current_bg_color = (255, 255, 255) # Default white

        # --- Main Layout ---
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)

        # --- Left Side (Main Controls) ---
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)

        # 1. Image Selection
        self.btn_select_images = QPushButton("选择图片")
        self.btn_select_images.clicked.connect(self.select_images)
        left_layout.addWidget(self.btn_select_images)

        self.lbl_images = QLabel("未选择图片")
        left_layout.addWidget(self.lbl_images)

        # 2. Text Input
        left_layout.addWidget(QLabel("滚动字幕："))
        self.txt_input = QTextEdit()
        self.txt_input.setPlaceholderText("请输入要在视频下方滚动的文字...")
        left_layout.addWidget(self.txt_input)

        # 3. Settings Control Group
        settings_control_group = QGroupBox("设置 (Settings)")
        settings_control_layout = QVBoxLayout()

        # Preset Selection (Video & Audio combined concept in user mind? No, just audio preset per prev code)
        # But we will keep Dubbing Presets here.
        settings_control_layout.addWidget(QLabel("配音预设 (Dubbing Preset):"))
        self.combo_presets = QComboBox()
        self.combo_presets.addItem("当前配置 (Current Temporary)", "temp")
        self.combo_presets.currentIndexChanged.connect(self.on_preset_changed)
        settings_control_layout.addWidget(self.combo_presets)

        # Toggle Buttons Row
        toggle_layout = QHBoxLayout()

        self.btn_toggle_video = QPushButton("视频配置 (Video Config) >>")
        self.btn_toggle_video.setCheckable(True)
        self.btn_toggle_video.clicked.connect(self.toggle_video_panel)
        toggle_layout.addWidget(self.btn_toggle_video)

        self.btn_toggle_dubbing = QPushButton("配音设置 (Dubbing Settings) >>")
        self.btn_toggle_dubbing.setCheckable(True)
        self.btn_toggle_dubbing.clicked.connect(self.toggle_dubbing_panel)
        toggle_layout.addWidget(self.btn_toggle_dubbing)

        settings_control_layout.addLayout(toggle_layout)

        self.lbl_preset_info = QLabel("请选择配音预设或展开设置进行配置。")
        self.lbl_preset_info.setWordWrap(True)
        self.lbl_preset_info.setStyleSheet("color: gray; font-size: 10px;")
        settings_control_layout.addWidget(self.lbl_preset_info)

        settings_control_group.setLayout(settings_control_layout)
        left_layout.addWidget(settings_control_group)

        # 4. Generate & Status
        self.btn_generate = QPushButton("生成视频")
        self.btn_generate.clicked.connect(self.generate_video)
        left_layout.addWidget(self.btn_generate)

        self.lbl_status = QLabel("就绪")
        left_layout.addWidget(self.lbl_status)

        left_layout.addStretch() # Push everything up
        main_layout.addWidget(left_widget, 1) # Stretch factor 1

        # --- Right Side (Collapsible Panels) ---
        self.right_widget = QWidget()
        self.right_layout_container = QVBoxLayout()
        self.right_widget.setLayout(self.right_layout_container)

        # Stacked Widget to switch between Video and Dubbing settings
        self.stack = QStackedWidget()

        # -- Video Configuration Panel --
        self.video_group = QGroupBox("视频配置 (Video Configuration)")
        video_layout = QVBoxLayout()

        # Aspect Ratio & Resolution
        video_layout.addWidget(QLabel("视频比例与尺寸 (Ratio & Size):"))
        ratio_layout = QHBoxLayout()
        self.combo_ratio = QComboBox()
        self.combo_ratio.addItems(["1:1", "16:9", "9:16", "4:3", "Custom"])
        self.combo_ratio.currentTextChanged.connect(self.on_ratio_changed)
        ratio_layout.addWidget(self.combo_ratio)
        video_layout.addLayout(ratio_layout)

        res_layout = QHBoxLayout()
        res_layout.addWidget(QLabel("W:"))
        self.spin_width = QSpinBox()
        self.spin_width.setRange(100, 4000)
        self.spin_width.setValue(1000)
        self.spin_width.valueChanged.connect(self.on_res_changed)
        res_layout.addWidget(self.spin_width)

        res_layout.addWidget(QLabel("H:"))
        self.spin_height = QSpinBox()
        self.spin_height.setRange(100, 4000)
        self.spin_height.setValue(1000)
        self.spin_height.valueChanged.connect(self.on_res_changed)
        res_layout.addWidget(self.spin_height)
        video_layout.addLayout(res_layout)

        # Background Color
        bg_layout = QHBoxLayout()
        bg_layout.addWidget(QLabel("背景颜色 (Background):"))
        self.btn_bg_color = QPushButton()
        self.btn_bg_color.setStyleSheet("background-color: white; border: 1px solid gray;")
        self.btn_bg_color.setFixedSize(50, 25)
        self.btn_bg_color.clicked.connect(self.select_bg_color)
        bg_layout.addWidget(self.btn_bg_color)
        video_layout.addLayout(bg_layout)

        # Font Selection
        video_layout.addWidget(QLabel("选择字体 (Font):"))
        font_layout = QHBoxLayout()
        self.combo_font = QComboBox()
        self.fonts = list_system_fonts()
        self.combo_font.addItem("默认 (Default)", None)
        for name, path in self.fonts:
            self.combo_font.addItem(name, path)
        self.combo_font.currentIndexChanged.connect(self.update_font_preview)
        font_layout.addWidget(self.combo_font)

        # Preview Label (small)
        self.lbl_font_preview = QLabel("字")
        self.lbl_font_preview.setStyleSheet("border: 1px solid gray; padding: 2px;")
        self.lbl_font_preview.setFixedSize(30, 30)
        self.lbl_font_preview.setAlignment(Qt.AlignCenter)
        font_layout.addWidget(self.lbl_font_preview)
        video_layout.addLayout(font_layout)

        # Subtitle Size & Margin
        sub_layout = QHBoxLayout()
        sub_layout.addWidget(QLabel("字体大小:"))
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(10, 300)
        self.spin_font_size.setValue(40)
        self.spin_font_size.valueChanged.connect(self.update_font_preview)
        sub_layout.addWidget(self.spin_font_size)

        sub_layout.addWidget(QLabel("底部距离:"))
        self.spin_margin = QSpinBox()
        self.spin_margin.setRange(0, 1000)
        self.spin_margin.setValue(50)
        sub_layout.addWidget(self.spin_margin)
        video_layout.addLayout(sub_layout)

        # Zoom & Duration
        param_layout = QHBoxLayout()
        param_layout.addWidget(QLabel("放大:"))
        self.spin_zoom = QDoubleSpinBox()
        self.spin_zoom.setRange(1.0, 5.0)
        self.spin_zoom.setSingleStep(0.1)
        self.spin_zoom.setValue(1.2)
        param_layout.addWidget(self.spin_zoom)

        param_layout.addWidget(QLabel("时长(s):"))
        self.spin_duration = QSpinBox()
        self.spin_duration.setRange(5, 3600)
        self.spin_duration.setValue(30)
        param_layout.addWidget(self.spin_duration)
        video_layout.addLayout(param_layout)

        # Transition
        video_layout.addWidget(QLabel("转场效果 (Transition):"))
        self.combo_transition = QComboBox()
        self.combo_transition.addItem("随机 (Random)", "random")
        self.combo_transition.addItem("淡入淡出 (Crossfade)", "crossfade")
        self.combo_transition.addItem("向左滑动 (Slide Left)", "slide_left")
        self.combo_transition.addItem("向右滑动 (Slide Right)", "slide_right")
        self.combo_transition.addItem("向上滑动 (Slide Top)", "slide_top")
        self.combo_transition.addItem("向下滑动 (Slide Bottom)", "slide_bottom")
        video_layout.addWidget(self.combo_transition)

        video_layout.addStretch()
        self.video_group.setLayout(video_layout)
        self.stack.addWidget(self.video_group)

        # -- Dubbing Settings Panel --
        self.dubbing_group = QGroupBox("配音设置 (Dubbing Settings)")
        dubbing_layout = QVBoxLayout()

        # API Key
        dubbing_layout.addWidget(QLabel("API Key:"))
        api_row = QHBoxLayout()
        self.txt_api_key = QLineEdit()
        self.txt_api_key.setEchoMode(QLineEdit.Password)
        self.txt_api_key.setPlaceholderText("Enter Minimax API Key")
        api_row.addWidget(self.txt_api_key)
        self.btn_refresh_voices = QPushButton("刷新")
        self.btn_refresh_voices.setFixedWidth(50)
        self.btn_refresh_voices.clicked.connect(self.fetch_voices)
        api_row.addWidget(self.btn_refresh_voices)
        dubbing_layout.addLayout(api_row)

        # Dubbing Text
        dubbing_layout.addWidget(QLabel("配音文本:"))
        self.txt_dubbing_input = QTextEdit()
        self.txt_dubbing_input.setPlaceholderText("请输入语音文本...")
        self.txt_dubbing_input.setFixedHeight(80)
        dubbing_layout.addWidget(self.txt_dubbing_input)

        # Voice ID & Tone
        voice_row = QHBoxLayout()
        self.combo_voice_id = QComboBox()
        self.combo_voice_id.setEditable(True)
        self.combo_voice_id.addItem("English_ManWithDeepVoice")
        voice_row.addWidget(self.combo_voice_id, 2)

        self.txt_tone = QLineEdit("happy")
        self.txt_tone.setPlaceholderText("Tone")
        voice_row.addWidget(self.txt_tone, 1)
        dubbing_layout.addLayout(voice_row)

        # Speed, Vol, Pitch
        svp_row = QHBoxLayout()
        svp_row.addWidget(QLabel("Spd:"))
        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setRange(0.5, 2.0)
        self.spin_speed.setValue(1.0)
        self.spin_speed.setSingleStep(0.1)
        svp_row.addWidget(self.spin_speed)

        svp_row.addWidget(QLabel("Vol:"))
        self.spin_vol = QDoubleSpinBox()
        self.spin_vol.setRange(0.1, 10.0)
        self.spin_vol.setValue(1.0)
        self.spin_vol.setSingleStep(0.1)
        svp_row.addWidget(self.spin_vol)

        svp_row.addWidget(QLabel("Ptch:"))
        self.spin_pitch = QDoubleSpinBox()
        self.spin_pitch.setRange(-10.0, 10.0)
        self.spin_pitch.setValue(0.0)
        self.spin_pitch.setSingleStep(0.5)
        svp_row.addWidget(self.spin_pitch)
        dubbing_layout.addLayout(svp_row)

        # Actions
        act_row = QHBoxLayout()
        self.btn_gen_audio = QPushButton("生成音频")
        self.btn_gen_audio.clicked.connect(self.generate_audio)
        act_row.addWidget(self.btn_gen_audio)

        self.btn_save_preset = QPushButton("存为预设")
        self.btn_save_preset.clicked.connect(self.save_as_preset)
        self.btn_save_preset.setEnabled(False)
        act_row.addWidget(self.btn_save_preset)
        dubbing_layout.addLayout(act_row)

        # Preview
        prev_row = QHBoxLayout()
        self.btn_play_audio = QPushButton("播放")
        self.btn_play_audio.clicked.connect(self.play_audio)
        self.btn_play_audio.setEnabled(False)
        prev_row.addWidget(self.btn_play_audio)

        self.btn_stop_audio = QPushButton("停止")
        self.btn_stop_audio.clicked.connect(self.stop_audio)
        self.btn_stop_audio.setEnabled(False)
        prev_row.addWidget(self.btn_stop_audio)
        dubbing_layout.addLayout(prev_row)

        self.lbl_audio_status = QLabel("音频未生成")
        dubbing_layout.addWidget(self.lbl_audio_status)

        dubbing_layout.addStretch()
        self.dubbing_group.setLayout(dubbing_layout)
        self.stack.addWidget(self.dubbing_group)

        # Finish Right Side
        self.right_layout_container.addWidget(self.stack)
        main_layout.addWidget(self.right_widget, 0) # Stretch factor 0 (fixed width based on content)

        # Initial State: Hide Right Panel
        self.right_widget.hide()

        self.load_settings()
        self.check_existing_audio()

    def toggle_video_panel(self):
        # If currently showing dubbing, switch to video (and ensure right is visible)
        # If currently showing video, toggle visibility.

        if self.right_widget.isVisible():
            if self.stack.currentWidget() == self.video_group:
                # Toggle OFF
                self.right_widget.hide()
                self.btn_toggle_video.setChecked(False)
                self.btn_toggle_video.setText("视频配置 (Video Config) >>")
            else:
                # Switch from Dubbing to Video
                self.stack.setCurrentWidget(self.video_group)
                self.btn_toggle_video.setChecked(True)
                self.btn_toggle_video.setText("视频配置 (Video Config) <<")
                # Reset other button
                self.btn_toggle_dubbing.setChecked(False)
                self.btn_toggle_dubbing.setText("配音设置 (Dubbing Settings) >>")
        else:
            # Show Video
            self.right_widget.show()
            self.stack.setCurrentWidget(self.video_group)
            self.btn_toggle_video.setChecked(True)
            self.btn_toggle_video.setText("视频配置 (Video Config) <<")

        # Adjust button text if it was hidden
        if not self.right_widget.isVisible():
             self.btn_toggle_dubbing.setText("配音设置 (Dubbing Settings) >>")
             self.btn_toggle_video.setText("视频配置 (Video Config) >>")

    def toggle_dubbing_panel(self):
        if self.right_widget.isVisible():
            if self.stack.currentWidget() == self.dubbing_group:
                # Toggle OFF
                self.right_widget.hide()
                self.btn_toggle_dubbing.setChecked(False)
                self.btn_toggle_dubbing.setText("配音设置 (Dubbing Settings) >>")
            else:
                # Switch from Video to Dubbing
                self.stack.setCurrentWidget(self.dubbing_group)
                self.btn_toggle_dubbing.setChecked(True)
                self.btn_toggle_dubbing.setText("配音设置 (Dubbing Settings) <<")
                # Reset other button
                self.btn_toggle_video.setChecked(False)
                self.btn_toggle_video.setText("视频配置 (Video Config) >>")
        else:
            # Show Dubbing
            self.right_widget.show()
            self.stack.setCurrentWidget(self.dubbing_group)
            self.btn_toggle_dubbing.setChecked(True)
            self.btn_toggle_dubbing.setText("配音设置 (Dubbing Settings) <<")

        if not self.right_widget.isVisible():
             self.btn_toggle_dubbing.setText("配音设置 (Dubbing Settings) >>")
             self.btn_toggle_video.setText("视频配置 (Video Config) >>")

    def on_ratio_changed(self, text):
        if text == "1:1":
            self.spin_width.setValue(1000)
            self.spin_height.setValue(1000)
        elif text == "16:9":
            self.spin_width.setValue(1920)
            self.spin_height.setValue(1080)
        elif text == "9:16":
            self.spin_width.setValue(1080)
            self.spin_height.setValue(1920)
        elif text == "4:3":
            self.spin_width.setValue(1024)
            self.spin_height.setValue(768)
        # If Custom, do nothing (user sets it)

    def on_res_changed(self):
        # If user manually changes spinbox, check if it matches a ratio.
        # If not, set combo to Custom.
        w = self.spin_width.value()
        h = self.spin_height.value()

        # Simple check for common ratios
        if w == 1000 and h == 1000:
            self.combo_ratio.setCurrentText("1:1")
        elif w == 1920 and h == 1080:
            self.combo_ratio.setCurrentText("16:9")
        elif w == 1080 and h == 1920:
            self.combo_ratio.setCurrentText("9:16")
        elif w == 1024 and h == 768:
            self.combo_ratio.setCurrentText("4:3")
        else:
            self.combo_ratio.setCurrentText("Custom")

    def select_bg_color(self):
        color = QColorDialog.getColor(QColor(*self.current_bg_color), self, "Select Background Color")
        if color.isValid():
            self.current_bg_color = (color.red(), color.green(), color.blue())
            self.btn_bg_color.setStyleSheet(f"background-color: {color.name()}; border: 1px solid gray;")

    def check_existing_audio(self):
        potential_path = os.path.abspath("generated_audio.mp3")
        if os.path.exists(potential_path):
            if self.combo_presets.currentData() == "temp":
                self.generated_audio_path = potential_path
                self.lbl_audio_status.setText(f"检测到已有音频: {os.path.basename(potential_path)}")
                self.btn_play_audio.setEnabled(True)
                self.btn_stop_audio.setEnabled(True)
                self.btn_save_preset.setEnabled(True)

    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)

    def load_settings(self):
        config_path = "config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)

                if "font_path" in settings:
                    index = self.combo_font.findData(settings["font_path"])
                    if index != -1: self.combo_font.setCurrentIndex(index)

                if "font_size" in settings: self.spin_font_size.setValue(settings["font_size"])
                if "margin" in settings: self.spin_margin.setValue(settings["margin"])
                if "zoom" in settings: self.spin_zoom.setValue(settings["zoom"])
                if "transition" in settings:
                    index = self.combo_transition.findData(settings["transition"])
                    if index != -1: self.combo_transition.setCurrentIndex(index)
                if "duration" in settings: self.spin_duration.setValue(settings["duration"])
                if "text" in settings: self.txt_input.setPlainText(settings["text"])

                # New settings
                if "video_width" in settings: self.spin_width.setValue(settings["video_width"])
                if "video_height" in settings: self.spin_height.setValue(settings["video_height"])
                if "video_bg_color" in settings:
                    self.current_bg_color = tuple(settings["video_bg_color"])
                    c = QColor(*self.current_bg_color)
                    self.btn_bg_color.setStyleSheet(f"background-color: {c.name()}; border: 1px solid gray;")

                if "api_key" in settings: self.txt_api_key.setText(settings["api_key"])
                if "dubbing_text" in settings: self.txt_dubbing_input.setPlainText(settings["dubbing_text"])
                if "voice_id" in settings: self.combo_voice_id.setCurrentText(settings["voice_id"])
                if "tone" in settings: self.txt_tone.setText(settings["tone"])
                if "speed" in settings: self.spin_speed.setValue(settings["speed"])
                if "vol" in settings: self.spin_vol.setValue(settings["vol"])
                if "pitch" in settings: self.spin_pitch.setValue(settings["pitch"])

                if "presets" in settings:
                    self.presets = settings["presets"]
                    for p in self.presets:
                        self.combo_presets.addItem(p["name"], p)

            except Exception as e:
                print(f"Error loading settings: {e}")
        else:
             self.presets = []

    def save_settings(self):
        settings = {
            "font_path": self.combo_font.currentData(),
            "font_size": self.spin_font_size.value(),
            "margin": self.spin_margin.value(),
            "zoom": self.spin_zoom.value(),
            "transition": self.combo_transition.currentData(),
            "duration": self.spin_duration.value(),
            "text": self.txt_input.toPlainText(),
            "video_width": self.spin_width.value(),
            "video_height": self.spin_height.value(),
            "video_bg_color": self.current_bg_color,
            "api_key": self.txt_api_key.text(),
            "dubbing_text": self.txt_dubbing_input.toPlainText(),
            "voice_id": self.combo_voice_id.currentText(),
            "tone": self.txt_tone.text(),
            "speed": self.spin_speed.value(),
            "vol": self.spin_vol.value(),
            "pitch": self.spin_pitch.value(),
            "presets": getattr(self, "presets", [])
        }

        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def on_preset_changed(self, index):
        data = self.combo_presets.currentData()
        if data == "temp":
            self.lbl_preset_info.setText("使用下方的配音设置进行生成。")
            self.check_existing_audio()
        elif isinstance(data, dict):
             info = f"Voice: {data.get('voice_id')}\nText: {data.get('dubbing_text')[:30]}..."
             self.lbl_preset_info.setText(info)

             self.txt_dubbing_input.setPlainText(data.get("dubbing_text", ""))
             self.combo_voice_id.setCurrentText(data.get("voice_id", ""))
             self.txt_tone.setText(data.get("tone", ""))
             self.spin_speed.setValue(data.get("speed", 1.0))
             self.spin_vol.setValue(data.get("vol", 1.0))
             self.spin_pitch.setValue(data.get("pitch", 0.0))

             if os.path.exists(data.get("audio_path", "")):
                 self.generated_audio_path = data.get("audio_path")
                 self.lbl_audio_status.setText(f"已加载固定配音: {data['name']}")
                 self.btn_play_audio.setEnabled(True)
                 self.btn_stop_audio.setEnabled(True)
                 self.btn_save_preset.setEnabled(False)
             else:
                 self.lbl_audio_status.setText("固定配音文件丢失")
                 self.btn_play_audio.setEnabled(False)

    def save_as_preset(self):
        if not self.generated_audio_path or not os.path.exists(self.generated_audio_path):
            return

        name, ok = QInputDialog.getText(self, "保存固定配音", "请输入配音名称:")
        if ok and name:
            safe_name = "".join(x for x in name if x.isalnum() or x in " _-")
            if not hasattr(self, "presets"): self.presets = []

            new_filename = f"preset_{len(self.presets)}_{safe_name}.mp3"
            new_path = os.path.abspath(new_filename)
            try:
                import shutil
                shutil.copy(self.generated_audio_path, new_path)

                preset = {
                    "name": name,
                    "audio_path": new_path,
                    "dubbing_text": self.txt_dubbing_input.toPlainText(),
                    "voice_id": self.combo_voice_id.currentText(),
                    "tone": self.txt_tone.text(),
                    "speed": self.spin_speed.value(),
                    "vol": self.spin_vol.value(),
                    "pitch": self.spin_pitch.value()
                }

                self.presets.append(preset)
                self.combo_presets.addItem(name, preset)
                self.combo_presets.setCurrentIndex(self.combo_presets.count() - 1)
                QMessageBox.information(self, "成功", "配音已保存为固定预设！")

            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存预设失败: {e}")

    def update_font_preview(self):
        font_size = self.spin_font_size.value()
        font = self.lbl_font_preview.font()
        font.setPointSize(max(10, min(30, font_size // 2)))
        self.lbl_font_preview.setFont(font)

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
            display_text = f"{v['voice_name']} ({v['voice_id']})"
            self.combo_voice_id.addItem(display_text, v['voice_id'])

        index = self.combo_voice_id.findData(current_text)
        if index == -1:
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

        index = self.combo_presets.findData("temp")
        if index != -1:
            self.combo_presets.setCurrentIndex(index)

        self.btn_gen_audio.setEnabled(False)
        self.lbl_audio_status.setText("正在生成音频...")

        voice_id = self.combo_voice_id.currentData()
        if not voice_id:
             voice_id = self.combo_voice_id.currentText()

        tone = self.txt_tone.text().strip()
        speed = self.spin_speed.value()
        vol = self.spin_vol.value()
        pitch = self.spin_pitch.value()
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
        self.btn_save_preset.setEnabled(True)
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
        if not text:
             QMessageBox.warning(self, "警告", "请输入滚动字幕文字。")
             return

        output_path, _ = QFileDialog.getSaveFileName(self, "保存视频", "output.mp4", "Video (*.mp4)")
        if not output_path:
            return

        self.btn_generate.setEnabled(False)
        self.lbl_status.setText("正在生成...")

        font_size = self.spin_font_size.value()
        font_path = self.combo_font.currentData()
        duration = self.spin_duration.value()
        margin = self.spin_margin.value()
        zoom_factor = self.spin_zoom.value()
        transition_effect = self.combo_transition.currentData()

        # New Params
        width = self.spin_width.value()
        height = self.spin_height.value()
        resolution = (width, height)
        bg_color = self.current_bg_color

        audio_path = None
        if self.generated_audio_path and os.path.exists(self.generated_audio_path):
             audio_path = self.generated_audio_path

        self.worker = VideoWorker(
            self.selected_images,
            text,
            output_path,
            duration=duration,
            resolution=resolution,
            font_size=font_size,
            font_path=font_path,
            bottom_margin=margin,
            zoom_factor=zoom_factor,
            transition_effect=transition_effect,
            audio_path=audio_path,
            bg_color=bg_color
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
