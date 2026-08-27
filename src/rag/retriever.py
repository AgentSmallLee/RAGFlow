"""
检索器模块
封装向量检索逻辑，支持相似度阈值过滤、Rerank 二次精排等
"""

from dataclasses import dataclass
from typing import List, Optional

from langchain_core.documents import Document

from src.vectorstore.base import BaseVectorStore
from src.reranker.base import BaseReranker
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
    支持 Rerank 二次精排：先向量召回 top_k 条，再用 Reranker 精排取 rerank_top_n 条
    """

    def __init__(
        self,
        vector_store: BaseVectorStore,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
        reranker: BaseReranker | None = None,
        rerank_top_n: int | None = None,
        rerank_threshold: float | None = None,
        enable_rerank: bool = False,
    ):
        """
        初始化检索器

        Args:
            vector_store: 向量库实例
            top_k: 向量检索召回的最大结果数，默认从配置读取
            similarity_threshold: 向量相似度阈值，低于此值的结果被过滤
            reranker: Reranker 实例（用于二次精排）
            rerank_top_n: Rerank 后返回的文档数量，默认从配置读取
            rerank_threshold: Rerank 分数阈值，低于此值的结果被过滤
            enable_rerank: 是否启用 Rerank
        """
        self._vector_store = vector_store
        self._top_k = top_k or settings.top_k
        self._threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else settings.similarity_threshold
        )
        self._reranker = reranker
        self._enable_rerank = enable_rerank and reranker is not None
        self._rerank_top_n = (
            rerank_top_n if rerank_top_n is not None else settings.rerank_top_n
        )
        self._rerank_threshold = (
            rerank_threshold
            if rerank_threshold is not None
            else settings.rerank_threshold
        )

        if self._enable_rerank:
            logger.info(
                f"检索器初始化完成: top_k={self._top_k}, "
                f"similarity_threshold={self._threshold}, "
                f"rerank_top_n={self._rerank_top_n}, "
                f"rerank_threshold={self._rerank_threshold}"
            )
        else:
            logger.info(
                f"检索器初始化完成: top_k={self._top_k}, "
                f"similarity_threshold={self._threshold}, "
                f"rerank=关闭"
            )

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        filter: Optional[dict] = None,
    ) -> List[RetrievedDocument]:
        """
        执行相似度检索（支持 Rerank 二次精排）

        Args:
            query: 用户查询
            top_k: 本次查询覆盖默认 top_k（向量召回数量）
            filter: 元数据过滤条件

        Returns:
            检索结果列表，按相关性从高到低排序
        """
        k = top_k or self._top_k
        logger.info(f"开始检索: query='{query}', k={k}")

        # 阶段 1：调用向量库检索
        results = self._vector_store.similarity_search_with_score(
            query=query,
            k=k,
            filter=filter,
        )

        # 应用向量相似度阈值过滤
        filtered = []
        for doc, score in results:
            if score >= self._threshold:
                filtered.append((doc, score))
            else:
                logger.debug(f"过滤低相似度结果: score={score:.4f}")

        logger.info(
            f"向量检索完成: 原始 {len(results)} 条，过滤后 {len(filtered)} 条"
        )

        # 阶段 2：Rerank 二次精排（如果启用）
        if self._enable_rerank and self._reranker and filtered:
            docs_for_rerank = [doc for doc, _ in filtered]
            reranked = self._reranker.rerank(
                query=query,
                documents=docs_for_rerank,
                top_n=self._rerank_top_n,
            )

            # 应用 Rerank 分数阈值过滤
            reranked_filtered = [
                (doc, score)
                for doc, score in reranked
                if score >= self._rerank_threshold
            ]

            # 封装为 RetrievedDocument（分数更新为 Rerank 分数）
            retrieved = [
                RetrievedDocument(document=doc, score=score, rank=i + 1)
                for i, (doc, score) in enumerate(reranked_filtered)
            ]

            logger.info(
                f"Rerank 精排完成: 召回 {len(filtered)} 条 → 精排后 {len(retrieved)} 条，"
                f"最高分数: {retrieved[0].score:.4f}" if retrieved else "Rerank 精排完成: 无结果"
            )
            return retrieved

        # 无 Rerank：直接封装返回
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

    @property
    def enable_rerank(self) -> bool:
        return self._enable_rerank

    @property
    def rerank_top_n(self) -> int:
        return self._rerank_top_n
