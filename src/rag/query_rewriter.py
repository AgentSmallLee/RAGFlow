"""
查询改写模块
用户的原始问题可能表述不规范、太口语化、太短或太长，导致检索效果不好。
查询改写的目的：把用户的问题改写成更适合向量检索的形式，提升召回率。
"""

from typing import List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from config.settings import settings
from src.utils import logger


class QueryRewriter:
    """
    查询改写器
    支持多种改写策略，可组合使用
    """

    def __init__(self, llm: Optional[ChatOpenAI] = None):
        """
        初始化查询改写器

        Args:
            llm: LLM 实例，为 None 则用配置中的默认模型
        """
        if llm is None:
            if not settings.llm_api_key:
                raise ValueError("未配置 LLM_API_KEY，无法使用查询改写")
            self._llm = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                temperature=0.3,
            )
        else:
            self._llm = llm

        # 改写模板：把原始问题改写成 3 个不同表述的搜索查询
        self._rewrite_prompt = ChatPromptTemplate.from_template(
            """你是一个搜索查询优化专家。请将用户的问题改写为 3 个不同表述的搜索查询，
用于在知识库中检索相关文档。

要求：
1. 每个查询用一行表示，不要编号，不要标点
2. 从不同角度改写：关键词提取、完整句子、同义词替换
3. 保持原意，不要添加额外信息
4. 输出 3 行，每行一个查询

用户问题：{question}

改写后的 3 个查询："""
        )

        self._chain = self._rewrite_prompt | self._llm | StrOutputParser()
        logger.info("查询改写器初始化完成")

    def rewrite(self, question: str, n: int = 3) -> List[str]:
        """
        将一个问题改写成多个不同表述的查询

        Args:
            question: 原始问题
            n: 生成几个改写版本（默认 3 个）

        Returns:
            改写后的查询列表（包含原始问题 + 改写后的查询）
        """
        logger.info(f"开始改写查询: '{question}'")
        try:
            result = self._chain.invoke({"question": question})
            # 按行分割，过滤空行
            queries = [
                line.strip()
                for line in result.strip().split("\n")
                if line.strip()
            ]
            # 去掉可能的编号（如 "1. "、"- " 等前缀）
            cleaned = []
            for q in queries:
                # 去掉数字+点+空格
                import re
                q = re.sub(r"^\d+[\.\、]\s*", "", q)
                q = re.sub(r"^[-*•]\s*", "", q)
                if q:
                    cleaned.append(q)

            # 去重，保留原始问题在最前面
            all_queries = [question]
            for q in cleaned:
                if q not in all_queries and q != question:
                    all_queries.append(q)

            # 限制数量
            all_queries = all_queries[: n + 1]

            logger.info(
                f"查询改写完成: 原始 1 个 → 共 {len(all_queries)} 个"
            )
            for i, q in enumerate(all_queries):
                logger.debug(f"  [{i}] {q}")

            return all_queries

        except Exception as e:
            logger.warning(f"查询改写失败: {e}，将使用原始查询")
            return [question]

    def rewrite_for_search(self, question: str) -> str:
        """
        简化版：只生成一个优化后的搜索查询
        适合不想多次检索的场景

        Args:
            question: 原始问题

        Returns:
            优化后的查询
        """
        queries = self.rewrite(question, n=1)
        # 返回改写后的版本，如果没有就返回原问题
        return queries[1] if len(queries) > 1 else question
