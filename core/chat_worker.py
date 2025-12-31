"""聊天工作线程模块"""

import time
import base64
from typing import Union
from PySide6.QtCore import QThread, Signal  # noqa: F401
from services.api_services.base_service import BaseAPIService


class FileProcessWorker(QThread):
    """文件处理工作线程 - 异步处理文件上传"""

    attachments_ready = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, files: list, should_compress: bool = True):
        super().__init__()
        self.files = files
        self.should_compress = should_compress

    def run(self):
        """处理文件"""
        try:
            from core.file_handler import FileHandler
            from pathlib import Path

            attachments = []
            for file_path in self.files:
                try:
                    file_info = FileHandler.get_file_info(file_path)

                    if file_info['is_image']:
                        if self.should_compress:
                            base64_data, media_type = FileHandler.compress_image(file_path)
                        else:
                            with open(file_path, 'rb') as f:
                                base64_data = base64.b64encode(f.read()).decode()
                            media_type = f"image/{file_info['suffix'][1:]}"

                        attachments.append({
                            'type': 'image',
                            'name': file_info['name'],
                            'data': base64_data,
                            'media_type': media_type
                        })

                    elif file_info['is_document']:
                        content = FileHandler.read_file(file_path)
                        attachments.append({
                            'type': 'document',
                            'name': file_info['name'],
                            'data': content
                        })

                except Exception as e:
                    self.error_occurred.emit(f"处理文件 {Path(file_path).name} 失败: {str(e)}")

            self.attachments_ready.emit(attachments)
        except Exception as e:
            self.error_occurred.emit(f"文件处理错误: {str(e)}")


class ChatWorker(QThread):
    """聊天工作线程"""

    response_chunk = Signal(str)
    response_ready = Signal()
    error_occurred = Signal(str)

    def __init__(
        self,
        service: BaseAPIService,
        message: str,
        attachments: list = None,
        system_prompt: str = "",
        timeout: int = 120,
        thinking_mode: str = None,
    ):
        super().__init__()
        self.service = service
        self.message = message
        self.attachments = attachments or []
        self.system_prompt = system_prompt
        self.thinking_mode = thinking_mode
        self.is_running = True
        self.timeout = timeout
        self.start_time = None

    def run(self):
        """Run worker thread"""
        try:
            self.start_time = time.time()
            has_output = False
            buffer = ""
            last_emit_time = time.time()
            chunk_count = 0

            print("[WORKER] Starting chat stream...")
            for chunk in self.service.chat_stream(
                self.message,
                self.system_prompt,
                attachments=self.attachments,
                thinking_mode=self.thinking_mode,
            ):
                if not self.is_running:
                    print("[WORKER] Worker stopped")
                    break
                # Only check timeout at start, not after output begins
                if not has_output:
                    elapsed = time.time() - self.start_time
                    if elapsed > self.timeout:
                        error_msg = f"API timeout ({self.timeout}s)"
                        print(f"[WORKER] Timeout: {error_msg}")
                        self.error_occurred.emit(error_msg)
                        return
                    has_output = True
                    print(f"[WORKER] First chunk received after {elapsed:.2f}s")

                chunk_count += 1
                buffer += chunk
                current_time = time.time()
                time_since_last = current_time - last_emit_time
                # Emit batched chunks every 200ms or when buffer is large (500 chars)
                # 减少UI更新频率,防止主线程过载
                if time_since_last > 0.2 or len(buffer) > 500:
                    print(f"[WORKER] Emitting batch: {len(buffer)} chars ({chunk_count} chunks, {time_since_last:.3f}s since last)")
                    try:
                        self.response_chunk.emit(buffer)
                        print(f"[WORKER] Batch emitted successfully")
                    except Exception as e:
                        print(f"[WORKER] Error emitting batch: {e}")
                        import traceback
                        traceback.print_exc()
                    buffer = ""
                    last_emit_time = current_time

            # Emit remaining buffer
            if buffer:
                print(f"[WORKER] Emitting final buffer: {len(buffer)} chars")
                self.response_chunk.emit(buffer)
            print(f"[WORKER] Stream complete, total chunks: {chunk_count}")
            self.response_ready.emit()
        except Exception as e:  # noqa: BLE001
            error_msg = str(e)
            print(f"[WORKER] Error: {error_msg}")
            import traceback
            traceback.print_exc()
            self.error_occurred.emit(error_msg)

    def stop(self):
        """Stop worker thread"""
        self.is_running = False
