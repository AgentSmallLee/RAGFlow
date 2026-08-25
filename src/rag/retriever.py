"""
检索器模块
封装向量检索逻辑，支持相似度阈值过滤、重排序等
"""

from dataclasses import dataclass
from typing import List, Optional

from langchain_core.documents import Document

from src.vectorstore.base import BaseVectorStore
from config.settings import settings
from src.utils import logger


@dataclass
class RetrievedDocument:
    """检索结果数据类"""
    document: Document       # 文档内容
    score: float             # 相似度分数 [0, 1]
    rank: int                # 排名（从 1 开始）


class Retriever:
    """
    检索器
    对向量库的检索做一层封装，提供更易用的接口
    """

    def __init__(
        self,
        vector_store: BaseVectorStore,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
    ):
        """
        初始化检索器

        Args:
            vector_store: 向量库实例
            top_k: 返回的最大结果数，默认从配置读取
            similarity_threshold: 相似度阈值，低于此值的结果被过滤
        """
        self._vector_store = vector_store
        self._top_k = top_k or settings.top_k
        self._threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else settings.similarity_threshold
        )

        logger.info(
            f"检索器初始化完成: top_k={self._top_k}, "
            f"similarity_threshold={self._threshold}"
        )

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        filter: Optional[dict] = None,
    ) -> List[RetrievedDocument]:
        """
        执行相似度检索

        Args:
            query: 用户查询
            top_k: 本次查询覆盖默认 top_k
            filter: 元数据过滤条件

        Returns:
            检索结果列表，按相似度从高到低排序
        """
        k = top_k or self._top_k
        logger.info(f"开始检索: query='{query}', k={k}")

        # 调用向量库检索
        results = self._vector_store.similarity_search_with_score(
            query=query,
            k=k,
            filter=filter,
        )

        # 应用相似度阈值过滤
        filtered = []
        for doc, score in results:
            if score >= self._threshold:
                filtered.append((doc, score))
            else:
                logger.debug(f"过滤低相似度结果: score={score:.4f}")

        # 封装为 RetrievedDocument
        retrieved = [
            RetrievedDocument(document=doc, score=score, rank=i + 1)
            for i, (doc, score) in enumerate(filtered)
        ]

        logger.info(
            f"检索完成: 原始 {len(results)} 条，过滤后 {len(retrieved)} 条，"
            f"最高相似度: {retrieved[0].score:.4f}" if retrieved else "检索完成: 无结果"
        )
        return retrieved

    def retrieve_as_documents(
        self,
        query: str,
        top_k: int | None = None,
        filter: Optional[dict] = None,
    ) -> List[Document]:
        """
        检索并仅返回 Document 列表（便于直接使用）

        Args:
            query: 用户查询
            top_k: 返回数量
            filter: 过滤条件

        Returns:
            Document 列表
        """
        results = self.retrieve(query, top_k, filter)
        return [r.document for r in results]

    @property
    def top_k(self) -> int:
        return self._top_k

    @property
    def similarity_threshold(self) -> float:
        return self._threshold
