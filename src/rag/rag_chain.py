"""
RAG 完整链路
将检索、Prompt 构建、LLM 生成串联起来，提供统一的问答接口
"""

from dataclasses import dataclass, field
from typing import List, Optional

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from .retriever import Retriever, RetrievedDocument
from .prompt_builder import PromptBuilder
from .query_rewriter import QueryRewriter
from config.settings import settings
from src.utils import logger


@dataclass
class RAGResponse:
    """
    RAG 回答结果
    包含最终回答、检索到的参考文档、以及处理过程信息
    """
    answer: str                                   # LLM 生成的回答
    question: str                                 # 原始问题
    source_documents: List[RetrievedDocument]     # 检索到的参考文档
    context: str                                  # 拼入 Prompt 的完整上下文
    metadata: dict = field(default_factory=dict)  # 其他元数据（耗时等）


class RAGChain:
    """
    RAG 问答链路
    整合检索器、Prompt 构建器和 LLM，提供 end-to-end 的问答能力
    """

    def __init__(
        self,
        retriever: Retriever,
        prompt_builder: Optional[PromptBuilder] = None,
        llm: Optional[ChatOpenAI] = None,
        query_rewriter: Optional[QueryRewriter] = None,
        enable_query_rewrite: bool = False,
        rewrite_on_empty_only: bool = True,
    ):
        """
        初始化 RAG 链

        Args:
            retriever: 检索器实例
            prompt_builder: Prompt 构建器，None 则使用默认
            llm: LLM 实例，None 则使用配置中的默认模型
            query_rewriter: 查询改写器实例，None 则根据 enable_query_rewrite 创建
            enable_query_rewrite: 是否启用查询改写（默认关闭）
            rewrite_on_empty_only: 只在检索不到时才改写（默认 True）
                                  False 表示每次都改写并合并检索结果
        """
        self._retriever = retriever
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._enable_query_rewrite = enable_query_rewrite
        self._rewrite_on_empty_only = rewrite_on_empty_only

        # 初始化 LLM
        if llm is None:
            if not settings.llm_api_key:
                raise ValueError(
                    "未配置 LLM_API_KEY。"
                    "请在 .env 文件中配置。"
                )
            self._llm = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                temperature=0.1,  # 问答场景使用较低温度以保证准确性
            )
        else:
            self._llm = llm

        # 初始化查询改写器
        if enable_query_rewrite:
            self._query_rewriter = query_rewriter or QueryRewriter(llm=self._llm)
        else:
            self._query_rewriter = None

        # 构建 LCEL 链：prompt → llm → 字符串输出
        self._chain = (
            self._prompt_builder.prompt_template
            | self._llm
            | StrOutputParser()
        )

        logger.info(
            f"RAG 链初始化完成: "
            f"model={settings.llm_model}, "
            f"top_k={retriever.top_k}, "
            f"query_rewrite={'on' if enable_query_rewrite else 'off'}"
        )

    def _retrieve_with_rewrite(
        self, question: str, top_k: int | None = None
    ) -> tuple[List[RetrievedDocument], dict]:
        """
        检索，支持查询改写

        Returns:
            (检索结果列表, 元数据字典)
        """
        # 先尝试原始查询
        retrieved_docs = self._retriever.retrieve(question, top_k=top_k)
        rewrite_info = {"rewritten": False, "original_count": len(retrieved_docs)}

        # 如果不启用改写，直接返回
        if not self._enable_query_rewrite or not self._query_rewriter:
            return retrieved_docs, rewrite_info

        # 策略 1：只有检索不到时才改写重试
        if self._rewrite_on_empty_only and retrieved_docs:
            return retrieved_docs, rewrite_info

        # 策略 2：改写查询，合并多个查询的检索结果（去重 + 按分数排序）
        logger.info("启用查询改写，生成多个查询版本...")
        queries = self._query_rewriter.rewrite(question)

        all_docs: dict[str, RetrievedDocument] = {}  # 用内容做 key 去重

        # 先加入原始查询的结果
        for doc in retrieved_docs:
            key = doc.document.page_content
            all_docs[key] = doc

        # 用每个改写后的查询再检索一次
        for q in queries[1:]:  # 跳过第一个（就是原始问题）
            more_docs = self._retriever.retrieve(q, top_k=top_k)
            for doc in more_docs:
                key = doc.document.page_content
                if key not in all_docs or doc.score > all_docs[key].score:
                    all_docs[key] = doc

        # 按分数从高到低排序，取 top_k
        k = top_k or self._retriever.top_k
        merged = sorted(all_docs.values(), key=lambda x: x.score, reverse=True)[:k]

        # 重新设置排名
        for i, doc in enumerate(merged):
            doc.rank = i + 1

        rewrite_info.update({
            "rewritten": True,
            "rewritten_queries": queries,
            "original_count": len(retrieved_docs),
            "merged_count": len(merged),
        })

        logger.info(
            f"查询改写完成: 原始 {len(retrieved_docs)} 条 → 合并后 {len(merged)} 条"
        )
        return merged, rewrite_info

    def query(self, question: str, top_k: int | None = None) -> RAGResponse:
        """
        执行一次 RAG 问答

        Args:
            question: 用户问题
            top_k: 可选，覆盖默认检索数量

        Returns:
            RAGResponse 回答结果对象
        """
        logger.info(f"RAG 查询开始: '{question}'")

        # 步骤 1: 检索相关文档（支持查询改写）
        retrieved_docs, rewrite_meta = self._retrieve_with_rewrite(question, top_k=top_k)
        documents = [r.document for r in retrieved_docs]

        # 步骤 2: 构建上下文
        context = self._prompt_builder.build_context(documents)

        if not retrieved_docs:
            logger.warning("未检索到相关文档，将告知用户无法回答")
            no_result_answer = "抱歉，未找到与您问题相关的参考资料，无法回答此问题。"
            return RAGResponse(
                answer=no_result_answer,
                question=question,
                source_documents=[],
                context=context,
                metadata={"retrieved_count": 0, **rewrite_meta},
            )

        # 步骤 3: 调用 LLM 生成回答
        logger.info(f"调用 LLM 生成回答，上下文长度: {len(context)} 字符")
        answer = self._chain.invoke({
            "context": context,
            "question": question,
        })

        logger.info(f"RAG 查询完成，回答长度: {len(answer)} 字符")

        return RAGResponse(
            answer=answer,
            question=question,
            source_documents=retrieved_docs,
            context=context,
            metadata={
                "retrieved_count": len(retrieved_docs),
                "top_score": retrieved_docs[0].score if retrieved_docs else 0.0,
                **rewrite_meta,
            },
        )

    def stream_query(self, question: str, top_k: int | None = None):
        """
        流式输出 RAG 回答（生成器方式）

        Args:
            question: 用户问题
            top_k: 可选，覆盖默认检索数量

        Yields:
            流式生成的回答片段（字符串）
        """
        logger.info(f"流式 RAG 查询开始: '{question}'")

        # 步骤 1: 检索
        retrieved_docs = self._retriever.retrieve(question, top_k=top_k)
        documents = [r.document for r in retrieved_docs]

        if not retrieved_docs:
            yield "抱歉，未找到与您问题相关的参考资料，无法回答此问题。"
            return

        # 步骤 2: 构建上下文
        context = self._prompt_builder.build_context(documents)

        # 步骤 3: 流式生成
        for chunk in self._chain.stream({
            "context": context,
            "question": question,
        }):
            yield chunk

    @property
    def retriever(self) -> Retriever:
        """获取检索器"""
        return self._retriever

    @property
    def prompt_builder(self) -> PromptBuilder:
        """获取 Prompt 构建器"""
        return self._prompt_builder
