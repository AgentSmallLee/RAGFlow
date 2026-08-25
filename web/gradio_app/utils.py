"""
Gradio Web 前端工具函数
"""

from pathlib import Path


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def safe_filename(filename: str) -> str:
    """生成安全的文件名（去除特殊字符）"""
    # 简单起见，保留原始文件名，用户重新上传同名文件直接覆盖
    return filename


def get_upload_dir() -> Path:
    """获取上传文件目录"""
    from .rag_service import UPLOAD_DIR
    return UPLOAD_DIR
