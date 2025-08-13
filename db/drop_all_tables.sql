-- Drop all tables in the correct order to handle foreign key constraints

-- Drop LangGraph checkpoint tables
DROP TABLE IF EXISTS checkpoint_blobs CASCADE;
DROP TABLE IF EXISTS checkpoint_writes CASCADE;
DROP TABLE IF EXISTS checkpoints CASCADE;

-- Drop application tables
DROP TABLE IF EXISTS chat_conversations CASCADE;
DROP TABLE IF EXISTS mcp_configurations CASCADE;
DROP TABLE IF EXISTS agent_configurations CASCADE;

-- Drop any other tables that might exist
DROP TABLE IF EXISTS checkpoint_migrations CASCADE;