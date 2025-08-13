-- Database initialization for LangGraph Multi-Agent System
-- Run with: psql langgraph_chats -f db/init_db.sql

-- Agent configurations table
CREATE TABLE IF NOT EXISTS agent_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,
    agent_type VARCHAR(50) NOT NULL CHECK (agent_type IN ('supervisor', 'specialized')),
    is_active BOOLEAN DEFAULT true,
    config JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MCP configurations table
CREATE TABLE IF NOT EXISTS mcp_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,
    server_type VARCHAR(50) NOT NULL CHECK (server_type IN ('internal', 'external')),
    is_active BOOLEAN DEFAULT true,
    config JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chat metadata table (for UI sidebar)
CREATE TABLE IF NOT EXISTS chat_metadata (
    thread_id VARCHAR(255) PRIMARY KEY,
    title VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Note: LangGraph checkpoint tables (checkpoints, checkpoint_writes, checkpoint_migrations, checkpoint_blobs)
-- are created automatically by LangGraph on first startup

-- Indexes (non-concurrent for transaction compatibility)
CREATE INDEX IF NOT EXISTS idx_agent_configurations_type ON agent_configurations(agent_type);
CREATE INDEX IF NOT EXISTS idx_agent_configurations_active ON agent_configurations(is_active);
CREATE INDEX IF NOT EXISTS idx_mcp_configurations_type ON mcp_configurations(server_type);

-- Default agent configurations
INSERT INTO agent_configurations (name, agent_type, config, is_active) 
VALUES 
(
    'Supervisor Agent',
    'supervisor',
    '{
        "description": "Coordinates with specialized agents and routes user requests",
        "model_config": {"model_name": "gemini-1.5-flash"},
        "mcp_tool_assignments": [],
        "managed_agents": ["Order Agent", "Customer Support Agent"]
    }'::jsonb,
    true
),
(
    'Order Agent',
    'specialized', 
    '{
        "description": "Handles order management including lookups, updates, and creation",
        "model_config": {"model_name": "gemini-1.5-flash"},
        "mcp_tool_assignments": ["get_order", "update_order_status", "list_orders", "create_order"],
        "managed_agents": []
    }'::jsonb,
    true
),
(
    'Customer Support Agent',
    'specialized',
    '{
        "description": "Handles customer inquiries and general support questions",
        "model_config": {"model_name": "gemini-1.5-flash"},
        "mcp_tool_assignments": [],
        "managed_agents": []
    }'::jsonb,
    true
)
ON CONFLICT (name) DO NOTHING;

-- Default MCP configurations
INSERT INTO mcp_configurations (name, server_type, config, is_active)
VALUES
(
    'Basic Tools',
    'internal',
    '{
        "command": "python",
        "args": ["mcp_server.py"],
        "transport": "stdio"
    }'::jsonb,
    true
),
(
    'Order Management',
    'external',
    '{
        "command": "python",
        "args": ["order_server.py"],
        "transport": "stdio"
    }'::jsonb,
    true
)
ON CONFLICT (name) DO NOTHING;