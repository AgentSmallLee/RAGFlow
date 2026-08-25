"""
纯文本 / Markdown 文档加载器
"""

from pathlib import Path
from typing import List

from langchain_core.documents import Document

from .base import BaseLoader
from src.utils import logger


class TextLoader(BaseLoader):
    """TXT 和 Markdown 文件加载器"""

    # 支持的文件扩展名
    SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown"}

    def load(self, file_path: Path) -> List[Document]:
        """
        加载文本文件

        Args:
            file_path: 文本文件路径

        Returns:
            包含文档内容的 Document 列表
        """
        logger.info(f"加载文本文件: {file_path}")

        try:
            # 尝试多种编码读取
            text = self._read_file(file_path)
            doc = Document(
                page_content=text,
                metadata={
                    "source": str(file_path),
                    "file_name": file_path.name,
                    "file_type": file_path.suffix.lstrip("."),
                },
            )
            logger.debug(f"文本加载完成，字符数: {len(text)}")
            return [doc]
        except Exception as e:
            logger.error(f"加载文本文件失败 {file_path}: {e}")
            raise

    def supports(self, file_path: Path) -> bool:
        """判断是否为支持的文本格式"""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    @staticmethod
    def _read_file(file_path: Path) -> str:
        """尝试用多种编码读取文件"""
        encodings = ["utf-8", "gbk", "gb2312", "latin-1"]
        for encoding in encodings:
            try:
                return file_path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError(f"无法识别文件编码: {file_path}")
