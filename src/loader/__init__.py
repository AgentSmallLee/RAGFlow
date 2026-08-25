"""
文档加载模块
支持多种格式文档的统一加载
"""

from .base import BaseLoader
from .text_loader import TextLoader
from .pdf_loader import PdfLoader
from .docx_loader import DocxLoader
from .document_loader import DocumentLoader

__all__ = [
    "BaseLoader",
    "TextLoader",
    "PdfLoader",
    "DocxLoader",
    "DocumentLoader",
]
