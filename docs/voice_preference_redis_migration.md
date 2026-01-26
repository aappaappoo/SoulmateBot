# VoicePreferenceService Redis Migration Guide

## Overview

The `VoicePreferenceService` has been migrated from JSON file-based storage to Redis-based storage to address critical issues in high-concurrency, multi-user scenarios.

## Problems Solved

### Previous Issues (JSON File Storage)
1. **Concurrent Write Conflicts**: Multiple users modifying settings simultaneously could corrupt the file
2. **No Lock Protection**: In-memory dictionary lacked thread safety
3. **Performance Issues**: Full file rewrite on every change
4. **Cannot Scale Horizontally**: Multiple instances couldn't share data
5. **Poor Data Reliability**: Crashes during write could lose data

### New Solution (Redis Storage)
1. **Atomic Operations**: Redis GET/SET operations are naturally atomic
2. **Thread-Safe**: Redis handles concurrency automatically
3. **High Performance**: O(1) operations, no full rewrites
4. **Horizontal Scaling**: Multiple instances can share the same Redis server
5. **Data Reliability**: Redis persistence mechanisms ensure data safety

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
REDIS_URL=redis://localhost:6379/0
```

### Redis Connection Options

The service supports various Redis configurations:

```bash
# Local Redis
REDIS_URL=redis://localhost:6379/0

# Redis with password
REDIS_URL=redis://:password@localhost:6379/0

# Redis with authentication
REDIS_URL=redis://username:password@localhost:6379/0

# Redis Sentinel
REDIS_URL=redis+sentinel://localhost:26379/mymaster/0

# Redis Cluster
REDIS_URL=redis://localhost:7000/0
```

## Graceful Degradation

If Redis is **not configured** or **connection fails**, the service automatically falls back to in-memory storage:

- ✅ Service remains available
- ⚠️ Data is not persisted across restarts
- ⚠️ Multiple instances won't share data
- 📝 Suitable for development and testing

### Checking Service Mode

Use the `health_check()` method to verify the service mode:

```python
from src.services.voice_preference_service import voice_preference_service

status = voice_preference_service.health_check()
print(status)
# Output (Redis mode):
# {'redis_available': True, 'mode': 'redis'}

# Output (Fallback mode):
# {'redis_available': False, 'mode': 'fallback', 'fallback_count': 5}
```

## API Reference

### Public API (Backward Compatible)

All existing code continues to work without changes:

#### `is_voice_enabled(user_id: int, bot_username: str) -> bool`
Check if user has voice reply enabled for a specific bot.

```python
enabled = voice_preference_service.is_voice_enabled(123456, "MyBot")
```

#### `set_voice_enabled(user_id: int, bot_username: str, enabled: bool)`
Set user's voice preference for a specific bot.

```python
voice_preference_service.set_voice_enabled(123456, "MyBot", True)
```

#### `toggle_voice(user_id: int, bot_username: str) -> bool`
Toggle voice setting and return the new state.

```python
new_state = voice_preference_service.toggle_voice(123456, "MyBot")
```

### New Features

#### `get_all_preferences_for_user(user_id: int) -> dict`
Get all voice preferences for a user across all bots.

```python
prefs = voice_preference_service.get_all_preferences_for_user(123456)
# Returns: {"BotA": True, "BotB": False, "BotC": True}
```

#### `delete_preference(user_id: int, bot_username: str) -> bool`
Delete a user's voice preference for a specific bot.

```python
success = voice_preference_service.delete_preference(123456, "MyBot")
```

#### `health_check() -> dict`
Check service health and operational mode.

```python
status = voice_preference_service.health_check()
```

## Performance Improvements

### Before (JSON File)
- Write: O(n) - Full file rewrite
- Read: O(1) - Dictionary lookup
- Concurrency: ❌ File locks required, prone to conflicts
- Scalability: ❌ Cannot share across instances

### After (Redis)
- Write: O(1) - Single key update
- Read: O(1) - Single key lookup
- Concurrency: ✅ Atomic operations, no conflicts
- Scalability: ✅ Horizontal scaling with shared Redis

### Optimizations Applied

1. **scan_iter() instead of keys()**: Prevents blocking Redis server with large datasets
2. **Connection Pooling**: Automatic via `redis.from_url()`
3. **Timeout Settings**: 5-second timeouts prevent indefinite blocking
4. **Lazy Initialization**: Redis connection only attempted once at startup

## Migration Notes

### Data Migration

**No automatic data migration** from JSON to Redis. This is intentional because:
1. Voice preferences are user-specific, non-critical settings
2. Users can simply re-enable voice if needed
3. Avoids complexity and potential migration errors

If you need to preserve existing data:

```python
import json
from src.services.voice_preference_service import voice_preference_service

# Load old JSON data
with open('data/voice_preferences.json', 'r') as f:
    old_data = json.load(f)

# Migrate to new service
for key, enabled in old_data.items():
    user_id, bot_username = key.split(':', 1)
    voice_preference_service.set_voice_enabled(int(user_id), bot_username, enabled)
```

### Deployment Considerations

1. **Development/Testing**: No Redis needed, uses fallback mode automatically
2. **Production**: Configure `REDIS_URL` for best performance and reliability
3. **Monitoring**: Use `health_check()` in your monitoring system
4. **Redis Persistence**: Configure Redis RDB or AOF for data persistence

## Testing

The implementation includes comprehensive tests:

- ✅ 20 unit tests covering all scenarios
- ✅ Redis connection success/failure
- ✅ Fallback mode operations
- ✅ Error handling and recovery
- ✅ Special characters in bot usernames
- ✅ Multi-user, multi-bot scenarios

Run tests:

```bash
pytest tests/test_voice_preference_service.py -v
```

## Security

- ✅ No security vulnerabilities detected (CodeQL analysis)
- ✅ Connection timeouts prevent DoS
- ✅ Input validation on user_id and bot_username
- ✅ Exception handling prevents information leakage

## Troubleshooting

### Service uses fallback mode in production

**Check:**
1. Is `REDIS_URL` configured in `.env`?
2. Is Redis server running?
3. Can the application connect to Redis? (check firewall, network)
4. Check logs for connection errors

### Data not persisting after restart

**Cause:** Service is in fallback mode (in-memory storage)

**Solution:** Configure Redis properly and restart the service

### High memory usage in fallback mode

**Cause:** All preferences stored in memory

**Solution:** Enable Redis to offload data storage

## Support

For issues or questions:
1. Check logs for detailed error messages
2. Verify Redis connectivity with `redis-cli ping`
3. Use `health_check()` to diagnose the service mode
4. Review this guide for configuration options
