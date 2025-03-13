import os
import cv2
import numpy as np
import tempfile
import uuid
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider, QComboBox,
    QProgressBar, QCheckBox, QSpinBox, QDoubleSpinBox, QListWidget, QListWidgetItem,
    QGroupBox, QSplitter, QFileDialog, QMessageBox, QScrollArea, QFormLayout, QDialog,
    QToolButton, QFrame, QMenu, QAction, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QRectF, QSize, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QPixmap, QImage, QIcon, QPainter, QPen, QColor

from gui.video_player import VideoPlayer, ClickableVideoWidget
from logger import logger

class EffectBase:
    """Base class for all effects that can be applied to frames"""
    def __init__(self, name, params=None):
        self.name = name
        self.params = params or {}
        
    def apply(self, frame):
        """Apply the effect to the given frame (numpy array) and return the result"""
        # To be implemented by subclasses
        return frame
        
    def get_ui_widget(self, parent=None):
        """Return a widget that allows configuring this effect's parameters"""
        # To be implemented by subclasses
        widget = QWidget(parent)
        layout = QFormLayout(widget)
        layout.addRow(QLabel("No parameters for this effect"))
        return widget
        
    def update_params(self, params):
        """Update the parameters for this effect"""
        self.params = params
        
    def __str__(self):
        """String representation of the effect for display"""
        return self.name

class SaveEveryNFrameEffect(EffectBase):
    """Effect to extract only every Nth frame"""
    def __init__(self, params=None):
        default_params = {"n": 1}
        if params:
            default_params.update(params)
        super().__init__("Save every n frame", default_params)
        
    def apply(self, frame):
        # This effect doesn't modify the frame, it just controls which frames are saved
        return frame
        
    def get_ui_widget(self, parent=None):
        widget = QWidget(parent)
        layout = QFormLayout(widget)
        
        n_spin = QSpinBox()
        n_spin.setMinimum(1)
        n_spin.setMaximum(1000)
        n_spin.setValue(self.params.get("n", 1))
        n_spin.valueChanged.connect(lambda value: self.update_params({"n": value}))
        
        layout.addRow("Extract every n frames:", n_spin)
        return widget
        
    def __str__(self):
        return f"Save every {self.params.get('n', 1)} frame"

class BrightnessEffect(EffectBase):
    """Effect to adjust brightness of frames"""
    def __init__(self, params=None):
        default_params = {"value": 0.0}
        if params:
            default_params.update(params)
        super().__init__("Brightness", default_params)
        
    def apply(self, frame):
        # Adjust brightness (-1.0 to 1.0)
        value = self.params.get("value", 0.0)
        if value > 0:
            return cv2.convertScaleAbs(frame, alpha=1, beta=value*255)
        else:
            return cv2.convertScaleAbs(frame, alpha=1+value, beta=0)
        
    def get_ui_widget(self, parent=None):
        widget = QWidget(parent)
        layout = QFormLayout(widget)
        
        value_spin = QDoubleSpinBox()
        value_spin.setMinimum(-1.0)
        value_spin.setMaximum(1.0)
        value_spin.setSingleStep(0.1)
        value_spin.setValue(self.params.get("value", 0.0))
        value_spin.valueChanged.connect(lambda value: self.update_params({"value": value}))
        
        layout.addRow("Brightness (-1 to 1):", value_spin)
        return widget
        
    def __str__(self):
        value = self.params.get("value", 0.0)
        return f"Brightness: {value:+.1f}"

class GaussianBlurEffect(EffectBase):
    """Effect to apply Gaussian blur to frames"""
    def __init__(self, params=None):
        default_params = {"kernel_size": 5, "sigma": 1.0}
        if params:
            default_params.update(params)
        super().__init__("Gaussian Blur", default_params)
        
    def apply(self, frame):
        kernel_size = self.params.get("kernel_size", 5)
        # Make sure kernel size is odd
        if kernel_size % 2 == 0:
            kernel_size += 1
        
        sigma = self.params.get("sigma", 1.0)
        return cv2.GaussianBlur(frame, (kernel_size, kernel_size), sigma)
        
    def get_ui_widget(self, parent=None):
        widget = QWidget(parent)
        layout = QFormLayout(widget)
        
        kernel_spin = QSpinBox()
        kernel_spin.setMinimum(3)
        kernel_spin.setMaximum(31)
        kernel_spin.setSingleStep(2)
        kernel_spin.setValue(self.params.get("kernel_size", 5))
        # Make sure kernel size is always odd
        kernel_spin.valueChanged.connect(lambda value: 
            self.update_params({"kernel_size": value if value % 2 == 1 else value + 1}))
        
        sigma_spin = QDoubleSpinBox()
        sigma_spin.setMinimum(0.1)
        sigma_spin.setMaximum(10.0)
        sigma_spin.setSingleStep(0.1)
        sigma_spin.setValue(self.params.get("sigma", 1.0))
        sigma_spin.valueChanged.connect(lambda value: self.update_params({"sigma": value}))
        
        layout.addRow("Kernel size:", kernel_spin)
        layout.addRow("Sigma:", sigma_spin)
        return widget
        
    def __str__(self):
        kernel = self.params.get("kernel_size", 5)
        sigma = self.params.get("sigma", 1.0)
        return f"Gaussian Blur: {kernel}x{kernel}, σ={sigma:.1f}"

class CropFrameEffect(EffectBase):
    """Effect to crop frames"""
    def __init__(self, params=None):
        default_params = {"x_min": 0, "y_min": 0, "x_max": 100, "y_max": 100}
        if params:
            default_params.update(params)
        super().__init__("Crop Frame", default_params)
        self.original_frame_shape = None
        
    def apply(self, frame):
        # Store original frame shape if not set
        if self.original_frame_shape is None:
            self.original_frame_shape = frame.shape
            
        h, w = frame.shape[:2]
        x_min = int(w * self.params.get("x_min", 0) / 100)
        y_min = int(h * self.params.get("y_min", 0) / 100)
        x_max = int(w * self.params.get("x_max", 100) / 100)
        y_max = int(h * self.params.get("y_max", 100) / 100)
        
        return frame[y_min:y_max, x_min:x_max]
        
    def get_ui_widget(self, parent=None):
        widget = QWidget(parent)
        layout = QFormLayout(widget)
        
        x_min_spin = QSpinBox()
        x_min_spin.setMinimum(0)
        x_min_spin.setMaximum(99)
        x_min_spin.setValue(self.params.get("x_min", 0))
        x_min_spin.valueChanged.connect(lambda value: self.update_params({"x_min": value}))
        
        y_min_spin = QSpinBox()
        y_min_spin.setMinimum(0)
        y_min_spin.setMaximum(99)
        y_min_spin.setValue(self.params.get("y_min", 0))
        y_min_spin.valueChanged.connect(lambda value: self.update_params({"y_min": value}))
        
        x_max_spin = QSpinBox()
        x_max_spin.setMinimum(1)
        x_max_spin.setMaximum(100)
        x_max_spin.setValue(self.params.get("x_max", 100))
        x_max_spin.valueChanged.connect(lambda value: self.update_params({"x_max": value}))
        
        y_max_spin = QSpinBox()
        y_max_spin.setMinimum(1)
        y_max_spin.setMaximum(100)
        y_max_spin.setValue(self.params.get("y_max", 100))
        y_max_spin.valueChanged.connect(lambda value: self.update_params({"y_max": value}))
        
        layout.addRow("X min (%):", x_min_spin)
        layout.addRow("Y min (%):", y_min_spin)
        layout.addRow("X max (%):", x_max_spin)
        layout.addRow("Y max (%):", y_max_spin)
        return widget
        
    def __str__(self):
        x_min = self.params.get("x_min", 0)
        y_min = self.params.get("y_min", 0)
        x_max = self.params.get("x_max", 100)
        y_max = self.params.get("y_max", 100)
        return f"Crop: ({x_min}%,{y_min}%) to ({x_max}%,{y_max}%)"

class ChangeResolutionEffect(EffectBase):
    """Effect to change resolution of frames"""
    def __init__(self, params=None):
        default_params = {"width": 640, "height": 480}
        if params:
            default_params.update(params)
        super().__init__("Change Resolution", default_params)
        
    def apply(self, frame):
        width = self.params.get("width", 640)
        height = self.params.get("height", 480)
        return cv2.resize(frame, (width, height))
        
    def get_ui_widget(self, parent=None):
        widget = QWidget(parent)
        layout = QFormLayout(widget)
        
        width_spin = QSpinBox()
        width_spin.setMinimum(1)
        width_spin.setMaximum(4096)
        width_spin.setValue(self.params.get("width", 640))
        width_spin.valueChanged.connect(lambda value: self.update_params({"width": value}))
        
        height_spin = QSpinBox()
        height_spin.setMinimum(1)
        height_spin.setMaximum(4096)
        height_spin.setValue(self.params.get("height", 480))
        height_spin.valueChanged.connect(lambda value: self.update_params({"height": value}))
        
        layout.addRow("Width:", width_spin)
        layout.addRow("Height:", height_spin)
        return widget
        
    def __str__(self):
        width = self.params.get("width", 640)
        height = self.params.get("height", 480)
        return f"Resolution: {width}x{height}"

class ChangeScaleEffect(EffectBase):
    """Effect to scale frames"""
    def __init__(self, params=None):
        default_params = {"scale": 0.5, "interpolation": cv2.INTER_LINEAR}
        if params:
            default_params.update(params)
        super().__init__("Change Scale", default_params)
        
    def apply(self, frame):
        scale = self.params.get("scale", 0.5)
        interpolation = self.params.get("interpolation", cv2.INTER_LINEAR)
        h, w = frame.shape[:2]
        new_size = (int(w * scale), int(h * scale))
        return cv2.resize(frame, new_size, interpolation=interpolation)
        
    def get_ui_widget(self, parent=None):
        widget = QWidget(parent)
        layout = QFormLayout(widget)
        
        scale_spin = QDoubleSpinBox()
        scale_spin.setMinimum(0.1)
        scale_spin.setMaximum(10.0)
        scale_spin.setSingleStep(0.1)
        scale_spin.setValue(self.params.get("scale", 0.5))
        scale_spin.valueChanged.connect(lambda value: self.update_params({"scale": value}))
        
        interp_combo = QComboBox()
        interp_combo.addItem("Nearest Neighbor", cv2.INTER_NEAREST)
        interp_combo.addItem("Bilinear", cv2.INTER_LINEAR)
        interp_combo.addItem("Bicubic", cv2.INTER_CUBIC)
        interp_combo.addItem("Lanczos", cv2.INTER_LANCZOS4)
        
        # Set current index based on saved interpolation
        current_interp = self.params.get("interpolation", cv2.INTER_LINEAR)
        for i in range(interp_combo.count()):
            if interp_combo.itemData(i) == current_interp:
                interp_combo.setCurrentIndex(i)
                break
                
        interp_combo.currentIndexChanged.connect(
            lambda index: self.update_params({"interpolation": interp_combo.itemData(index)})
        )
        
        layout.addRow("Scale factor:", scale_spin)
        layout.addRow("Interpolation:", interp_combo)
        return widget
        
    def __str__(self):
        scale = self.params.get("scale", 0.5)
        interp_names = {
            cv2.INTER_NEAREST: "Nearest",
            cv2.INTER_LINEAR: "Bilinear",
            cv2.INTER_CUBIC: "Bicubic",
            cv2.INTER_LANCZOS4: "Lanczos"
        }
        interp = interp_names.get(self.params.get("interpolation", cv2.INTER_LINEAR), "Unknown")
        return f"Scale: {scale:.1f}x ({interp})"

class EffectListWidget(QListWidget):
    """Widget for displaying and managing a list of effects"""
    effectDoubleClicked = pyqtSignal(int)  # Signal emitted when an effect is double-clicked
    effectOrderChanged = pyqtSignal()      # Signal emitted when effects are reordered
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QListWidget.InternalMove)
        self.setSelectionMode(QListWidget.SingleSelection)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.model().rowsMoved.connect(lambda: self.effectOrderChanged.emit())
        
    def _on_item_double_clicked(self, item):
        row = self.row(item)
        self.effectDoubleClicked.emit(row)
        
    def add_effect(self, effect):
        """Add an effect to the list"""
        item = QListWidgetItem(str(effect))
        item.setData(Qt.UserRole, effect)
        self.addItem(item)
        
    def remove_selected_effect(self):
        """Remove the selected effect from the list"""
        selected_items = self.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            row = self.row(item)
            self.takeItem(row)
        self.effectOrderChanged.emit()
        
    def get_effects(self):
        """Return a list of all effects in the current order"""
        effects = []
        for i in range(self.count()):
            item = self.item(i)
            effect = item.data(Qt.UserRole)
            effects.append(effect)
        return effects
        
    def update_effect_display(self, row):
        """Update the display text for an effect after parameters have changed"""
        if 0 <= row < self.count():
            item = self.item(row)
            effect = item.data(Qt.UserRole)
            item.setText(str(effect))

class FramePreviewWidget(QLabel):
    """Widget for displaying a preview of a video frame with optional effects"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background-color: #1e1e1e; border: 1px solid #444;")
        self.setText("No preview available")
        
    def set_frame(self, frame):
        """Set the frame to display (numpy array)"""
        if frame is None:
            self.clear()
            self.setText("No preview available")
            return
            
        # Convert the frame to QImage and then to QPixmap
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        # Convert NumPy array to bytes for QImage
        frame_data = frame.tobytes()
        q_img = QImage(frame_data, width, height, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        
        # Scale the pixmap to fit the label while maintaining aspect ratio
        scaled_pixmap = pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(scaled_pixmap)
        
    def clear(self):
        """Clear the preview"""
        super().clear()
        self.setText("No preview available")
        
    def resizeEvent(self, event):
        """Handle resize events to update the preview scaling"""
        if self.pixmap():
            pixmap = self.pixmap()
            scaled_pixmap = pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(scaled_pixmap)
        super().resizeEvent(event)

class TrimSlider(QWidget):
    """Custom slider widget with trim points for selecting video segments"""
    trimPointsChanged = pyqtSignal(int, int)  # start, end in milliseconds
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(50)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Main slider for current position
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        
        # Trim point sliders
        self.start_slider = QSlider(Qt.Horizontal)
        self.start_slider.setRange(0, 0)
        self.start_slider.setStyleSheet("QSlider::handle { background: green; }")
        
        self.end_slider = QSlider(Qt.Horizontal)
        self.end_slider.setRange(0, 0)
        self.end_slider.setStyleSheet("QSlider::handle { background: red; }")
        
        layout.addWidget(self.position_slider)
        
        trim_layout = QHBoxLayout()
        trim_layout.addWidget(QLabel("Start:"))
        trim_layout.addWidget(self.start_slider)
        trim_layout.addWidget(QLabel("End:"))
        trim_layout.addWidget(self.end_slider)
        layout.addLayout(trim_layout)
        
        # Connect signals
        self.start_slider.valueChanged.connect(self._emit_trim_points)
        self.end_slider.valueChanged.connect(self._emit_trim_points)
        
    def set_range(self, min_value, max_value):
        """Set the range for all sliders"""
        self.position_slider.setRange(min_value, max_value)
        self.start_slider.setRange(min_value, max_value)
        self.end_slider.setRange(min_value, max_value)
        
        # Set default trim points to full range
        self.start_slider.setValue(min_value)
        self.end_slider.setValue(max_value)
        
    def set_position(self, position):
        """Set the current position slider value"""
        self.position_slider.setValue(position)
        
    def get_trim_points(self):
        """Get the current trim points"""
        return self.start_slider.value(), self.end_slider.value()
        
    def _emit_trim_points(self):
        """Emit signal when trim points change"""
        start = self.start_slider.value()
        end = self.end_slider.value()
        
        # Ensure start <= end
        if start > end:
            if self.sender() == self.start_slider:
                self.end_slider.setValue(start)
            else:
                self.start_slider.setValue(end)
            start, end = self.get_trim_points()
            
        self.trimPointsChanged.emit(start, end)

class VideoExtractorWidget(QWidget):
    """Main widget for extracting frames from videos with effects"""
    # Signal emitted when frames are extracted and saved
    framesExtracted = pyqtSignal(list)  # list of frame paths
    
    def __init__(self, video_path=None, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.effects = []
        self.preview_frame = None
        self.cap = None
        self.frame_count = 0
        self.fps = 0
        self.trim_start_ms = 0
        self.trim_end_ms = 0
        
        self.init_ui()
        
        # Load video if path is provided
        if video_path:
            self.load_video(video_path)
            
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Create a splitter for the four main areas
        main_splitter = QSplitter(Qt.Vertical)
        top_splitter = QSplitter(Qt.Horizontal)
        bottom_splitter = QSplitter(Qt.Horizontal)
        
        # === Top Left: Video Player ===
        # Instead of using a full VideoPlayer, we'll create a simpler video display
        video_container = QWidget()
        video_layout = QVBoxLayout(video_container)
        
        # Use a QLabel for video preview
        self.video_preview = QLabel("Video preview")
        self.video_preview.setAlignment(Qt.AlignCenter)
        self.video_preview.setMinimumSize(320, 240)
        self.video_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_preview.setStyleSheet("background-color: #1e1e1e; border: 1px solid #444;")
        video_layout.addWidget(self.video_preview)
        
        # Add trim slider 
        self.trim_slider = TrimSlider()
        self.trim_slider.trimPointsChanged.connect(self.on_trim_points_changed)
        video_layout.addWidget(self.trim_slider)
        
        # Add video position slider
        position_layout = QHBoxLayout()
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.set_position)
        
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.toggle_play)
        self.play_button.setMaximumWidth(60)
        
        self.position_label = QLabel("00:00 / 00:00")
        
        position_layout.addWidget(self.play_button)
        position_layout.addWidget(self.position_slider)
        position_layout.addWidget(self.position_label)
        video_layout.addLayout(position_layout)
        
        # Add "Set to Preview" button
        self.set_preview_btn = QPushButton("Set to Preview")
        self.set_preview_btn.clicked.connect(self.set_current_frame_to_preview)
        video_layout.addWidget(self.set_preview_btn)
        
        # === Top Right: Preview Panel ===
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        
        preview_label = QLabel("Preview with Effects")
        preview_label.setAlignment(Qt.AlignCenter)
        self.frame_preview = FramePreviewWidget()
        
        preview_layout.addWidget(preview_label)
        preview_layout.addWidget(self.frame_preview)
        
        # Add preview update button
        self.update_preview_btn = QPushButton("Update Preview")
        self.update_preview_btn.clicked.connect(self.update_preview)
        preview_layout.addWidget(self.update_preview_btn)
        
        # === Bottom Left: Processing Pipeline ===
        pipeline_container = QWidget()
        pipeline_layout = QVBoxLayout(pipeline_container)
        
        pipeline_label = QLabel("Processing Pipeline")
        pipeline_label.setAlignment(Qt.AlignCenter)
        
        # Effect list widget
        self.effect_list = EffectListWidget()
        self.effect_list.effectDoubleClicked.connect(self.edit_effect)
        self.effect_list.effectOrderChanged.connect(self.update_preview)
        
        # Buttons for pipeline management
        pipeline_buttons = QHBoxLayout()
        self.remove_effect_btn = QPushButton("Remove Effect")
        self.remove_effect_btn.clicked.connect(self.effect_list.remove_selected_effect)
        self.remove_effect_btn.clicked.connect(self.update_preview)
        
        pipeline_buttons.addWidget(self.remove_effect_btn)
        
        pipeline_layout.addWidget(pipeline_label)
        pipeline_layout.addWidget(self.effect_list)
        pipeline_layout.addLayout(pipeline_buttons)
        
        # === Bottom Right: Effects Selection ===
        effects_container = QWidget()
        effects_layout = QVBoxLayout(effects_container)
        
        effects_label = QLabel("Available Effects")
        effects_label.setAlignment(Qt.AlignCenter)
        
        # Create buttons for each available effect
        self.save_every_n_btn = QPushButton("Save every n frame")
        self.save_every_n_btn.clicked.connect(lambda: self.add_effect(SaveEveryNFrameEffect()))
        
        self.brightness_btn = QPushButton("Brightness")
        self.brightness_btn.clicked.connect(lambda: self.add_effect(BrightnessEffect()))
        
        self.gaussian_blur_btn = QPushButton("Gaussian Blur")
        self.gaussian_blur_btn.clicked.connect(lambda: self.add_effect(GaussianBlurEffect()))
        
        self.crop_frame_btn = QPushButton("Crop Frame")
        self.crop_frame_btn.clicked.connect(lambda: self.add_effect(CropFrameEffect()))
        
        self.change_resolution_btn = QPushButton("Change Resolution")
        self.change_resolution_btn.clicked.connect(lambda: self.add_effect(ChangeResolutionEffect()))
        
        self.change_scale_btn = QPushButton("Change Scale")
        self.change_scale_btn.clicked.connect(lambda: self.add_effect(ChangeScaleEffect()))
        
        effects_layout.addWidget(effects_label)
        effects_layout.addWidget(self.save_every_n_btn)
        effects_layout.addWidget(self.brightness_btn)
        effects_layout.addWidget(self.gaussian_blur_btn)
        effects_layout.addWidget(self.crop_frame_btn)
        effects_layout.addWidget(self.change_resolution_btn)
        effects_layout.addWidget(self.change_scale_btn)
        
        # Add containers to splitters
        top_splitter.addWidget(video_container)
        top_splitter.addWidget(preview_container)
        bottom_splitter.addWidget(pipeline_container)
        bottom_splitter.addWidget(effects_container)
        
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(bottom_splitter)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        # Extract button
        self.extract_btn = QPushButton("Extract Frames")
        self.extract_btn.clicked.connect(self.extract_frames)
        
        main_layout.addWidget(main_splitter)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.extract_btn)
        
        # Set initial splitter sizes
        top_splitter.setSizes([500, 500])
        bottom_splitter.setSizes([500, 500])
        main_splitter.setSizes([600, 400])
        
        # Video playback handling variables
        self.video_timer = QTimer(self)
        self.video_timer.timeout.connect(self.update_video_frame)
        self.is_playing = False
        self.current_position = 0
    
    def load_video(self, video_path):
        """Load a video file"""
        self.video_path = video_path
        
        # Open video with OpenCV to get metadata
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            QMessageBox.critical(self, "Error", f"Could not open video file: {video_path}")
            return False
            
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.duration_ms = int(self.frame_count * 1000 / self.fps) if self.fps > 0 else 0
        
        # Update trim slider and position slider
        self.trim_slider.set_range(0, self.duration_ms)
        self.trim_start_ms = 0
        self.trim_end_ms = self.duration_ms
        
        self.position_slider.setRange(0, self.duration_ms)
        self.position_slider.setValue(0)
        self.update_position_label(0, self.duration_ms)
        
        # Get first frame for preview
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.preview_frame = frame.copy()
            self.frame_preview.set_frame(frame)
            
            # Display first frame in video preview
            self.update_video_preview(frame)
        
        return True
    
    def add_effect(self, effect):
        """Add an effect to the pipeline"""
        self.effect_list.add_effect(effect)
        self.update_preview()
    
    def edit_effect(self, index):
        """Open a dialog to edit the effect at the given index"""
        if index < 0 or index >= self.effect_list.count():
            return
            
        item = self.effect_list.item(index)
        effect = item.data(Qt.UserRole)
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit {effect.name} Parameters")
        
        layout = QVBoxLayout(dialog)
        
        # Get the UI widget for this effect
        effect_widget = effect.get_ui_widget(dialog)
        layout.addWidget(effect_widget)
        
        # Add buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # Show dialog
        result = dialog.exec_()
        if result == QDialog.Accepted:
            # Update the effect display
            self.effect_list.update_effect_display(index)
            self.update_preview()
    
    def on_trim_points_changed(self, start_ms, end_ms):
        """Handle changes to trim points"""
        self.trim_start_ms = start_ms
        self.trim_end_ms = end_ms
    
    def update_video_preview(self, frame):
        """Update the video preview with the current frame"""
        if frame is None:
            return
            
        # Convert frame to QImage and QPixmap
        q_img = self.convert_np_to_qimage(frame)
        if q_img:
            pixmap = QPixmap.fromImage(q_img)
            scaled_pixmap = pixmap.scaled(
                self.video_preview.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.video_preview.setPixmap(scaled_pixmap)
    
    def set_position(self, position):
        """Set the video position in milliseconds"""
        self.current_position = position
        # Update slider
        self.position_slider.setValue(position)
        self.update_position_label(position, self.duration_ms)
        
        # Set the frame at this position
        if self.cap:
            frame_pos = int((position / 1000.0) * self.fps)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.update_video_preview(frame)
    
    def toggle_play(self):
        """Toggle video playback"""
        if self.is_playing:
            self.video_timer.stop()
            self.play_button.setText("Play")
        else:
            self.video_timer.start(33)  # ~30 fps
            self.play_button.setText("Pause")
        
        self.is_playing = not self.is_playing
    
    def update_video_frame(self):
        """Update the video frame during playback"""
        if not self.cap or not self.is_playing:
            return
            
        # If we've reached the end, restart from the beginning
        if self.current_position >= self.trim_end_ms:
            self.current_position = self.trim_start_ms
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, int((self.trim_start_ms / 1000.0) * self.fps))
        
        # Read the next frame
        ret, frame = self.cap.read()
        if not ret:
            self.toggle_play()  # Stop playing if we can't read a frame
            return
            
        # Convert frame to RGB
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Update the video preview
        self.update_video_preview(frame)
        
        # Update position
        self.current_position += int(1000 / self.fps)
        self.position_slider.setValue(self.current_position)
        self.update_position_label(self.current_position, self.duration_ms)
    
    def update_position_label(self, position, duration):
        """Update the position/duration label"""
        position_str = self.ms_to_str(position)
        duration_str = self.ms_to_str(duration)
        self.position_label.setText(f"{position_str} / {duration_str}")
    
    @staticmethod
    def ms_to_str(ms):
        """Convert milliseconds to a time string (MM:SS)"""
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def set_current_frame_to_preview(self):
        """Set the current frame from the video player as the preview frame"""
        if not self.video_path or not self.cap:
            return
            
        # Get the current frame based on position
        frame_position = int((self.current_position / 1000.0) * self.fps)
        
        # Seek to the position and read the frame
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_position)
        ret, frame = self.cap.read()
        
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.preview_frame = frame.copy()
            # Apply effects for preview
            self.update_preview()
    
    def update_preview(self):
        """Update the preview with the current frame and effects"""
        if self.preview_frame is None:
            return
            
        # Get a copy of the preview frame
        processed_frame = self.preview_frame.copy()
        
        # Apply all effects in order
        effects = self.effect_list.get_effects()
        for effect in effects:
            # Skip SaveEveryNFrameEffect in the preview as it doesn't modify the frame
            if isinstance(effect, SaveEveryNFrameEffect):
                continue
            processed_frame = effect.apply(processed_frame)
        
        # Update the preview widget
        self.frame_preview.set_frame(processed_frame)
    
    def extract_frames(self):
        """Extract frames from the video according to the settings"""
        if not self.video_path or not self.cap:
            QMessageBox.warning(self, "Warning", "No video loaded")
            return
            
        # Ask for output directory
        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if not output_dir:
            return
            
        # Get effects
        effects = self.effect_list.get_effects()
        
        # Find SaveEveryNFrameEffect if present
        n_frames = 1  # Default: extract every frame
        for effect in effects:
            if isinstance(effect, SaveEveryNFrameEffect):
                n_frames = effect.params.get("n", 1)
                break
        
        # Calculate frames to extract based on trim points
        start_frame = int(self.trim_start_ms / 1000.0 * self.fps)
        end_frame = int(self.trim_end_ms / 1000.0 * self.fps)
        
        # Ensure valid frame range
        start_frame = max(0, start_frame)
        end_frame = min(self.frame_count - 1, end_frame)
        
        # Number of frames to process
        frames_to_process = end_frame - start_frame + 1
        frames_to_extract = frames_to_process // n_frames
        if frames_to_extract == 0:
            QMessageBox.warning(self, "Warning", "No frames to extract with current settings")
            return
        
        # Create a unique subfolder
        timestamp = uuid.uuid4().hex[:8]
        output_subdir = os.path.join(output_dir, f"extracted_frames_{timestamp}")
        os.makedirs(output_subdir, exist_ok=True)
        
        # Prepare progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, frames_to_extract)
        self.progress_bar.setValue(0)
        self.extract_btn.setEnabled(False)
        
        # Extraction variables
        extracted_frames = []
        frame_number = 0
        progress_value = 0
        
        # Reset video position
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        
        # Use a timer for smoother UI updates
        def extract_batch():
            nonlocal frame_number, progress_value
            
            # Process a batch of frames
            batch_size = 10  # Process 10 frames per batch
            for _ in range(batch_size):
                if frame_number > end_frame - start_frame:
                    finish_extraction()
                    return
                
                ret, frame = self.cap.read()
                if not ret:
                    finish_extraction()
                    return
                
                # Extract only every n-th frame
                if frame_number % n_frames == 0:
                    # Process frame
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    processed_frame = frame.copy()
                    
                    # Apply effects (except SaveEveryNFrameEffect)
                    for effect in effects:
                        if not isinstance(effect, SaveEveryNFrameEffect):
                            processed_frame = effect.apply(processed_frame)
                    
                    # Save frame
                    output_path = os.path.join(output_subdir, f"frame_{frame_number + start_frame:06d}.png")
                    cv2.imwrite(output_path, cv2.cvtColor(processed_frame, cv2.COLOR_RGB2BGR))
                    extracted_frames.append(output_path)
                    
                    # Update progress
                    progress_value += 1
                    self.progress_bar.setValue(progress_value)
                
                frame_number += 1
            
            # Continue extracting if not finished
            if frame_number <= end_frame - start_frame:
                QTimer.singleShot(0, extract_batch)
        
        def finish_extraction():
            # Hide progress bar
            self.progress_bar.setVisible(False)
            self.extract_btn.setEnabled(True)
            
            # Show message
            QMessageBox.information(
                self, 
                "Extraction Complete", 
                f"Extracted {len(extracted_frames)} frames to {output_subdir}"
            )
            
            # Emit signal with extracted frame paths
            self.framesExtracted.emit(extracted_frames)
        
        # Start the extraction process
        QTimer.singleShot(0, extract_batch)
            
    def closeEvent(self, event):
        """Clean up resources when widget is closed"""
        if self.cap:
            self.cap.release()
        super().closeEvent(event)

    @staticmethod
    def convert_np_to_qimage(np_array):
        """Convert a numpy array to QImage"""
        if np_array is None:
            return None
        height, width, channels = np_array.shape
        assert channels == 3, "Ожидается массив с 3 каналами (RGB)"
        bytes_per_line = width * 3
        # Convert NumPy array to bytes for QImage
        frame_data = np_array.tobytes()
        image = QImage(frame_data, width, height, bytes_per_line, QImage.Format_RGB888)
        return image.copy()

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    widget = VideoExtractorWidget()
    widget.setWindowTitle("Video Frame Extractor")
    widget.resize(1200, 800)
    widget.show()
    
    sys.exit(app.exec_()) 