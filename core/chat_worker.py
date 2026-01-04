"""聊天工作线程模块"""

import time
import base64
import threading
from typing import Callable
from services.api_services.base_service import BaseAPIService


class FileProcessWorker:
    """文件处理工作线程 - 异步处理文件上传"""

    def __init__(self, files: list, should_compress: bool = True):
        self.files = files
        self.should_compress = should_compress
        self._thread = None
        # 回调函数
        self.on_attachments_ready: Callable[[list], None] = None
        self.on_error: Callable[[str], None] = None

    def start(self):
        """启动线程"""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
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
                    if self.on_error:
                        self.on_error(f"处理文件 {Path(file_path).name} 失败: {str(e)}")

            if self.on_attachments_ready:
                self.on_attachments_ready(attachments)
        except Exception as e:
            if self.on_error:
                self.on_error(f"文件处理错误: {str(e)}")


class ChatWorker:
    """聊天工作线程"""

    def __init__(
        self,
        service: BaseAPIService,
        message: str,
        attachments: list = None,
        system_prompt: str = "",
        timeout: int = 120,
        thinking_mode: str = None,
    ):
        self.service = service
        self.message = message
        self.attachments = attachments or []
        self.system_prompt = system_prompt
        self.thinking_mode = thinking_mode
        self.is_running = True
        self.timeout = timeout
        self.start_time = None
        self._thread = None
        # 回调函数
        self.on_response_chunk: Callable[[str], None] = None
        self.on_response_ready: Callable[[], None] = None
        self.on_error: Callable[[str], None] = None

    def start(self):
        """启动线程"""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
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
                        if self.on_error:
                            self.on_error(error_msg)
                        return
                    has_output = True
                    print(f"[WORKER] First chunk received after {elapsed:.2f}s")

                chunk_count += 1
                buffer += chunk
                current_time = time.time()
                time_since_last = current_time - last_emit_time
                # Emit batched chunks every 200ms or when buffer is large (500 chars)
                if time_since_last > 0.2 or len(buffer) > 500:
                    print(f"[WORKER] Emitting batch: {len(buffer)} chars ({chunk_count} chunks, {time_since_last:.3f}s since last)")
                    try:
                        if self.on_response_chunk:
                            self.on_response_chunk(buffer)
                        print("[WORKER] Batch emitted successfully")
                    except Exception as e:
                        print(f"[WORKER] Error emitting batch: {e}")
                        import traceback
                        traceback.print_exc()
                    buffer = ""
                    last_emit_time = current_time

            # Emit remaining buffer
            if buffer:
                print(f"[WORKER] Emitting final buffer: {len(buffer)} chars")
                if self.on_response_chunk:
                    self.on_response_chunk(buffer)
            print(f"[WORKER] Stream complete, total chunks: {chunk_count}")
            if self.on_response_ready:
                self.on_response_ready()
        except Exception as e:
            error_msg = str(e)
            print(f"[WORKER] Error: {error_msg}")
            import traceback
            traceback.print_exc()
            if self.on_error:
                self.on_error(error_msg)

    def stop(self):
        """Stop worker thread"""
        self.is_running = False
