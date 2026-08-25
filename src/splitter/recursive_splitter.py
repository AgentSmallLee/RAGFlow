"""
递归字符文本切分器
按段落、句子、字符的优先级逐步切分，尽量保持语义完整
"""

from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .base import BaseSplitter
from config.settings import settings
from src.utils import logger


class RecursiveSplitter(BaseSplitter):
    """
    递归字符切分器
    优先在段落边界切分，其次是句子，最后是字符
    """

    # 切分分隔符优先级（从高到低）
    DEFAULT_SEPARATORS = [
        "\n\n\n",  # 三段换行
        "\n\n",    # 两段换行（段落分隔）
        "\n",      # 单行换行
        "。",       # 中文句号
        "！",       # 中文感叹号
        "？",       # 中文问号
        ". ",       # 英文句号+空格
        "! ",       # 英文感叹号+空格
        "? ",       # 英文问号+空格
        "; ",       # 分号+空格
        "；",       # 中文分号
        ", ",       # 英文逗号+空格
        "，",       # 中文逗号
        " ",        # 空格
        "",         # 最后按字符切分
    ]

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        separators: List[str] | None = None,
    ):
        """
        初始化切分器

        Args:
            chunk_size: 每个块的最大字符数，默认从配置读取
            chunk_overlap: 块之间的重叠字符数，默认从配置读取
            separators: 自定义分隔符列表
        """
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.separators = separators or self.DEFAULT_SEPARATORS

        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=self.separators,
            length_function=len,
            is_separator_regex=False,
        )

        logger.info(
            f"切分器初始化完成: chunk_size={self.chunk_size}, "
            f"chunk_overlap={self.chunk_overlap}"
        )

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """
        切分文档列表

        Args:
            documents: 待切分的文档列表

        Returns:
            切分后的文档块列表，每个块保留原始元数据并新增 chunk_index
        """
        if not documents:
            logger.warning("切分器收到空文档列表")
            return []

        logger.info(f"开始切分 {len(documents)} 个文档...")
        chunks = self._splitter.split_documents(documents)

        # 为每个 chunk 添加索引
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["chunk_size"] = len(chunk.page_content)

        logger.info(f"切分完成，共 {len(chunks)} 个文本块")
        return chunks

    def split_text(self, text: str) -> List[str]:
        """
        切分单个文本

        Args:
            text: 待切分的文本

        Returns:
            切分后的文本块列表
        """
        if not text:
            return []
        return self._splitter.split_text(text)
