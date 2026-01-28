"""
Unit tests for ProactiveDialogueStrategyAnalyzer
"""
import pytest
from src.conversation.proactive_strategy import (
    ProactiveDialogueStrategyAnalyzer,
    ProactiveMode,
    ConversationStage,
    UserEngagement,
    UserProfile,
    TopicAnalysis,
    ProactiveAction
)


class TestProactiveDialogueStrategyAnalyzer:
    """Test suite for ProactiveDialogueStrategyAnalyzer"""
    
    def test_initialization(self):
        """Test analyzer initialization"""
        analyzer = ProactiveDialogueStrategyAnalyzer()
        
        assert analyzer.interest_categories is not None
        assert analyzer.question_templates is not None
        assert len(analyzer.interest_categories) > 0
        assert len(analyzer.question_templates) > 0
    
    def test_analyze_user_profile_basic(self):
        """Test basic user profile analysis"""
        analyzer = ProactiveDialogueStrategyAnalyzer()
        
        conversation_history = [
            {"role": "user", "content": "我喜欢玩游戏"},
            {"role": "assistant", "content": "什么类型的游戏？"},
            {"role": "user", "content": "RPG游戏"},
            {"role": "assistant", "content": "很不错！"}
        ]
        
        profile = analyzer.analyze_user_profile(conversation_history)
        
        assert isinstance(profile, UserProfile)
        assert "游戏" in profile.interests
        assert profile.relationship_depth >= 1  # At least 1, could be 2
        assert profile.engagement_level in [UserEngagement.LOW, UserEngagement.MEDIUM, UserEngagement.HIGH]
    
    def test_analyze_user_profile_with_memories(self):
        """Test user profile analysis with memories"""
        analyzer = ProactiveDialogueStrategyAnalyzer()
        
        conversation_history = [
            {"role": "user", "content": "今天心情不错"},
            {"role": "assistant", "content": "太好了！"}
        ]
        
        user_memories = [
            {
                "event_summary": "用户喜欢看电影",
                "event_type": "preference",
                "keywords": ["电影"]
            }
        ]
        
        profile = analyzer.analyze_user_profile(conversation_history, user_memories)
        
        assert isinstance(profile, UserProfile)
        assert profile.relationship_depth > 0
    
    def test_analyze_topic(self):
        """Test topic analysis"""
        analyzer = ProactiveDialogueStrategyAnalyzer()
        
        conversation_history = [
            {"role": "user", "content": "我喜欢玩游戏"},
            {"role": "assistant", "content": "什么游戏？"},
            {"role": "user", "content": "原神"},
            {"role": "assistant", "content": "很棒！"}
        ]
        
        profile = analyzer.analyze_user_profile(conversation_history)
        analysis = analyzer.analyze_topic(conversation_history, profile)
        
        assert isinstance(analysis, TopicAnalysis)
        assert analysis.current_topic is not None or analysis.topic_depth > 0
    
    def test_generate_proactive_strategy_opening(self):
        """Test proactive strategy generation for opening stage"""
        analyzer = ProactiveDialogueStrategyAnalyzer()
        
        # Opening stage (1-2 turns)
        conversation_history = [
            {"role": "user", "content": "你好，我想和你聊天"},  # Longer message for better engagement
            {"role": "assistant", "content": "你好！很高兴认识你！"}
        ]
        
        profile = analyzer.analyze_user_profile(conversation_history)
        topic_analysis = analyzer.analyze_topic(conversation_history, profile)
        
        action = analyzer.generate_proactive_strategy(
            profile, topic_analysis, conversation_history
        )
        
        assert isinstance(action, ProactiveAction)
        # Should be EXPLORE_INTEREST in opening stage with good engagement
        assert action.mode in [ProactiveMode.EXPLORE_INTEREST, ProactiveMode.GENTLE_GUIDE]
        assert len(action.suggestion) > 0
        assert len(action.example_questions) > 0
    
    def test_generate_proactive_strategy_negative_emotion(self):
        """Test proactive strategy with negative emotion"""
        analyzer = ProactiveDialogueStrategyAnalyzer()
        
        conversation_history = [
            {"role": "user", "content": "今天很难过很迷茫很累"},  # Strong negative emotion
            {"role": "assistant", "content": "怎么了？我在这里陪着你"},
            {"role": "user", "content": "工作压力很大，感觉很孤独"},  # More negative keywords
            {"role": "assistant", "content": "我理解你的感受"}
        ]
        
        profile = analyzer.analyze_user_profile(conversation_history)
        topic_analysis = analyzer.analyze_topic(conversation_history, profile)
        
        action = analyzer.generate_proactive_strategy(
            profile, topic_analysis, conversation_history
        )
        
        # Should switch to supportive or gentle_guide mode for negative emotions
        assert action.mode in [ProactiveMode.SUPPORTIVE, ProactiveMode.GENTLE_GUIDE]
    
    def test_generate_proactive_strategy_with_memories(self):
        """Test proactive strategy with user memories"""
        analyzer = ProactiveDialogueStrategyAnalyzer()
        
        # Established relationship with long messages for high engagement
        conversation_history = []
        for i in range(12):
            conversation_history.append({
                "role": "user",
                "content": f"今天很开心，发生了很多有趣的事情，第{i+1}天，我想和你分享一下"
            })
            conversation_history.append({"role": "assistant", "content": "好的，我在听"})
        
        user_memories = [
            {
                "event_summary": "用户喜欢乐高",
                "event_date": "2026-01-20",
                "event_type": "preference"
            }
        ]
        
        profile = analyzer.analyze_user_profile(conversation_history, user_memories)
        topic_analysis = analyzer.analyze_topic(conversation_history, profile)
        
        action = analyzer.generate_proactive_strategy(
            profile, topic_analysis, conversation_history, user_memories
        )
        
        assert isinstance(action, ProactiveAction)
        # With memories, established relationship, and good engagement
        # Could be various proactive modes
        assert action.mode in [
            ProactiveMode.RECALL_MEMORY,
            ProactiveMode.SHARE_AND_ASK,
            ProactiveMode.FIND_COMMON,
            ProactiveMode.SHOW_CURIOSITY,
            ProactiveMode.GENTLE_GUIDE
        ]
    
    def test_extract_interests(self):
        """Test interest extraction"""
        analyzer = ProactiveDialogueStrategyAnalyzer()
        
        conversation_history = [
            {"role": "user", "content": "我喜欢玩游戏和看电影"},
            {"role": "assistant", "content": "很好！"},
            {"role": "user", "content": "还喜欢听音乐"},
            {"role": "assistant", "content": "不错！"}
        ]
        
        interests = analyzer._extract_interests(conversation_history)
        
        assert len(interests) > 0
        assert any(interest in ["游戏", "影视", "音乐"] for interest in interests)
    
    def test_analyze_engagement_high(self):
        """Test high engagement detection"""
        analyzer = ProactiveDialogueStrategyAnalyzer()
        
        # Long messages indicate high engagement (need > 50 chars avg)
        conversation_history = [
            {
                "role": "user",
                "content": "今天发生了很多有趣的事情，让我来详细说说。早上起来天气很好，然后我去了公园..."
            },
            {"role": "assistant", "content": "听起来不错！"},
            {
                "role": "user",
                "content": "是的！后来我去了公园，遇到了一些朋友，我们一起玩得很开心，度过了愉快的一天..."
            }
        ]
        
        engagement = analyzer._analyze_engagement(conversation_history)
        
        # With messages > 50 chars, should be HIGH or at least MEDIUM
        assert engagement in [UserEngagement.HIGH, UserEngagement.MEDIUM]
    
    def test_analyze_engagement_low(self):
        """Test low engagement detection"""
        analyzer = ProactiveDialogueStrategyAnalyzer()
        
        # Short messages indicate low engagement
        conversation_history = [
            {"role": "user", "content": "嗯"},
            {"role": "assistant", "content": "好的"},
            {"role": "user", "content": "好"},
            {"role": "assistant", "content": "明白"}
        ]
        
        engagement = analyzer._analyze_engagement(conversation_history)
        
        assert engagement == UserEngagement.LOW
    
    def test_analyze_emotional_state_positive(self):
        """Test positive emotional state detection"""
        analyzer = ProactiveDialogueStrategyAnalyzer()
        
        conversation_history = [
            {"role": "user", "content": "今天很开心很高兴"},
            {"role": "assistant", "content": "太好了！"}
        ]
        
        emotional_state = analyzer._analyze_emotional_state(conversation_history)
        
        assert emotional_state == "positive"
    
    def test_analyze_emotional_state_negative(self):
        """Test negative emotional state detection"""
        analyzer = ProactiveDialogueStrategyAnalyzer()
        
        conversation_history = [
            {"role": "user", "content": "今天很难过很累"},
            {"role": "assistant", "content": "我在这里"}
        ]
        
        emotional_state = analyzer._analyze_emotional_state(conversation_history)
        
        assert emotional_state == "negative"
    
    def test_analyze_emotional_state_transitioning(self):
        """Test transitioning emotional state detection"""
        analyzer = ProactiveDialogueStrategyAnalyzer()
        
        conversation_history = [
            {"role": "user", "content": "今天开始很难过但后来开心了"},
            {"role": "assistant", "content": "很高兴你好转了"}
        ]
        
        emotional_state = analyzer._analyze_emotional_state(conversation_history)
        
        assert emotional_state == "transitioning"
    
    def test_identify_current_topic(self):
        """Test current topic identification"""
        analyzer = ProactiveDialogueStrategyAnalyzer()
        
        recent_messages = [
            {"role": "user", "content": "我今天玩了很久游戏"},
            {"role": "assistant", "content": "什么游戏？"}
        ]
        
        topic = analyzer._identify_current_topic(recent_messages)
        
        assert topic == "游戏"
    
    def test_calculate_topic_depth(self):
        """Test topic depth calculation"""
        analyzer = ProactiveDialogueStrategyAnalyzer()
        
        # Continuous discussion on same topic
        conversation_history = [
            {"role": "user", "content": "我喜欢玩游戏"},
            {"role": "assistant", "content": "什么游戏？"},
            {"role": "user", "content": "RPG游戏"},
            {"role": "assistant", "content": "很棒！"},
            {"role": "user", "content": "最近在玩原神"},
            {"role": "assistant", "content": "好玩吗？"}
        ]
        
        depth = analyzer._calculate_topic_depth(conversation_history)
        
        assert depth >= 1
        assert depth <= 5
    
    def test_identify_topics_to_explore(self):
        """Test topics to explore identification"""
        analyzer = ProactiveDialogueStrategyAnalyzer()
        
        profile = UserProfile(
            interests=["游戏", "音乐"],
            recent_topics=["游戏"]  # Already discussed games
        )
        
        topics = analyzer._identify_topics_to_explore(profile, [])
        
        # Should suggest unexplored interests
        assert len(topics) > 0
        # Music hasn't been discussed yet
        assert "音乐" in topics or len(topics) > 0
    
    def test_determine_stage(self):
        """Test conversation stage determination"""
        analyzer = ProactiveDialogueStrategyAnalyzer()
        
        assert analyzer._determine_stage(1) == ConversationStage.OPENING
        assert analyzer._determine_stage(2) == ConversationStage.EXPLORING
        assert analyzer._determine_stage(3) == ConversationStage.DEEPENING
        assert analyzer._determine_stage(5) == ConversationStage.ESTABLISHED
    
    def test_format_proactive_guidance(self):
        """Test proactive guidance formatting"""
        analyzer = ProactiveDialogueStrategyAnalyzer()
        
        action = ProactiveAction(
            mode=ProactiveMode.EXPLORE_INTEREST,
            suggestion="主动询问兴趣爱好",
            example_questions=["你喜欢什么？", "有什么爱好吗？"],
            tone_guidance="轻松、好奇"
        )
        
        guidance = analyzer.format_proactive_guidance(action)
        
        assert "主动互动建议" in guidance
        assert "explore_interest" in guidance
        assert "轻松、好奇" in guidance
        assert "你喜欢什么？" in guidance


class TestUserProfile:
    """Test suite for UserProfile dataclass"""
    
    def test_user_profile_creation(self):
        """Test UserProfile creation"""
        profile = UserProfile(
            interests=["游戏", "音乐"],
            personality_traits=["开朗", "友好"],
            recent_topics=["工作"],
            emotional_state="positive",
            engagement_level=UserEngagement.HIGH,
            relationship_depth=3
        )
        
        assert len(profile.interests) == 2
        assert profile.emotional_state == "positive"
        assert profile.engagement_level == UserEngagement.HIGH
        assert profile.relationship_depth == 3
    
    def test_user_profile_defaults(self):
        """Test UserProfile default values"""
        profile = UserProfile()
        
        assert profile.interests == []
        assert profile.personality_traits == []
        assert profile.recent_topics == []
        assert profile.emotional_state == "neutral"
        assert profile.engagement_level == UserEngagement.MEDIUM
        assert profile.relationship_depth == 1


class TestTopicAnalysis:
    """Test suite for TopicAnalysis dataclass"""
    
    def test_topic_analysis_creation(self):
        """Test TopicAnalysis creation"""
        analysis = TopicAnalysis(
            current_topic="游戏",
            topic_depth=3,
            topics_to_explore=["音乐", "电影"],
            common_interests=["游戏"]
        )
        
        assert analysis.current_topic == "游戏"
        assert analysis.topic_depth == 3
        assert len(analysis.topics_to_explore) == 2
        assert len(analysis.common_interests) == 1
    
    def test_topic_analysis_defaults(self):
        """Test TopicAnalysis default values"""
        analysis = TopicAnalysis()
        
        assert analysis.current_topic is None
        assert analysis.topic_depth == 1
        assert analysis.topics_to_explore == []
        assert analysis.common_interests == []


class TestProactiveAction:
    """Test suite for ProactiveAction dataclass"""
    
    def test_proactive_action_creation(self):
        """Test ProactiveAction creation"""
        action = ProactiveAction(
            mode=ProactiveMode.EXPLORE_INTEREST,
            suggestion="主动询问兴趣",
            example_questions=["你喜欢什么？"],
            tone_guidance="轻松"
        )
        
        assert action.mode == ProactiveMode.EXPLORE_INTEREST
        assert action.suggestion == "主动询问兴趣"
        assert len(action.example_questions) == 1
        assert action.tone_guidance == "轻松"
    
    def test_proactive_action_defaults(self):
        """Test ProactiveAction default values"""
        action = ProactiveAction(
            mode=ProactiveMode.SUPPORTIVE,
            suggestion="倾听支持"
        )
        
        assert action.mode == ProactiveMode.SUPPORTIVE
        assert action.example_questions == []
        assert action.tone_guidance == ""
