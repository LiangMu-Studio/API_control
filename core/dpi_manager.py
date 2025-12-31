"""DPI自适应管理器 - 处理不同分辨率的自动缩放"""

from PySide6.QtWidgets import QApplication


class DPIManager:
    """DPI管理器 - 统一处理分辨率自适应"""

    # 标准DPI（96 DPI = 100%）
    STANDARD_DPI = 96

    @staticmethod
    def get_dpi_scale() -> float:
        """获取DPI缩放比例"""
        app = QApplication.instance()
        if not app:
            return 1.0

        screen = app.primaryScreen()
        if not screen:
            return 1.0

        dpi = screen.logicalDotsPerInch()
        return dpi / DPIManager.STANDARD_DPI

    @staticmethod
    def scale_size(size: int) -> int:
        """缩放尺寸"""
        return int(size * DPIManager.get_dpi_scale())

    @staticmethod
    def scale_font_size(size: int) -> int:
        """缩放字体大小"""
        return int(size * DPIManager.get_dpi_scale())

    @staticmethod
    def get_screen_info() -> dict:
        """获取屏幕信息"""
        app = QApplication.instance()
        if not app:
            return {}

        screen = app.primaryScreen()
        if not screen:
            return {}

        geometry = screen.geometry()
        return {
            'width': geometry.width(),
            'height': geometry.height(),
            'dpi': screen.logicalDotsPerInch(),
            'scale': DPIManager.get_dpi_scale(),
            'physical_dpi': screen.physicalDotsPerInch(),
        }
