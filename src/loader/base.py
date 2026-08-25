"""
文档加载器基类
定义所有文档加载器的通用接口
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from langchain_core.documents import Document


class BaseLoader(ABC):
    """文档加载器抽象基类"""

    @abstractmethod
    def load(self, file_path: Path) -> List[Document]:
        """
        加载单个文档文件

        Args:
            file_path: 文档文件路径

        Returns:
            Document 对象列表（一个文件可能对应多个 Document）
        """
        ...

    @abstractmethod
    def supports(self, file_path: Path) -> bool:
        """
        判断该加载器是否支持指定文件

        Args:
            file_path: 文档文件路径

        Returns:
            True 表示支持，False 表示不支持
        """
        ...
