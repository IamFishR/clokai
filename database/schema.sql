-- Clokai Tracking Database Schema

CREATE DATABASE IF NOT EXISTS clokai_tracking;
USE clokai_tracking;

-- Sessions table to track conversation sessions
CREATE TABLE sessions (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    session_metadata JSON
);

-- Interactions table for user prompts and AI responses
CREATE TABLE interactions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    sequence_number INT NOT NULL,
    user_prompt TEXT NOT NULL,
    llm_response TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_time_ms INT,
    token_count_input INT,
    token_count_output INT,
    model_used VARCHAR(100),
    status ENUM('pending', 'completed', 'error') DEFAULT 'pending',
    error_message TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    INDEX idx_session_sequence (session_id, sequence_number)
);

-- Tool calls table to track function executions
CREATE TABLE tool_calls (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    interaction_id BIGINT NOT NULL,
    tool_name VARCHAR(100) NOT NULL,
    input_data JSON,
    output_data JSON,
    execution_time_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status ENUM('success', 'error') DEFAULT 'success',
    error_message TEXT,
    FOREIGN KEY (interaction_id) REFERENCES interactions(id) ON DELETE CASCADE,
    INDEX idx_interaction_tool (interaction_id, tool_name)
);

-- File snapshots table for tracking file changes
CREATE TABLE file_snapshots (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    tool_call_id BIGINT NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    snapshot_type ENUM('before', 'after') NOT NULL,
    content LONGTEXT,
    file_hash VARCHAR(64),
    file_size BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tool_call_id) REFERENCES tool_calls(id) ON DELETE CASCADE,
    INDEX idx_tool_call_file (tool_call_id, file_path),
    INDEX idx_file_snapshots_time (created_at)
);

-- AI processing metrics table
CREATE TABLE ai_metrics (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    interaction_id BIGINT NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(10,4),
    metric_unit VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON,
    FOREIGN KEY (interaction_id) REFERENCES interactions(id) ON DELETE CASCADE,
    INDEX idx_interaction_metric (interaction_id, metric_name)
);

-- Command executions table for shell command tracking
CREATE TABLE command_executions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    tool_call_id BIGINT NOT NULL,
    command TEXT NOT NULL,
    exit_code INT,
    stdout TEXT,
    stderr TEXT,
    execution_time_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tool_call_id) REFERENCES tool_calls(id) ON DELETE CASCADE,
    INDEX idx_tool_call_command (tool_call_id)
);