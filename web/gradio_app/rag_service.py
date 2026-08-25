"""
RAG 服务封装
管理 RAG 系统的生命周期，提供参数动态调整、文件上传建库、流式问答等能力
"""

import shutil
import threading
from pathlib import Path
from typing import Generator, List, Optional, Tuple

from config.settings import settings
from src.embedding import OpenAIEmbedding
from src.embedding.base import BaseEmbedding
from src.loader import DocumentLoader
from src.rag import RAGChain, RAGResponse, Retriever
from src.splitter import RecursiveSplitter
from src.utils import logger
from src.vectorstore import create_vector_store
from src.vectorstore.base import BaseVectorStore

# 上传文件持久化目录（与 data/documents 分开）
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "data" / "uploads"


class RAGService:
    """
    RAG 服务封装
    管理 RAGChain 生命周期，支持参数动态调整、文件上传建库、流式问答
    """

    def __init__(self):
        # 组件实例（按策略缓存）
        self._embedding: Optional[BaseEmbedding] = None
        self._vector_store: Optional[BaseVectorStore] = None
        self._rag_chain: Optional[RAGChain] = None
        self._loader = DocumentLoader()
        self._splitter: Optional[RecursiveSplitter] = None

        # 当前生效的参数
        self._params: dict = {}

        # 线程锁（防止上传/检索并发操作向量库）
        self._lock = threading.Lock()

        # 确保上传目录存在
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # ===================== 初始化 =====================

    def initialize(self) -> None:
        """
        首次初始化 RAG 服务
        使用配置文件中的默认参数
        """
        logger.info("正在初始化 RAG 服务...")

        # 1. 创建 embedding（只创建一次，永久缓存）
        if self._embedding is None:
            self._embedding = OpenAIEmbedding()
            logger.info(f"Embedding 模型就绪: {settings.embedding_model}")

        # 2. 创建向量库
        self._vector_store = create_vector_store(embedding=self._embedding)
        logger.info(f"向量库就绪，现有 {self._vector_store.count()} 个文档块")

        # 3. 创建切分器
        self._splitter = RecursiveSplitter()

        # 4. 创建检索器和 RAGChain
        retriever = Retriever(
            vector_store=self._vector_store,
            top_k=settings.top_k,
            similarity_threshold=settings.similarity_threshold,
        )
        self._rag_chain = RAGChain(
            retriever=retriever,
            enable_query_rewrite=settings.enable_query_rewrite,
            rewrite_on_empty_only=settings.rewrite_on_empty_only,
        )

        # 记录当前参数
        self._params = {
            "top_k": settings.top_k,
            "similarity_threshold": settings.similarity_threshold,
            "enable_query_rewrite": settings.enable_query_rewrite,
            "rewrite_on_empty_only": settings.rewrite_on_empty_only,
            "enable_hybrid_search": settings.enable_hybrid_search,
            "hybrid_fusion_method": settings.hybrid_fusion_method,
            "hybrid_vector_weight": settings.hybrid_vector_weight,
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
        }

        logger.info("RAG 服务初始化完成")

    # ===================== 参数管理 =====================

    def update_parameters(
        self,
        top_k: int,
        similarity_threshold: float,
        enable_query_rewrite: bool,
        rewrite_on_empty_only: bool,
        enable_hybrid_search: bool,
        hybrid_fusion_method: str,
        hybrid_vector_weight: float,
        chunk_size: int,
        chunk_overlap: int,
    ) -> str:
        """
        更新参数，按需重建组件

        Returns:
            状态消息字符串
        """
        with self._lock:
            if self._rag_chain is None:
                raise RuntimeError("RAG 服务未初始化，请先调用 initialize()")

            old = self._params
            need_rebuild_vs = False
            need_rebuild_chain = False
            need_reindex = False

            # 检测混合检索相关参数变化（需要重建向量库）
            if (
                enable_hybrid_search != old["enable_hybrid_search"]
                or hybrid_fusion_method != old["hybrid_fusion_method"]
                or hybrid_vector_weight != old["hybrid_vector_weight"]
            ):
                need_rebuild_vs = True
                need_rebuild_chain = True
                need_reindex = True
                logger.info("混合检索参数变化，需要重建向量库")

            # 检测 chunk 参数变化（切分器重建，下次上传生效）
            if (
                chunk_size != old["chunk_size"]
                or chunk_overlap != old["chunk_overlap"]
            ):
                self._splitter = RecursiveSplitter(
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
                logger.info(f"切分参数更新: chunk_size={chunk_size}, overlap={chunk_overlap}")

            # 重建向量库
            if need_rebuild_vs:
                # 临时修改 settings 来影响 create_vector_store
                settings.enable_hybrid_search = enable_hybrid_search
                settings.hybrid_fusion_method = hybrid_fusion_method
                settings.hybrid_vector_weight = hybrid_vector_weight

                self._vector_store = create_vector_store(embedding=self._embedding)
                logger.info("向量库已重建")

            # 检测检索/RAG 链参数变化
            if (
                top_k != old["top_k"]
                or similarity_threshold != old["similarity_threshold"]
                or enable_query_rewrite != old["enable_query_rewrite"]
                or rewrite_on_empty_only != old["rewrite_on_empty_only"]
                or need_rebuild_chain
            ):
                retriever = Retriever(
                    vector_store=self._vector_store,
                    top_k=top_k,
                    similarity_threshold=similarity_threshold,
                )
                self._rag_chain = RAGChain(
                    retriever=retriever,
                    enable_query_rewrite=enable_query_rewrite,
                    rewrite_on_empty_only=rewrite_on_empty_only,
                )
                logger.info("检索器和 RAG 链已重建")

            # 如果需要重建索引（混合检索切换）
            reindex_msg = ""
            if need_reindex:
                count, msg = self._reindex_all_internal(chunk_size, chunk_overlap)
                reindex_msg = f"，已重新索引 {count} 个文档块"

            # 更新参数记录
            self._params.update({
                "top_k": top_k,
                "similarity_threshold": similarity_threshold,
                "enable_query_rewrite": enable_query_rewrite,
                "rewrite_on_empty_only": rewrite_on_empty_only,
                "enable_hybrid_search": enable_hybrid_search,
                "hybrid_fusion_method": hybrid_fusion_method,
                "hybrid_vector_weight": hybrid_vector_weight,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
            })

            return f"参数已更新{reindex_msg}"

    def get_current_params(self) -> dict:
        """获取当前参数值"""
        return dict(self._params)

    # ===================== 文档管理 =====================

    def add_uploaded_files(
        self,
        file_paths: List[str],
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> Tuple[int, int, str]:
        """
        处理上传的文件，添加到向量库

        Args:
            file_paths: Gradio 上传的文件路径列表
            chunk_size: 切分块大小（None 使用当前参数）
            chunk_overlap: 切分重叠大小（None 使用当前参数）

        Returns:
            (新增文档块数, 总文档块数, 状态消息)
        """
        with self._lock:
            if self._vector_store is None:
                raise RuntimeError("RAG 服务未初始化")

            cs = chunk_size or self._params["chunk_size"]
            co = chunk_overlap or self._params["chunk_overlap"]

            # 如果切分参数和当前不同，临时创建新 splitter
            splitter = self._splitter
            if cs != self._params["chunk_size"] or co != self._params["chunk_overlap"]:
                splitter = RecursiveSplitter(chunk_size=cs, chunk_overlap=co)

            total_new = 0
            success_files = []
            failed_files = []

            for src_path in file_paths:
                src = Path(src_path)
                if not src.exists():
                    failed_files.append(f"{src.name} (文件不存在)")
                    continue

                try:
                    # 移动到持久化上传目录
                    dest = UPLOAD_DIR / src.name
                    # 同名文件直接覆盖（用户重新上传 = 更新）
                    shutil.move(str(src), str(dest))

                    # 加载文档
                    docs = self._loader.load_file(dest)
                    if not docs:
                        failed_files.append(f"{src.name} (无内容)")
                        continue

                    # 切分
                    chunks = splitter.split_documents(docs)

                    # 添加 source_file 元数据
                    for chunk in chunks:
                        chunk.metadata["source_file"] = dest.name

                    # 入库
                    self._vector_store.add_documents(chunks)
                    total_new += len(chunks)
                    success_files.append(f"{src.name} ({len(chunks)} 块)")

                    logger.info(f"文件 {src.name} 入库成功，{len(chunks)} 个文本块")

                except Exception as e:
                    logger.error(f"处理文件 {src.name} 失败: {e}")
                    failed_files.append(f"{src.name} ({str(e)})")

            # 持久化
            self._vector_store.persist()

            total_count = self._vector_store.count()

            # 组装消息
            msg_parts = []
            if success_files:
                msg_parts.append(f"成功: {', '.join(success_files)}")
            if failed_files:
                msg_parts.append(f"失败: {', '.join(failed_files)}")

            return total_new, total_count, "\n".join(msg_parts)

    def rebuild_all(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> Tuple[int, str]:
        """
        清空并重建整个向量库索引

        Returns:
            (总文档块数, 状态消息)
        """
        with self._lock:
            cs = chunk_size or self._params["chunk_size"]
            co = chunk_overlap or self._params["chunk_overlap"]
            count, msg = self._reindex_all_internal(cs, co)
            return count, msg

    def _reindex_all_internal(self, chunk_size: int, chunk_overlap: int) -> Tuple[int, str]:
        """
        内部重建索引方法（调用方需持有锁）
        从 uploads 目录和 documents 目录加载所有文档重建
        """
        if self._vector_store is None:
            raise RuntimeError("RAG 服务未初始化")

        # 清空现有向量库
        self._vector_store.delete()
        logger.info("已清空向量库")

        # 收集所有文档目录
        doc_dirs = [UPLOAD_DIR, settings.documents_path]

        splitter = RecursiveSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        total_chunks = 0
        dir_results = []

        for doc_dir in doc_dirs:
            if not doc_dir.exists():
                continue

            files = list(doc_dir.glob("**/*"))
            files = [f for f in files if f.is_file() and not f.name.startswith(".")]
            if not files:
                continue

            try:
                docs = self._loader.load_directory(doc_dir)
                if not docs:
                    continue

                chunks = splitter.split_documents(docs)
                self._vector_store.add_documents(chunks)
                total_chunks += len(chunks)
                dir_results.append(f"{doc_dir.name}: {len(chunks)} 块")

            except Exception as e:
                logger.error(f"重建索引时处理 {doc_dir} 失败: {e}")
                dir_results.append(f"{doc_dir.name}: 失败 ({e})")

        # 持久化
        self._vector_store.persist()

        msg = f"重建完成，共 {total_chunks} 个文档块"
        if dir_results:
            msg += "\n" + "\n".join(dir_results)

        logger.info(msg)
        return total_chunks, msg

    def get_uploaded_file_list(self) -> List[str]:
        """获取已上传文件列表"""
        if not UPLOAD_DIR.exists():
            return []
        return sorted([f.name for f in UPLOAD_DIR.iterdir() if f.is_file()])

    def get_total_documents(self) -> int:
        """获取向量库中文档块总数"""
        if self._vector_store is None:
            return 0
        return self._vector_store.count()

    # ===================== 问答 =====================

    def query(self, question: str, top_k: Optional[int] = None) -> RAGResponse:
        """
        非流式问答

        Args:
            question: 用户问题
            top_k: 覆盖默认 top_k

        Returns:
            RAGResponse 回答结果
        """
        if self._rag_chain is None:
            raise RuntimeError("RAG 服务未初始化")
        return self._rag_chain.query(question, top_k=top_k)

    def stream_query(
        self,
        question: str,
        top_k: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """
        流式问答（生成器）

        Args:
            question: 用户问题
            top_k: 覆盖默认 top_k

        Yields:
            回答文本片段
        """
        if self._rag_chain is None:
            raise RuntimeError("RAG 服务未初始化")

        for chunk in self._rag_chain.stream_query(question, top_k=top_k):
            yield chunk

    def stream_query_with_sources(
        self,
        question: str,
        top_k: Optional[int] = None,
    ) -> Generator[Tuple[str, str], None, None]:
        """
        流式问答，同时返回参考资料

        Yields:
            (当前完整回答, 参考资料 Markdown)
        """
        # 先做一次完整查询拿到 source_documents
        response = self.query(question, top_k=top_k)
        sources_md = self._format_sources_markdown(response)

        # 如果没有检索到结果，直接返回完整回答
        if not response.source_documents:
            yield response.answer, sources_md
            return

        # 流式输出（把完整回答按字符模拟流式，效果不如 stream_query 但避免两次 LLM 调用）
        # 为了更好的体验，用 stream_query 再跑一次流式
        full_answer = ""
        for chunk in self.stream_query(question, top_k=top_k):
            full_answer += chunk
            yield full_answer, sources_md

    @staticmethod
    def _format_sources_markdown(response: RAGResponse) -> str:
        """将检索来源格式化为 Markdown"""
        if not response.source_documents:
            return "⚠️ 未检索到相关参考资料"

        lines = ["### 📚 参考资料\n"]
        for item in response.source_documents:
            doc = item.document
            source = doc.metadata.get("file_name", doc.metadata.get("source_file", "未知"))
            page = doc.metadata.get("page")
            if page:
                source += f" (p.{page})"

            preview = doc.page_content[:80].replace("\n", " ")
            if len(doc.page_content) > 80:
                preview += "..."

            lines.append(
                f"- **[{item.rank}]** {source}  \n"
                f"  相似度: `{item.score:.4f}`  \n"
                f"  摘要: {preview}"
            )

        return "\n".join(lines)

    # ===================== 属性 =====================

    @property
    def rag_chain(self) -> RAGChain:
        if self._rag_chain is None:
            raise RuntimeError("RAG 服务未初始化")
        return self._rag_chain

    @property
    def is_initialized(self) -> bool:
        return self._rag_chain is not None
