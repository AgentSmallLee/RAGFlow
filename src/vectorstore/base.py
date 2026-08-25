"""
向量存储基类
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from langchain_core.documents import Document


class BaseVectorStore(ABC):
    """向量数据库抽象基类"""

    @abstractmethod
    def add_documents(self, documents: List[Document]) -> List[str]:
        """
        向向量库添加文档（自动向量化）

        Args:
            documents: 待添加的文档列表

        Returns:
            添加的文档 ID 列表
        """
        ...

    @abstractmethod
    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[dict] = None,
    ) -> List[Document]:
        """
        相似度检索（基于文本查询）

        Args:
            query: 查询文本
            k: 返回结果数量
            filter: 元数据过滤条件

        Returns:
            最相关的文档列表（按相似度从高到低）
        """
        ...

    @abstractmethod
    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: Optional[dict] = None,
    ) -> List[tuple[Document, float]]:
        """
        带分数的相似度检索

        Args:
            query: 查询文本
            k: 返回结果数量
            filter: 元数据过滤条件

        Returns:
            (文档, 相似度分数) 元组列表
        """
        ...

    @abstractmethod
    def delete(self, ids: Optional[List[str]] = None) -> None:
        """
        删除向量库中的文档

        Args:
            ids: 要删除的文档 ID 列表，None 表示清空全部
        """
        ...

    @abstractmethod
    def count(self) -> int:
        """获取向量库中的文档数量"""
        ...

    @abstractmethod
    def persist(self) -> None:
        """持久化向量库到磁盘"""
        ...
