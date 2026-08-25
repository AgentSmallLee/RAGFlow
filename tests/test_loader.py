"""
文档加载器单元测试
"""

import pytest

from src.loader import TextLoader, DocumentLoader


@pytest.fixture
def sample_txt_file(tmp_path):
    """创建一个临时文本文件"""
    content = "这是第一段文本。\n\n这是第二段文本，内容更长一些。\n\n这是第三段。"
    file_path = tmp_path / "test.txt"
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def sample_md_file(tmp_path):
    """创建一个临时 Markdown 文件"""
    content = "# 标题\n\n这是正文内容。\n\n## 二级标题\n\n更多内容在这里。"
    file_path = tmp_path / "test.md"
    file_path.write_text(content, encoding="utf-8")
    return file_path


class TestTextLoader:
    """测试 TextLoader"""

    def test_load_txt_file(self, sample_txt_file):
        """测试加载 TXT 文件"""
        loader = TextLoader()
        docs = loader.load(sample_txt_file)

        assert len(docs) == 1
        assert "这是第一段文本" in docs[0].page_content
        assert docs[0].metadata["file_name"] == "test.txt"
        assert docs[0].metadata["file_type"] == "txt"

    def test_load_md_file(self, sample_md_file):
        """测试加载 Markdown 文件"""
        loader = TextLoader()
        docs = loader.load(sample_md_file)

        assert len(docs) == 1
        assert "# 标题" in docs[0].page_content
        assert docs[0].metadata["file_type"] == "md"

    def test_supports_txt(self, sample_txt_file):
        """测试支持 TXT 格式"""
        loader = TextLoader()
        assert loader.supports(sample_txt_file) is True

    def test_supports_md(self, sample_md_file):
        """测试支持 MD 格式"""
        loader = TextLoader()
        assert loader.supports(sample_md_file) is True

    def test_not_supports_pdf(self, tmp_path):
        """测试不支持 PDF 格式"""
        loader = TextLoader()
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.touch()
        assert loader.supports(fake_pdf) is False

    def test_file_not_found(self):
        """测试文件不存在时抛出异常"""
        loader = TextLoader()
        with pytest.raises(FileNotFoundError):
            # 通过 DocumentLoader 间接测试
            DocumentLoader().load_file("nonexistent_file.txt")


class TestDocumentLoader:
    """测试 DocumentLoader（统一加载入口）"""

    def test_load_single_file(self, sample_txt_file):
        """测试加载单个文件"""
        loader = DocumentLoader()
        docs = loader.load_file(sample_txt_file)

        assert len(docs) == 1
        assert "这是第一段文本" in docs[0].page_content

    def test_load_directory(self, tmp_path):
        """测试加载整个目录"""
        # 创建多个文件
        (tmp_path / "file1.txt").write_text("文件1的内容", encoding="utf-8")
        (tmp_path / "file2.md").write_text("# 文件2\n\n内容", encoding="utf-8")
        (tmp_path / "file3.unknown").write_text("不支持的格式")

        loader = DocumentLoader()
        docs = loader.load_directory(tmp_path, recursive=False)

        # 应该只加载支持的格式
        assert len(docs) == 2

    def test_load_directory_recursive(self, tmp_path):
        """测试递归加载子目录"""
        sub_dir = tmp_path / "subdir"
        sub_dir.mkdir()
        (tmp_path / "file1.txt").write_text("顶层文件", encoding="utf-8")
        (sub_dir / "file2.txt").write_text("子目录文件", encoding="utf-8")

        loader = DocumentLoader()

        # 非递归
        docs_non_recursive = loader.load_directory(tmp_path, recursive=False)
        assert len(docs_non_recursive) == 1

        # 递归
        docs_recursive = loader.load_directory(tmp_path, recursive=True)
        assert len(docs_recursive) == 2

    def test_unsupported_format_raises(self, tmp_path):
        """测试加载不支持的格式时抛出异常"""
        fake_file = tmp_path / "test.unknown"
        fake_file.write_text("test")

        loader = DocumentLoader()
        with pytest.raises(ValueError, match="不支持的文件格式"):
            loader.load_file(fake_file)

    def test_supported_extensions(self):
        """测试支持的扩展名列表"""
        loader = DocumentLoader()
        exts = loader.supported_extensions
        assert ".txt" in exts
        assert ".md" in exts
        assert ".pdf" in exts
        assert ".docx" in exts
