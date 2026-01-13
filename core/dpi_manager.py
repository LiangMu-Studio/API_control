"""DPI自适应管理器 - 处理不同分辨率的自动缩放"""

import ctypes


class DPIManager:
    """DPI管理器 - 统一处理分辨率自适应"""

    # 标准DPI（96 DPI = 100%）
    STANDARD_DPI = 96

    @staticmethod
    def get_dpi_scale() -> float:
        """获取DPI缩放比例"""
        try:
            # Windows API 获取 DPI
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            dc = user32.GetDC(0)
            gdi32 = ctypes.windll.gdi32
            dpi = gdi32.GetDeviceCaps(dc, 88)  # LOGPIXELSX = 88
            user32.ReleaseDC(0, dc)
            return dpi / DPIManager.STANDARD_DPI
        except Exception:
            return 1.0

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
        try:
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            width = user32.GetSystemMetrics(0)  # SM_CXSCREEN
            height = user32.GetSystemMetrics(1)  # SM_CYSCREEN
            dc = user32.GetDC(0)
            gdi32 = ctypes.windll.gdi32
            dpi = gdi32.GetDeviceCaps(dc, 88)
            user32.ReleaseDC(0, dc)
            return {
                'width': width,
                'height': height,
                'dpi': dpi,
                'scale': dpi / DPIManager.STANDARD_DPI,
            }
        except Exception:
            return {}
