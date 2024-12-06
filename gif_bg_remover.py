import sys
import os
import shutil
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QSlider,
    QMessageBox,
    QToolTip,
)
from PyQt5.QtGui import QPixmap, QImage, QColor, QCursor, QMovie, QIcon
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PIL import Image, ImageSequence
import tempfile

class InfoLabel(QLabel):
    def __init__(self, parent=None, tooltip_text="", icon_path="", size=(32, 32), delay=200):
        super().__init__(parent)
        self.tooltip_text = tooltip_text
        self.delay = delay  # Delay in milliseconds
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.show_tooltip)

        if icon_path and os.path.exists(icon_path):
            pixmap = QPixmap(icon_path).scaled(
                size[0],
                size[1],
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.setPixmap(pixmap)
        else:
            # Fallback to a default info symbol if info.png is missing
            self.setText("ℹ️")
            self.setAlignment(Qt.AlignCenter)

    def enterEvent(self, event):
        self.timer.start(self.delay)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.timer.stop()
        QToolTip.hideText()
        super().leaveEvent(event)

    def show_tooltip(self):
        # Position the tooltip above the info icon
        QToolTip.showText(
            self.mapToGlobal(self.rect().bottomLeft()),
            self.tooltip_text,
            self
        )

class GifLabel(QLabel):
    colorSelected = pyqtSignal(tuple)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.pixmap = None
        self.movie = None
        self.cursorOverImage = False

    def setPixmap(self, pixmap):
        super().setPixmap(pixmap)
        self.pixmap = pixmap

    def setMovie(self, movie):
        super().setMovie(movie)
        self.movie = movie

    def enterEvent(self, event):
        if self.pixmap or self.movie:
            self.cursorOverImage = True
            self.setCursor(QCursor(Qt.CrossCursor))
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.cursorOverImage = False
        self.unsetCursor()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self.cursorOverImage and (self.pixmap or self.movie):
            pos = event.pos()
            if self.movie:
                frame = self.movie.currentPixmap()
                image = frame.toImage()
                label_width = self.width()
                label_height = self.height()
                pixmap_width = frame.width()
                pixmap_height = frame.height()
            else:
                image = self.pixmap.toImage()
                label_width = self.width()
                label_height = self.height()
                pixmap_width = self.pixmap.width()
                pixmap_height = self.pixmap.height()

            if label_width == 0 or label_height == 0:
                return  # Prevent division by zero

            x_ratio = pixmap_width / label_width
            y_ratio = pixmap_height / label_height

            x = int(pos.x() * x_ratio)
            y = int(pos.y() * y_ratio)

            if x < 0 or y < 0 or x >= image.width() or y >= image.height():
                return

            color = image.pixelColor(x, y)
            self.colorSelected.emit((color.red(), color.green(), color.blue()))
        super().mousePressEvent(event)

class GifBackgroundRemover(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GIF Background Remover")

        # Set the window icon
        script_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        window_icon_path = os.path.join(script_dir, "icon.ico")
        self.setWindowIcon(QIcon(window_icon_path))  # Ensure the path is correct

        self.setStyleSheet(
            """
            QWidget {
                background-color: #282a36;
                color: #f8f8f2;
            }
            QPushButton {
                background-color: #44475a;
                color: #f8f8f2;
                border: none;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #6272a4;
            }
            QLabel {
                color: #f8f8f2;
            }
            QSlider::handle:horizontal {
                background-color: #6272a4;
                border: 1px solid #44475a;
                width: 20px;
                margin: -5px 0;
                border-radius: 3px;
            }
            QSlider::groove:horizontal {
                height: 10px;
                background: #44475a;
                border-radius: 5px;
            }
            """
        )

        # Initialize variables
        self.gif_path = None
        self.selected_color = None
        self.pixmap = None
        self.processed_gif_path = None
        self.movie = None

        # Create widgets
        self.gif_label = GifLabel(self)
        self.gif_label.setAlignment(Qt.AlignCenter)
        self.gif_label.colorSelected.connect(self.on_color_selected)

        self.open_button = QPushButton("Open GIF", self)
        self.open_button.clicked.connect(self.open_gif)

        self.process_button = QPushButton("Remove Background", self)
        self.process_button.clicked.connect(self.process_gif)
        self.process_button.hide()  # Hide initially

        self.save_button = QPushButton("Save Processed GIF", self)
        self.save_button.clicked.connect(self.save_gif)
        self.save_button.hide()  # Hide initially

        # Fuzz Slider and Label
        self.fuzz_label = QLabel("Fuzziness: 0%", self)
        self.fuzz_label.hide()  # Hide initially

        self.fuzz_slider = QSlider(Qt.Horizontal, self)
        self.fuzz_slider.setMinimum(0)
        self.fuzz_slider.setMaximum(100)
        self.fuzz_slider.setValue(0)
        self.fuzz_slider.setTickPosition(QSlider.TicksBelow)
        self.fuzz_slider.setTickInterval(10)
        self.fuzz_slider.hide()  # Hide initially

        self.fuzz_slider.valueChanged.connect(self.update_fuzz_label)

        # Info Icon (Using info.png with 200ms tooltip delay)
        info_icon_path = os.path.join(script_dir, "info.png")
        self.info_label = InfoLabel(
            parent=self,
            tooltip_text="Adjust the fuzziness percentage to remove slight gradients or shadows in the background.",
            icon_path=info_icon_path,
            size=(32, 32),
            delay=200  # Tooltip delay set to 200ms
        )
        self.info_label.hide()  # Hide initially

        # Layout setup
        button_layout = QVBoxLayout()
        button_layout.addWidget(self.open_button)

        # Fuzz Layout with Horizontal Arrangement
        fuzz_layout = QHBoxLayout()
        fuzz_layout.addWidget(self.fuzz_label)
        fuzz_layout.addWidget(self.fuzz_slider)
        fuzz_layout.addWidget(self.info_label)
        button_layout.addLayout(fuzz_layout)

        button_layout.addWidget(self.process_button)
        button_layout.addWidget(self.save_button)

        # Main Layout
        layout = QVBoxLayout()
        layout.addWidget(self.gif_label)
        layout.addLayout(button_layout)

        # Initialize status_label without using the walrus operator
        self.status_label = QLabel("", self)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setContentsMargins(-40, -40, -40, -40)
        layout.addWidget(self.status_label)

        self.setLayout(layout)

        # Initial window sizing
        self.set_initial_size()

    def set_initial_size(self):
        self.adjustSize()
        self.setMaximumSize(800, 600)  # Prevent excessive resizing
        self.move_center()

    def update_fuzz_label(self, value):
        self.fuzz_label.setText(f"Fuzziness: {value}%")

    def open_gif(self):
        options = QFileDialog.Options()
        self.gif_path, _ = QFileDialog.getOpenFileName(
            self, "Open GIF", "", "GIF Files (*.gif)", options=options
        )
        if self.gif_path:
            if self.movie:
                self.movie.stop()
                self.movie = None
                self.gif_label.setMovie(None)

            self.movie = QMovie(self.gif_path)
            self.gif_label.setMovie(self.movie)
            self.movie.start()
            self.selected_color = None

            # Get the first frame dimensions for resizing
            frame_pixmap = self.movie.currentPixmap()

            # Adjust window size based on GIF dimensions
            if frame_pixmap and not frame_pixmap.isNull():
                self.adjust_window_size(frame_pixmap)
            else:
                self.status_label.setText("Unable to load GIF dimensions for resizing.")

            # Update button visibility
            self.open_button.hide()
            self.process_button.show()
            self.save_button.hide()

            # Show fuzz slider and label
            self.fuzz_slider.show()
            self.fuzz_label.show()
            self.info_label.show()

            self.status_label.setText("Click a colour on the image to select the background colour.")

    def adjust_window_size(self, pixmap):
        max_dimension = 600
        pixmap_width = pixmap.width()
        pixmap_height = pixmap.height()

        # Calculate scaling factor
        scaling_factor = min(max_dimension / pixmap_width, max_dimension / pixmap_height, 1)

        # Calculate new size
        new_width = int(pixmap_width * scaling_factor)
        new_height = int(pixmap_height * scaling_factor)

        # If the pixmap is associated with QMovie, don't set it statically
        if not isinstance(self.movie, QMovie):
            # Scale the pixmap for static images
            scaled_pixmap = pixmap.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.gif_label.setPixmap(scaled_pixmap)

        # Calculate the required window size
        buttons_height = self.open_button.sizeHint().height() * 3 + 10  # Open, Process, Save buttons + spacing
        fuzz_height = self.fuzz_slider.sizeHint().height() + 10  # Fuzz slider and label
        total_height = new_height + buttons_height + fuzz_height + 50  # Additional space for margins and status label
        total_width = new_width + 50  # Additional space for margins

        # Adjust window size
        self.setMinimumSize(total_width, total_height)
        self.adjustSize()

        # Move window to keep it centered
        self.move_center()


    def move_center(self):
        # Get the screen geometry
        screen_geometry = QApplication.desktop().screenGeometry(self)
        # Calculate the center point
        center_point = screen_geometry.center()
        # Calculate the top-left point for the window to be centered
        window_geometry = self.frameGeometry()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

    def on_color_selected(self, color):
        self.selected_color = color
        self.status_label.setText(f"Selected color: {self.selected_color}")
        if self.gif_path and self.selected_color:
            self.process_button.setEnabled(True)

    def process_gif(self):
        if not self.gif_path or not self.selected_color:
            self.status_label.setText("Please select a color first.")
            return

        fuzz_percentage = self.fuzz_slider.value()
        self.status_label.setText("Processing GIF...")
        QApplication.processEvents()

        try:
            img = Image.open(self.gif_path)
            frames = []
            durations = []
            transparency_color = self.selected_color

            self.status_label.setText("Calculating GIF's overall bounding box...")
            QApplication.processEvents()

            min_x = img.width
            min_y = img.height
            max_x = 0
            max_y = 0

            temp_frames = []

            for frame in ImageSequence.Iterator(img):
                duration = frame.info.get("duration", 100)

                frame_rgba = frame.convert('RGBA')
                datas = frame_rgba.getdata()

                non_transparent_pixels = []

                new_data = []
                for index, item in enumerate(datas):
                    if self.color_within_fuzz(item[:3], transparency_color, fuzz_percentage):
                        new_data.append((0, 0, 0, 0))
                    else:
                        new_data.append(item)
                        x = index % frame_rgba.width
                        y = index // frame_rgba.width
                        non_transparent_pixels.append((x, y))

                frame_rgba.putdata(new_data)

                for x, y in non_transparent_pixels:
                    if x < min_x:
                        min_x = x
                    if x > max_x:
                        max_x = x
                    if y < min_y:
                        min_y = y
                    if y > max_y:
                        max_y = y

                temp_frames.append((frame_rgba, duration))

            if min_x > max_x or min_y > max_y:
                self.status_label.setText("All pixels are transparent after color removal.")
                QMessageBox.information(self, "Info", "All pixels are transparent after color removal.")
                return

            new_width = max_x - min_x + 1
            new_height = max_y - min_y + 1

            # Ensure the new canvas size is not larger than the original
            new_width = min(new_width, img.width)
            new_height = min(new_height, img.height)

            self.status_label.setText(f"New canvas size: {new_width}x{new_height}")
            QApplication.processEvents()

            self.status_label.setText("Cropping frames to the new canvas size...")
            QApplication.processEvents()

            processed_frames = []
            processed_durations = []

            for frame_rgba, duration in temp_frames:

                cropped_frame = frame_rgba.crop((min_x, min_y, max_x + 1, max_y + 1))

                frame_p = cropped_frame.convert('P', palette=Image.ADAPTIVE, colors=255)

                palette = frame_p.getpalette()

                palette[255 * 3:255 * 3 + 3] = transparency_color[:3]
                frame_p.putpalette(palette)

                frame_p_data = list(frame_p.getdata())
                pixels = cropped_frame.getdata()

                for i in range(len(frame_p_data)):
                    if pixels[i][3] == 0:
                        frame_p_data[i] = 255

                frame_p.putdata(frame_p_data)

                frame_p.info['transparency'] = 255

                processed_frames.append(frame_p)
                processed_durations.append(duration)

            self.status_label.setText("Saving processed frames...")
            QApplication.processEvents()

            temp_dir = tempfile.gettempdir()
            self.processed_gif_path = os.path.join(temp_dir, "temp_output.gif")
            processed_frames[0].save(
                self.processed_gif_path,
                save_all=True,
                append_images=processed_frames[1:],
                duration=processed_durations,
                loop=0,
                transparency=255,
                disposal=2,
            )

            if self.movie:
                self.movie.stop()
                self.movie = None
                self.gif_label.setMovie(None)

            self.movie = QMovie(self.processed_gif_path)
            self.gif_label.setMovie(self.movie)
            self.movie.start()

            # Update button visibility
            self.status_label.setText("Background removed.")
            self.save_button.show()
            self.process_button.hide()
            self.fuzz_slider.hide()
            self.fuzz_label.hide()
            self.info_label.hide()

            # Adjust window size
            self.adjustSize()
            self.move_center()

        except Exception as e:
            self.status_label.setText(f"Error processing GIF: {e}")
            QMessageBox.critical(self, "Error", f"Error processing GIF: {e}")

    def save_gif(self):
        if not self.processed_gif_path:
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Processed GIF", "output.gif", "GIF Files (*.gif)"
        )
        if not save_path:
            return

        if self.movie:
            self.movie.stop()
            self.movie = None
            self.gif_label.setMovie(None)

        try:
            shutil.copy(self.processed_gif_path, save_path)
            self.status_label.setText(f"Processed GIF saved as {save_path}")
            QMessageBox.information(self, "Success", f"Processed GIF saved as {save_path}")
        except Exception as e:
            self.status_label.setText(f"Error saving GIF: {e}")
            QMessageBox.critical(self, "Error", f"Error saving GIF: {e}")
            return

        try:
            os.remove(self.processed_gif_path)
        except PermissionError:
            self.status_label.setText("Unable to delete temporary file.")
            QMessageBox.warning(self, "Warning", "Unable to delete temporary file.")
            return

        self.processed_gif_path = None

        # Reset button visibility
        self.save_button.hide()
        self.open_button.show()

        # Hide fuzz slider and label
        self.fuzz_slider.hide()
        self.fuzz_label.hide()
        self.info_label.hide()

        # Adjust window size
        self.adjustSize()
        self.move_center()

    def closeEvent(self, event):
        if self.movie:
            self.movie.stop()
            self.movie = None
            self.gif_label.setMovie(None)

        if self.processed_gif_path and os.path.exists(self.processed_gif_path):
            try:
                os.remove(self.processed_gif_path)
            except PermissionError:
                pass
        event.accept()

    def color_within_fuzz(self, pixel_color, target_color, fuzz_percentage):
        """
        Determines if the pixel_color is within the fuzz_percentage of the target_color.
        """
        threshold = fuzz_percentage / 100 * 255  # Convert percentage to threshold
        r_diff = abs(pixel_color[0] - target_color[0])
        g_diff = abs(pixel_color[1] - target_color[1])
        b_diff = abs(pixel_color[2] - target_color[2])

        # Euclidean distance
        distance = (r_diff ** 2 + g_diff ** 2 + b_diff ** 2) ** 0.5
        return distance <= threshold

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GifBackgroundRemover()
    window.show()
    sys.exit(app.exec_())
