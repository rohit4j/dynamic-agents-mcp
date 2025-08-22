# MCP Connection Resilience Guide

## Overview

This document explains the comprehensive MCP (Model Context Protocol) connection resilience system implemented to solve SSE (Server-Sent Events) timeout issues and provide robust connection management for external MCP servers.

## Problem Solved

### Original Issues
- **ReadTimeout errors** with external HTTP/SSE MCP servers after prolonged use
- **ClosedResourceError** during tool invocations when connections were lost
- **No automatic reconnection** when external servers became unavailable
- **Poor user experience** with cryptic error messages

### Root Causes
1. Default SSE read timeout too short (5 minutes)
2. No connection health monitoring
3. Missing session resumption for MCP protocol compliance
4. No circuit breaker pattern for failing servers
5. Tools continuing to invoke on closed connections

## Solution Architecture

### 1. Enhanced Timeout Configuration (`MCPConfiguration`)

**Files**: `src/domain/entities/mcp_configuration.py`

```python
# Enhanced SSE Configuration Example
{
    "transport": "sse",
    "url": "https://your-server.com/sse",
    "timeout": 30,                    # Initial connection timeout
    "sse_read_timeout": 1800,         # 30 minutes read timeout  
    "max_retries": 5,                 # Retry attempts
    "retry_backoff": 2.0,             # Exponential backoff
    "session_resumption": True        # MCP session resumption
}
```

**Key Features**:
- ✅ 30-minute SSE read timeout (vs 5-minute default)
- ✅ Configurable connection and retry parameters
- ✅ MCP protocol compliance with session resumption

### 2. Custom HTTPx Client Factory (`httpx_factory.py`)

**Files**: `src/infrastructure/mcp/httpx_factory.py`

**Key Features**:
- ✅ **Infinite read timeout** for SSE connections (`read=None`)
- ✅ Connection pooling and keep-alive optimization
- ✅ Proper headers for SSE streams
- ✅ SSL verification and redirect handling

```python
# HTTPx timeout configuration for SSE
timeout_config = httpx.Timeout(
    connect=30.0,    # Connection establishment
    read=None,       # Infinite read timeout (prevents ReadTimeout)
    write=30.0,      # Standard write timeout
    pool=10.0        # Pool timeout
)
```

### 3. Connection Health Monitoring (`MCPClientFactory`)

**Files**: `src/infrastructure/mcp/mcp_client_factory.py`

**Key Features**:
- ✅ **Circuit breaker pattern** (3 failures → 5-minute cooldown)
- ✅ Connection success/failure tracking
- ✅ Health metrics and monitoring APIs
- ✅ Automatic failure detection and recovery initiation

```python
class ConnectionHealth:
    - last_success_time
    - consecutive_failures  
    - circuit_breaker_until
    - is_healthy status
```

### 4. Auto-Reconnection with Session Resumption (`resilient_mcp_client.py`)

**Files**: `src/infrastructure/mcp/resilient_mcp_client.py`

**Key Features**:
- ✅ **Automatic reconnection** with exponential backoff
- ✅ **MCP session resumption** using `Last-Event-ID` headers
- ✅ Tool caching for performance
- ✅ Connection validation before tool invocations
- ✅ Transparent retry logic for connection errors

### 5. Protected Tool Wrappers (`protected_tools.py`)

**Files**: `src/infrastructure/mcp/protected_tools.py`

**Key Features**:
- ✅ **Graceful error handling** for tool invocations
- ✅ **User-friendly error messages** instead of crashes
- ✅ Automatic retry for connection-related failures
- ✅ Fallback responses when servers unavailable

```python
# Example protected tool response
"Tool 'getEligibleProducts' is temporarily unavailable: Connection to Catalog Server was lost. Please try again."
```

### 6. Error Recovery Service (`error_recovery_service.py`)

**Files**: `src/infrastructure/mcp/error_recovery_service.py`

**Key Features**:
- ✅ **Centralized error handling** and recovery coordination
- ✅ **Periodic health checks** and automated recovery
- ✅ Connection status monitoring and reporting
- ✅ Manual recovery triggers and circuit breaker resets

### 7. Health Monitoring API (`mcp_health.py`)

**Files**: `web/api/routes/mcp_health.py`

**Available Endpoints**:
- `GET /api/mcp-health/status` - Overall connection status
- `GET /api/mcp-health/health/{config_id}` - Specific server health
- `POST /api/mcp-health/reconnect/{config_id}` - Force reconnection
- `POST /api/mcp-health/reconnect-all` - Reconnect all servers
- `POST /api/mcp-health/reset-circuit-breaker/{config_id}` - Reset circuit breaker
- `GET /api/mcp-health/failed-servers` - List failed servers

## Configuration Examples

### Basic External SSE Server
```json
{
    "name": "Weather Service",
    "server_type": "external",
    "config": {
        "transport": "sse",
        "url": "https://weather-api.example.com/sse",
        "headers": {
            "Authorization": "Bearer your-token"
        }
    }
}
```

### Production SSE Server with Full Resilience
```json
{
    "name": "Catalog Service",
    "server_type": "external", 
    "config": {
        "transport": "sse",
        "url": "https://catalog-api.example.com/sse",
        "timeout": 30,
        "sse_read_timeout": 1800,
        "max_retries": 5,
        "retry_backoff": 2.0,
        "session_resumption": true,
        "headers": {
            "Authorization": "Bearer your-token",
            "Connection": "keep-alive"
        }
    }
}
```

## Usage Examples

### 1. Creating Resilient MCP Client
```python
from src.infrastructure.mcp.mcp_client_factory import MCPClientFactory
from src.infrastructure.mcp.resilient_mcp_client import ResilientMCPClient

client_factory = MCPClientFactory()
resilient_client = ResilientMCPClient(
    configuration=your_config,
    client_factory=client_factory
)

# Automatic connection management
tools = await resilient_client.get_tools()
```

### 2. Using Error Recovery Service
```python
from src.infrastructure.mcp.error_recovery_service import MCPErrorRecoveryService

recovery_service = MCPErrorRecoveryService(client_factory)

# Handle connection error
await recovery_service.handle_connection_error(config, error)

# Get status summary
status = recovery_service.get_connection_status_summary()
```

### 3. Monitoring Connection Health
```python
# Check specific connection
healthy = client_factory.is_connection_healthy(config_id)

# Get detailed health info
health_info = client_factory.get_connection_health(config_id)

# Reset circuit breaker manually
client_factory.reset_circuit_breaker(config_id)
```

## Monitoring and Troubleshooting

### Health Check Endpoints

**Get Overall Status**:
```bash
curl http://localhost:8000/api/mcp-health/status
```

**Response**:
```json
{
    "status": "success",
    "data": {
        "total_connections": 3,
        "healthy_connections": 2,
        "failed_connections": 1,
        "recovering_connections": 0
    }
}
```

**Get Failed Servers**:
```bash
curl http://localhost:8000/api/mcp-health/failed-servers
```

**Force Reconnection**:
```bash
curl -X POST http://localhost:8000/api/mcp-health/reconnect/server-id
```

### Log Monitoring

**Key log patterns to monitor**:
```
# Connection successes
✅ MCP client created successfully: Catalog Service

# Connection failures  
❌ MCP client creation failed: Weather Service (ReadTimeout)

# Circuit breaker activation
⚠️ Circuit breaker activated for Catalog Service (failures: 3, timeout: 300s)

# Recovery attempts
🔄 Starting recovery process for Weather Service
✅ Recovery successful for Weather Service - 5 tools available
```

### Configuration Validation

The system validates all MCP configurations:
```python
# Required fields for SSE transport
{
    "url": "https://...",           # Required
    "transport": "sse",             # Required
    "timeout": 30,                  # Optional (default: 30)
    "sse_read_timeout": 1800        # Optional (default: 1800)
}
```

## Best Practices

### 1. Timeout Configuration
- **Connection timeout**: 30 seconds (sufficient for most networks)
- **SSE read timeout**: 1800 seconds (30 minutes) for production
- **Retry backoff**: 2.0 multiplier with max 5 attempts

### 2. Monitoring
- Enable health check endpoints in production
- Monitor circuit breaker activations
- Set up alerts for connection failures
- Track recovery success rates

### 3. Error Handling
- Always use protected tool wrappers
- Implement graceful degradation
- Provide user-friendly error messages
- Log detailed error information for debugging

### 4. Production Deployment
- Use connection pooling for better performance
- Enable session resumption for MCP compliance
- Configure appropriate SSL settings
- Set up monitoring dashboards

## Migration Guide

### Existing External MCP Servers

1. **Update configuration** to include new timeout parameters
2. **Test connection stability** with new timeouts
3. **Enable monitoring** endpoints
4. **Update error handling** in your application code

### Before (Problematic Configuration)
```json
{
    "transport": "sse",
    "url": "https://api.example.com/sse"
}
```

### After (Resilient Configuration)
```json
{
    "transport": "sse",
    "url": "https://api.example.com/sse", 
    "timeout": 30,
    "sse_read_timeout": 1800,
    "max_retries": 5,
    "session_resumption": true
}
```

## Troubleshooting Common Issues

### ReadTimeout Errors
**Solution**: Increase `sse_read_timeout` or set to higher value (1800+ seconds)

### ClosedResourceError  
**Solution**: Enable `session_resumption` and use resilient client wrappers

### Circuit Breaker Activation
**Solution**: Check server health, reset manually via API, or wait for timeout

### Tool Invocation Failures
**Solution**: Use protected tool wrappers for graceful error handling

This resilience system provides production-grade stability for MCP connections while maintaining MCP protocol compliance and delivering excellent user experience.