"""
Vector Store Service - 向量存储服务

提供向量存储和检索功能，支持：
1. 内存向量存储（用于快速检索）
2. 数据库向量存储（用于持久化）
3. 混合检索（向量相似度 + 元数据过滤）

设计目标：
- 支持对话记忆RAG
- 为未来的文件RAG提供扩展基础
- 支持多种索引类型
"""
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone
import numpy as np
from loguru import logger

from .embedding_service import EmbeddingService, EmbeddingResult


@dataclass
class VectorDocument:
    """
    向量文档对象
    
    Attributes:
        id: 文档ID
        content: 文本内容
        embedding: 向量嵌入
        metadata: 元数据（用于过滤）
        source_type: 来源类型（memory, file, etc.）
        created_at: 创建时间
    """
    id: str
    content: str
    embedding: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_type: str = "memory"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "content": self.content,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "source_type": self.source_type,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VectorDocument":
        """从字典创建"""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now(timezone.utc)
        
        return cls(
            id=data["id"],
            content=data["content"],
            embedding=data["embedding"],
            metadata=data.get("metadata", {}),
            source_type=data.get("source_type", "memory"),
            created_at=created_at
        )


@dataclass
class SearchResult:
    """
    搜索结果对象
    
    Attributes:
        document: 匹配的文档
        score: 相似度得分
        rank: 排名
    """
    document: VectorDocument
    score: float
    rank: int = 0


class VectorStore(ABC):
    """向量存储抽象基类"""
    
    @abstractmethod
    async def add_document(self, document: VectorDocument) -> bool:
        """添加文档"""
        pass
    
    @abstractmethod
    async def add_documents(self, documents: List[VectorDocument]) -> int:
        """批量添加文档"""
        pass
    
    @abstractmethod
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
        min_score: float = 0.0
    ) -> List[SearchResult]:
        """向量相似度搜索"""
        pass
    
    @abstractmethod
    async def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        pass
    
    @abstractmethod
    async def get_document(self, doc_id: str) -> Optional[VectorDocument]:
        """获取文档"""
        pass
    
    @abstractmethod
    async def update_document(self, document: VectorDocument) -> bool:
        """更新文档"""
        pass


class InMemoryVectorStore(VectorStore):
    """
    内存向量存储
    
    适用于小规模数据的快速检索。
    支持元数据过滤和余弦相似度搜索。
    """
    
    def __init__(self):
        """初始化内存向量存储"""
        self._documents: Dict[str, VectorDocument] = {}
        self._embeddings: Optional[np.ndarray] = None
        self._doc_ids: List[str] = []
        self._needs_rebuild = True
        
        logger.info("InMemoryVectorStore initialized")
    
    def _rebuild_index(self) -> None:
        """重建索引"""
        if not self._needs_rebuild:
            return
        
        if not self._documents:
            self._embeddings = None
            self._doc_ids = []
        else:
            self._doc_ids = list(self._documents.keys())
            embeddings = [self._documents[doc_id].embedding for doc_id in self._doc_ids]
            self._embeddings = np.array(embeddings, dtype=np.float32)
        
        self._needs_rebuild = False
    
    async def add_document(self, document: VectorDocument) -> bool:
        """添加文档"""
        self._documents[document.id] = document
        self._needs_rebuild = True
        return True
    
    async def add_documents(self, documents: List[VectorDocument]) -> int:
        """批量添加文档"""
        for doc in documents:
            self._documents[doc.id] = doc
        self._needs_rebuild = True
        return len(documents)
    
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
        min_score: float = 0.0
    ) -> List[SearchResult]:
        """向量相似度搜索"""
        self._rebuild_index()
        
        if self._embeddings is None or len(self._embeddings) == 0:
            return []
        
        # 计算余弦相似度
        query_vec = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []
        
        query_normalized = query_vec / query_norm
        
        # 归一化文档向量
        doc_norms = np.linalg.norm(self._embeddings, axis=1, keepdims=True)
        doc_norms[doc_norms == 0] = 1
        doc_normalized = self._embeddings / doc_norms
        
        # 计算相似度
        similarities = np.dot(doc_normalized, query_normalized)
        
        # 元数据过滤
        valid_indices = []
        for i, doc_id in enumerate(self._doc_ids):
            doc = self._documents[doc_id]
            
            # 检查最小得分
            if similarities[i] < min_score:
                continue
            
            # 检查元数据过滤
            if filter_metadata:
                match = True
                for key, value in filter_metadata.items():
                    if key not in doc.metadata or doc.metadata[key] != value:
                        match = False
                        break
                if not match:
                    continue
            
            valid_indices.append(i)
        
        # 排序并返回top_k
        valid_indices.sort(key=lambda i: similarities[i], reverse=True)
        top_indices = valid_indices[:top_k]
        
        results = []
        for rank, i in enumerate(top_indices):
            doc_id = self._doc_ids[i]
            results.append(SearchResult(
                document=self._documents[doc_id],
                score=float(similarities[i]),
                rank=rank
            ))
        
        return results
    
    async def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        if doc_id in self._documents:
            del self._documents[doc_id]
            self._needs_rebuild = True
            return True
        return False
    
    async def get_document(self, doc_id: str) -> Optional[VectorDocument]:
        """获取文档"""
        return self._documents.get(doc_id)
    
    async def update_document(self, document: VectorDocument) -> bool:
        """更新文档"""
        if document.id in self._documents:
            self._documents[document.id] = document
            self._needs_rebuild = True
            return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_documents": len(self._documents),
            "index_built": not self._needs_rebuild
        }


class VectorStoreService:
    """
    向量存储服务
    
    提供统一的向量存储和检索接口，结合EmbeddingService进行端到端的文本向量检索。
    
    特性：
    - 自动向量化：自动将文本转换为向量
    - 混合检索：支持向量相似度 + 元数据过滤
    - 多来源支持：支持不同类型的文档来源（memory, file等）
    - 分区管理：按用户/Bot进行数据分区
    
    Usage:
        service = VectorStoreService(embedding_service, vector_store)
        
        # 添加文档
        await service.add_text("用户说他喜欢Python", metadata={"user_id": 123})
        
        # 搜索
        results = await service.search_text("喜欢什么编程语言", top_k=5)
    """
    
    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: Optional[VectorStore] = None
    ):
        """
        初始化向量存储服务
        
        Args:
            embedding_service: 向量嵌入服务
            vector_store: 向量存储实例（默认使用内存存储）
        """
        self.embedding_service = embedding_service
        self.vector_store = vector_store or InMemoryVectorStore()
        
        logger.info("VectorStoreService initialized")
    
    async def add_text(
        self,
        text: str,
        doc_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        source_type: str = "memory"
    ) -> VectorDocument:
        """
        添加文本文档
        
        自动进行向量化并存储。
        
        Args:
            text: 文本内容
            doc_id: 文档ID
            metadata: 元数据
            source_type: 来源类型
            
        Returns:
            创建的VectorDocument对象
        """
        # 生成向量
        result = await self.embedding_service.embed_text(text)
        
        # 创建文档
        document = VectorDocument(
            id=doc_id,
            content=text,
            embedding=result.embedding,
            metadata=metadata or {},
            source_type=source_type
        )
        
        # 存储文档
        await self.vector_store.add_document(document)
        
        logger.debug(f"Added text document: {doc_id}")
        return document
    
    async def add_texts(
        self,
        texts: List[str],
        doc_ids: List[str],
        metadata_list: Optional[List[Dict[str, Any]]] = None,
        source_type: str = "memory"
    ) -> List[VectorDocument]:
        """
        批量添加文本文档
        
        Args:
            texts: 文本内容列表
            doc_ids: 文档ID列表
            metadata_list: 元数据列表
            source_type: 来源类型
            
        Returns:
            创建的VectorDocument列表
        """
        if not texts:
            return []
        
        if len(texts) != len(doc_ids):
            raise ValueError("texts and doc_ids must have the same length")
        
        # Validate metadata_list before setting default
        if metadata_list is not None and len(metadata_list) != len(texts):
            raise ValueError("metadata_list must have the same length as texts")
        
        metadata_list = metadata_list or [{}] * len(texts)
        
        # 批量生成向量
        results = await self.embedding_service.embed_batch(texts)
        
        # 创建文档
        documents = []
        for i, result in enumerate(results):
            document = VectorDocument(
                id=doc_ids[i],
                content=texts[i],
                embedding=result.embedding,
                metadata=metadata_list[i],
                source_type=source_type
            )
            documents.append(document)
        
        # 批量存储
        await self.vector_store.add_documents(documents)
        
        logger.debug(f"Added {len(documents)} text documents")
        return documents
    
    async def search_text(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
        min_score: float = 0.0
    ) -> List[SearchResult]:
        """
        文本相似度搜索
        
        自动将查询文本向量化后进行检索。
        
        Args:
            query: 查询文本
            top_k: 返回的最大结果数
            filter_metadata: 元数据过滤条件
            min_score: 最小相似度阈值
            
        Returns:
            SearchResult列表
        """
        # 生成查询向量
        result = await self.embedding_service.embed_text(query)
        
        # 执行搜索
        search_results = await self.vector_store.search(
            query_embedding=result.embedding,
            top_k=top_k,
            filter_metadata=filter_metadata,
            min_score=min_score
        )
        
        logger.debug(f"Search completed: query='{query[:50]}...', results={len(search_results)}")
        return search_results
    
    async def search_by_embedding(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
        min_score: float = 0.0
    ) -> List[SearchResult]:
        """
        使用预计算的向量进行搜索
        
        Args:
            query_embedding: 查询向量
            top_k: 返回的最大结果数
            filter_metadata: 元数据过滤条件
            min_score: 最小相似度阈值
            
        Returns:
            SearchResult列表
        """
        return await self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filter_metadata=filter_metadata,
            min_score=min_score
        )
    
    async def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        return await self.vector_store.delete_document(doc_id)
    
    async def get_document(self, doc_id: str) -> Optional[VectorDocument]:
        """获取文档"""
        return await self.vector_store.get_document(doc_id)
    
    async def update_text(
        self,
        doc_id: str,
        new_text: str,
        new_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[VectorDocument]:
        """
        更新文档文本
        
        重新生成向量并更新存储。
        
        Args:
            doc_id: 文档ID
            new_text: 新文本内容
            new_metadata: 新元数据（如果为None则保留原有）
            
        Returns:
            更新后的VectorDocument对象，如果不存在则返回None
        """
        existing = await self.vector_store.get_document(doc_id)
        if not existing:
            return None
        
        # 生成新向量
        result = await self.embedding_service.embed_text(new_text)
        
        # 更新文档
        updated_doc = VectorDocument(
            id=doc_id,
            content=new_text,
            embedding=result.embedding,
            metadata=new_metadata if new_metadata is not None else existing.metadata,
            source_type=existing.source_type,
            created_at=existing.created_at
        )
        
        await self.vector_store.update_document(updated_doc)
        
        logger.debug(f"Updated text document: {doc_id}")
        return updated_doc


# 全局服务实例
_vector_store_service: Optional[VectorStoreService] = None


def get_vector_store_service() -> VectorStoreService:
    """
    获取全局向量存储服务实例
    """
    global _vector_store_service
    
    if _vector_store_service is None:
        from .embedding_service import get_embedding_service
        
        embedding_service = get_embedding_service()
        _vector_store_service = VectorStoreService(
            embedding_service=embedding_service,
            vector_store=InMemoryVectorStore()
        )
    
    return _vector_store_service
