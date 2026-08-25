#!/usr/bin/env python3
"""
RAGFlow Gradio Web 前端启动脚本

用法:
    python app.py                  # 默认 0.0.0.0:7860
    python app.py --port 8080      # 指定端口
    python app.py --share          # 生成公开分享链接
    python app.py --host 127.0.0.1 # 仅本地访问
"""

import argparse
import sys

from config.settings import settings
from src.utils import setup_logger
from web.gradio_app.rag_service import RAGService
from web.gradio_app.app import create_gradio_app


def main():
    parser = argparse.ArgumentParser(
        description="RAGFlow - 基于 RAG 的智能问答系统 (Gradio Web 前端)"
    )
    parser.add_argument(
        "--host", default="0.0.0.0",
        help="监听地址，默认 0.0.0.0（允许外部访问）",
    )
    parser.add_argument(
        "--port", type=int, default=7860,
        help="监听端口，默认 7860",
    )
    parser.add_argument(
        "--share", action="store_true",
        help="生成公开分享链接（通过 Gradio 官方服务器内网穿透）",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="调试模式（自动热重载）",
    )
    args = parser.parse_args()

    setup_logger()

    # 检查必需配置
    if not settings.llm_api_key:
        print("❌ 错误: 未配置 LLM_API_KEY")
        print("请复制 .env.example 为 .env 并填入 LLM_API_KEY")
        sys.exit(1)
    if not settings.embedding_api_key:
        print("❌ 错误: 未配置 EMBEDDING_API_KEY")
        print("请复制 .env.example 为 .env 并填入 EMBEDDING_API_KEY")
        sys.exit(1)

    # 初始化 RAG 服务
    print("🚀 正在初始化 RAG 服务...")
    try:
        service = RAGService()
        service.initialize()
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        sys.exit(1)

    print(f"✅ RAG 服务就绪，向量库: {service.get_total_documents()} 个文档块")

    # 创建 Gradio 应用
    demo = create_gradio_app(service)

    # 启动
    url = f"http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}"
    print(f"🌐 Web 界面启动中...")
    print(f"📡 本地访问: {url}")
    if args.share:
        print("🔗 正在生成公开分享链接...")

    # 从 demo 获取 launch 参数（Gradio 6.0+ theme/css 通过 launch 传入）
    launch_kwargs = getattr(demo, "launch_kwargs", {})

    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        show_error=True,
        debug=args.debug,
        **launch_kwargs,
    )


if __name__ == "__main__":
    main()
