"""
Reranker 抽象基类
"""

from abc import ABC, abstractmethod
from typing import List, Tuple

from langchain_core.documents import Document


class BaseReranker(ABC):
    """Reranker 抽象基类，对检索结果进行二次精排"""

    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: List[Document],
        top_n: int | None = None,
    ) -> List[Tuple[Document, float]]:
        """
        对文档列表进行重排序

        Args:
            query: 查询文本
            documents: 待重排的文档列表
            top_n: 返回前 N 条，None 则返回全部

        Returns:
            重排后的 (Document, score) 列表，按相关性从高到低排序
        """
        ...
