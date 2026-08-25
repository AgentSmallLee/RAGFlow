"""
混合检索实现
向量检索 + BM25 关键词检索，用 RRF 算法融合结果
"""

from typing import List, Optional

from langchain_core.documents import Document

from .base import BaseVectorStore
from .bm25_store import BM25Store
from src.utils import logger


class HybridStore(BaseVectorStore):
    """
    混合检索：向量检索 + BM25 关键词检索
    同时保留两种检索的优势：
      - 向量检索：语义理解、同义词匹配
      - BM25：精确关键词、专有名词匹配

    融合算法：RRF（Reciprocal Rank Fusion，倒数排名融合）
    优点：不需要归一化不同体系的分数，直接按排名融合
    """

    # RRF 的 k 参数，经验值 60
    # 值越大，排名靠后的结果权重越高
    RRF_K = 60

    def __init__(
        self,
        vector_store: BaseVectorStore,
        bm25_store: BM25Store | None = None,
        vector_weight: float = 0.7,
        fusion_method: str = "rrf",
    ):
        """
        初始化混合检索

        Args:
            vector_store: 向量检索实例
            bm25_store: BM25 检索实例，None 则自动创建一个空的
            vector_weight: 向量检索权重（0~1），仅 weighted 模式使用
            fusion_method: 融合方式，'rrf' 或 'weighted'
        """
        self._vector_store = vector_store
        self._bm25_store = bm25_store or BM25Store()
        self._vector_weight = vector_weight
        self._fusion_method = fusion_method

        if fusion_method not in ("rrf", "weighted"):
            raise ValueError(f"不支持的融合方式: {fusion_method}，可选: rrf, weighted")

        logger.info(
            f"混合检索初始化完成: "
            f"fusion={fusion_method}, "
            f"vector_weight={vector_weight}"
        )

    def add_documents(self, documents: List[Document]) -> List[str]:
        """
        同时向向量库和 BM25 索引添加文档

        Args:
            documents: 待添加的文档列表

        Returns:
            向量库返回的文档 ID 列表
        """
        # 同时写入两路
        vector_ids = self._vector_store.add_documents(documents)
        self._bm25_store.add_documents(documents)

        logger.info(f"混合检索添加文档完成: {len(documents)} 个")
        return vector_ids

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[dict] = None,
    ) -> List[Document]:
        """
        混合检索（不带分数）

        Args:
            query: 查询文本
            k: 返回结果数量
            filter: 元数据过滤条件（传给向量检索）

        Returns:
            融合排序后的文档列表
        """
        results = self.similarity_search_with_score(query, k, filter)
        return [doc for doc, _ in results]

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: Optional[dict] = None,
    ) -> List[tuple[Document, float]]:
        """
        带分数的混合检索

        融合策略：
          - 用 RRF / 加权融合 计算"融合排名分数"，用于排序
          - 最终返回的分数使用**向量检索的原始相似度分数**
            （因为向量分数有绝对的语义意义，可用于阈值过滤）

        Args:
            query: 查询文本
            k: 返回结果数量
            filter: 元数据过滤条件（传给向量检索）

        Returns:
            (文档, 向量相似度分数) 列表，按融合排名从高到低
        """
        # 两路召回：都多取一些，保证融合后有足够结果
        fetch_k = max(k * 3, 20)

        # 向量检索结果（保留原始分数，作为最终输出的分数）
        vector_results = self._vector_store.similarity_search_with_score(
            query=query, k=fetch_k, filter=filter
        )
        vector_scores: dict[str, float] = {}
        for doc, score in vector_results:
            vector_scores[doc.page_content] = score

        # BM25 检索结果
        bm25_results = self._bm25_store.similarity_search_with_score(
            query=query, k=fetch_k
        )

        logger.debug(
            f"混合检索召回: 向量 {len(vector_results)} 条, BM25 {len(bm25_results)} 条"
        )

        # 用融合算法计算排名分数（仅用于排序）
        if self._fusion_method == "rrf":
            merged = self._fuse_rrf(vector_results, bm25_results)
        else:
            merged = self._fuse_weighted(vector_results, bm25_results)

        # 按融合分数排序，取 top k
        merged.sort(key=lambda x: x[1], reverse=True)
        top_merged = merged[:k]

        # 最终结果：用融合排名排序，但分数用向量检索的原始分数
        # （向量分数有绝对语义意义，可用于阈值过滤）
        results = []
        for doc, _ in top_merged:
            key = doc.page_content
            # 如果向量检索没命中（只有 BM25 命中），给一个较低的保底分数
            score = vector_scores.get(key, 0.0)
            results.append((doc, score))

        logger.debug(
            f"混合检索完成: 融合后 {len(merged)} 条, 返回 top {len(results)} 条, "
            f"最高向量分: {results[0][1]:.4f}" if results else "无结果"
        )
        return results

    def _fuse_rrf(
        self,
        vector_results: List[tuple[Document, float]],
        bm25_results: List[tuple[Document, float]],
    ) -> List[tuple[Document, float]]:
        """
        RRF（倒数排名融合）
        score = Σ 1 / (k + rank)
        不需要关心分数的绝对值，只看排名

        Args:
            vector_results: 向量检索结果
            bm25_results: BM25 检索结果

        Returns:
            融合后的 (文档, 融合分数) 列表
        """
        rrf_scores: dict[str, float] = {}
        doc_map: dict[str, Document] = {}

        # 向量检索结果的 RRF 分数
        for rank, (doc, _) in enumerate(vector_results, 1):
            key = doc.page_content
            doc_map[key] = doc
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (self.RRF_K + rank)

        # BM25 检索结果的 RRF 分数
        for rank, (doc, _) in enumerate(bm25_results, 1):
            key = doc.page_content
            doc_map[key] = doc
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (self.RRF_K + rank)

        # 组装结果
        merged = [(doc_map[key], score) for key, score in rrf_scores.items()]
        return merged

    def _fuse_weighted(
        self,
        vector_results: List[tuple[Document, float]],
        bm25_results: List[tuple[Document, float]],
    ) -> List[tuple[Document, float]]:
        """
        加权融合
        score = vector_score * vector_weight + bm25_score * (1 - vector_weight)
        需要先对两边的分数做归一化到 [0, 1]

        Args:
            vector_results: 向量检索结果
            bm25_results: BM25 检索结果

        Returns:
            融合后的 (文档, 融合分数) 列表
        """
        # 归一化向量分数（已经是 [0, 1] 范围的相似度，直接用）
        vector_scores: dict[str, float] = {}
        doc_map: dict[str, Document] = {}
        for doc, score in vector_results:
            key = doc.page_content
            doc_map[key] = doc
            vector_scores[key] = score

        # 归一化 BM25 分数（BM25 分数范围不定，用最大最小归一化）
        bm25_scores: dict[str, float] = {}
        if bm25_results:
            bm25_max = max(s for _, s in bm25_results)
            bm25_min = min(s for _, s in bm25_results)
            bm25_range = bm25_max - bm25_min if bm25_max > bm25_min else 1.0
            for doc, score in bm25_results:
                key = doc.page_content
                doc_map[key] = doc
                bm25_scores[key] = (score - bm25_min) / bm25_range

        # 加权融合
        all_keys = set(vector_scores.keys()) | set(bm25_scores.keys())
        merged = []
        vw = self._vector_weight
        bw = 1.0 - vw

        for key in all_keys:
            vs = vector_scores.get(key, 0.0)
            bs = bm25_scores.get(key, 0.0)
            # 只在一边出现的文档，加权时要打折扣（只乘以自己的权重）
            if key in vector_scores and key in bm25_scores:
                fused = vs * vw + bs * bw
            elif key in vector_scores:
                fused = vs * vw  # 只向量命中
            else:
                fused = bs * bw  # 只 BM25 命中
            merged.append((doc_map[key], fused))

        return merged

    def delete(self, ids: Optional[List[str]] = None) -> None:
        """
        同时删除向量库和 BM25 索引中的文档

        Args:
            ids: 文档 ID 列表，None 表示清空全部
        """
        self._vector_store.delete(ids)
        self._bm25_store.delete(ids)
        logger.info("混合检索删除完成")

    def count(self) -> int:
        """获取文档数量（以向量库为准）"""
        return self._vector_store.count()

    def persist(self) -> None:
        """持久化向量库（BM25 是内存结构，不持久化）"""
        self._vector_store.persist()

    @property
    def vector_store(self) -> BaseVectorStore:
        """获取向量检索实例"""
        return self._vector_store

    @property
    def bm25_store(self) -> BM25Store:
        """获取 BM25 检索实例"""
        return self._bm25_store
