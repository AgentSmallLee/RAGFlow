"""
DashScope Reranker 实现
基于阿里云 DashScope 的文本排序（TextRanking）API
"""

from typing import List, Tuple

from langchain_core.documents import Document

from config.settings import settings
from src.utils import logger
from .base import BaseReranker


class DashScopeReranker(BaseReranker):
    """
    DashScope 文本重排序
    使用阿里云 DashScope 的 TextRanking API 对检索结果进行二次精排
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
    ):
        self.model = model or settings.rerank_model
        # API Key 优先使用独立配置，没有则复用 embedding 的 key
        self._api_key = api_key or settings.rerank_api_key or settings.embedding_api_key

        if not self._api_key:
            logger.warning("未配置 Rerank API Key，重排序功能将不可用")

        # 延迟导入 dashscope
        try:
            import dashscope  # noqa: F401
            self._dashscope_available = True
        except ImportError:
            self._dashscope_available = False
            logger.warning(
                "dashscope 库未安装，DashScope Reranker 将无法使用。"
                "请运行: pip install dashscope"
            )

        logger.info(f"DashScope Reranker 初始化完成: model={self.model}")

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
        if not documents:
            return []

        if not self._dashscope_available or not self._api_key:
            logger.warning("DashScope Reranker 不可用，直接返回原始排序")
            # 返回原始顺序，分数用 0 填充
            return [(doc, 0.0) for doc in documents][:top_n]

        import dashscope

        # 准备文档文本列表
        texts = [doc.page_content for doc in documents]

        # top_n 参数：如果传入则用，否则返回全部
        return_n = top_n if top_n and top_n > 0 else len(texts)
        # DashScope API 的 top_n 不能超过文档数量
        return_n = min(return_n, len(texts))

        logger.info(
            f"开始 Rerank: query='{query}', docs={len(documents)}, top_n={return_n}"
        )

        try:
            # 调用 DashScope TextReRank API
            resp = dashscope.TextReRank.call(
                model=self.model,
                query=query,
                documents=texts,
                top_n=return_n,
                api_key=self._api_key,
            )

            # 检查响应状态
            if resp.status_code != 200:
                logger.error(f"Rerank API 调用失败: status_code={resp.status_code}, "
                             f"code={resp.code}, message={resp.message}")
                return [(doc, 0.0) for doc in documents][:return_n]

            # 解析结果：resp.output.results 是 ReRankResult 对象列表
            # 每个对象含 index 和 relevance_score 属性
            output = resp.output
            results = getattr(output, 'results', []) if output else []
            if not results:
                logger.warning("Rerank 返回结果为空，返回原始排序")
                return [(doc, 0.0) for doc in documents][:return_n]

            # 按返回的顺序和分数组装结果
            reranked = []
            for item in results:
                # 兼容对象属性和字典两种形式
                if hasattr(item, 'index'):
                    idx = item.index
                    score = float(getattr(item, 'relevance_score', 0.0))
                else:
                    idx = item.get("index", 0)
                    score = float(item.get("relevance_score", item.get("score", 0.0)))
                if 0 <= idx < len(documents):
                    reranked.append((documents[idx], score))

            logger.info(
                f"Rerank 完成: 返回 {len(reranked)} 条，"
                f"最高分数: {reranked[0][1]:.4f}" if reranked else "Rerank 完成: 无结果"
            )

            return reranked

        except Exception as e:
            logger.error(f"Rerank 调用异常: {e}")
            # 降级：返回原始文档列表（不重排）
            return [(doc, 0.0) for doc in documents][:return_n]
