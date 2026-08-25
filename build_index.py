#!/usr/bin/env python3
"""
离线建库脚本
流程：加载文档 → 切分文本 → 向量化 → 存入向量数据库
"""

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from config.settings import settings
from src.loader import DocumentLoader
from src.splitter import RecursiveSplitter
from src.embedding import OpenAIEmbedding
from src.vectorstore import create_vector_store
from src.utils import logger, setup_logger

console = Console()


def main():
    """建库主流程"""

    console.print(Panel.fit(
        "[bold cyan]RAG 离线建库工具[/bold cyan]\n"
        "文档加载 → 文本切分 → 向量化 → 入库",
        border_style="cyan",
    ))

    # 0. 检查配置
    if not settings.embedding_api_key:
        console.print(
            "[red]错误: 未配置 EMBEDDING_API_KEY[/red]\n"
            "请复制 .env.example 为 .env 并填入 EMBEDDING_API_KEY"
        )
        sys.exit(1)

    docs_dir = settings.documents_path
    if not docs_dir.exists():
        console.print(f"[yellow]文档目录不存在，创建中: {docs_dir}[/yellow]")
        docs_dir.mkdir(parents=True, exist_ok=True)

    # 检查是否有文档
    doc_files = list(docs_dir.glob("**/*"))
    doc_files = [f for f in doc_files if f.is_file() and not f.name.startswith(".")]

    if not doc_files:
        console.print(
            f"[yellow]文档目录为空: {docs_dir}[/yellow]\n"
            "请将文档放入该目录后重新运行。\n"
            "支持格式: TXT, Markdown, PDF, DOCX"
        )
        sys.exit(0)

    console.print(f"📁 文档目录: [bold]{docs_dir}[/bold]")
    console.print(f"📄 发现文件: [bold]{len(doc_files)}[/bold] 个")
    console.print()

    # 步骤 1: 加载文档
    console.print("[bold green]步骤 1/4: 加载文档[/bold green]")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("正在加载文档...", total=None)
        loader = DocumentLoader()
        documents = loader.load_directory(docs_dir)
        progress.update(task, completed=True, description="文档加载完成 ✓")

    if not documents:
        console.print("[red]没有加载到任何有效文档[/red]")
        sys.exit(1)

    total_chars = sum(len(d.page_content) for d in documents)
    console.print(f"   加载了 [bold]{len(documents)}[/bold] 个文档片段，总字符数: [bold]{total_chars:,}[/bold]")
    console.print()

    # 步骤 2: 文本切分
    console.print("[bold green]步骤 2/4: 文本切分[/bold green]")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("正在切分文本...", total=None)
        splitter = RecursiveSplitter()
        chunks = splitter.split_documents(documents)
        progress.update(task, completed=True, description="文本切分完成 ✓")

    console.print(
        f"   切分为 [bold]{len(chunks)}[/bold] 个文本块 "
        f"(chunk_size={settings.chunk_size}, overlap={settings.chunk_overlap})"
    )
    console.print()

    # 步骤 3: 初始化 Embedding 和向量库
    console.print("[bold green]步骤 3/4: 初始化向量化模型 & 向量库[/bold green]")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("初始化 Embedding 模型...", total=None)
        embedding = OpenAIEmbedding()
        progress.update(task, completed=True, description=f"Embedding 模型就绪 ({settings.embedding_model}) ✓")

        task2 = progress.add_task("初始化向量数据库...", total=None)
        vector_store = create_vector_store(embedding=embedding)
        progress.update(task2, completed=True, description=f"向量库就绪 (已有 {vector_store.count()} 条) ✓")
    console.print()

    # 步骤 4: 向量化并存入向量库
    console.print("[bold green]步骤 4/4: 向量化并存入向量库[/bold green]")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("正在向量化并入库...", total=None)
        ids = vector_store.add_documents(chunks)
        vector_store.persist()
        progress.update(task, completed=True, description="向量入库完成 ✓")

    console.print()
    console.print(Panel.fit(
        f"[bold green]🎉 建库完成！[/bold green]\n\n"
        f"新增文档块: [bold]{len(ids)}[/bold] 个\n"
        f"向量库总量: [bold]{vector_store.count()}[/bold] 个\n"
        f"存储位置: [dim]{settings.vector_db_full_path}[/dim]",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
