import cv2
from PyQt5.QtWidgets import QWidget, QFormLayout, QLabel, QSpinBox, QDoubleSpinBox, QComboBox


class EffectBase:
    """Базовый класс для всех эффектов, применяемых к кадрам"""
    def __init__(self, name, params=None):
        self.name = name
        self.params = params or {}

    def apply(self, frame):
        return frame

    def get_ui_widget(self, parent=None):
        widget = QWidget(parent)
        layout = QFormLayout(widget)
        layout.addRow(QLabel("Нет параметров для этого эффекта"))
        return widget

    def update_params(self, params):
        self.params = params

    def __str__(self):
        return self.name
    

class SaveEveryNFrameEffect(EffectBase):
    """Эффект для извлечения каждого n-го кадра"""
    def __init__(self, params=None):
        default_params = {"n": 1}
        if params:
            default_params.update(params)
        super().__init__("Save every n frame", default_params)

    def apply(self, frame):
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
    """Эффект для регулировки яркости кадра"""
    def __init__(self, params=None):
        default_params = {"value": 0.0}
        if params:
            default_params.update(params)
        super().__init__("Brightness", default_params)

    def apply(self, frame):
        value = self.params.get("value", 0.0)
        if value > 0:
            return cv2.convertScaleAbs(frame, alpha=1, beta=value * 255)
        else:
            return cv2.convertScaleAbs(frame, alpha=1 + value, beta=0)

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
    """Эффект для применения гауссового размытия"""
    def __init__(self, params=None):
        default_params = {"kernel_size": 5, "sigma": 1.0}
        if params:
            default_params.update(params)
        super().__init__("Gaussian Blur", default_params)

    def apply(self, frame):
        kernel_size = self.params.get("kernel_size", 5)
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
        kernel_spin.valueChanged.connect(lambda value: self.update_params({"kernel_size": value if value % 2 == 1 else value + 1}))
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
    """Эффект для обрезки кадра"""
    def __init__(self, params=None):
        default_params = {"x_min": 0, "y_min": 0, "x_max": 100, "y_max": 100}
        if params:
            default_params.update(params)
        super().__init__("Crop Frame", default_params)
        self.original_frame_shape = None

    def apply(self, frame):
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
    """Эффект для изменения разрешения кадра"""
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
    """Эффект для масштабирования кадра"""
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
        current_interp = self.params.get("interpolation", cv2.INTER_LINEAR)
        for i in range(interp_combo.count()):
            if interp_combo.itemData(i) == current_interp:
                interp_combo.setCurrentIndex(i)
                break
        interp_combo.currentIndexChanged.connect(lambda index: self.update_params({"interpolation": interp_combo.itemData(index)}))
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