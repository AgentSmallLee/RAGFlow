"""
BM25 关键词检索实现
基于 rank_bm25 + jieba 分词，提供纯关键词检索能力
作为向量检索的补充，用于混合检索
"""

import re
from typing import List, Optional

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
import jieba

from .base import BaseVectorStore
from src.utils import logger


# 停用词（常见无意义词，过滤掉减少噪声）
DEFAULT_STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就",
    "不", "人", "都", "一", "一个", "上", "也", "很",
    "到", "说", "要", "去", "你", "会", "着", "没有",
    "看", "好", "自己", "这", "那", "他", "她", "它",
    "们", "什么", "怎么", "为什么", "哪", "哪些", "如何",
    "可以", "吗", "吧", "啊", "呢", "了", "之", "与",
    "及", "或", "等", "等等", "例如", "比如",
}


def tokenize(text: str, stop_words: set | None = None) -> List[str]:
    """
    中文分词：jieba 分词 + 过滤停用词和标点

    Args:
        text: 待分词文本
        stop_words: 停用词集合，None 则用默认

    Returns:
        分词结果列表
    """
    if stop_words is None:
        stop_words = DEFAULT_STOP_WORDS

    # 先去掉标点和特殊字符，只保留中文、英文、数字
    text = re.sub(r"[^一-龥a-zA-Z0-9]", " ", text)

    # jieba 分词
    words = jieba.lcut(text)

    # 过滤停用词、空串、纯空格
    tokens = [w.strip() for w in words if w.strip() and w.strip() not in stop_words]
    return tokens


class BM25Store(BaseVectorStore):
    """
    基于 BM25 算法的关键词检索
    实现 BaseVectorStore 接口，可以和向量库无缝替换 / 配合使用
    """

    def __init__(self, stop_words: set | None = None):
        """
        初始化 BM25 检索器

        Args:
            stop_words: 自定义停用词集合，None 则用默认
        """
        self._stop_words = stop_words or DEFAULT_STOP_WORDS
        self._documents: List[Document] = []
        self._corpus_tokens: List[List[str]] = []
        self._bm25: BM25Okapi | None = None
        logger.info("BM25 关键词检索器初始化完成")

    def add_documents(self, documents: List[Document]) -> List[str]:
        """
        添加文档到 BM25 索引

        Args:
            documents: 待添加的文档列表

        Returns:
            文档 ID 列表（用索引下标作为 ID）
        """
        if not documents:
            logger.warning("空文档列表，跳过添加")
            return []

        logger.info(f"开始向 BM25 索引添加 {len(documents)} 个文档块...")

        start_idx = len(self._documents)
        self._documents.extend(documents)

        # 对新文档分词
        new_tokens = [
            tokenize(doc.page_content, self._stop_words)
            for doc in documents
        ]
        self._corpus_tokens.extend(new_tokens)

        # 重建 BM25 索引（BM25Okapi 不支持增量添加）
        self._bm25 = BM25Okapi(self._corpus_tokens)

        ids = [str(start_idx + i) for i in range(len(documents))]
        logger.info(f"BM25 索引更新完成，当前总量: {self.count()}")
        return ids

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[dict] = None,
    ) -> List[Document]:
        """
        BM25 关键词检索

        Args:
            query: 查询文本
            k: 返回结果数量
            filter: 元数据过滤条件（暂不支持，保留接口兼容）

        Returns:
            最相关的文档列表（按 BM25 分数从高到低）
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
        带 BM25 分数的关键词检索

        Args:
            query: 查询文本
            k: 返回结果数量
            filter: 元数据过滤条件（暂不支持）

        Returns:
            (文档, BM25 分数) 列表，按分数从高到低
        """
        if not self._bm25 or self.count() == 0:
            logger.debug("BM25 索引为空，返回空结果")
            return []

        logger.debug(f"BM25 检索: query='{query[:50]}...', k={k}")

        # 对查询分词
        query_tokens = tokenize(query, self._stop_words)
        if not query_tokens:
            logger.debug("查询分词后为空，返回空结果")
            return []

        # 计算 BM25 分数
        scores = self._bm25.get_scores(query_tokens)

        # 按分数排序，取 top k
        scored_pairs = list(enumerate(scores))
        scored_pairs.sort(key=lambda x: x[1], reverse=True)
        top_pairs = scored_pairs[:k]

        results = []
        for idx, score in top_pairs:
            if score <= 0:
                continue  # 0 分的不要
            results.append((self._documents[idx], float(score)))

        logger.debug(f"BM25 检索到 {len(results)} 个结果")
        return results

    def delete(self, ids: Optional[List[str]] = None) -> None:
        """
        删除文档

        Args:
            ids: 文档 ID 列表，None 表示清空全部
        """
        if ids is None:
            logger.warning("清空 BM25 索引")
            self._documents = []
            self._corpus_tokens = []
            self._bm25 = None
        else:
            # BM25 不支持高效删除，重建索引
            id_set = set(ids)
            new_docs = []
            new_tokens = []
            for i, (doc, tokens) in enumerate(zip(self._documents, self._corpus_tokens)):
                if str(i) not in id_set:
                    new_docs.append(doc)
                    new_tokens.append(tokens)
            self._documents = new_docs
            self._corpus_tokens = new_tokens
            self._bm25 = BM25Okapi(self._corpus_tokens) if new_tokens else None
            logger.info(f"删除 {len(ids)} 个文档，BM25 索引重建完成")

    def count(self) -> int:
        """获取 BM25 索引中的文档数量"""
        return len(self._documents)

    def persist(self) -> None:
        """
        持久化（BM25 索引是内存中的，不支持持久化）
        启动时需要重新建索引，或者自己实现 pickle 序列化
        """
        logger.debug("BM25 索引为内存结构，无需持久化")

    @property
    def documents(self) -> List[Document]:
        """获取所有文档（只读）"""
        return self._documents.copy()
