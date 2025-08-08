import time
import json
import hashlib
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from database.connection import db_connection
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

class InteractionTracker:
    def __init__(self):
        self.current_session_id = None
        self.current_interaction_id = None
        self.interaction_start_time = None
        self.interaction_completed = False
    
    def start_session(self) -> str:
        """Start a new tracking session"""
        self.current_session_id = str(uuid.uuid4())
        
        try:
            with db_connection.get_session() as session:
                session.execute(text("""
                    INSERT INTO sessions (id, created_at, session_metadata)
                    VALUES (:id, NOW(), :metadata)
                """), {
                    'id': self.current_session_id,
                    'metadata': json.dumps({'start_time': datetime.now().isoformat()})
                })
            logger.info(f"Started tracking session: {self.current_session_id}")
        except Exception as e:
            logger.error(f"Failed to start tracking session: {e}")
        
        return self.current_session_id
    
    def start_interaction(self, user_prompt: str, sequence_number: int) -> int:
        """Start tracking a new user interaction"""
        self.interaction_start_time = time.time()
        self.interaction_completed = False
        
        try:
            with db_connection.get_session() as session:
                result = session.execute(text("""
                    INSERT INTO interactions (session_id, sequence_number, user_prompt, created_at, status)
                    VALUES (:session_id, :sequence_number, :user_prompt, NOW(), 'pending')
                """), {
                    'session_id': self.current_session_id,
                    'sequence_number': sequence_number,
                    'user_prompt': user_prompt
                })
                
                # Get the last inserted ID
                self.current_interaction_id = session.execute(text("SELECT LAST_INSERT_ID()")).scalar()
            
            logger.info(f"Started tracking interaction: {self.current_interaction_id}")
        except Exception as e:
            logger.error(f"Failed to start tracking interaction: {e}")
        
        return self.current_interaction_id
    
    def complete_interaction(self, llm_response: str, model_used: str, 
                           token_count_input: Optional[int] = None,
                           token_count_output: Optional[int] = None,
                           error_message: Optional[str] = None):
        """Complete the current interaction with results"""
        if not self.current_interaction_id or not self.interaction_start_time:
            print("[ERROR] No active interaction to complete.")
            return
        
        if self.interaction_completed:
            logger.warning("Interaction already completed, skipping duplicate completion")
            return
        
        processing_time_ms = int((time.time() - self.interaction_start_time) * 1000)
        status = 'error' if error_message else 'completed'
        
        try:
            with db_connection.get_session() as session:
                session.execute(text("""
                    UPDATE interactions 
                    SET llm_response = :response, processing_time_ms = :processing_time,
                        token_count_input = :token_input, token_count_output = :token_output,
                        model_used = :model, status = :status, error_message = :error
                    WHERE id = :interaction_id
                """), {
                    'response': llm_response,
                    'processing_time': processing_time_ms,
                    'token_input': token_count_input,
                    'token_output': token_count_output,
                    'model': model_used,
                    'status': status,
                    'error': error_message,
                    'interaction_id': self.current_interaction_id
                })
            
            self.interaction_completed = True
            logger.info(f"Completed tracking interaction: {self.current_interaction_id}")
        except Exception as e:
            logger.error(f"Failed to complete tracking interaction: {e}")
    
    def track_tool_call(self, tool_name: str, input_data: Dict[str, Any], 
                       output_data: Any, execution_time_ms: int,
                       status: str = 'success', error_message: Optional[str] = None) -> int:
        """Track a tool execution"""
        if not self.current_interaction_id:
            print("[ERROR] No active interaction to track tool call.")
            return None
        
        try:
            with db_connection.get_session() as session:
                result = session.execute(text("""
                    INSERT INTO tool_calls (interaction_id, tool_name, input_data, output_data,
                                          execution_time_ms, status, error_message, created_at)
                    VALUES (:interaction_id, :tool_name, :input_data, :output_data,
                            :execution_time, :status, :error, NOW())
                """), {
                    'interaction_id': self.current_interaction_id,
                    'tool_name': tool_name,
                    'input_data': json.dumps(input_data),
                    'output_data': json.dumps(output_data),
                    'execution_time': execution_time_ms,
                    'status': status,
                    'error': error_message
                })
                
                tool_call_id = session.execute(text("SELECT LAST_INSERT_ID()")).scalar()
            
            logger.info(f"Tracked tool call: {tool_call_id}")
            return tool_call_id
        except Exception as e:
            logger.error(f"Failed to track tool call: {e}")
            return None
    
    def track_file_snapshot(self, tool_call_id: int, file_path: str, 
                          snapshot_type: str, content: str):
        """Track file state before/after modifications"""
        if not tool_call_id:
            return
        
        file_hash = hashlib.sha256(content.encode()).hexdigest()
        file_size = len(content.encode())
        
        try:
            with db_connection.get_session() as session:
                session.execute(text("""
                    INSERT INTO file_snapshots (tool_call_id, file_path, snapshot_type,
                                              content, file_hash, file_size, created_at)
                    VALUES (:tool_call_id, :file_path, :snapshot_type,
                            :content, :file_hash, :file_size, NOW())
                """), {
                    'tool_call_id': tool_call_id,
                    'file_path': file_path,
                    'snapshot_type': snapshot_type,
                    'content': content,
                    'file_hash': file_hash,
                    'file_size': file_size
                })
            
            logger.info(f"Tracked file snapshot: {file_path} ({snapshot_type})")
        except Exception as e:
            logger.error(f"Failed to track file snapshot: {e}")
    
    def track_command_execution(self, tool_call_id: int, command: str, 
                              exit_code: int, stdout: str, stderr: str,
                              execution_time_ms: int):
        """Track command execution details"""
        if not tool_call_id:
            return
        
        try:
            with db_connection.get_session() as session:
                session.execute(text("""
                    INSERT INTO command_executions (tool_call_id, command, exit_code,
                                                   stdout, stderr, execution_time_ms, created_at)
                    VALUES (:tool_call_id, :command, :exit_code,
                            :stdout, :stderr, :execution_time, NOW())
                """), {
                    'tool_call_id': tool_call_id,
                    'command': command,
                    'exit_code': exit_code,
                    'stdout': stdout,
                    'stderr': stderr,
                    'execution_time': execution_time_ms
                })
            
            logger.info(f"Tracked command execution: {command}")
        except Exception as e:
            logger.error(f"Failed to track command execution: {e}")
    
    def track_ai_metric(self, metric_name: str, metric_value: float,
                       metric_unit: str, metadata: Optional[Dict] = None):
        """Track AI processing metrics"""
        if not self.current_interaction_id:
            return
        
        try:
            with db_connection.get_session() as session:
                session.execute(text("""
                    INSERT INTO ai_metrics (interaction_id, metric_name, metric_value,
                                          metric_unit, metadata, created_at)
                    VALUES (:interaction_id, :metric_name, :metric_value,
                            :metric_unit, :metadata, NOW())
                """), {
                    'interaction_id': self.current_interaction_id,
                    'metric_name': metric_name,
                    'metric_value': metric_value,
                    'metric_unit': metric_unit,
                    'metadata': json.dumps(metadata) if metadata else None
                })
            
            logger.info(f"Tracked AI metric: {metric_name} = {metric_value} {metric_unit}")
        except Exception as e:
            logger.error(f"Failed to track AI metric: {e}")
    
    def track_llm_call(self, call_type: str, full_prompt: str, system_prompt: str,
                      conversation_context: List[Dict], llm_response: str,
                      model_used: str, processing_time_ms: int,
                      token_count_input: int, token_count_output: int,
                      call_sequence: int = 1) -> int:
        """Track detailed LLM call information"""
        if not self.current_interaction_id:
            return None
        
        try:
            with db_connection.get_session() as session:
                # Try to insert into llm_calls table if it exists
                try:
                    session.execute(text("""
                        INSERT INTO llm_calls (interaction_id, call_type, call_sequence, 
                                             full_prompt, system_prompt, conversation_context,
                                             llm_response, model_used, processing_time_ms,
                                             token_count_input, token_count_output, created_at)
                        VALUES (:interaction_id, :call_type, :call_sequence,
                                :full_prompt, :system_prompt, :conversation_context,
                                :llm_response, :model_used, :processing_time_ms,
                                :token_count_input, :token_count_output, NOW())
                    """), {
                        'interaction_id': self.current_interaction_id,
                        'call_type': call_type,
                        'call_sequence': call_sequence,
                        'full_prompt': full_prompt,
                        'system_prompt': system_prompt,
                        'conversation_context': json.dumps(conversation_context),
                        'llm_response': llm_response,
                        'model_used': model_used,
                        'processing_time_ms': processing_time_ms,
                        'token_count_input': token_count_input,
                        'token_count_output': token_count_output
                    })
                    
                    llm_call_id = session.execute(text("SELECT LAST_INSERT_ID()")).scalar()
                    logger.info(f"Tracked LLM call: {call_type} (ID: {llm_call_id})")
                    return llm_call_id
                    
                except Exception as e:
                    # If table doesn't exist, log the info but don't fail
                    logger.warning(f"LLM calls table not available, logging to file: {e}")
                    
                    # Log to file as fallback
                    import os
                    log_file = os.path.join(os.path.dirname(__file__), '..', 'llm_calls.log')
                    with open(log_file, 'a', encoding='utf-8') as f:
                        import datetime
                        timestamp = datetime.datetime.now().isoformat()
                        f.write(f"\n=== LLM Call {timestamp} ===\n")
                        f.write(f"Interaction ID: {self.current_interaction_id}\n")
                        f.write(f"Call Type: {call_type}\n")
                        f.write(f"System Prompt: {system_prompt[:200]}...\n")
                        f.write(f"Full Prompt: {full_prompt[:500]}...\n")
                        f.write(f"Response: {llm_response[:500]}...\n")
                        f.write(f"Model: {model_used}\n")
                        f.write(f"Tokens: {token_count_input}/{token_count_output}\n")
                    
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to track LLM call: {e}")
            return None

# Global tracker instance
tracker = InteractionTracker()