"""
Embedding 实现
支持 OpenAI 兼容接口和 DashScope（通义千问）
"""

from typing import List

from langchain_community.embeddings import DashScopeEmbeddings
from langchain_openai import OpenAIEmbeddings

from .base import BaseEmbedding
from config.settings import settings
from src.utils import logger


class OpenAIEmbedding(BaseEmbedding):
    """
    Embedding 封装
    自动根据模型名称选择 OpenAI 或 DashScope 后端
    """

    # BGE 系列模型的查询前缀（用于提升检索效果）
    # 参考: https://github.com/FlagOpen/FlagEmbedding
    BGE_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        """
        初始化 Embedding

        Args:
            model: 模型名称，默认从配置读取
            api_key: API Key，默认从配置读取
            base_url: API 基础 URL，默认从配置读取
        """
        self.model = model or settings.embedding_model
        self._api_key = api_key or settings.embedding_api_key
        self._base_url = base_url or settings.embedding_base_url

        if not self._api_key:
            logger.warning("未配置 EMBEDDING_API_KEY，向量化功能将不可用")

        # 判断使用哪个后端：DashScope 模型使用 DashScopeEmbeddings
        self._is_dashscope = self.model.startswith("text-embedding-v")
        if self._is_dashscope:
            # DashScope 模型（如 text-embedding-v3）使用官方 SDK
            self._embedding = DashScopeEmbeddings(
                model=self.model,
                dashscope_api_key=self._api_key,
            )
            logger.info(f"DashScope Embedding 初始化完成: model={self.model}")
        else:
            # OpenAI 兼容接口
            self._embedding = OpenAIEmbeddings(
                model=self.model,
                api_key=self._api_key,
                base_url=self._base_url,
            )
            logger.info(f"OpenAI Embedding 初始化完成: model={self.model}")

        # 检测是否为 BGE 系列模型，自动启用查询前缀
        self._is_bge = self.model.lower().startswith("bge") or "/bge-" in self.model.lower()
        if self._is_bge:
            logger.info(f"检测到 BGE 系列模型 ({self.model})，将自动添加查询前缀")

    def embed_query(self, text: str) -> List[float]:
        """
        对单个查询文本生成向量
        BGE 系列模型会自动添加查询前缀以提升检索效果

        Args:
            text: 查询文本

        Returns:
            向量表示
        """
        logger.debug(f"生成查询向量，文本长度: {len(text)}")
        query_text = self.BGE_QUERY_PREFIX + text if self._is_bge else text
        return self._embedding.embed_query(query_text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        批量生成文档向量

        Args:
            texts: 文档文本列表

        Returns:
            向量列表
        """
        logger.info(f"批量生成文档向量，数量: {len(texts)}")
        return self._embedding.embed_documents(texts)
