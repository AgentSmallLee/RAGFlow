# RAG 完整流程演示

一个结构清晰、符合开发规范的 RAG (Retrieval-Augmented Generation) 演示项目，覆盖从文档加载到在线问答的完整链路。

## 项目特点

- 🌲 **清晰的目录结构**：按功能模块划分，职责单一
- 🔌 **插件化设计**：加载器、切分器、Embedding、向量库均可插拔替换
- 📚 **多格式支持**：支持 TXT、Markdown、PDF、Word、PPT、Excel 等文档格式
- ⚡ **完整流程**：文档加载 → 文本切分 → 向量化 → 入库 → 检索 → Prompt 拼接 → LLM 回答
- 🔑 **配置分离**：LLM 和 Embedding 完全独立配置，支持不同服务商
- 🧪 **可测试**：核心模块均有单元测试

## 项目结构

```
RAGFlow/
├── README.md                    # 项目说明文档
├── requirements.txt             # 项目依赖
├── .env                         # 环境变量（密钥等，不提交到 git）
├── .gitignore                   # Git 忽略规则
├── config/
│   └── settings.py              # 配置管理（从 .env 读取环境变量）
├── src/
│   ├── __init__.py
│   ├── loader/                  # 文档加载模块
│   │   ├── __init__.py
│   │   ├── base.py              # 加载器基类
│   │   ├── text_loader.py       # TXT / Markdown 加载器
│   │   ├── pdf_loader.py        # PDF 加载器
│   │   ├── docx_loader.py       # Word 加载器
│   │   └── document_loader.py   # 统一加载入口（自动识别格式）
│   ├── splitter/                # 文本切分模块
│   │   ├── __init__.py
│   │   ├── base.py              # 切分器基类
│   │   └── recursive_splitter.py # 递归字符切分器
│   ├── embedding/               # 向量化模块
│   │   ├── __init__.py
│   │   ├── base.py              # Embedding 基类
│   │   └── openai_embedding.py  # OpenAI 兼容 Embedding 实现
│   ├── vectorstore/             # 向量存储模块
│   │   ├── __init__.py
│   │   ├── base.py              # 向量库基类
│   │   └── chroma_store.py      # ChromaDB 实现（本地持久化）
│   ├── rag/                     # RAG 核心流程
│   │   ├── __init__.py
│   │   ├── retriever.py         # 检索器
│   │   ├── prompt_builder.py    # Prompt 构建器
│   │   └── rag_chain.py         # RAG 完整链路
│   └── utils/                   # 工具模块
│       ├── __init__.py
│       └── logger.py            # 日志工具
├── data/
│   ├── documents/               # 待处理的原始文档
│   └── vector_db/               # 向量数据库持久化目录
├── tests/                       # 单元测试
│   ├── __init__.py
│   ├── test_loader.py
│   ├── test_splitter.py
│   └── test_rag.py
├── build_index.py               # 建库入口脚本
└── chat.py                      # 在线问答入口脚本
```

## 快速开始

### 1. 安装依赖

```bash
cd RAGFlow
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件，填入你的配置（LLM 和 Embedding 可以用不同的服务商）：

```ini
# ===== 聊天模型配置 =====
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://xxx.com/v1
LLM_MODEL=gpt-4o-mini

# ===== Embedding 模型配置 =====
EMBEDDING_API_KEY=sk-yyy
EMBEDDING_BASE_URL=https://yyy.com/v1
EMBEDDING_MODEL=text-embedding-3-small
```

> 💡 所有可用配置项见 `config/settings.py`。字段名转大写后即为环境变量名。

### 3. 准备文档

将你的文档放入 `data/documents/` 目录，支持 TXT、MD、PDF、DOCX 等格式。

### 4. 构建向量索引

```bash
python build_index.py
```

### 5. 开始问答

```bash
python chat.py
```

## 核心流程说明

### 离线建库流程
```
文档文件 → DocumentLoader → 原始文本 → TextSplitter → 文本块
                                              ↓
                              向量数据库 ← Embedding ← 文本块
```

### 在线问答流程
```
用户问题 → Embedding → 查询向量
                    ↓
向量数据库 → 相似度检索 → 相关文档片段
                    ↓
            Prompt 构建器（问题 + 上下文）
                    ↓
                LLM 生成回答
```

## 扩展说明

- **更换 Embedding 模型**：在 `src/embedding/` 下新增实现类，继承 `BaseEmbedding`
- **更换向量数据库**：在 `src/vectorstore/` 下新增实现类，继承 `BaseVectorStore`
- **更换 LLM**：修改 `src/rag/rag_chain.py` 中的 LLM 初始化
- **新增文档格式**：在 `src/loader/` 下新增加载器，继承 `BaseLoader`
