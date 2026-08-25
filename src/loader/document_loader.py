"""
统一文档加载器
自动识别文件格式并选择合适的加载器
"""

from pathlib import Path
from typing import List, Optional

from langchain_core.documents import Document

from .base import BaseLoader
from .text_loader import TextLoader
from .pdf_loader import PdfLoader
from .docx_loader import DocxLoader
from src.utils import logger


class DocumentLoader:
    """
    统一文档加载入口
    支持从单个文件或整个目录加载文档
    """

    def __init__(self):
        # 注册所有加载器（按优先级排序）
        self._loaders: List[BaseLoader] = [
            TextLoader(),
            PdfLoader(),
            DocxLoader(),
        ]

    def load_file(self, file_path: str | Path) -> List[Document]:
        """
        加载单个文档文件

        Args:
            file_path: 文档文件路径

        Returns:
            Document 对象列表

        Raises:
            ValueError: 不支持的文件格式
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        if not file_path.is_file():
            raise ValueError(f"不是文件: {file_path}")

        loader = self._get_loader(file_path)
        if loader is None:
            raise ValueError(f"不支持的文件格式: {file_path.suffix}")

        return loader.load(file_path)

    def load_directory(
        self,
        dir_path: str | Path,
        recursive: bool = True,
    ) -> List[Document]:
        """
        加载整个目录下的所有支持的文档

        Args:
            dir_path: 目录路径
            recursive: 是否递归子目录

        Returns:
            所有文档的 Document 列表
        """
        dir_path = Path(dir_path)
        if not dir_path.exists():
            raise FileNotFoundError(f"目录不存在: {dir_path}")
        if not dir_path.is_dir():
            raise ValueError(f"不是目录: {dir_path}")

        all_docs: List[Document] = []
        pattern = "**/*" if recursive else "*"

        for file_path in sorted(dir_path.glob(pattern)):
            if not file_path.is_file():
                continue

            # 跳过隐藏文件
            if file_path.name.startswith("."):
                continue

            loader = self._get_loader(file_path)
            if loader is None:
                logger.debug(f"跳过不支持的文件: {file_path}")
                continue

            try:
                docs = loader.load(file_path)
                all_docs.extend(docs)
            except Exception as e:
                logger.warning(f"加载文件失败 {file_path}: {e}")
                continue

        logger.info(f"目录加载完成，共获取 {len(all_docs)} 个文档片段，来自 {dir_path}")
        return all_docs

    def _get_loader(self, file_path: Path) -> Optional[BaseLoader]:
        """获取适配该文件的加载器"""
        for loader in self._loaders:
            if loader.supports(file_path):
                return loader
        return None

    @property
    def supported_extensions(self) -> List[str]:
        """获取所有支持的文件扩展名"""
        exts = set()
        for loader in self._loaders:
            # 动态获取每个加载器支持的扩展名
            for ext in getattr(loader, "SUPPORTED_EXTENSIONS", set()):
                exts.add(ext)
        return sorted(exts)
