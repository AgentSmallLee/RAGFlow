"""
PDF 文档加载器
"""

from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader

from .base import BaseLoader
from src.utils import logger


class PdfLoader(BaseLoader):
    """PDF 文件加载器"""

    SUPPORTED_EXTENSIONS = {".pdf"}

    def load(self, file_path: Path) -> List[Document]:
        """
        加载 PDF 文件

        Args:
            file_path: PDF 文件路径

        Returns:
            Document 列表（每一页对应一个 Document）
        """
        logger.info(f"加载 PDF 文件: {file_path}")

        try:
            loader = PyPDFLoader(str(file_path))
            pages = loader.load()

            # 统一添加元数据
            for i, page in enumerate(pages):
                page.metadata.update({
                    "source": str(file_path),
                    "file_name": file_path.name,
                    "file_type": "pdf",
                    "page": i + 1,
                })

            logger.info(f"PDF 加载完成，共 {len(pages)} 页")
            return pages
        except Exception as e:
            logger.error(f"加载 PDF 文件失败 {file_path}: {e}")
            raise

    def supports(self, file_path: Path) -> bool:
        """判断是否为 PDF 文件"""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS
