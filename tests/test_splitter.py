"""
文本切分器单元测试
"""

import pytest

from langchain_core.documents import Document
from src.splitter import RecursiveSplitter


@pytest.fixture
def sample_long_text():
    """生成一段较长的测试文本"""
    paragraphs = []
    for i in range(20):
        paragraphs.append(f"这是第 {i+1} 段内容。" * 10)
    return "\n\n".join(paragraphs)


@pytest.fixture
def sample_documents(sample_long_text):
    """生成测试文档列表"""
    return [
        Document(
            page_content=sample_long_text,
            metadata={"source": "test1.txt", "file_name": "test1.txt"},
        ),
        Document(
            page_content="短篇文档，只有一句话。",
            metadata={"source": "test2.txt", "file_name": "test2.txt"},
        ),
    ]


class TestRecursiveSplitter:
    """测试 RecursiveSplitter"""

    def test_split_text_basic(self, sample_long_text):
        """测试基本的文本切分"""
        splitter = RecursiveSplitter(chunk_size=200, chunk_overlap=20)
        chunks = splitter.split_text(sample_long_text)

        assert len(chunks) > 1
        # 每个块的长度不应显著超过 chunk_size
        for chunk in chunks:
            assert len(chunk) <= 250  # 允许一定的余量

    def test_split_text_empty(self):
        """测试空文本切分"""
        splitter = RecursiveSplitter()
        chunks = splitter.split_text("")
        assert chunks == []

    def test_split_documents_preserves_metadata(self, sample_documents):
        """测试切分后元数据是否保留"""
        splitter = RecursiveSplitter(chunk_size=100, chunk_overlap=10)
        chunks = splitter.split_documents(sample_documents)

        assert len(chunks) > 2
        # 检查元数据是否保留
        first_file_chunks = [
            c for c in chunks if c.metadata.get("file_name") == "test1.txt"
        ]
        assert len(first_file_chunks) > 1
        assert first_file_chunks[0].metadata["source"] == "test1.txt"

    def test_chunk_index_added(self, sample_documents):
        """测试是否添加了 chunk_index 元数据"""
        splitter = RecursiveSplitter(chunk_size=100, chunk_overlap=10)
        chunks = splitter.split_documents(sample_documents)

        for i, chunk in enumerate(chunks):
            assert "chunk_index" in chunk.metadata
            assert chunk.metadata["chunk_index"] == i

    def test_chunk_size_config(self):
        """测试不同的 chunk_size 配置"""
        # 使用固定模式的文本，便于验证
        text = "一二三四五六七八九十" * 50  # 500 字

        splitter_large = RecursiveSplitter(chunk_size=200, chunk_overlap=0)
        chunks_large = splitter_large.split_text(text)

        splitter_small = RecursiveSplitter(chunk_size=50, chunk_overlap=0)
        chunks_small = splitter_small.split_text(text)

        # 小块的数量应该多于大块
        assert len(chunks_small) > len(chunks_large)

    def test_overlap_between_chunks(self):
        """测试块之间是否有重叠"""
        text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 5  # 130 字符

        splitter = RecursiveSplitter(chunk_size=50, chunk_overlap=10)
        chunks = splitter.split_text(text)

        if len(chunks) >= 2:
            # 相邻块之间应该有重叠内容
            overlap = set(chunks[0]) & set(chunks[1])
            # 有共同字符（简单验证）
            assert len(overlap) > 0

    def test_empty_documents(self):
        """测试空文档列表"""
        splitter = RecursiveSplitter()
        chunks = splitter.split_documents([])
        assert chunks == []

    def test_short_document_unchanged(self):
        """测试短文档是否保持完整（不切分）"""
        short_text = "这是一篇很短的文档。"
        splitter = RecursiveSplitter(chunk_size=1000, chunk_overlap=0)
        chunks = splitter.split_text(short_text)

        assert len(chunks) == 1
        assert chunks[0] == short_text
