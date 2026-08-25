"""
文本切分模块
将长文档切分为适合向量化的文本块
"""

from .base import BaseSplitter
from .recursive_splitter import RecursiveSplitter

__all__ = [
    "BaseSplitter",
    "RecursiveSplitter",
]
