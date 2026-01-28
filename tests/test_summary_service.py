"""
Unit tests for ConversationSummaryService
"""
import pytest
from src.conversation.summary_service import (
    ConversationSummaryService,
    ConversationSummary
)


@pytest.mark.asyncio
class TestConversationSummaryService:
    """Test suite for ConversationSummaryService"""
    
    async def test_basic_rule_summarization(self):
        """Test basic rule-based summarization"""
        service = ConversationSummaryService()
        
        conversations = [
            {"role": "user", "content": "我今天工作很累"},
            {"role": "assistant", "content": "辛苦了！要注意休息哦"},
            {"role": "user", "content": "是啊，加班到很晚"},
            {"role": "assistant", "content": "那一定要好好放松一下"}
        ]
        
        summary = await service.summarize_conversations(conversations)
        
        assert isinstance(summary, ConversationSummary)
        assert len(summary.summary_text) > 0
        assert summary.turn_range == (1, 2)  # 2 user messages
        assert summary.metadata["method"] == "rule_based"
    
    async def test_empty_conversations(self):
        """Test with empty conversation list"""
        service = ConversationSummaryService()
        
        summary = await service.summarize_conversations([])
        
        assert isinstance(summary, ConversationSummary)
        assert "暂无对话历史" in summary.summary_text
        assert summary.turn_range == (0, 0)
    
    async def test_topic_extraction(self):
        """Test topic extraction from conversations"""
        service = ConversationSummaryService()
        
        conversations = [
            {"role": "user", "content": "我今天工作很忙，项目进度很紧张"},
            {"role": "assistant", "content": "工作辛苦了"},
            {"role": "user", "content": "晚上想玩会游戏放松一下"},
            {"role": "assistant", "content": "游戏是个好的放松方式"}
        ]
        
        summary = await service.summarize_conversations(conversations)
        
        # Should identify "工作" and "兴趣" topics
        assert len(summary.key_topics) > 0
        assert any(topic in ["工作", "兴趣", "游戏"] for topic in summary.key_topics)
    
    async def test_emotion_trajectory_positive(self):
        """Test positive emotion trajectory detection"""
        service = ConversationSummaryService()
        
        conversations = [
            {"role": "user", "content": "今天很开心！"},
            {"role": "assistant", "content": "太好了！"},
            {"role": "user", "content": "我很喜欢这个"},
            {"role": "assistant", "content": "很棒！"}
        ]
        
        summary = await service.summarize_conversations(conversations)
        
        assert "积极" in summary.emotion_trajectory or "positive" in summary.emotion_trajectory.lower()
    
    async def test_emotion_trajectory_negative(self):
        """Test negative emotion trajectory detection"""
        service = ConversationSummaryService()
        
        conversations = [
            {"role": "user", "content": "今天很难过"},
            {"role": "assistant", "content": "我在这里陪着你"},
            {"role": "user", "content": "感觉很累很迷茫"},
            {"role": "assistant", "content": "我理解"}
        ]
        
        summary = await service.summarize_conversations(conversations)
        
        assert "消极" in summary.emotion_trajectory or "negative" in summary.emotion_trajectory.lower()
    
    async def test_emotion_trajectory_mixed(self):
        """Test mixed emotion trajectory detection"""
        service = ConversationSummaryService()
        
        conversations = [
            {"role": "user", "content": "今天开始很难过"},
            {"role": "assistant", "content": "怎么了？"},
            {"role": "user", "content": "但后来好多了，很开心"},
            {"role": "assistant", "content": "太好了！"}
        ]
        
        summary = await service.summarize_conversations(conversations)
        
        assert "波动" in summary.emotion_trajectory or len(summary.emotion_trajectory) > 0
    
    async def test_user_needs_identification(self):
        """Test user needs identification"""
        service = ConversationSummaryService()
        
        conversations = [
            {"role": "user", "content": "我想和你聊聊天"},
            {"role": "assistant", "content": "当然！"},
            {"role": "user", "content": "你能给我一些建议吗？"},
            {"role": "assistant", "content": "好的"}
        ]
        
        summary = await service.summarize_conversations(conversations)
        
        # Should identify needs like "陪伴" or "建议"
        assert len(summary.user_needs) > 0
        assert any(need in ["陪伴", "建议"] for need in summary.user_needs)
    
    async def test_max_summary_length(self):
        """Test summary length limitation"""
        service = ConversationSummaryService()
        
        # Create a long conversation
        conversations = []
        for i in range(20):
            conversations.append({
                "role": "user",
                "content": f"这是一条很长的消息，包含很多内容和细节，用于测试摘要长度限制功能。消息{i+1}"
            })
            conversations.append({
                "role": "assistant",
                "content": "我理解了"
            })
        
        summary = await service.summarize_conversations(
            conversations,
            max_summary_length=100
        )
        
        # Summary should be truncated
        assert len(summary.summary_text) <= 103  # Allow for "..."
    
    def test_extract_topics(self):
        """Test topic extraction method"""
        service = ConversationSummaryService()
        
        conversations = [
            {"role": "user", "content": "我今天工作很忙，老板布置了很多任务"},
            {"role": "assistant", "content": "辛苦了"},
            {"role": "user", "content": "晚上想回家看书"},
            {"role": "assistant", "content": "好的"}
        ]
        
        topics = service._extract_topics(conversations)
        
        assert "工作" in topics
        assert "兴趣" in topics or len(topics) > 0
    
    def test_analyze_emotion_trajectory(self):
        """Test emotion trajectory analysis"""
        service = ConversationSummaryService()
        
        # Test positive emotions
        positive_convs = [
            {"role": "user", "content": "我很开心很喜欢"},
            {"role": "user", "content": "真的很棒"}
        ]
        trajectory = service._analyze_emotion_trajectory(positive_convs)
        assert "积极" in trajectory
        
        # Test negative emotions
        negative_convs = [
            {"role": "user", "content": "我很难过很累"},
            {"role": "user", "content": "感觉很迷茫"}
        ]
        trajectory = service._analyze_emotion_trajectory(negative_convs)
        assert "消极" in trajectory
        
        # Test mixed emotions
        mixed_convs = [
            {"role": "user", "content": "我很开心"},
            {"role": "user", "content": "但也有点担心"}
        ]
        trajectory = service._analyze_emotion_trajectory(mixed_convs)
        assert len(trajectory) > 0
    
    def test_identify_user_needs(self):
        """Test user needs identification"""
        service = ConversationSummaryService()
        
        conversations = [
            {"role": "user", "content": "我想说说话，需要你的建议"},
            {"role": "assistant", "content": "好的"},
            {"role": "user", "content": "希望你能理解我"},
            {"role": "assistant", "content": "我明白"}
        ]
        
        needs = service._identify_user_needs(conversations)
        
        # Should identify multiple needs
        assert len(needs) > 0
        possible_needs = ["倾诉", "建议", "理解", "陪伴"]
        assert any(need in possible_needs for need in needs)
    
    def test_generate_rule_based_summary(self):
        """Test rule-based summary generation"""
        service = ConversationSummaryService()
        
        conversations = [
            {"role": "user", "content": "今天工作很累"},
            {"role": "assistant", "content": "辛苦了"}
        ]
        
        topics = ["工作"]
        emotion_trajectory = "整体消极"
        user_needs = ["倾诉", "理解"]
        
        summary_text = service._generate_rule_based_summary(
            conversations,
            topics,
            emotion_trajectory,
            user_needs,
            max_length=200
        )
        
        assert len(summary_text) > 0
        assert "工作" in summary_text
        assert "消极" in summary_text or "倾诉" in summary_text
    
    def test_get_short_summary(self):
        """Test short summary generation"""
        service = ConversationSummaryService()
        
        full_summary = ConversationSummary(
            summary_text="用户讨论了工作和生活。",
            key_topics=["工作", "生活"],
            emotion_trajectory="情绪平稳",
            user_needs=["倾诉"],
            turn_range=(1, 5)
        )
        
        short_summary = service.get_short_summary(full_summary)
        
        assert len(short_summary) > 0
        assert "工作" in short_summary or "生活" in short_summary


@pytest.mark.asyncio
class TestConversationSummary:
    """Test suite for ConversationSummary dataclass"""
    
    def test_summary_creation(self):
        """Test creating a ConversationSummary"""
        summary = ConversationSummary(
            summary_text="测试摘要",
            key_topics=["工作", "生活"],
            emotion_trajectory="积极",
            user_needs=["陪伴"],
            turn_range=(1, 10),
            metadata={"method": "rule_based"}
        )
        
        assert summary.summary_text == "测试摘要"
        assert len(summary.key_topics) == 2
        assert summary.emotion_trajectory == "积极"
        assert len(summary.user_needs) == 1
        assert summary.turn_range == (1, 10)
        assert summary.metadata["method"] == "rule_based"
    
    def test_summary_defaults(self):
        """Test ConversationSummary default values"""
        summary = ConversationSummary(summary_text="测试")
        
        assert summary.summary_text == "测试"
        assert summary.key_topics == []
        assert summary.emotion_trajectory == ""
        assert summary.user_needs == []
        assert summary.turn_range == (0, 0)
        assert summary.metadata == {}
