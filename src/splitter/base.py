"""
文本切分器基类
"""

from abc import ABC, abstractmethod
from typing import List

from langchain_core.documents import Document


class BaseSplitter(ABC):
    """文本切分器抽象基类"""

    @abstractmethod
    def split_documents(self, documents: List[Document]) -> List[Document]:
        """
        将文档列表切分为更小的文本块

        Args:
            documents: 待切分的文档列表

        Returns:
            切分后的文档块列表
        """
        ...

    @abstractmethod
    def split_text(self, text: str) -> List[str]:
        """
        将单个文本切分为多个块

        Args:
            text: 待切分的文本

        Returns:
            切分后的文本块列表
        """
        ...
