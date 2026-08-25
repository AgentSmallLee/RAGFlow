"""
向量存储工厂
根据配置创建合适的向量存储实例（纯向量 / 混合检索）
"""

from .base import BaseVectorStore
from .chroma_store import ChromaVectorStore
from .bm25_store import BM25Store
from .hybrid_store import HybridStore
from src.embedding.base import BaseEmbedding
from config.settings import settings
from src.utils import logger


def create_vector_store(embedding: BaseEmbedding) -> BaseVectorStore:
    """
    根据配置创建向量存储实例

    Args:
        embedding: Embedding 模型实例

    Returns:
        向量存储实例（ChromaVectorStore 或 HybridStore）
    """
    vector_store = ChromaVectorStore(embedding=embedding)

    if not settings.enable_hybrid_search:
        logger.info("使用纯向量检索")
        return vector_store

    # 混合检索模式
    bm25_store = BM25Store()
    hybrid = HybridStore(
        vector_store=vector_store,
        bm25_store=bm25_store,
        vector_weight=settings.hybrid_vector_weight,
        fusion_method=settings.hybrid_fusion_method,
    )
    logger.info(
        f"使用混合检索: method={settings.hybrid_fusion_method}, "
        f"vector_weight={settings.hybrid_vector_weight}"
    )
    return hybrid
