-- Clokai Database Log Queries
-- Run these queries to view all tracking data

-- =============================================================================
-- 1. SESSIONS - All conversation sessions
-- =============================================================================
SELECT 
    id as session_id,
    created_at,
    updated_at,
    session_metadata
FROM sessions 
ORDER BY created_at DESC;

-- =============================================================================
-- 2. INTERACTIONS - User prompts and AI responses with timing
-- =============================================================================
SELECT 
    i.id,
    i.session_id,
    i.sequence_number,
    LEFT(i.user_prompt, 100) as prompt_preview,
    LEFT(i.llm_response, 100) as response_preview,
    i.processing_time_ms,
    i.token_count_input,
    i.token_count_output,
    i.model_used,
    i.status,
    i.error_message,
    i.created_at
FROM interactions i 
ORDER BY i.created_at DESC;

-- =============================================================================
-- 3. TOOL CALLS - All function executions with I/O data
-- =============================================================================
SELECT 
    tc.id,
    tc.interaction_id,
    tc.tool_name,
    tc.input_data,
    CASE 
        WHEN LENGTH(tc.output_data) > 200 
        THEN CONCAT(LEFT(tc.output_data, 200), '...')
        ELSE tc.output_data 
    END as output_preview,
    tc.execution_time_ms,
    tc.status,
    tc.error_message,
    tc.created_at
FROM tool_calls tc 
ORDER BY tc.created_at DESC;

-- =============================================================================
-- 4. FILE SNAPSHOTS - Before/after file content changes
-- =============================================================================
SELECT 
    fs.id,
    fs.tool_call_id,
    fs.file_path,
    fs.snapshot_type,
    CASE 
        WHEN LENGTH(fs.content) > 500 
        THEN CONCAT(LEFT(fs.content, 500), '...')
        ELSE fs.content 
    END as content_preview,
    fs.file_hash,
    fs.file_size,
    fs.created_at
FROM file_snapshots fs 
ORDER BY fs.created_at DESC, fs.file_path, fs.snapshot_type;

-- =============================================================================
-- 5. COMMAND EXECUTIONS - Shell command details
-- =============================================================================
SELECT 
    ce.id,
    ce.tool_call_id,
    ce.command,
    ce.exit_code,
    CASE 
        WHEN LENGTH(ce.stdout) > 200 
        THEN CONCAT(LEFT(ce.stdout, 200), '...')
        ELSE ce.stdout 
    END as stdout_preview,
    CASE 
        WHEN LENGTH(ce.stderr) > 200 
        THEN CONCAT(LEFT(ce.stderr, 200), '...')
        ELSE ce.stderr 
    END as stderr_preview,
    ce.execution_time_ms,
    ce.created_at
FROM command_executions ce 
ORDER BY ce.created_at DESC;

-- =============================================================================
-- 6. AI METRICS - Processing metrics and performance data
-- =============================================================================
SELECT 
    am.id,
    am.interaction_id,
    am.metric_name,
    am.metric_value,
    am.metric_unit,
    am.metadata,
    am.created_at
FROM ai_metrics am 
ORDER BY am.created_at DESC;

-- =============================================================================
-- 7. COMPLETE SESSION VIEW - Join sessions with interactions
-- =============================================================================
SELECT 
    s.id as session_id,
    s.created_at as session_start,
    i.sequence_number,
    LEFT(i.user_prompt, 80) as prompt,
    i.processing_time_ms,
    i.status as interaction_status,
    COUNT(tc.id) as tool_calls_count
FROM sessions s
LEFT JOIN interactions i ON s.id = i.session_id
LEFT JOIN tool_calls tc ON i.id = tc.interaction_id
GROUP BY s.id, i.id
ORDER BY s.created_at DESC, i.sequence_number;

-- =============================================================================
-- 8. TOOL USAGE SUMMARY - Tool execution statistics
-- =============================================================================
SELECT 
    tc.tool_name,
    COUNT(*) as total_calls,
    AVG(tc.execution_time_ms) as avg_execution_time,
    MIN(tc.execution_time_ms) as min_time,
    MAX(tc.execution_time_ms) as max_time,
    SUM(CASE WHEN tc.status = 'success' THEN 1 ELSE 0 END) as successful_calls,
    SUM(CASE WHEN tc.status = 'error' THEN 1 ELSE 0 END) as failed_calls
FROM tool_calls tc
GROUP BY tc.tool_name
ORDER BY total_calls DESC;

-- =============================================================================
-- 9. FILE CHANGE HISTORY - Track all file modifications
-- =============================================================================
SELECT 
    tc.created_at as change_time,
    JSON_UNQUOTE(JSON_EXTRACT(tc.input_data, '$.path')) as file_path,
    tc.tool_name,
    fs_before.file_size as size_before,
    fs_after.file_size as size_after,
    (fs_after.file_size - COALESCE(fs_before.file_size, 0)) as size_change
FROM tool_calls tc
LEFT JOIN file_snapshots fs_before ON tc.id = fs_before.tool_call_id AND fs_before.snapshot_type = 'before'
LEFT JOIN file_snapshots fs_after ON tc.id = fs_after.tool_call_id AND fs_after.snapshot_type = 'after'
WHERE tc.tool_name IN ('write_file', 'read_file')
ORDER BY tc.created_at DESC;

-- =============================================================================
-- 10. PERFORMANCE OVERVIEW - System performance metrics
-- =============================================================================
SELECT 
    'Interactions' as metric_type,
    COUNT(*) as total_count,
    AVG(processing_time_ms) as avg_time_ms,
    MAX(processing_time_ms) as max_time_ms
FROM interactions
UNION ALL
SELECT 
    'Tool Calls' as metric_type,
    COUNT(*) as total_count,
    AVG(execution_time_ms) as avg_time_ms,
    MAX(execution_time_ms) as max_time_ms
FROM tool_calls
UNION ALL
SELECT 
    'Commands' as metric_type,
    COUNT(*) as total_count,
    AVG(execution_time_ms) as avg_time_ms,
    MAX(execution_time_ms) as max_time_ms
FROM command_executions;