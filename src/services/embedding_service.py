"""
Embedding Service - 向量嵌入服务

提供统一的文本向量化接口，支持多种Embedding服务提供商：
1. OpenAI Embedding API
2. DashScope (通义千问) Text Embedding API

设计目标：
- 为对话记忆RAG和未来的文件RAG提供向量化支持
- 支持多Provider切换
- 支持批量向量化以提高效率
- 缓存常用embedding以减少API调用
"""
import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Union
from dataclasses import dataclass
import numpy as np
from loguru import logger

# Optional imports for providers
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("openai package not installed. OpenAI Embedding will not be available.")

try:
    import dashscope
    from dashscope import TextEmbedding
    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False
    logger.warning("dashscope package not installed. DashScope Embedding will not be available.")


@dataclass
class EmbeddingResult:
    """
    向量嵌入结果
    
    Attributes:
        embedding: 嵌入向量
        text: 原始文本
        model: 使用的模型名称
        tokens_used: 消耗的token数量
    """
    embedding: List[float]
    text: str
    model: str
    tokens_used: int = 0
    
    def to_numpy(self) -> np.ndarray:
        """转换为numpy数组"""
        return np.array(self.embedding, dtype=np.float32)


class EmbeddingProvider(ABC):
    """向量嵌入Provider抽象基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider名称"""
        pass
    
    @property
    @abstractmethod
    def dimension(self) -> int:
        """向量维度"""
        pass
    
    @abstractmethod
    async def embed_text(self, text: str) -> EmbeddingResult:
        """
        对单个文本进行向量化
        
        Args:
            text: 待向量化的文本
            
        Returns:
            EmbeddingResult对象
        """
        pass
    
    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """
        批量向量化文本
        
        Args:
            texts: 待向量化的文本列表
            
        Returns:
            EmbeddingResult列表
        """
        pass


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI Embedding Provider"""
    
    # 模型维度映射
    MODEL_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }
    
    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimensions: Optional[int] = None
    ):
        """
        初始化OpenAI Embedding Provider
        
        Args:
            api_key: OpenAI API密钥
            model: 模型名称
            dimensions: 自定义维度（仅text-embedding-3支持）
        """
        if not OPENAI_AVAILABLE:
            raise RuntimeError("openai package is not installed")
        
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        self._dimensions = dimensions or self.MODEL_DIMENSIONS.get(model, 1536)
        logger.info(f"OpenAI Embedding Provider initialized with model: {model}")
    
    @property
    def name(self) -> str:
        return "openai"
    
    @property
    def dimension(self) -> int:
        return self._dimensions
    
    async def embed_text(self, text: str) -> EmbeddingResult:
        """对单个文本进行向量化"""
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self._dimensions if "text-embedding-3" in self.model else None
            )
            
            return EmbeddingResult(
                embedding=response.data[0].embedding,
                text=text,
                model=self.model,
                tokens_used=response.usage.total_tokens
            )
        except Exception as e:
            logger.error(f"OpenAI Embedding error: {e}")
            raise
    
    async def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """批量向量化文本"""
        if not texts:
            return []
        
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=self._dimensions if "text-embedding-3" in self.model else None
            )
            
            results = []
            for i, data in enumerate(response.data):
                results.append(EmbeddingResult(
                    embedding=data.embedding,
                    text=texts[i],
                    model=self.model,
                    tokens_used=response.usage.total_tokens // len(texts)
                ))
            
            return results
        except Exception as e:
            logger.error(f"OpenAI Batch Embedding error: {e}")
            raise


class DashScopeEmbeddingProvider(EmbeddingProvider):
    """
    阿里云DashScope Embedding Provider
    通义千问文本向量化服务
    """
    
    # 模型维度映射
    MODEL_DIMENSIONS = {
        "text-embedding-v1": 1536,
        "text-embedding-v2": 1536,
        "text-embedding-v3": 1024,
    }
    
    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-v3"
    ):
        """
        初始化DashScope Embedding Provider
        
        Args:
            api_key: DashScope API密钥
            model: 模型名称
        """
        if not DASHSCOPE_AVAILABLE:
            raise RuntimeError("dashscope package is not installed")
        
        dashscope.api_key = api_key
        self.model = model
        self._dimensions = self.MODEL_DIMENSIONS.get(model, 1024)
        logger.info(f"DashScope Embedding Provider initialized with model: {model}")
    
    @property
    def name(self) -> str:
        return "dashscope"
    
    @property
    def dimension(self) -> int:
        return self._dimensions
    
    async def embed_text(self, text: str) -> EmbeddingResult:
        """对单个文本进行向量化"""
        try:
            # DashScope同步API，使用asyncio.to_thread包装
            def _embed():
                return TextEmbedding.call(
                    model=self.model,
                    input=text
                )
            
            response = await asyncio.to_thread(_embed)
            
            if response.status_code != 200:
                raise Exception(f"DashScope API error: {response.code} - {response.message}")
            
            embedding = response.output['embeddings'][0]['embedding']
            
            return EmbeddingResult(
                embedding=embedding,
                text=text,
                model=self.model,
                tokens_used=response.usage.get('total_tokens', 0) if response.usage else 0
            )
        except Exception as e:
            logger.error(f"DashScope Embedding error: {e}")
            raise
    
    async def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """批量向量化文本"""
        if not texts:
            return []
        
        try:
            # DashScope批量处理，每批最多25个
            batch_size = 25
            all_results = []
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                
                def _embed_batch():
                    return TextEmbedding.call(
                        model=self.model,
                        input=batch
                    )
                
                response = await asyncio.to_thread(_embed_batch)
                
                if response.status_code != 200:
                    raise Exception(f"DashScope API error: {response.code} - {response.message}")
                
                for j, emb_data in enumerate(response.output['embeddings']):
                    all_results.append(EmbeddingResult(
                        embedding=emb_data['embedding'],
                        text=batch[j],
                        model=self.model,
                        tokens_used=response.usage.get('total_tokens', 0) // len(batch) if response.usage else 0
                    ))
            
            return all_results
        except Exception as e:
            logger.error(f"DashScope Batch Embedding error: {e}")
            raise


class EmbeddingService:
    """
    统一的向量嵌入服务
    
    提供向量生成、相似度计算等功能。
    支持多Provider和缓存机制。
    
    Usage:
        service = EmbeddingService()
        
        # 生成单个向量
        result = await service.embed_text("用户的消息内容")
        
        # 批量生成向量
        results = await service.embed_batch(["文本1", "文本2"])
        
        # 计算相似度
        similarity = service.cosine_similarity(vec1, vec2)
    """

    def __init__(
            self,
            provider: Optional[EmbeddingProvider] = None,
            enable_cache: bool = True,
            cache_size: int = 1000
    ):
        """
        初始化向量嵌入服务

        Args:
            provider: 向量嵌入Provider
            enable_cache: 是否启用缓存
            cache_size: 缓存大小
        """
        self.provider = provider
        self.enable_cache = enable_cache
        self._cache: Dict[str, EmbeddingResult] = {}
        self._cache_size = cache_size

        if provider:
            logger.info(
                f"🔢 EmbeddingService initialized | "
                f"provider={provider.name} | "
                f"dimension={provider.dimension} | "
                f"cache_enabled={enable_cache} | "
                f"cache_size={cache_size}"
            )
    def set_provider(self, provider: EmbeddingProvider) -> None:
        """设置Provider"""
        self.provider = provider
        logger.info(f"EmbeddingService provider set to: {provider.name}")
    
    @property
    def dimension(self) -> int:
        """获取向量维度"""
        if not self.provider:
            raise ValueError("No embedding provider configured")
        return self.provider.dimension
    
    async def embed_text(self, text: str, use_cache: bool = True) -> EmbeddingResult:
        """
        对文本进行向量化
        
        Args:
            text: 待向量化的文本
            use_cache: 是否使用缓存
            
        Returns:
            EmbeddingResult对象
        """
        if not self.provider:
            raise ValueError("No embedding provider configured")
        
        # 检查缓存
        if use_cache and self.enable_cache and text in self._cache:
            logger.debug(f"Embedding cache hit for text: {text[:50]}...")
            return self._cache[text]
        
        # 生成向量
        result = await self.provider.embed_text(text)
        
        # 缓存结果
        if use_cache and self.enable_cache:
            if len(self._cache) >= self._cache_size:
                # 移除最旧的缓存项
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            self._cache[text] = result
        
        return result
    
    async def embed_batch(
        self,
        texts: List[str],
        use_cache: bool = True
    ) -> List[EmbeddingResult]:
        """
        批量向量化文本
        
        Args:
            texts: 待向量化的文本列表
            use_cache: 是否使用缓存
            
        Returns:
            EmbeddingResult列表
        """
        if not self.provider:
            raise ValueError("No embedding provider configured")
        
        if not texts:
            return []
        
        # 分离缓存命中和未命中的文本
        results = [None] * len(texts)
        texts_to_embed = []
        indices_to_embed = []
        
        if use_cache and self.enable_cache:
            for i, text in enumerate(texts):
                if text in self._cache:
                    results[i] = self._cache[text]
                else:
                    texts_to_embed.append(text)
                    indices_to_embed.append(i)
        else:
            texts_to_embed = texts
            indices_to_embed = list(range(len(texts)))
        
        # 批量生成未命中的向量
        if texts_to_embed:
            new_results = await self.provider.embed_batch(texts_to_embed)
            
            # Use enumerate to avoid inefficient index lookup
            for idx, (original_idx, result) in enumerate(zip(indices_to_embed, new_results)):
                results[original_idx] = result
                
                # 缓存结果
                if use_cache and self.enable_cache:
                    if len(self._cache) >= self._cache_size:
                        oldest_key = next(iter(self._cache))
                        del self._cache[oldest_key]
                    self._cache[texts_to_embed[idx]] = result
        
        return results
    
    @staticmethod
    def cosine_similarity(
        vec1: Union[List[float], np.ndarray],
        vec2: Union[List[float], np.ndarray]
    ) -> float:
        """
        计算两个向量的余弦相似度
        
        Args:
            vec1: 向量1
            vec2: 向量2
            
        Returns:
            余弦相似度 (-1 到 1)
        """
        if isinstance(vec1, list):
            vec1 = np.array(vec1, dtype=np.float32)
        if isinstance(vec2, list):
            vec2 = np.array(vec2, dtype=np.float32)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    @staticmethod
    def batch_cosine_similarity(
        query_vec: Union[List[float], np.ndarray],
        candidate_vecs: List[Union[List[float], np.ndarray]]
    ) -> List[float]:
        """
        计算查询向量与多个候选向量的余弦相似度
        
        Args:
            query_vec: 查询向量
            candidate_vecs: 候选向量列表
            
        Returns:
            相似度列表
        """
        if isinstance(query_vec, list):
            query_vec = np.array(query_vec, dtype=np.float32)
        
        # 转换候选向量为矩阵
        if not candidate_vecs:
            return []
        
        candidate_matrix = np.array(candidate_vecs, dtype=np.float32)
        
        # 计算余弦相似度
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return [0.0] * len(candidate_vecs)
        
        query_normalized = query_vec / query_norm
        
        # 归一化候选向量
        candidate_norms = np.linalg.norm(candidate_matrix, axis=1, keepdims=True)
        # 避免除零
        candidate_norms[candidate_norms == 0] = 1
        candidate_normalized = candidate_matrix / candidate_norms
        
        # 批量计算相似度
        similarities = np.dot(candidate_normalized, query_normalized)
        
        return similarities.tolist()
    
    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()
        logger.info("Embedding cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            "cache_size": len(self._cache),
            "max_cache_size": self._cache_size,
            "cache_enabled": self.enable_cache
        }


# 全局服务实例
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """
    获取全局向量嵌入服务实例

    自动根据配置初始化合适的Provider
    """
    global _embedding_service

    if _embedding_service is None:
        provider = None

        # 先尝试自动配置Provider
        try:
            from config import settings

            # 优先使用DashScope（如果��配置）
            if hasattr(settings, 'dashscope_api_key') and settings.dashscope_api_key and DASHSCOPE_AVAILABLE:
                provider = DashScopeEmbeddingProvider(
                    api_key=settings.dashscope_api_key,
                    model=getattr(settings, 'dashscope_embedding_model', 'text-embedding-v3')
                )
                logger.info("Auto-configured DashScope embedding provider")
            elif hasattr(settings, 'openai_api_key') and settings.openai_api_key and OPENAI_AVAILABLE:
                provider = OpenAIEmbeddingProvider(
                    api_key=settings.openai_api_key,
                    model=getattr(settings, 'openai_embedding_model', 'text-embedding-3-small')
                )
                logger.info("Auto-configured OpenAI embedding provider")
            else:
                logger.warning(
                    "No embedding provider configured. "
                    "Please set DASHSCOPE_API_KEY or OPENAI_API_KEY in your .env file."
                )
        except ImportError:
            logger.warning("Could not import config settings for embedding service")
        except Exception as e:
            logger.error(f"Error auto-configuring embedding provider: {e}")

        # 使用已配置的provider创建服务（如果有的话）
        _embedding_service = EmbeddingService(provider=provider)

    return _embedding_service