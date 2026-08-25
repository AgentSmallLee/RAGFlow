"""
Word 文档加载器（DOCX）
"""

from pathlib import Path
from typing import List

from langchain_core.documents import Document

try:
    from langchain_community.document_loaders import Docx2txtLoader
    HAS_DOCX_LOADER = True
except ImportError:
    HAS_DOCX_LOADER = False

from .base import BaseLoader
from src.utils import logger


class DocxLoader(BaseLoader):
    """Word DOCX 文件加载器"""

    SUPPORTED_EXTENSIONS = {".docx", ".doc"}

    def load(self, file_path: Path) -> List[Document]:
        """
        加载 Word 文档

        Args:
            file_path: DOCX 文件路径

        Returns:
            Document 列表
        """
        logger.info(f"加载 Word 文档: {file_path}")

        if not HAS_DOCX_LOADER:
            raise ImportError(
                "缺少 docx 加载依赖，请安装: pip install python-docx"
            )

        try:
            loader = Docx2txtLoader(str(file_path))
            docs = loader.load()

            for doc in docs:
                doc.metadata.update({
                    "source": str(file_path),
                    "file_name": file_path.name,
                    "file_type": "docx",
                })

            logger.info(f"Word 文档加载完成，字符数: {len(docs[0].page_content)}")
            return docs
        except Exception as e:
            logger.error(f"加载 Word 文档失败 {file_path}: {e}")
            raise

    def supports(self, file_path: Path) -> bool:
        """判断是否为 Word 文档"""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS
