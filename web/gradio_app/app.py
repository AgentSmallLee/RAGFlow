"""
Gradio Web 界面
左侧边栏（参数调节）+ 主区域（聊天 / 文档管理 / 关于 标签页）
"""

import gradio as gr

from .rag_service import RAGService


def create_gradio_app(service: RAGService) -> gr.Blocks:
    """
    创建 Gradio 应用

    Args:
        service: RAGService 实例

    Returns:
        gr.Blocks 应用实例
    """
    params = service.get_current_params()

    # ========== 自定义 CSS ==========
    custom_css = """
    .app-title {
        text-align: center;
        margin-bottom: 0 !important;
    }
    .app-subtitle {
        text-align: center;
        color: #666;
        margin-top: 0 !important;
        font-size: 0.9em;
    }
    .sidebar-header {
        font-weight: bold;
        margin-bottom: 8px;
    }
    #chatbot {
        height: 500px;
    }
    #sources-box {
        max-height: 300px;
        overflow-y: auto;
    }
    .upload-status {
        padding: 10px;
        border-radius: 8px;
        background: #f0fdf4;
        border: 1px solid #86efac;
    }
    /* 智能滚动提示条 */
    #scroll-hint {
        position: absolute;
        bottom: 10px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 100;
        display: none;
    }
    #scroll-hint.show {
        display: block;
    }
    """

    # ========== 智能滚动 JS ==========
    # 用户向上滚动时暂停自动滚动，滚回底部或点提示按钮时恢复
    scroll_js = """
    (function() {
        let scrollContainer = null;
        let userScrolledUp = false;
        let scrollHint = null;
        let lastScrollTop = 0;
        let chatbotEl = null;

        function findScrollContainer() {
            // 找到 chatbot 组件
            chatbotEl = document.querySelector('#chatbot');
            if (!chatbotEl) return null;

            // 遍历所有后代元素，找有 overflow-y 且可滚动的容器
            const all = chatbotEl.querySelectorAll('*');
            for (const el of all) {
                const style = window.getComputedStyle(el);
                if ((style.overflowY === 'auto' || style.overflowY === 'scroll')
                    && el.scrollHeight > el.clientHeight + 10) {
                    return el;
                }
            }

            // 兜底：找第一个 scrollHeight 大于 clientHeight 的元素
            for (const el of all) {
                if (el.scrollHeight > el.clientHeight + 50 && el.clientHeight > 100) {
                    return el;
                }
            }

            return null;
        }

        function createScrollHint() {
            scrollHint = document.createElement('button');
            scrollHint.id = 'scroll-hint';
            scrollHint.textContent = '⬇ 有新消息';
            scrollHint.style.cssText = `
                position: absolute;
                bottom: 15px;
                left: 50%;
                transform: translateX(-50%);
                z-index: 1000;
                padding: 6px 16px;
                border-radius: 20px;
                background: #3b82f6;
                color: white;
                border: none;
                cursor: pointer;
                box-shadow: 0 2px 12px rgba(0,0,0,0.2);
                font-size: 13px;
                display: none;
                transition: opacity 0.2s;
            `;
            scrollHint.onclick = (e) => {
                e.stopPropagation();
                if (scrollContainer) {
                    scrollContainer.scrollTo({
                        top: scrollContainer.scrollHeight,
                        behavior: 'smooth'
                    });
                }
            };
            chatbotEl.style.position = 'relative';
            chatbotEl.appendChild(scrollHint);
        }

        function isAtBottom() {
            if (!scrollContainer) return true;
            const distance = scrollContainer.scrollHeight - scrollContainer.scrollTop - scrollContainer.clientHeight;
            return distance < 60;
        }

        function scrollToBottom() {
            if (scrollContainer && !userScrolledUp) {
                scrollContainer.scrollTop = scrollContainer.scrollHeight;
            }
        }

        function updateScrollHint() {
            if (!scrollHint) return;
            if (userScrolledUp) {
                scrollHint.style.display = 'block';
            } else {
                scrollHint.style.display = 'none';
            }
        }

        function init() {
            scrollContainer = findScrollContainer();
            if (!scrollContainer) {
                setTimeout(init, 1000);
                return;
            }

            // 创建提示按钮
            if (!scrollHint) {
                createScrollHint();
            }

            // 初始化状态
            lastScrollTop = scrollContainer.scrollTop;
            userScrolledUp = false;

            // 监听滚动
            scrollContainer.addEventListener('scroll', () => {
                const scrollingUp = scrollContainer.scrollTop < lastScrollTop;
                const atBottom = isAtBottom();

                if (scrollingUp && !atBottom) {
                    userScrolledUp = true;
                    updateScrollHint();
                }
                if (atBottom) {
                    userScrolledUp = false;
                    updateScrollHint();
                }

                lastScrollTop = scrollContainer.scrollTop;
            }, { passive: true });

            // 监听内容变化，智能滚动
            const observer = new MutationObserver(() => {
                scrollToBottom();
            });

            observer.observe(scrollContainer, {
                childList: true,
                subtree: true,
                characterData: true,
            });

            console.log('✅ Smart scroll initialized');
        }

        // 启动
        function start() {
            if (document.querySelector('#chatbot')) {
                init();
            } else {
                setTimeout(start, 500);
            }
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', start);
        } else {
            start();
        }
    })();
    """

    # ========== 事件处理函数 ==========

    def user_submit(message, history):
        """用户提交消息：清空输入框，添加用户消息到历史"""
        if not message.strip():
            return "", history
        return "", history + [{"role": "user", "content": message}]

    def bot_respond(history, top_k_val):
        """机器人流式回复"""
        if not history or history[-1]["role"] != "user":
            yield history, "请先输入问题"
            return

        message = history[-1]["content"]
        # 确保 message 是字符串
        if not isinstance(message, str):
            message = str(message) if message else ""
        if not message.strip():
            yield history + [{"role": "assistant", "content": "请输入有效问题"}], "请输入有效问题"
            return

        # 添加空的 assistant 消息
        history = history + [{"role": "assistant", "content": ""}]
        yield history, "⏳ 正在检索参考资料..."

        # 流式生成回答
        for chunk in service.stream_query(message, top_k=top_k_val):
            history[-1]["content"] += chunk
            yield history, "🤔 正在生成回答..."

        # 获取完整响应来显示参考资料
        response = service.query(message, top_k=top_k_val)
        sources_md = service._format_sources_markdown(response)
        yield history, sources_md

    def reset_params():
        """重置为默认参数"""
        from config.settings import settings
        return {
            top_k_slider: settings.top_k,
            threshold_slider: settings.similarity_threshold,
            query_rewrite_check: settings.enable_query_rewrite,
            rewrite_empty_check: settings.rewrite_on_empty_only,
            hybrid_check: settings.enable_hybrid_search,
            fusion_dropdown: settings.hybrid_fusion_method,
            vector_weight_slider: settings.hybrid_vector_weight,
            chunk_size_slider: settings.chunk_size,
            chunk_overlap_slider: settings.chunk_overlap,
            status_text: "已重置为默认参数",
        }

    def apply_params(
        top_k_val, threshold_val, qr_val, re_val,
        hs_val, fm_val, vw_val, cs_val, co_val
    ):
        """应用参数变更"""
        try:
            msg = service.update_parameters(
                top_k=top_k_val,
                similarity_threshold=threshold_val,
                enable_query_rewrite=qr_val,
                rewrite_on_empty_only=re_val,
                enable_hybrid_search=hs_val,
                hybrid_fusion_method=fm_val,
                hybrid_vector_weight=vw_val,
                chunk_size=cs_val,
                chunk_overlap=co_val,
            )
            return msg, refresh_docs_info()
        except Exception as e:
            return f"❌ 参数更新失败: {e}", refresh_docs_info()

    def handle_upload(files):
        """处理文件上传"""
        if not files:
            return "请选择文件", refresh_docs_info()

        file_paths = [f.name for f in files] if hasattr(files[0], 'name') else files
        try:
            new_count, total_count, msg = service.add_uploaded_files(file_paths)
            status = f"✅ 新增 {new_count} 个文档块，总量 {total_count} 个\n{msg}"
            return status, refresh_docs_info()
        except Exception as e:
            return f"❌ 上传失败: {e}", refresh_docs_info()

    def handle_rebuild(cs_val, co_val):
        """重建索引"""
        try:
            count, msg = service.rebuild_all(
                chunk_size=cs_val,
                chunk_overlap=co_val,
            )
            return f"✅ {msg}", refresh_docs_info()
        except Exception as e:
            return f"❌ 重建失败: {e}", refresh_docs_info()

    def refresh_docs_info():
        """刷新文档信息"""
        files = service.get_uploaded_file_list()
        total = service.get_total_documents()
        files_str = "\n".join([f"- {f}" for f in files]) if files else "（暂无上传文件）"
        return f"📊 向量库文档块总数: **{total}**\n\n📁 已上传文件:\n{files_str}"

    # ========== 界面构建 ==========

    with gr.Blocks(
        title="RAGFlow - 智能问答系统",
    ) as demo:

        # 注入智能滚动 JS
        gr.HTML(f"<script>{scroll_js}</script>")

        # 标题
        gr.Markdown(
            "# 🤖 RAGFlow\n基于 RAG 的智能问答系统",
            elem_classes=["app-title"],
        )
        gr.Markdown(
            "支持文档上传、混合检索、查询改写、流式输出",
            elem_classes=["app-subtitle"],
        )

        with gr.Row():
            # ========== 左侧边栏：参数调节 ==========
            with gr.Column(scale=1, min_width=280):
                with gr.Group():
                    gr.Markdown("### ⚙️ 参数调节", elem_classes=["sidebar-header"])

                    top_k_slider = gr.Slider(
                        minimum=1, maximum=10, step=1,
                        value=params["top_k"],
                        label="返回结果数 (top_k)",
                        info="检索返回的最相关文档数量",
                    )
                    threshold_slider = gr.Slider(
                        minimum=0.0, maximum=1.0, step=0.05,
                        value=params["similarity_threshold"],
                        label="相似度阈值",
                        info="低于此值的结果被过滤",
                    )

                    gr.Markdown("#### 🔄 查询改写")
                    query_rewrite_check = gr.Checkbox(
                        value=params["enable_query_rewrite"],
                        label="启用查询改写",
                        info="用 LLM 改写问题提升召回率",
                    )
                    rewrite_empty_check = gr.Checkbox(
                        value=params["rewrite_on_empty_only"],
                        label="仅空结果时改写",
                        info="关闭则每次都改写并合并结果",
                    )

                    gr.Markdown("#### 🔍 混合检索")
                    hybrid_check = gr.Checkbox(
                        value=params["enable_hybrid_search"],
                        label="启用混合检索",
                        info="向量 + BM25 关键词检索",
                    )
                    fusion_dropdown = gr.Dropdown(
                        choices=["rrf", "weighted"],
                        value=params["hybrid_fusion_method"],
                        label="融合方式",
                        info="RRF: 按排名融合 | Weighted: 加权融合",
                    )
                    vector_weight_slider = gr.Slider(
                        minimum=0.0, maximum=1.0, step=0.05,
                        value=params["hybrid_vector_weight"],
                        label="向量检索权重",
                        info="仅 weighted 模式生效，BM25 权重 = 1 - 向量权重",
                    )

                    gr.Markdown("#### 📄 文本切分")
                    chunk_size_slider = gr.Slider(
                        minimum=100, maximum=2000, step=50,
                        value=params["chunk_size"],
                        label="切分块大小 (字符)",
                        info="下次上传/重建时生效",
                    )
                    chunk_overlap_slider = gr.Slider(
                        minimum=0, maximum=500, step=10,
                        value=params["chunk_overlap"],
                        label="块重叠大小 (字符)",
                        info="下次上传/重建时生效",
                    )

                    with gr.Row():
                        apply_btn = gr.Button("✅ 应用参数", variant="primary")
                        reset_btn = gr.Button("🔄 重置")

                    status_text = gr.Markdown("")

            # ========== 右侧主区域：标签页 ==========
            with gr.Column(scale=3):
                with gr.Tabs():

                    # ---- 标签页 1：聊天对话 ----
                    with gr.TabItem("💬 聊天", id="chat"):
                        chatbot = gr.Chatbot(
                            label="对话",
                            elem_id="chatbot",
                            show_label=False,
                            autoscroll=False,  # 关闭自带自动滚动，用自定义智能滚动
                        )

                        with gr.Row():
                            msg_input = gr.Textbox(
                                placeholder="输入你的问题，按回车发送...",
                                scale=5,
                                show_label=False,
                                container=False,
                            )
                            submit_btn = gr.Button("发送", variant="primary", scale=1)

                        sources_box = gr.Markdown(
                            "📚 参考资料将在这里显示",
                            elem_id="sources-box",
                        )

                    # ---- 标签页 2：文档管理 ----
                    with gr.TabItem("📁 文档管理", id="docs"):
                        with gr.Row():
                            with gr.Column(scale=2):
                                gr.Markdown("### 📤 上传文档")
                                upload_comp = gr.File(
                                    file_count="multiple",
                                    file_types=[".txt", ".md", ".pdf", ".docx"],
                                    label="支持格式: TXT, Markdown, PDF, DOCX",
                                    height=200,
                                )
                                upload_btn = gr.Button(
                                    "📥 上传并加入知识库",
                                    variant="primary",
                                )
                                upload_status = gr.Markdown("", elem_classes=["upload-status"])

                            with gr.Column(scale=1):
                                gr.Markdown("### 📊 知识库状态")
                                docs_info = gr.Markdown(refresh_docs_info())
                                rebuild_btn = gr.Button("🔄 重建全部索引")

                    # ---- 标签页 3：关于 ----
                    with gr.TabItem("ℹ️ 关于", id="about"):
                        gr.Markdown("""
                        ## RAGFlow - 基于 RAG 的智能问答系统

                        ### 功能特性

                        - **📄 多格式支持** - 支持 PDF、Word、Markdown、纯文本等格式
                        - **🧠 语义检索** - 基于向量的语义检索，理解同义词和不同表述
                        - **🔍 混合检索** - 向量检索 + BM25 关键词检索，兼顾语义和精确匹配
                        - **🔄 查询改写** - 用 LLM 改写问题，提升召回率
                        - **⚡ 流式输出** - 回答逐字生成，体验更流畅
                        - **📚 参考资料** - 显示回答引用的来源文档和相似度

                        ### 技术栈

                        - 前端: Gradio
                        - 后端: LangChain + ChromaDB
                        - 检索: 向量检索 / BM25 / 混合检索
                        - 切分: 递归字符切分（支持中文）

                        ### 使用说明

                        1. 在"文档管理"页面上传你的文档
                        2. 回到"聊天"页面，输入问题即可对话
                        3. 在左侧边栏调整参数，实时体验不同效果

                        ### 项目地址

                        [GitHub - AgentSmallLee/RAGFlow](https://github.com/AgentSmallLee/RAGFlow)
                        """)

        # ========== 事件绑定 ==========

        # 发送消息：先添加用户消息，再流式生成回复
        submit_btn.click(
            user_submit,
            inputs=[msg_input, chatbot],
            outputs=[msg_input, chatbot],
        ).then(
            bot_respond,
            inputs=[chatbot, top_k_slider],
            outputs=[chatbot, sources_box],
        )

        msg_input.submit(
            user_submit,
            inputs=[msg_input, chatbot],
            outputs=[msg_input, chatbot],
        ).then(
            bot_respond,
            inputs=[chatbot, top_k_slider],
            outputs=[chatbot, sources_box],
        )

        # 参数按钮
        apply_btn.click(
            apply_params,
            inputs=[
                top_k_slider, threshold_slider,
                query_rewrite_check, rewrite_empty_check,
                hybrid_check, fusion_dropdown, vector_weight_slider,
                chunk_size_slider, chunk_overlap_slider,
            ],
            outputs=[status_text, docs_info],
        )
        reset_btn.click(
            reset_params,
            outputs=[
                top_k_slider, threshold_slider,
                query_rewrite_check, rewrite_empty_check,
                hybrid_check, fusion_dropdown, vector_weight_slider,
                chunk_size_slider, chunk_overlap_slider,
                status_text,
            ],
        )

        # 文件上传
        upload_btn.click(
            handle_upload,
            inputs=[upload_comp],
            outputs=[upload_status, docs_info],
        )

        # 重建索引
        rebuild_btn.click(
            handle_rebuild,
            inputs=[chunk_size_slider, chunk_overlap_slider],
            outputs=[upload_status, docs_info],
        )

    # Gradio 6.0+: theme 和 css 通过 launch() 传入
    demo.launch_kwargs = {
        "theme": gr.themes.Soft(),
        "css": custom_css,
    }

    return demo
