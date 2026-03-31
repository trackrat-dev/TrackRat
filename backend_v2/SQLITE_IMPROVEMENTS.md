# SQLite Database Improvements for TrackRat Backend V2

## Overview

This document outlines proposed improvements to the SQLite database integration in TrackRat Backend V2. The current implementation is solid but can be optimized for better performance, reduced code duplication, and enhanced monitoring.

## Current Implementation Analysis

### Strengths
- **Proper SQLite async implementation** with aiosqlite
- **Sophisticated concurrency handling** with retry logic and exponential backoff
- **Clean schema design** with proper indexes and relationships
- **Transaction management** with proper rollback/commit patterns
- **No PostgreSQL legacy code** - fully SQLite-optimized

### Areas for Improvement

1. **Duplicated concurrency handling** across collectors
2. **SQLite WAL mode not enabled** (missing performance boost)
3. **Connection pool could be optimized** for SQLite workloads
4. **Bulk operations could be more efficient**
5. **Error handling could be centralized**

## Design Proposal

### 1. Enhanced Database Engine (`src/trackrat/db/engine.py`)

```python
"""
Optimized SQLite database engine with WAL mode and enhanced connection pooling.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Callable, TypeVar
import asyncio
import functools

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool
from sqlalchemy.engine.events import event
from sqlalchemy import text
from structlog import get_logger

from trackrat.settings import get_settings

logger = get_logger(__name__)

# Type for decorated functions
F = TypeVar('F', bound=Callable[..., Any])

# Global engine and session maker
_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create the async engine with SQLite optimizations."""
    global _engine
    if _engine is None:
        settings = get_settings()
        db_url = str(settings.database_url)

        # SQLite optimizations
        connect_args = {
            "check_same_thread": False,
            "timeout": 30,
        }
        
        engine_kwargs = {
            "connect_args": connect_args,
            "poolclass": StaticPool,
            "echo": settings.debug,
            "pool_pre_ping": True,  # Validate connections
        }

        _engine = create_async_engine(db_url, **engine_kwargs)
        
        # Enable WAL mode and other optimizations on new connections
        @event.listens_for(_engine.sync_engine, "connect")
        def enable_wal_mode(dbapi_connection, connection_record):
            """Enable WAL mode and other SQLite optimizations."""
            cursor = dbapi_connection.cursor()
            
            # Enable WAL mode for better concurrent performance
            cursor.execute("PRAGMA journal_mode=WAL")
            
            # Other optimizations
            cursor.execute("PRAGMA synchronous=NORMAL")  # Faster than FULL
            cursor.execute("PRAGMA cache_size=10000")     # 10MB cache
            cursor.execute("PRAGMA temp_store=MEMORY")    # Store temp tables in memory
            cursor.execute("PRAGMA mmap_size=268435456")  # 256MB memory-mapped I/O
            
            cursor.close()

    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Get or create the session factory."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _sessionmaker


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions with optimized error handling."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            # Log structured error information
            logger.error(
                "database_session_error",
                error=str(e),
                error_type=type(e).__name__,
                is_concurrency_error=_is_concurrency_error(e)
            )
            raise
        finally:
            await session.close()


def _is_concurrency_error(error: Exception) -> bool:
    """Check if an error is related to SQLite concurrency issues."""
    error_msg = str(error).lower()
    return any(
        msg in error_msg for msg in [
            "database is locked",
            "database is busy",
            "resource temporarily unavailable",
            "could not obtain lock",
            "unique constraint failed",
            "cannot commit transaction",
        ]
    )


def with_db_retry(max_attempts: int = 3, base_delay: float = 0.5):
    """Decorator for database operations with retry logic for concurrency errors."""
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if _is_concurrency_error(e) and attempt < max_attempts - 1:
                        # Wait with exponential backoff
                        wait_time = base_delay * (2 ** attempt)
                        logger.debug(
                            "database_retry",
                            function=func.__name__,
                            attempt=attempt + 1,
                            wait_time=wait_time,
                            error=str(e)
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        # Re-raise if not a concurrency error or max attempts reached
                        raise
            return None  # This shouldn't be reached
        return wrapper
    return decorator


async def close_engine() -> None:
    """Close the database engine and cleanup resources."""
    global _engine, _sessionmaker
    if _engine:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with get_session() as session:
        yield session


async def health_check() -> dict[str, Any]:
    """Database health check with performance metrics."""
    try:
        async with get_session() as session:
            # Simple query to test connection
            result = await session.execute(text("SELECT 1"))
            result.fetchone()
            
            # Check WAL mode
            wal_result = await session.execute(text("PRAGMA journal_mode"))
            journal_mode = wal_result.scalar()
            
            return {
                "status": "healthy",
                "journal_mode": journal_mode,
                "wal_enabled": journal_mode == "wal"
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "error_type": type(e).__name__
        }
```

### 2. Simplified Journey Collector Base Class

```python
"""
Base class for journey collectors with centralized retry logic.
"""

from abc import ABC, abstractmethod
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from trackrat.db.engine import with_db_retry


class BaseJourneyCollector(ABC):
    """Base class for all journey collectors with retry logic."""
    
    @with_db_retry(max_attempts=3)
    async def collect_journey_with_retry(self, *args, **kwargs) -> Any:
        """Collect journey with automatic retry on concurrency errors."""
        return await self._collect_journey_impl(*args, **kwargs)
    
    @abstractmethod
    async def _collect_journey_impl(self, *args, **kwargs) -> Any:
        """Implement the actual collection logic."""
        pass
```

### 3. Optimized Bulk Operations

```python
"""
Bulk database operations optimized for SQLite.
"""

from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from trackrat.models.database import JourneyStop


class BulkOperations:
    """Optimized bulk operations for SQLite."""
    
    @staticmethod
    async def bulk_upsert_stops(
        session: AsyncSession,
        journey_id: int,
        stops_data: List[Dict[str, Any]]
    ) -> None:
        """Efficiently upsert journey stops using REPLACE INTO."""
        
        # Use SQLite's REPLACE INTO for efficient upserts
        query = text("""
            INSERT OR REPLACE INTO journey_stops (
                journey_id, station_code, station_name, stop_sequence,
                scheduled_arrival, scheduled_departure,
                actual_arrival, actual_departure,
                departed, status, track, pickup_only, dropoff_only
            ) VALUES (
                :journey_id, :station_code, :station_name, :stop_sequence,
                :scheduled_arrival, :scheduled_departure,
                :actual_arrival, :actual_departure,
                :departed, :status, :track, :pickup_only, :dropoff_only
            )
        """)
        
        # Prepare data for bulk insert
        bulk_data = []
        for i, stop_data in enumerate(stops_data):
            bulk_data.append({
                "journey_id": journey_id,
                "stop_sequence": i,
                **stop_data
            })
        
        # Execute bulk insert
        await session.execute(query, bulk_data)
    
    @staticmethod
    async def cleanup_old_snapshots(
        session: AsyncSession,
        days_to_keep: int = 30
    ) -> int:
        """Clean up old snapshots to maintain database size."""
        query = text("""
            DELETE FROM journey_snapshots 
            WHERE captured_at < datetime('now', '-{} days')
        """.format(days_to_keep))
        
        result = await session.execute(query)
        return result.rowcount
```

### 4. Enhanced Settings for SQLite

```python
"""
Enhanced settings for SQLite optimization.
"""

from pydantic import BaseSettings, Field


class DatabaseSettings(BaseSettings):
    """Database-specific settings."""
    
    database_url: str = Field(
        default="sqlite+aiosqlite:///trackrat.db",
        description="Database URL"
    )
    
    # SQLite-specific settings
    wal_mode: bool = Field(
        default=True,
        description="Enable WAL mode for better concurrency"
    )
    
    cache_size_mb: int = Field(
        default=10,
        description="SQLite cache size in MB"
    )
    
    mmap_size_mb: int = Field(
        default=256,
        description="Memory-mapped I/O size in MB"
    )
    
    # Connection pool settings
    pool_timeout: int = Field(
        default=30,
        description="Connection timeout in seconds"
    )
    
    # Cleanup settings
    snapshot_retention_days: int = Field(
        default=30,
        description="Days to keep journey snapshots"
    )
```

### 5. Monitoring and Metrics

```python
"""
Database monitoring and metrics.
"""

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from prometheus_client import Counter, Histogram, Gauge
from sqlalchemy.ext.asyncio import AsyncSession

# Metrics
db_operations_total = Counter(
    "database_operations_total",
    "Total database operations",
    ["operation", "status"]
)

db_operation_duration = Histogram(
    "database_operation_duration_seconds",
    "Database operation duration",
    ["operation"]
)

db_connection_pool_size = Gauge(
    "database_connection_pool_size",
    "Database connection pool size"
)

db_retry_attempts = Counter(
    "database_retry_attempts_total",
    "Total retry attempts",
    ["operation", "error_type"]
)


@asynccontextmanager
async def monitored_session(operation: str) -> AsyncGenerator[AsyncSession, None]:
    """Database session with monitoring."""
    start_time = time.time()
    
    try:
        async with get_session() as session:
            yield session
            db_operations_total.labels(operation=operation, status="success").inc()
    except Exception as e:
        db_operations_total.labels(operation=operation, status="error").inc()
        raise
    finally:
        duration = time.time() - start_time
        db_operation_duration.labels(operation=operation).observe(duration)
```

## Key Improvements

### 1. WAL Mode Enhancement
- **Benefit**: Enables SQLite's Write-Ahead Logging for better concurrent read performance
- **Impact**: Reduces database locking and improves throughput
- **Implementation**: Automatic PRAGMA execution on connection

### 2. Centralized Retry Logic
- **Benefit**: Eliminates code duplication across collectors
- **Impact**: Consistent error handling and easier maintenance
- **Implementation**: `@with_db_retry` decorator with exponential backoff

### 3. Bulk Operations
- **Benefit**: Efficient `REPLACE INTO` operations for better performance
- **Impact**: Faster journey stop updates and reduced transaction overhead
- **Implementation**: Batched operations using SQLite-specific syntax

### 4. Connection Optimizations
- **Benefit**: Better cache settings and memory-mapped I/O
- **Impact**: Improved query performance and reduced disk I/O
- **Implementation**: PRAGMA settings applied on connection

### 5. Enhanced Monitoring
- **Benefit**: Prometheus metrics for database operations
- **Impact**: Better observability and performance tracking
- **Implementation**: Metrics collection with minimal overhead

## Performance Improvements Expected

| Metric | Current | Improved | Gain |
|--------|---------|----------|------|
| Concurrent Read Performance | Blocked by writes | WAL allows concurrent reads | 3-5x |
| Retry Code Duplication | ~150 lines | Centralized decorator | -80% |
| Bulk Insert Performance | Individual INSERTs | Batched REPLACE INTO | 2-3x |
| Cache Hit Rate | Default (2MB) | 10MB cache | 20-30% |
| Memory-Mapped I/O | Disabled | 256MB mmap | 15-25% |

## Migration Strategy

### Phase 1: Core Engine Enhancements
1. **Deploy enhanced engine** with WAL mode and optimizations
2. **Add health check** to verify WAL mode is enabled
3. **Test performance** with current collectors
4. **Monitor metrics** for baseline performance

### Phase 2: Centralized Retry Logic
1. **Implement `@with_db_retry` decorator** in engine module
2. **Refactor NJT journey collector** to use decorator
3. **Refactor Amtrak journey collector** to use decorator
4. **Remove duplicate retry code** from collectors

### Phase 3: Bulk Operations
1. **Implement bulk operations** class with SQLite-specific queries
2. **Update journey collectors** to use bulk operations
3. **Optimize stop updates** with REPLACE INTO
4. **Add cleanup procedures** for old snapshots

### Phase 4: Monitoring and Cleanup
1. **Add Prometheus metrics** for database operations
2. **Implement monitoring session** context manager
3. **Add automated cleanup** for old snapshots
4. **Create database health dashboard**

## Testing Strategy

### Unit Tests
- **Engine initialization** with WAL mode
- **Retry decorator** with various error types
- **Bulk operations** with mock data
- **Health check** functionality

### Integration Tests
- **Concurrent access** performance under load
- **Error recovery** with database locks
- **Bulk insert** performance benchmarks
- **Cleanup procedures** effectiveness

### Performance Tests
- **Before/after** WAL mode benchmarks
- **Concurrent read/write** performance
- **Memory usage** with enhanced caching
- **Query response times** under load

## Rollback Plan

### Immediate Rollback
- **Disable WAL mode** via PRAGMA (if issues arise)
- **Revert to original engine** configuration
- **Remove retry decorator** usage

### Gradual Rollback
- **Phase-by-phase** reversion if needed
- **Fallback to original** collector implementations
- **Monitoring** to detect performance regressions

## Risk Assessment

### Low Risk
- **WAL mode** is well-tested and stable
- **Retry decorator** is defensive programming
- **Bulk operations** use standard SQLite features

### Medium Risk
- **Connection pool** changes may affect stability
- **PRAGMA settings** need proper testing
- **Monitoring overhead** should be minimal

### Mitigation
- **Gradual rollout** with monitoring
- **Comprehensive testing** before deployment
- **Easy rollback** procedures documented

## Success Metrics

### Performance
- **Query response time** < 50ms (95th percentile)
- **Concurrent operations** increase by 3x
- **Memory usage** stable under load
- **Error rate** decrease by 50%

### Code Quality
- **Code duplication** reduced by 80%
- **Test coverage** maintained at 90%+
- **Technical debt** reduction measurable
- **Maintainability** improved

### Operational
- **Database health** monitoring in place
- **Alerting** for performance issues
- **Cleanup procedures** automated
- **Documentation** comprehensive

## Implementation Timeline

| Phase | Duration | Key Deliverables |
|-------|----------|------------------|
| Phase 1 | 1 week | Enhanced engine, WAL mode, health checks |
| Phase 2 | 1 week | Centralized retry logic, refactored collectors |
| Phase 3 | 1 week | Bulk operations, optimized updates |
| Phase 4 | 1 week | Monitoring, cleanup, dashboard |

**Total Timeline**: 4 weeks with gradual rollout and monitoring

## Conclusion

These SQLite improvements maintain the simplicity philosophy of Backend V2 while significantly enhancing performance and reducing code complexity. The changes are backward-compatible and provide substantial benefits for concurrent database operations, which are critical for the train tracking system's real-time requirements.

The implementation prioritizes:
- **Performance**: WAL mode and connection optimizations
- **Maintainability**: Centralized retry logic and bulk operations
- **Observability**: Comprehensive monitoring and health checks
- **Reliability**: Proper error handling and rollback procedures

These improvements will provide a solid foundation for the backend's database operations while maintaining the zero-configuration simplicity that makes SQLite ideal for this use case.