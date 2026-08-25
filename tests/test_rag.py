"""
RAG 核心流程单元测试
使用 mock 避免实际调用 API
"""

from unittest.mock import Mock, MagicMock

import pytest
from langchain_core.documents import Document

from src.rag.prompt_builder import PromptBuilder
from src.rag.retriever import Retriever, RetrievedDocument


@pytest.fixture
def sample_documents():
    """测试用的文档列表"""
    return [
        Document(
            page_content="RAG 的全称是 Retrieval-Augmented Generation，即检索增强生成。",
            metadata={"file_name": "rag_intro.md", "source": "rag_intro.md"},
        ),
        Document(
            page_content="RAG 可以减少大模型的幻觉问题，提高回答的准确性。",
            metadata={"file_name": "rag_intro.md", "source": "rag_intro.md"},
        ),
        Document(
            page_content="LangChain 是一个用于开发 LLM 应用的开源框架。",
            metadata={"file_name": "langchain.txt", "source": "langchain.txt"},
        ),
    ]


class TestPromptBuilder:
    """测试 PromptBuilder"""

    def test_build_context_with_docs(self, sample_documents):
        """测试构建包含文档的上下文"""
        builder = PromptBuilder()
        context = builder.build_context(sample_documents)

        assert "文档 1" in context
        assert "文档 2" in context
        assert "文档 3" in context
        assert "rag_intro.md" in context
        assert "Retrieval-Augmented Generation" in context

    def test_build_context_empty(self):
        """测试空文档的上下文"""
        builder = PromptBuilder()
        context = builder.build_context([])

        assert "无相关参考资料" in context

    def test_build_context_includes_page_number(self):
        """测试上下文中包含页码"""
        docs = [
            Document(
                page_content="测试内容",
                metadata={"file_name": "test.pdf", "page": 5},
            )
        ]
        builder = PromptBuilder()
        context = builder.build_context(docs)

        assert "第 5 页" in context

    def test_system_template_default(self):
        """测试默认系统提示词存在"""
        builder = PromptBuilder()
        assert len(builder.system_template) > 100
        assert "参考资料" in builder.system_template

    def test_custom_system_template(self):
        """测试自定义系统提示词"""
        custom_template = "你是一个测试助手。\n\n{context}"
        builder = PromptBuilder(system_template=custom_template)
        assert builder.system_template == custom_template

    def test_prompt_template_has_variables(self):
        """测试 prompt 模板包含必要的变量"""
        builder = PromptBuilder()
        template = builder.prompt_template

        # 检查变量
        input_vars = template.input_variables
        assert "context" in input_vars
        assert "question" in input_vars


class TestRetriever:
    """测试 Retriever"""

    def test_retrieve_returns_ranked_results(self):
        """测试检索结果按排名返回"""
        # Mock 向量库
        mock_vector_store = Mock()
        mock_vector_store.similarity_search_with_score.return_value = [
            (Document(page_content="最相关", metadata={}), 0.95),
            (Document(page_content="次相关", metadata={}), 0.85),
            (Document(page_content="一般", metadata={}), 0.75),
        ]

        retriever = Retriever(
            vector_store=mock_vector_store,
            top_k=3,
            similarity_threshold=0.0,
        )
        results = retriever.retrieve("测试问题")

        assert len(results) == 3
        assert results[0].rank == 1
        assert results[0].score == 0.95
        assert results[1].rank == 2
        assert results[2].rank == 3

    def test_retrieve_filters_by_threshold(self):
        """测试相似度阈值过滤"""
        mock_vector_store = Mock()
        mock_vector_store.similarity_search_with_score.return_value = [
            (Document(page_content="高相关", metadata={}), 0.90),
            (Document(page_content="低相关", metadata={}), 0.50),
            (Document(page_content="不相关", metadata={}), 0.30),
        ]

        retriever = Retriever(
            vector_store=mock_vector_store,
            top_k=5,
            similarity_threshold=0.6,
        )
        results = retriever.retrieve("测试问题")

        # 只有 0.9 分的应该被保留
        assert len(results) == 1
        assert results[0].score >= 0.6

    def test_retrieve_as_documents(self):
        """测试 retrieve_as_documents 返回 Document 列表"""
        mock_vector_store = Mock()
        mock_vector_store.similarity_search_with_score.return_value = [
            (Document(page_content="内容1", metadata={}), 0.9),
            (Document(page_content="内容2", metadata={}), 0.8),
        ]

        retriever = Retriever(
            vector_store=mock_vector_store,
            top_k=2,
            similarity_threshold=0.0,
        )
        docs = retriever.retrieve_as_documents("测试问题")

        assert len(docs) == 2
        assert all(isinstance(d, Document) for d in docs)

    def test_retrieve_empty_results(self):
        """测试无结果的情况"""
        mock_vector_store = Mock()
        mock_vector_store.similarity_search_with_score.return_value = []

        retriever = Retriever(
            vector_store=mock_vector_store,
            top_k=4,
            similarity_threshold=0.0,
        )
        results = retriever.retrieve("测试问题")

        assert len(results) == 0

    def test_retrieve_passes_k_to_vectorstore(self):
        """测试 top_k 参数正确传递给向量库"""
        mock_vector_store = Mock()
        mock_vector_store.similarity_search_with_score.return_value = []

        retriever = Retriever(
            vector_store=mock_vector_store,
            top_k=5,
            similarity_threshold=0.0,
        )
        retriever.retrieve("测试问题", top_k=3)

        # 验证传递给向量库的 k 值
        mock_vector_store.similarity_search_with_score.assert_called_once()
        call_kwargs = mock_vector_store.similarity_search_with_score.call_args
        assert call_kwargs.kwargs.get("k", call_kwargs[1].get("k")) == 3
