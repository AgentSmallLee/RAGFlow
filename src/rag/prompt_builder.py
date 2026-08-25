"""
Prompt 构建器模块
负责将用户问题和检索到的上下文拼接成最终的 Prompt
"""

from typing import List

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate

from src.utils import logger


# 系统提示词模板 —— 定义 AI 的角色和回答规范
SYSTEM_PROMPT_TEMPLATE = """你是一个专业的知识助手，请根据提供的上下文信息回答用户的问题。

## 回答规则：
1.  **基于上下文**：请主要根据下方【参考资料中的内容来回答问题
2.  **不要编造**：如果参考资料中没有相关信息，请明确说"根据现有资料无法回答此问题"，不要编造内容
3.  **引用来源**：回答中涉及的关键信息，可以注明来源（如"根据文档XXX"）
4.  **结构清晰**：回答应当条理清晰，分点说明时使用有序列表
5.  **语言简洁**：回答要准确、简洁，避免无关信息
6.  **客观中立**：保持客观中立的语气，不添加个人观点

---
【参考资料】
{context}
---

请根据以上参考资料回答用户问题。如果问题与参考资料无关，请告知用户。"""


class PromptBuilder:
    """
    Prompt 构建器
    负责将用户问题和检索到的上下文组合成最终的 Prompt
    """

    def __init__(
        self,
        system_template: str | None = None):
        """
        初始化 Prompt 构建器

        Args:
            system_template: 自定义系统提示词模板，None 使用默认模板
        """
        self._system_template = system_template or SYSTEM_PROMPT_TEMPLATE
        self._prompt = self._build_chat_prompt()

    def _build_chat_prompt(self) -> ChatPromptTemplate:
        """构建 ChatPromptTemplate"""
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(self._system_template),
            HumanMessagePromptTemplate.from_template("{question}"),
        ])

    def build_context(self, documents: List[Document]) -> str:
        """
        将检索到的文档列表格式化为上下文字符串

        Args:
            documents: 检索到的文档列表

        Returns:
            格式化后的上下文字符串
        """
        if not documents:
            return "（无相关参考资料）"

        context_parts = []
        for i, doc in enumerate(documents, 1):
            source = doc.metadata.get("file_name", doc.metadata.get("source", "未知来源"))
            page = doc.metadata.get("page")
            source_info = f"文档 {i}（来源: {source}"
            if page:
                source_info += f"，第 {page} 页"
            source_info += "）"

            content = doc.page_content.strip()
            context_parts.append(f"{source_info}:\n{content}")

        context = "\n\n".join(context_parts)
        logger.debug(f"构建上下文，共 {len(documents)} 个文档片段")
        return context

    def build_prompt(self, question: str, documents: List[Document]) -> ChatPromptTemplate:
        """
        构建完整的 Prompt

        Args:
            question: 用户问题
            documents: 检索到的相关文档

        Returns:
            格式化后的 ChatPromptTemplate
        """
        context = self.build_context(documents)
        logger.debug(f"构建 Prompt: question='{question[:50]}...', context_length={len(context)}")
        return self._prompt.format_messages(context=context, question=question)

    @property
    def prompt_template(self) -> ChatPromptTemplate:
        """获取原始的 prompt template（用于 LCEL 链）"""
        return self._prompt

    @property
    def system_template(self) -> str:
        """获取系统提示词模板"""
        return self._system_template
