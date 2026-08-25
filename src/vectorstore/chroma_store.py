"""
ChromaDB 向量存储实现
轻量级、本地持久化，适合演示和小规模场景
"""

from pathlib import Path
from typing import List, Optional

from langchain_core.documents import Document
from langchain_chroma import Chroma

from .base import BaseVectorStore
from src.embedding.base import BaseEmbedding
from config.settings import settings
from src.utils import logger


class ChromaVectorStore(BaseVectorStore):
    """
    基于 ChromaDB 的向量存储实现
    支持本地持久化，开箱即用
    """

    def __init__(
        self,
        embedding: BaseEmbedding,
        persist_directory: str | Path | None = None,
        collection_name: str | None = None,
    ):
        """
        初始化 Chroma 向量库

        Args:
            embedding: Embedding 模型实例
            persist_directory: 持久化目录，默认从配置读取
            collection_name: 集合名称，默认从配置读取
        """
        self._embedding = embedding
        self._persist_dir = str(
            Path(persist_directory or settings.vector_db_path).resolve()
        )
        self._collection_name = collection_name or settings.collection_name

        # 确保目录存在
        Path(self._persist_dir).mkdir(parents=True, exist_ok=True)

        # 使用 langchain 的 Chroma 封装
        # 注意：Chroma 支持多种距离度量，l2 为欧氏距离平方，cosine 为余弦距离
        # 对于大多数 embedding 模型（尤其是 bge 系列），余弦相似度效果更好
        # 如果集合已存在，Chroma 会忽略 collection_metadata，沿用原有配置
        self._chroma = Chroma(
            collection_name=self._collection_name,
            embedding_function=self._embedding,  # type: ignore
            persist_directory=self._persist_dir,
            collection_metadata={"hnsw:space": "cosine"},
        )

        # 检测实际使用的距离度量（用于分数转换）
        self._distance = self._detect_distance()
        if self._distance == "l2" and self.count() > 0:
            logger.warning(
                f"当前向量集合 '{self._collection_name}' 使用 L2 距离，"
                f"推荐使用余弦相似度（cosine）以获得更好的检索效果。"
                f"如需切换，请删除向量库目录后重新建库。"
            )

        count = self.count()
        logger.info(
            f"Chroma 向量库初始化完成: "
            f"collection={self._collection_name}, "
            f"distance={self._distance}, "
            f"persist_dir={self._persist_dir}, "
            f"已有文档数={count}"
        )

    def _detect_distance(self) -> str:
        """检测集合使用的距离度量，返回 'l2' 或 'cosine'"""
        try:
            metadata = self._chroma._collection.metadata  # type: ignore
            space = metadata.get("hnsw:space", "l2") if metadata else "l2"
            return str(space)
        except Exception:
            return "l2"

    def add_documents(self, documents: List[Document]) -> List[str]:
        """
        批量添加文档到向量库

        Args:
            documents: 待添加的文档列表

        Returns:
            文档 ID 列表
        """
        if not documents:
            logger.warning("空文档列表，跳过添加")
            return []

        logger.info(f"开始向向量库添加 {len(documents)} 个文档块...")
        ids = self._chroma.add_documents(documents)
        logger.info(f"添加完成，向量库当前总量: {self.count()}")
        return ids

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[dict] = None,
    ) -> List[Document]:
        """
        基于文本的相似度检索

        Args:
            query: 查询文本
            k: 返回结果数量
            filter: 元数据过滤条件

        Returns:
            最相关的文档列表
        """
        logger.debug(f"相似度检索: query='{query[:50]}...', k={k}")
        results = self._chroma.similarity_search(
            query=query,
            k=k,
            filter=filter,
        )
        logger.debug(f"检索到 {len(results)} 个结果")
        return results

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: Optional[dict] = None,
    ) -> List[tuple[Document, float]]:
        """
        带分数的相似度检索
        注意：Chroma 返回的是距离分数（越小越相似），这里转换为相似度（越大越相似）

        Args:
            query: 查询文本
            k: 返回结果数量
            filter: 元数据过滤条件

        Returns:
            (文档, 相似度分数) 列表，分数范围 [0, 1]，越大越相似
        """
        logger.debug(f"带分数相似度检索: query='{query[:50]}...', k={k}")

        results = self._chroma.similarity_search_with_score(
            query=query,
            k=k,
            filter=filter,
        )

        # 根据距离度量类型转换为相似度分数 [0, 1]，越大越相似
        converted = []
        for doc, distance in results:
            if self._distance == "cosine":
                # 余弦距离 = 1 - 余弦相似度 → 相似度 = 1 - distance
                similarity = 1.0 - distance
            else:
                # L2（欧氏距离平方）：使用归一化转换
                # 距离越小越相似，通过 1 / (1 + distance) 映射到 (0, 1]
                similarity = 1.0 / (1.0 + distance)
            converted.append((doc, similarity))

        logger.debug(f"检索到 {len(converted)} 个结果，最高相似度: {converted[0][1]:.4f}" if converted else "无结果")
        return converted

    def delete(self, ids: Optional[List[str]] = None) -> None:
        """
        删除文档

        Args:
            ids: 文档 ID 列表，None 表示清空整个集合
        """
        if ids is None:
            logger.warning("清空整个向量集合")
            # Chroma 没有直接清空的方法，删除并重建
            self._chroma.delete_collection()
            self._chroma = Chroma(
                collection_name=self._collection_name,
                embedding_function=self._embedding,  # type: ignore
                persist_directory=self._persist_dir,
                collection_metadata={"hnsw:space": "cosine"},
            )
        else:
            logger.info(f"删除 {len(ids)} 个文档")
            self._chroma.delete(ids=ids)

    def count(self) -> int:
        """获取向量库中文档数量"""
        try:
            return self._chroma._collection.count()  # type: ignore
        except Exception:
            return 0

    def persist(self) -> None:
        """
        持久化向量库
        注：新版 Chroma 自动持久化，此方法保留用于兼容接口
        """
        logger.debug("Chroma 自动持久化，无需手动调用 persist")

    @property
    def chroma_instance(self) -> Chroma:
        """获取底层 Chroma 实例（高级用法）"""
        return self._chroma
