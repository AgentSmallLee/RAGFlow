"""
配置管理模块
使用 pydantic-settings 统一管理环境变量和项目配置
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """项目全局配置"""

    # ========== 聊天模型 (LLM) 配置 ==========
    # 所有配置均在 .env 文件中设置，代码中不保留默认值
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""

    # ========== Embedding 模型配置 ==========
    # 可以和聊天模型使用不同的服务商，API Key / Base URL / Model 独立配置
    # 所有配置均在 .env 文件中设置
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = ""

    # ========== 文本切分配置 ==========
    chunk_size: int = 500
    chunk_overlap: int = 50

    # ========== 向量检索配置 ==========
    top_k: int = 4
    similarity_threshold: float = 0.4

    # ========== 向量数据库配置 ==========
    vector_db_path: str = "./data/vector_db"
    collection_name: str = "rag_flow"

    # ========== 查询改写配置 ==========
    # 是否启用查询改写（用 LLM 改写问题后再检索，提升召回率）
    enable_query_rewrite: bool = False
    # 只在检索不到结果时才改写（True=保底模式，False=每次都改写合并）
    rewrite_on_empty_only: bool = True

    # ========== 混合检索配置 ==========
    # 是否启用混合检索（向量 + BM25 关键词）
    enable_hybrid_search: bool = False
    # 融合方式: rrf（倒数排名融合）或 weighted（加权融合）
    hybrid_fusion_method: str = "rrf"
    # 向量检索权重，仅 weighted 模式生效（BM25 权重 = 1 - vector_weight）
    hybrid_vector_weight: float = 0.7

    # ========== 文档目录配置 ==========
    documents_dir: str = "./data/documents"

    # 从 .env 文件加载配置
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def documents_path(self) -> Path:
        """获取文档目录的 Path 对象"""
        return Path(self.documents_dir).resolve()

    @property
    def vector_db_full_path(self) -> Path:
        """获取向量数据库目录的 Path 对象"""
        return Path(self.vector_db_path).resolve()



# 全局单例配置
settings = Settings()
