"""
Technical Support Agent

Handles technical, programming, and IT-related questions.
Provides expertise in software development and technical problem-solving.
"""
from typing import Dict, Any
from src.agents import BaseAgent, Message, ChatContext, AgentResponse, MemoryStore, SQLiteMemoryStore


class TechAgent(BaseAgent):
    """
    Agent specialized in technical support and programming assistance.
    
    This agent is best suited for:
    - Programming questions (Python, JavaScript, etc.)
    - Software development issues
    - Technical troubleshooting
    - Code review and debugging
    - System administration
    - Technology explanations
    """
    
    def __init__(self, memory_store: MemoryStore = None):
        """
        Initialize the Tech Agent.
        
        Args:
            memory_store: Optional memory store for persistence
        """
        self._name = "TechAgent"
        self._description = (
            "Provides technical support and programming assistance. "
            "Specializes in software development, debugging, "
            "system administration, and technology explanations."
        )
        self._memory = memory_store or SQLiteMemoryStore()
        
        # Technical keywords
        self._tech_keywords = [
            # Programming languages
            "python", "javascript", "java", "c++", "cpp", "c#", "csharp",
            "ruby", "php", "go", "golang", "rust", "kotlin", "swift",
            "typescript", "bash", "shell", "sql",
            
            # Frameworks and tools
            "react", "vue", "angular", "django", "flask", "fastapi",
            "node", "nodejs", "express", "spring", "docker", "kubernetes",
            "git", "github", "gitlab", "jenkins", "ci/cd",
            
            # Concepts
            "code", "coding", "program", "programming", "script", "scripting",
            "function", "class", "method", "variable", "algorithm",
            "debug", "debugging", "error", "exception", "bug", "issue",
            "compile", "compiler", "interpreter", "runtime",
            "api", "rest", "graphql", "database", "db", "query",
            "server", "client", "frontend", "backend", "fullstack",
            "web", "website", "app", "application", "software",
            
            # Operations
            "install", "configuration", "setup", "deploy", "deployment",
            "build", "compile", "run", "execute", "test", "testing",
            "performance", "optimization", "security", "authentication",
            
            # Technical actions
            "implement", "refactor", "migrate", "integrate", "develop",
            "how to", "how do i", "how can i",
        ]
        
        # Code-related patterns
        self._code_patterns = [
            "```", "import", "export", "def ", "class ", "function",
            "const ", "let ", "var ", "if (", "for (", "while (",
            "try:", "except:", "catch", "throw", "return",
        ]
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    def can_handle(self, message: Message, context: ChatContext) -> float:
        """
        Determine confidence for handling this message.
        
        Returns high confidence for technical/programming messages.
        """
        # Check for explicit mention
        if message.has_mention(self.name):
            return 1.0
        
        content = message.content.lower()
        
        # Check for code blocks or code patterns
        has_code = any(pattern in message.content for pattern in self._code_patterns)
        if has_code:
            return 0.95
        
        # Count technical keywords
        keyword_matches = sum(1 for keyword in self._tech_keywords if keyword in content)
        
        # Calculate base confidence from keyword matches
        if keyword_matches >= 3:
            confidence = 0.9
        elif keyword_matches == 2:
            confidence = 0.75
        elif keyword_matches == 1:
            confidence = 0.6
        else:
            confidence = 0.0
        
        # Boost for "how to" questions (technical tutorials)
        if any(phrase in content for phrase in ["how to", "how do i", "how can i", "what is"]):
            if keyword_matches > 0:
                confidence = min(1.0, confidence + 0.15)
        
        # Check conversation history for technical context
        recent_messages = context.get_recent_messages(5)
        for msg in recent_messages:
            msg_content = msg.content.lower()
            if any(keyword in msg_content for keyword in self._tech_keywords[:30]):
                # Boost confidence if recent conversation was technical
                confidence = min(1.0, confidence + 0.1)
                break
        
        return confidence
    
    def respond(self, message: Message, context: ChatContext) -> AgentResponse:
        """Generate a technical response."""
        # Read user's technical context
        user_memory = self.memory_read(message.user_id)
        interaction_count = user_memory.get("interaction_count", 0)
        preferred_languages = user_memory.get("preferred_languages", [])
        
        # Analyze message content
        content = message.get_clean_content().lower()
        
        # Detect programming language
        detected_lang = self._detect_language(content)
        if detected_lang and detected_lang not in preferred_languages:
            preferred_languages.append(detected_lang)
        
        # Detect type of technical question
        if any(word in content for word in ["error", "exception", "bug", "crash", "fail"]):
            question_type = "debugging"
            response = self._respond_to_debugging(message, detected_lang)
        elif any(word in content for word in ["how to", "how do i", "how can i"]):
            question_type = "tutorial"
            response = self._respond_to_tutorial(message, detected_lang)
        elif any(word in content for word in ["what is", "explain", "difference"]):
            question_type = "explanation"
            response = self._respond_to_explanation(message, detected_lang)
        elif any(word in content for word in ["optimize", "performance", "slow", "speed"]):
            question_type = "optimization"
            response = self._respond_to_optimization(message, detected_lang)
        else:
            question_type = "general"
            response = self._respond_general(message, interaction_count)
        
        # Update memory
        user_memory["interaction_count"] = interaction_count + 1
        user_memory["preferred_languages"] = preferred_languages[:5]  # Keep top 5
        user_memory["last_question_type"] = question_type
        self.memory_write(message.user_id, user_memory)
        
        return AgentResponse(
            content=response,
            agent_name=self.name,
            confidence=0.85,
            metadata={
                "question_type": question_type,
                "detected_language": detected_lang,
            },
            should_continue=False
        )
    
    def _detect_language(self, content: str) -> str:
        """Detect programming language from content."""
        languages = {
            "python": ["python", "py", "django", "flask", "fastapi", "pandas", "numpy"],
            "javascript": ["javascript", "js", "node", "react", "vue", "angular", "npm"],
            "java": ["java", "spring", "maven", "gradle"],
            "cpp": ["c++", "cpp"],
            "csharp": ["c#", "csharp", ".net", "dotnet"],
            "go": ["golang", "go"],
            "rust": ["rust", "cargo"],
        }
        
        for lang, keywords in languages.items():
            if any(kw in content for kw in keywords):
                return lang
        
        return "general"
    
    def _respond_to_debugging(self, message: Message, lang: str) -> str:
        """Generate response for debugging questions."""
        return (
            f"I can help you debug this issue. Let me break down the problem:\n\n"
            f"1. First, let's identify the error message or unexpected behavior\n"
            f"2. Check the relevant code section and look for common issues\n"
            f"3. Verify your inputs and expected outputs\n\n"
            f"Could you provide:\n"
            f"- The exact error message\n"
            f"- The relevant code snippet\n"
            f"- What you expected to happen\n\n"
            f"This will help me give you a more specific solution."
        )
    
    def _respond_to_tutorial(self, message: Message, lang: str) -> str:
        """Generate response for tutorial/how-to questions."""
        lang_str = f"in {lang.title()}" if lang != "general" else ""
        return (
            f"I'd be happy to guide you through this {lang_str}! "
            f"Here's a step-by-step approach:\n\n"
            f"1. Start with the basic setup and requirements\n"
            f"2. Break down the task into smaller steps\n"
            f"3. Implement each step with proper error handling\n"
            f"4. Test thoroughly\n\n"
            f"Could you provide more details about:\n"
            f"- Your current setup/environment\n"
            f"- What you've tried so far\n"
            f"- Any specific constraints or requirements\n\n"
            f"I'll provide code examples and best practices!"
        )
    
    def _respond_to_explanation(self, message: Message, lang: str) -> str:
        """Generate response for explanation questions."""
        return (
            f"Great question! Let me explain this concept clearly:\n\n"
            f"I'll break it down into:\n"
            f"1. What it is (definition)\n"
            f"2. Why it's used (purpose)\n"
            f"3. How it works (implementation)\n"
            f"4. When to use it (best practices)\n\n"
            f"I can provide examples and comparisons to help you understand better. "
            f"What specific aspect would you like me to focus on?"
        )
    
    def _respond_to_optimization(self, message: Message, lang: str) -> str:
        """Generate response for optimization questions."""
        return (
            f"Let's optimize your code for better performance! Here's my approach:\n\n"
            f"1. Identify bottlenecks (profiling)\n"
            f"2. Analyze time and space complexity\n"
            f"3. Apply appropriate optimization techniques\n"
            f"4. Measure improvements\n\n"
            f"Common optimization strategies:\n"
            f"- Algorithm improvements\n"
            f"- Data structure selection\n"
            f"- Caching and memoization\n"
            f"- Parallel processing\n\n"
            f"Share your code and I'll provide specific optimization recommendations!"
        )
    
    def _respond_general(self, message: Message, interaction_count: int) -> str:
        """Generate general technical response."""
        if interaction_count == 0:
            return (
                "Hello! I'm your technical support agent. "
                "I can help with programming, debugging, system administration, "
                "and general technology questions. "
                "What technical challenge can I help you with today?"
            )
        else:
            return (
                "I'm here to help with your technical questions. "
                "Whether it's coding, debugging, architecture, or technology explanations, "
                "I'll do my best to provide clear and practical guidance. "
                "What would you like to know?"
            )
    
    def memory_read(self, user_id: str) -> Dict[str, Any]:
        """Read user's technical context."""
        return self._memory.read(self.name, user_id)
    
    def memory_write(self, user_id: str, data: Dict[str, Any]) -> None:
        """Write user's technical context."""
        self._memory.write(self.name, user_id, data)
