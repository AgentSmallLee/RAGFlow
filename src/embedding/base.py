"""
Embedding 向量化基类
"""

from abc import ABC, abstractmethod
from typing import List


class BaseEmbedding(ABC):
    """Embedding 模型抽象基类"""

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """
        对单个查询文本生成向量（用于在线检索）

        Args:
            text: 查询文本

        Returns:
            向量表示（float 列表）
        """
        ...

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        批量生成文档向量（用于离线建库）

        Args:
            texts: 文档文本列表

        Returns:
            向量列表
        """
        ...
