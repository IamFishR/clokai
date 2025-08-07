#!/usr/bin/env python3

import pymysql
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

def create_tables():
    connection = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    
    tables = [
        """
        CREATE TABLE IF NOT EXISTS interactions (
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
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS tool_calls (
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
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS file_snapshots (
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
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ai_metrics (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            interaction_id BIGINT NOT NULL,
            metric_name VARCHAR(100) NOT NULL,
            metric_value DECIMAL(10,4),
            metric_unit VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata JSON,
            FOREIGN KEY (interaction_id) REFERENCES interactions(id) ON DELETE CASCADE,
            INDEX idx_interaction_metric (interaction_id, metric_name)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS command_executions (
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
        )
        """
    ]
    
    try:
        with connection.cursor() as cursor:
            for i, table_sql in enumerate(tables, 1):
                print(f"Creating table {i}/5...")
                cursor.execute(table_sql)
                print(f"Table {i} created successfully!")
        
        connection.commit()
        print("All tables created successfully!")
        
        # Show all tables
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables_result = cursor.fetchall()
            print(f"All tables: {[table[0] for table in tables_result]}")
            
    finally:
        connection.close()

if __name__ == "__main__":
    create_tables()