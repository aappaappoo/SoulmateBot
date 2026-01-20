#!/usr/bin/env python3
"""
Demo CLI for the multi-agent group chat system.

This provides a simple command-line interface to test and demonstrate
the agent routing system.
"""
import sys
from pathlib import Path

# Add parent directory to path to import src
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime, timezone
from loguru import logger

from src.agents import (
    Router,
    RouterConfig,
    AgentLoader,
    Message,
    ChatContext,
    MessageType,
)


def print_banner():
    """Print welcome banner."""
    print("=" * 60)
    print("  Multi-Agent Group Chat System - Demo")
    print("=" * 60)
    print()


def print_agents(agents):
    """Print available agents."""
    print("\n📋 Available Agents:")
    print("-" * 60)
    for agent in agents:
        print(f"  • @{agent.name}")
        print(f"    {agent.description}")
        print()


def print_response(responses):
    """Print agent responses."""
    if not responses:
        print("\n❌ No agent responded to your message.")
        print("   Try mentioning an agent with @AgentName or ask a different question.")
        return
    
    print("\n" + "=" * 60)
    for i, response in enumerate(responses, 1):
        if len(responses) > 1:
            print(f"\n🤖 Response {i} from @{response.agent_name}:")
        else:
            print(f"\n🤖 @{response.agent_name}:")
        print(f"   Confidence: {response.confidence:.2f}")
        print("-" * 60)
        print(response.content)
        print("-" * 60)


def print_help():
    """Print help information."""
    print("\n💡 Help:")
    print("-" * 60)
    print("  • Type your message and press Enter")
    print("  • Mention an agent with @AgentName to route to specific agent")
    print("  • Type 'help' to see this help message")
    print("  • Type 'agents' to list available agents")
    print("  • Type 'config' to see router configuration")
    print("  • Type 'quit' or 'exit' to exit")
    print()


def print_config(config: RouterConfig):
    """Print router configuration."""
    print("\n⚙️  Router Configuration:")
    print("-" * 60)
    print(f"  • Minimum Confidence: {config.min_confidence}")
    print(f"  • Max Agents: {config.max_agents}")
    print(f"  • Exclusive Mention: {config.exclusive_mention}")
    print(f"  • Parallel Execution: {config.enable_parallel}")
    print(f"  • Cooldown: {config.cooldown_seconds}s")
    if config.fallback_agent_name:
        print(f"  • Fallback Agent: @{config.fallback_agent_name}")
    print()


def main():
    """Main demo function."""
    # Configure logger
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="WARNING"  # Only show warnings and errors in demo
    )
    
    print_banner()
    
    # Load agents
    print("🔄 Loading agents...")
    loader = AgentLoader(agents_dir="agents")
    agents = loader.load_agents()
    
    if not agents:
        print("❌ No agents found! Please ensure agents are in the 'agents/' directory.")
        print("   Expected agents: EmotionalAgent, TechAgent")
        return
    
    print(f"✅ Loaded {len(agents)} agents successfully!")
    print_agents(agents)
    
    # Create router with configuration
    config = RouterConfig(
        min_confidence=0.4,  # Lower threshold for demo
        max_agents=2,
        exclusive_mention=True,
        enable_parallel=False,
        cooldown_seconds=0,  # No cooldown for demo
    )
    
    router = Router(agents, config)
    print("✅ Router initialized!")
    print_config(config)
    
    # Initialize chat context
    chat_id = "demo_chat"
    user_id = "demo_user"
    context = ChatContext(
        chat_id=chat_id,
        active_users=[user_id],
    )
    
    print_help()
    print("\n" + "=" * 60)
    print("Ready! Start chatting:")
    print("=" * 60)
    
    # Main chat loop
    message_count = 0
    while True:
        try:
            # Get user input
            print("\n💬 You: ", end="")
            user_input = input().strip()
            
            if not user_input:
                continue
            
            # Handle commands
            if user_input.lower() in ["quit", "exit", "bye"]:
                print("\n👋 Goodbye! Thanks for trying the multi-agent system!")
                break
            
            if user_input.lower() == "help":
                print_help()
                continue
            
            if user_input.lower() == "agents":
                print_agents(agents)
                continue
            
            if user_input.lower() == "config":
                print_config(config)
                continue
            
            # Create message
            message = Message(
                content=user_input,
                user_id=user_id,
                chat_id=chat_id,
                message_type=MessageType.TEXT,
                timestamp=datetime.now(timezone.utc),
            )
            
            # Add message to context
            context.add_message(message)
            message_count += 1
            
            # Route message
            print("\n🔍 Routing message...")
            responses = router.route(message, context)
            
            # Print responses
            print_response(responses)
            
            # Add responses to context (as system messages)
            for response in responses:
                response_message = Message(
                    content=response.content,
                    user_id=f"agent_{response.agent_name}",
                    chat_id=chat_id,
                    message_type=MessageType.TEXT,
                    timestamp=datetime.now(timezone.utc),
                    metadata={"agent_name": response.agent_name}
                )
                context.add_message(response_message)
            
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Goodbye!")
            break
        except Exception as e:
            logger.error(f"Error in chat loop: {e}")
            print(f"\n❌ Error: {e}")
            print("Please try again.")


if __name__ == "__main__":
    main()
