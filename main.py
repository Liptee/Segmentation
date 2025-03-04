from gui.video_player import VideoPlayer
from gui.class_manager import SegmentationClassManagerWidget
from gui.media_importer import MediaImporterWidget
from gui.image_viewer import ImageViewerWidget
import sys
from PyQt5.QtWidgets import QApplication

app = QApplication(sys.argv)

# Создаем и запускаем оба виджета
player = VideoPlayer()
player.setWindowTitle("VideoPlayer")
player.resize(800, 600)
player.show()

widget = SegmentationClassManagerWidget()
widget.show()

import_widget = MediaImporterWidget()
import_widget.show()

image_viewer_widget = ImageViewerWidget()
image_viewer_widget.load_image("/Users/mac/Pictures/IMG_20240425_010855.jpeg")
image_viewer_widget.show()


sys.exit(app.exec_())
