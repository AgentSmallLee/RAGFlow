"""
向量化模块
提供文本到向量的转换能力
"""

from .base import BaseEmbedding
from .openai_embedding import OpenAIEmbedding

__all__ = [
    "BaseEmbedding",
    "OpenAIEmbedding",
]
