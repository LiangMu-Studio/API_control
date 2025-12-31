"""文件处理工具 - 支持图片压缩和文件读取"""

import base64
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image
import io


class FileHandler:
    """文件处理工具"""

    SUPPORTED_IMAGES = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    SUPPORTED_DOCUMENTS = {'.md', '.txt', '.pdf'}
    MAX_IMAGE_SIZE = (2048, 2048)

    @staticmethod
    def compress_image(file_path: str, quality: int = 85) -> Tuple[str, str]:
        """
        压缩图片并转换为 Base64

        Args:
            file_path: 图片文件路径
            quality: 压缩质量 (1-100)

        Returns:
            (base64_data, media_type)
        """
        path = Path(file_path)
        if path.suffix.lower() not in FileHandler.SUPPORTED_IMAGES:
            raise ValueError(f"不支持的图片格式: {path.suffix}")

        img = Image.open(file_path)

        # 转换 RGBA 为 RGB（如果需要）
        if img.mode in ('RGBA', 'LA', 'P'):
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = rgb_img

        # 压缩尺寸
        img.thumbnail(FileHandler.MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)

        # 保存为 Base64
        buffer = io.BytesIO()
        fmt = 'JPEG' if path.suffix.lower() in {'.jpg', '.jpeg'} else path.suffix[1:].upper()
        img.save(buffer, format=fmt, quality=quality, optimize=True)
        base64_data = base64.b64encode(buffer.getvalue()).decode()

        media_type = f"image/{fmt.lower()}"
        return base64_data, media_type

    @staticmethod
    def read_file(file_path: str) -> str:
        """
        读取文本文件内容

        Args:
            file_path: 文件路径

        Returns:
            文件内容
        """
        path = Path(file_path)
        if path.suffix.lower() not in FileHandler.SUPPORTED_DOCUMENTS:
            raise ValueError(f"不支持的文件格式: {path.suffix}")

        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    @staticmethod
    def get_file_info(file_path: str) -> dict:
        """获取文件信息"""
        path = Path(file_path)
        return {
            'name': path.name,
            'size': path.stat().st_size,
            'suffix': path.suffix.lower(),
            'is_image': path.suffix.lower() in FileHandler.SUPPORTED_IMAGES,
            'is_document': path.suffix.lower() in FileHandler.SUPPORTED_DOCUMENTS,
        }
