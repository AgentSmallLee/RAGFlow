#!/usr/bin/env python3
"""
在线问答脚本
交互式 RAG 问答，支持多轮对话
"""
import sys

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.table import Table

from config.settings import settings
from src.embedding import OpenAIEmbedding
from src.vectorstore import create_vector_store
from src.rag import RAGChain, Retriever
from src.utils import logger, setup_logger

console = Console()


def print_sources(response, rag_chain):
    """打印参考来源表格"""
    if not response.source_documents:
        return

    table = Table(
        title="📚 参考资料",
        show_header=True,
        header_style="bold magenta",
        border_style="magenta",
    )
    table.add_column("排名", style="dim", width=6)
    table.add_column("来源文档", width=40)
    table.add_column("相似度", width=12, justify="right")
    table.add_column("内容预览", width=50)

    for item in response.source_documents:
        doc = item.document
        source = doc.metadata.get("file_name", "未知")
        page = doc.metadata.get("page")
        if page:
            source += f" (p.{page})"
        score = f"{item.score:.4f}"
        preview = doc.page_content[:50].replace("\n", " ") + "..."
        table.add_row(str(item.rank), source, score, preview)

    console.print(table)


def init_rag_chain():
    """初始化 RAG 链"""
    # 检查 API Key（LLM 和 Embedding 都需要）
    if not settings.llm_api_key:
        console.print(
            "[red]错误: 未配置 LLM_API_KEY[/red]\n"
            "请复制 .env.example 为 .env 并填入 LLM_API_KEY"
        )
        sys.exit(1)
    if not settings.embedding_api_key:
        console.print(
            "[red]错误: 未配置 EMBEDDING_API_KEY[/red]\n"
            "请复制 .env.example 为 .env 并填入 EMBEDDING_API_KEY"
        )
        sys.exit(1)

    # 初始化 Embedding
    embedding = OpenAIEmbedding()

    # 初始化向量库（根据配置自动选择纯向量或混合检索）
    vector_store = create_vector_store(embedding=embedding)
    count = vector_store.count()

    if count == 0:
        console.print(
            "[yellow]⚠️  向量库为空！[/yellow]\n"
            "请先运行 [bold]python build_index.py[/bold] 构建向量索引。"
        )
        sys.exit(1)

    console.print(f"📚 向量库已加载，共 [bold]{count}[/bold] 个文档块")
    if settings.enable_query_rewrite:
        mode = "仅空结果时改写" if settings.rewrite_on_empty_only else "每次都改写合并"
        console.print(f"✏️  查询改写已开启: {mode}")

    # 初始化检索器和 RAG 链
    retriever = Retriever(vector_store=vector_store)
    rag_chain = RAGChain(
        retriever=retriever,
        enable_query_rewrite=settings.enable_query_rewrite,
        rewrite_on_empty_only=settings.rewrite_on_empty_only,
    )

    return rag_chain


def main():
    """交互式问答主循环"""

    console.print(Panel.fit(
        "[bold cyan]🤖 RAG 智能问答系统[/bold cyan]\n"
        "输入问题即可获取基于文档知识库的回答\n"
        "输入 [bold]exit[/bold] 或 [bold]quit[/bold] 退出，"
        "输入 [bold]sources[/bold] 查看上次回答的参考资料",
        border_style="cyan",
    ))
    console.print()

    # 初始化 RAG 链
    try:
        rag_chain = init_rag_chain()
    except Exception as e:
        console.print(f"[red]初始化失败: {e}[/red]")
        sys.exit(1)

    console.print()
    last_response = None

    while True:
        try:
            question = Prompt.ask("[bold yellow]你[/bold yellow]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]再见！👋[/dim]")
            break

        question = question.strip()

        if not question:
            continue

        # 退出命令
        if question.lower() in {"exit", "quit", "q"}:
            console.print("[dim]再见！👋[/dim]")
            break

        # 查看来源命令
        if question.lower() == "sources":
            if last_response:
                print_sources(last_response, rag_chain)
            else:
                console.print("[dim]还没有查询记录[/dim]")
            console.print()
            continue

        # 执行 RAG 查询
        console.print()
        with console.status("[bold green]思考中...[/bold green]", spinner="dots"):
            try:
                response = rag_chain.query(question)
                last_response = response
            except Exception as e:
                console.print(f"[red]查询失败: {e}[/red]")
                console.print()
                continue

        # 显示回答
        console.print(Panel(
            Markdown(response.answer),
            title="🤖 回答",
            border_style="green",
        ))

        # 显示参考资料（简化版）
        if response.source_documents:
            sources_str = " | ".join(
                f"[{item.rank}] {item.document.metadata.get('file_name', '?')} "
                f"({item.score:.3f})"
                for item in response.source_documents[:3]
            )
            console.print(f"[dim]📎 参考: {sources_str}[/dim]")
            console.print("[dim]💡 输入 sources 查看详细参考资料[/dim]")

        console.print()


if __name__ == "__main__":
    main()
