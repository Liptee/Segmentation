import os
import cv2
import uuid
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider,
    QProgressBar, QListWidget, QListWidgetItem,
    QSplitter, QFileDialog, QMessageBox, QDialog,  QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QUrl, QRect
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from gui.video_player import ClickableVideoWidget
from gui.utils import convert_np_to_qimage, ms_to_str
from logger import logger
from core.effects import (
    SaveEveryNFrameEffect,
    BrightnessEffect,
    GaussianBlurEffect,
    CropFrameEffect,
    ChangeResolutionEffect,
    ChangeScaleEffect
)


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
            
        q_img = convert_np_to_qimage(frame)
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

class UnifiedVideoSlider(QWidget):
    """Custom slider widget that shows current position, trim start and trim end on a single control"""
    # Signals
    positionChanged = pyqtSignal(int)  # Current position changed (ms)
    trimPointsChanged = pyqtSignal(int, int)  # Trim start and end points changed (ms)
    
    # Constants for handle types
    POSITION_HANDLE = 0
    START_HANDLE = 1
    END_HANDLE = 2
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(50)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        
        # Slider values
        self.duration = 1000  # Default duration in ms
        self.position = 0     # Current position in ms
        self.start_trim = 0   # Trim start in ms
        self.end_trim = 1000  # Trim end in ms
        
        # UI state
        self.handle_radius = 8
        self.slider_height = 10
        self.active_handle = None
        self.hover_handle = None
        self.hover_pos = None
        self.dragging = False
        
        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
    
    def set_range(self, min_value, max_value):
        """Set the range for the slider"""
        self.start_trim = min_value
        self.end_trim = max_value
        self.duration = max_value
        self.update()
        
    def set_position(self, position):
        """Set the current position value"""
        if position != self.position:
            self.position = max(0, min(position, self.duration))
            self.update()
    
    def set_trim_points(self, start, end):
        """Set the trim start and end points"""
        if start > end:
            start, end = end, start
            
        self.start_trim = max(0, min(start, self.duration))
        self.end_trim = max(0, min(end, self.duration))
        self.update()
        
    def get_trim_points(self):
        """Get the current trim points"""
        return self.start_trim, self.end_trim
    
    def paintEvent(self, event):
        """Draw the custom slider and handles"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Calculate dimensions
        width = self.width()
        height = self.height()
        slider_y = (height - self.slider_height) // 2
        
        # Draw the slider track
        track_rect = QRect(self.handle_radius, slider_y, 
                            width - 2 * self.handle_radius, self.slider_height)
        
        # Draw background track
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(80, 80, 80))  # Dark gray for background
        painter.drawRoundedRect(track_rect, 4, 4)
        
        # Draw the highlighted area between trim points
        if self.start_trim < self.end_trim:
            start_x = self._value_to_position(self.start_trim)
            end_x = self._value_to_position(self.end_trim)
            
            highlight_rect = QRect(start_x, slider_y, end_x - start_x, self.slider_height)
            painter.setBrush(QColor(120, 120, 220))  # Blue for active range
            painter.drawRoundedRect(highlight_rect, 2, 2)
        
        # Draw the position handle (gray dot)
        pos_x = self._value_to_position(self.position)
        painter.setPen(QPen(Qt.darkGray, 1))
        painter.setBrush(QColor(180, 180, 180))  # Gray
        pos_rect = QRect(pos_x - self.handle_radius, slider_y + self.slider_height//2 - self.handle_radius,
                         self.handle_radius*2, self.handle_radius*2)
        painter.drawEllipse(pos_rect)
        
        # Draw the trim start handle (black vertical rectangle)
        start_x = self._value_to_position(self.start_trim)
        start_rect = QRect(start_x - 3, slider_y - 5, 6, self.slider_height + 10)
        painter.setPen(QPen(Qt.black, 1))
        painter.setBrush(QColor(0, 0, 0))  # Black
        painter.drawRect(start_rect)
        
        # Draw the trim end handle (white vertical rectangle)
        end_x = self._value_to_position(self.end_trim)
        end_rect = QRect(end_x - 3, slider_y - 5, 6, self.slider_height + 10)
        painter.setPen(QPen(Qt.black, 1))
        painter.setBrush(QColor(255, 255, 255))  # White
        painter.drawRect(end_rect)
        
        # Draw hover effect
        if self.hover_handle is not None and not self.dragging:
            painter.setPen(QPen(QColor(255, 255, 0), 2))  # Yellow highlight
            if self.hover_handle == self.POSITION_HANDLE:
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(pos_rect.adjusted(-2, -2, 2, 2))
            elif self.hover_handle == self.START_HANDLE:
                painter.drawRect(start_rect.adjusted(-2, -2, 2, 2))
            elif self.hover_handle == self.END_HANDLE:
                painter.drawRect(end_rect.adjusted(-2, -2, 2, 2))
    
    def _value_to_position(self, value):
        """Convert a value in ms to an x position on the slider"""
        width = self.width() - 2 * self.handle_radius
        if self.duration <= 0:
            return self.handle_radius
        ratio = value / self.duration
        return int(self.handle_radius + ratio * width)
    
    def _position_to_value(self, pos):
        """Convert an x position on the slider to a value in ms"""
        width = self.width() - 2 * self.handle_radius
        adjusted_pos = max(0, min(width, pos - self.handle_radius))
        ratio = adjusted_pos / width
        return int(ratio * self.duration)
    
    def _get_handle_at_position(self, pos):
        """Determine which handle is at the given position"""
        pos_x = self._value_to_position(self.position)
        start_x = self._value_to_position(self.start_trim)
        end_x = self._value_to_position(self.end_trim)
        
        # Check which handle is closest to the click position, prioritizing the one under cursor
        distances = [
            (abs(pos.x() - pos_x), self.POSITION_HANDLE),
            (abs(pos.x() - start_x), self.START_HANDLE),
            (abs(pos.x() - end_x), self.END_HANDLE)
        ]
        
        # Sort by distance
        distances.sort(key=lambda x: x[0])
        
        # If within the hover threshold, return the handle
        if distances[0][0] <= self.handle_radius * 2:
            return distances[0][1]
        
        return None
    
    def mousePressEvent(self, event):
        """Handle mouse press events to start dragging"""
        if event.button() == Qt.LeftButton:
            self.active_handle = self._get_handle_at_position(event.pos())
            if self.active_handle is not None:
                self.dragging = True
                # If no specific handle was clicked, move the position
                if self.active_handle is None:
                    self.active_handle = self.POSITION_HANDLE
                    new_pos = self._position_to_value(event.pos().x())
                    self.set_position(new_pos)
                    self.positionChanged.emit(self.position)
            else:
                # If clicked elsewhere on the slider, move position directly
                new_pos = self._position_to_value(event.pos().x())
                self.set_position(new_pos)
                self.positionChanged.emit(self.position)
                
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events for dragging and hover effects"""
        if self.dragging and self.active_handle is not None:
            value = self._position_to_value(event.pos().x())
            
            if self.active_handle == self.POSITION_HANDLE:
                self.set_position(value)
                self.positionChanged.emit(self.position)
            elif self.active_handle == self.START_HANDLE:
                self.start_trim = min(value, self.end_trim)
                self.trimPointsChanged.emit(self.start_trim, self.end_trim)
                self.update()
            elif self.active_handle == self.END_HANDLE:
                self.end_trim = max(value, self.start_trim)
                self.trimPointsChanged.emit(self.start_trim, self.end_trim)
                self.update()
        else:
            # Update hover state
            self.hover_handle = self._get_handle_at_position(event.pos())
            self.hover_pos = event.pos()
            self.update()
            
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events to stop dragging"""
        if event.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            self.active_handle = None
            
        super().mouseReleaseEvent(event)
    
    def leaveEvent(self, event):
        """Handle mouse leave events to clear hover state"""
        self.hover_handle = None
        self.hover_pos = None
        self.update()
        super().leaveEvent(event)

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
        video_container = QWidget()
        video_layout = QVBoxLayout(video_container)
        
        # Use QMediaPlayer and ClickableVideoWidget for video playback
        self.mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.videoWidget = ClickableVideoWidget()
        self.videoWidget.clicked.connect(self.toggle_play)
        self.videoWidget.setMinimumSize(320, 240)
        self.videoWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.mediaPlayer.setVideoOutput(self.videoWidget)
        video_layout.addWidget(self.videoWidget)
        
        # Connect media player signals
        self.mediaPlayer.positionChanged.connect(self.position_changed)
        self.mediaPlayer.durationChanged.connect(self.duration_changed)
        self.mediaPlayer.stateChanged.connect(self.media_state_changed)
        
        # Add unified video slider (combines position and trim controls)
        self.unified_slider = UnifiedVideoSlider()
        self.unified_slider.positionChanged.connect(self.set_position)
        self.unified_slider.trimPointsChanged.connect(self.on_trim_points_changed)
        video_layout.addWidget(self.unified_slider)
        
        # Player controls
        controls_layout = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.toggle_play)
        self.play_button.setMaximumWidth(60)
        
        self.position_label = QLabel("00:00 / 00:00")
        
        controls_layout.addWidget(self.play_button)
        controls_layout.addWidget(self.position_label)
        video_layout.addLayout(controls_layout)
        
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
        
    def load_video(self, video_path):
        """Load a video file"""
        self.video_path = video_path
        
        # Load video with QMediaPlayer
        self.mediaPlayer.setMedia(QMediaContent(QUrl.fromLocalFile(video_path)))
        
        # We still need OpenCV for frame extraction and metadata
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            QMessageBox.critical(self, "Error", f"Could not open video file: {video_path}")
            return False
            
        # Get metadata from OpenCV
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.duration_ms = int(self.frame_count * 1000 / self.fps) if self.fps > 0 else 0
        
        # Update unified slider range
        self.unified_slider.set_range(0, self.duration_ms)
        self.trim_start_ms = 0
        self.trim_end_ms = self.duration_ms
        
        # Reset position
        self.update_position_label(0, self.duration_ms)
        
        # Load first frame for preview
        frame = self.get_frame_at_position(0)
        if frame is not None:
            self.preview_frame = frame.copy()
            self.frame_preview.set_frame(frame)
        
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
        
        # If current position is outside the trim range, reset it
        current_pos = self.mediaPlayer.position()
        if current_pos < start_ms or current_pos > end_ms:
            self.mediaPlayer.setPosition(start_ms)
    
    def set_position(self, position):
        """Set the video position in milliseconds"""
        self.mediaPlayer.setPosition(position)
    
    def toggle_play(self):
        """Toggle video playback"""
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.mediaPlayer.pause()
        else:
            # If we're at or past the trim end, reset to trim start
            if self.mediaPlayer.position() >= self.trim_end_ms:
                self.mediaPlayer.setPosition(self.trim_start_ms)
            self.mediaPlayer.play()
    
    def position_changed(self, position):
        """Handle QMediaPlayer position changes"""
        # Update unified slider
        self.unified_slider.set_position(position)
        self.update_position_label(position, self.mediaPlayer.duration())
        
        # Handle trim points
        if position >= self.trim_end_ms:
            self.mediaPlayer.pause()
            self.mediaPlayer.setPosition(self.trim_start_ms)
            # Can automatically restart from trim start
            # self.mediaPlayer.play()
    
    def duration_changed(self, duration):
        """Handle QMediaPlayer duration changes"""
        self.unified_slider.set_range(0, duration)
        self.update_position_label(self.mediaPlayer.position(), duration)
    
    def update_position_label(self, position, duration):
        """Update the position/duration label"""
        position_str = ms_to_str(position)
        duration_str = ms_to_str(duration)
        self.position_label.setText(f"{position_str} / {duration_str}")
    
    def get_frame_at_position(self, position_ms):
        """Get a frame at specified position using OpenCV"""
        if not self.cap or not self.video_path:
            return None
            
        # Convert position from ms to frame number
        frame_pos = int((position_ms / 1000.0) * self.fps)
        
        # Seek to the position and read the frame
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
        ret, frame = self.cap.read()
        
        if ret:
            # Convert BGR to RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return frame
        return None
    
    def set_current_frame_to_preview(self):
        """Set the current frame from the video player as the preview frame"""
        if not self.video_path:
            return
            
        # Get current position from QMediaPlayer
        position_ms = self.mediaPlayer.position()
        
        # Get frame using OpenCV
        frame = self.get_frame_at_position(position_ms)
        
        if frame is not None:
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
            
            # Emit signal with extracted frame paths
            self.framesExtracted.emit(extracted_frames)
            
            # Show message
            QMessageBox.information(
                self, 
                "Extraction Complete", 
                f"Extracted {len(extracted_frames)} frames to {output_subdir}"
            )
            
            # Import frames to MediaImporter if not already connected
            self.import_to_media_importer(extracted_frames)
        
        # Start the extraction process
        QTimer.singleShot(0, extract_batch)
    
    def import_to_media_importer(self, frame_paths):
        """Import extracted frames to MediaImporter if possible"""
        if not frame_paths:
            return
            
        # Check if we're running as a standalone app or from within the media_importer
        from gui.media_importer import MediaImporterWidget
        
        # Look for a MediaImporterWidget in the parent chain
        parent = self.parent()
        media_importer = None
        
        # Try to find MediaImporterWidget in parent chain
        while parent:
            if isinstance(parent, MediaImporterWidget):
                media_importer = parent
                break
            parent = parent.parent()
            
        # If we're running standalone or media_importer not found in parent chain
        if media_importer is None:
            # In PyQt5 we can't directly check if signal has receivers
            # Instead, we'll create a new MediaImporter to show the extracted frames
            # if we're running standalone
            
            # Check if this is likely a standalone run (windowTitle would be set in this case)
            if "Extractor" in self.windowTitle():
                # Create a temporary media importer to show the extracted frames
                media_importer = MediaImporterWidget()
                media_importer.setWindowTitle("Extracted Frames")
                media_importer.resize(800, 600)
                
                # Import the frames
                media_importer.import_extracted_frames(frame_paths)
                
                # Show the media importer
                media_importer.show()
    
    def closeEvent(self, event):
        """Clean up resources when widget is closed"""
        # Cleanup OpenCV resources
        if self.cap:
            self.cap.release()
        
        # Cleanup QMediaPlayer
        self.mediaPlayer.stop()
        
        super().closeEvent(event)

    def media_state_changed(self, state):
        """Handle QMediaPlayer state changes"""
        if state == QMediaPlayer.PlayingState:
            self.play_button.setText("Pause")
        else:
            self.play_button.setText("Play")
        
        # Show overlay icon in video widget
        self.videoWidget.showOverlayIcon(state)


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    widget = VideoExtractorWidget()
    widget.setWindowTitle("Video Frame Extractor")
    widget.resize(1200, 800)
    widget.show()
    
    sys.exit(app.exec_()) 