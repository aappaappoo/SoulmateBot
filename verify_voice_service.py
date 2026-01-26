#!/usr/bin/env python3
"""
Manual verification script for VoicePreferenceService
测试 VoicePreferenceService 的手动验证脚本
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import only what we need, bypassing the services __init__.py
import importlib.util
spec = importlib.util.spec_from_file_location(
    "voice_preference_service", 
    project_root / "src" / "services" / "voice_preference_service.py"
)
voice_pref_module = importlib.util.module_from_spec(spec)
sys.modules["voice_preference_service"] = voice_pref_module
spec.loader.exec_module(voice_pref_module)

voice_preference_service = voice_pref_module.voice_preference_service

def test_fallback_mode():
    """测试 fallback 模式"""
    print("=" * 60)
    print("Testing VoicePreferenceService in fallback mode")
    print("=" * 60)
    
    # Check health
    health = voice_preference_service.health_check()
    print(f"\n1. Health Check: {health}")
    
    # Test basic operations
    user_id = 123456
    bot_username = "TestBot"
    
    print(f"\n2. Initial state for user {user_id} with {bot_username}:")
    print(f"   Voice enabled: {voice_preference_service.is_voice_enabled(user_id, bot_username)}")
    
    print(f"\n3. Setting voice to enabled...")
    voice_preference_service.set_voice_enabled(user_id, bot_username, True)
    print(f"   Voice enabled: {voice_preference_service.is_voice_enabled(user_id, bot_username)}")
    
    print(f"\n4. Toggling voice...")
    new_state = voice_preference_service.toggle_voice(user_id, bot_username)
    print(f"   New state: {new_state}")
    print(f"   Voice enabled: {voice_preference_service.is_voice_enabled(user_id, bot_username)}")
    
    print(f"\n5. Testing multiple users and bots...")
    voice_preference_service.set_voice_enabled(111, "BotA", True)
    voice_preference_service.set_voice_enabled(111, "BotB", False)
    voice_preference_service.set_voice_enabled(222, "BotA", False)
    voice_preference_service.set_voice_enabled(222, "BotB", True)
    
    print(f"   User 111, BotA: {voice_preference_service.is_voice_enabled(111, 'BotA')}")
    print(f"   User 111, BotB: {voice_preference_service.is_voice_enabled(111, 'BotB')}")
    print(f"   User 222, BotA: {voice_preference_service.is_voice_enabled(222, 'BotA')}")
    print(f"   User 222, BotB: {voice_preference_service.is_voice_enabled(222, 'BotB')}")
    
    print(f"\n6. Testing delete preference...")
    result = voice_preference_service.delete_preference(111, "BotA")
    print(f"   Delete result: {result}")
    print(f"   User 111, BotA after delete: {voice_preference_service.is_voice_enabled(111, 'BotA')}")
    
    print(f"\n7. Testing get_all_preferences_for_user...")
    all_prefs = voice_preference_service.get_all_preferences_for_user(111)
    print(f"   User 111 preferences: {all_prefs}")
    
    print("\n" + "=" * 60)
    print("✅ All fallback mode tests completed successfully!")
    print("=" * 60)

def test_key_format():
    """测试 key 格式"""
    print("\n" + "=" * 60)
    print("Testing key format")
    print("=" * 60)
    
    key = voice_preference_service._get_key(123456, "TestBot")
    print(f"\nKey format: {key}")
    assert key == "voice_pref:123456:TestBot", f"Expected 'voice_pref:123456:TestBot', got '{key}'"
    print("✅ Key format is correct!")

if __name__ == "__main__":
    try:
        test_fallback_mode()
        test_key_format()
        print("\n🎉 All manual verification tests passed!")
    except Exception as e:
        print(f"\n❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
