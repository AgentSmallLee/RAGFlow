# 企业制度问答助手

基于 RAG (Retrieval-Augmented Generation) 技术的企业内部制度智能问答系统，支持员工手册、考勤管理制度等文档的智能查询。

## 项目特点

- 🏢 **场景明确**：面向企业内部制度问答，开箱即用
- 🌲 **清晰的目录结构**：按功能模块划分，职责单一
- 🔌 **插件化设计**：加载器、切分器、Embedding、向量库、Reranker 均可插拔替换
- 📚 **多格式支持**：支持 TXT、Markdown、PDF、Word 等文档格式
- 🎛️ **可视化调参**：Gradio Web 界面，参数实时调整，即时生效
- 🔍 **多级检索优化**：向量检索 + BM25 混合检索 + 查询改写 + Rerank 二次精排
- 🔑 **配置分离**：LLM、Embedding、Rerank 完全独立配置，支持不同服务商
- 📁 **双文档目录**：预置文档 + 用户上传文档，统一建库
- 🧪 **可测试**：核心模块均有单元测试

## 功能特性

| 功能 | 说明 |
|------|------|
| 向量检索 | ChromaDB + 余弦相似度，支持相似度阈值过滤 |
| 混合检索 | 向量 + BM25 关键词双路召回，支持 RRF / 加权融合 |
| 查询改写 | 用 LLM 改写问题提升召回率，支持"仅空结果时改写"和"每次都改写"两种模式 |
| Rerank 精排 | 基于 DashScope gte-rerank-v2 的二次精排，提升排序准确率 |
| 文档管理 | Web 界面上传文档、重建索引、查看文档列表 |
| 流式输出 | 回答逐字输出，体验流畅 |
| 参考来源 | 自动展示回答依据的文档片段和来源 |

## 项目结构

```
RAGFlow/
├── README.md                    # 项目说明文档
├── requirements.txt             # 项目依赖
├── .env                         # 环境变量（密钥等，不提交到 git）
├── .env.example                 # 环境变量模板（提交到 git）
├── .gitignore                   # Git 忽略规则
├── config/
│   └── settings.py              # 配置管理（从 .env 读取环境变量）
├── src/
│   ├── loader/                  # 文档加载模块
│   │   ├── base.py              # 加载器基类
│   │   ├── text_loader.py       # TXT / Markdown 加载器
│   │   ├── pdf_loader.py        # PDF 加载器
│   │   ├── docx_loader.py       # Word 加载器
│   │   └── document_loader.py   # 统一加载入口（自动识别格式）
│   ├── splitter/                # 文本切分模块
│   │   ├── base.py              # 切分器基类
│   │   └── recursive_splitter.py # 递归字符切分器
│   ├── embedding/               # 向量化模块
│   │   ├── base.py              # Embedding 基类
│   │   └── openai_embedding.py  # OpenAI 兼容 / DashScope Embedding 实现
│   ├── reranker/                # 重排序模块
│   │   ├── base.py              # Reranker 基类
│   │   └── dashscope_reranker.py # DashScope Rerank 实现
│   ├── vectorstore/             # 向量存储模块
│   │   ├── base.py              # 向量库基类
│   │   ├── chroma_store.py      # ChromaDB 实现（本地持久化）
│   │   ├── bm25_store.py        # BM25 关键词检索
│   │   ├── hybrid_store.py      # 混合检索（向量 + BM25）
│   │   └── factory.py           # 向量库工厂
│   ├── rag/                     # RAG 核心流程
│   │   ├── retriever.py         # 检索器（支持 Rerank）
│   │   ├── prompt_builder.py    # Prompt 构建器
│   │   ├── query_rewriter.py    # 查询改写器
│   │   └── rag_chain.py         # RAG 完整链路
│   └── utils/                   # 工具模块
│       └── logger.py            # 日志工具
├── web/
│   └── gradio_app/              # Gradio Web 前端
│       ├── app.py               # 界面构建和交互逻辑
│       └── rag_service.py       # RAG 服务封装（生命周期管理）
├── data/
│   ├── documents/               # 预置文档（如员工手册、考勤制度）
│   ├── uploads/                 # 用户上传的文档
│   └── vector_db/               # 向量数据库持久化目录
├── tests/                       # 单元测试
│   ├── test_loader.py
│   ├── test_splitter.py
│   └── test_rag.py
├── build_index.py               # 离线建库脚本
└── app.py                       # Web 服务启动入口
```

## 快速开始

### 1. 安装依赖

```bash
cd RAGFlow
pip install -r requirements.txt
```

### 2. 配置环境变量

复制模板文件并填入你的配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，至少需要配置 LLM 和 Embedding 的 API Key：

```ini
# ===== 聊天模型配置 =====
LLM_API_KEY=your-llm-api-key
LLM_BASE_URL=
LLM_MODEL=qwen-plus

# ===== Embedding 模型配置 =====
EMBEDDING_API_KEY=your-embedding-api-key
EMBEDDING_BASE_URL=
EMBEDDING_MODEL=text-embedding-v3
```

> 💡 Rerank 默认关闭。如需开启，设置 `ENABLE_RERANK=true`，并确保开通了 `gte-rerank-v2` 模型服务。
>
> 💡 所有可用配置项见 `config/settings.py` 或 `.env.example`。字段名转大写后即为环境变量名。

### 3. 准备文档

将制度文档放入 `data/documents/` 目录，支持 TXT、MD、PDF、DOCX 等格式。

项目已预置：
- `员工手册.pdf`
- `员工考勤管理制度.pdf`

### 4. 构建向量索引

```bash
python build_index.py
```

### 5. 启动 Web 服务

```bash
python app.py
```

启动后访问 `http://127.0.0.1:7860` 即可使用。

## 核心流程

### 离线建库流程
```
文档文件 → DocumentLoader → 原始文本 → TextSplitter → 文本块
                                              ↓
                              向量数据库 ← Embedding ← 文本块
```

### 在线问答流程
```
用户问题 → [查询改写] → Embedding → 查询向量
                              ↓
          ┌─── 向量检索 ───┐
          │                │
    混合检索 ─────────── BM25 检索
          │
          └──→ 结果融合 → Rerank 精排 → 阈值过滤
                              ↓
                    Prompt 构建器（问题 + 上下文）
                              ↓
                        LLM 生成回答 → 流式输出
```

## 检索优化说明

项目提供四层检索优化，可根据需要开启和组合：

| 优化手段 | 作用 | 适用场景 |
|---------|------|---------|
| 混合检索 | 向量 + BM25 双路召回，兼顾语义和精确匹配 | 专有名词多、需要精确匹配 |
| 查询改写 | 用 LLM 改写问题，多角度检索提升召回率 | 用户提问口语化、表述不标准 |
| Rerank 精排 | 交叉编码器二次排序，提升 top 结果准确率 | 对排序质量要求高 |
| 相似度阈值 | 过滤低相似度结果，减少误检 | 要求高准确率 |

**推荐组合**：混合检索 + Rerank 精排（效果提升最明显）

## 参数调优说明

所有参数都可以在 Web 界面左侧"参数调节"面板中实时调整，点击"应用参数"立即生效：

- **返回结果数 (top_k)**：向量检索召回的文档数量
- **相似度阈值**：低于此值的检索结果被过滤
- **查询改写**：用 LLM 改写问题提升召回率
- **混合检索**：向量 + BM25 关键词双路召回
- **重排序**：用交叉编码器对结果二次精排
- **切分块大小**：文档切分的块大小（下次上传/重建时生效）

## 扩展说明

- **更换 Embedding 模型**：在 `src/embedding/` 下新增实现类，继承 `BaseEmbedding`
- **更换向量数据库**：在 `src/vectorstore/` 下新增实现类，继承 `BaseVectorStore`
- **更换 Reranker**：在 `src/reranker/` 下新增实现类，继承 `BaseReranker`
- **更换 LLM**：修改配置即可（支持所有 OpenAI 兼容接口）
- **新增文档格式**：在 `src/loader/` 下新增加载器，继承 `BaseLoader`

## 技术栈

- **LLM**：OpenAI 兼容接口（支持通义千问、DeepSeek、硅基流动等）
- **Embedding**：DashScope / OpenAI 兼容
- **Rerank**：DashScope gte-rerank-v2
- **向量数据库**：ChromaDB（本地持久化）
- **关键词检索**：BM25（rank_bm25）
- **Web 框架**：Gradio
- **配置管理**：pydantic-settings
- **测试框架**：pytest
