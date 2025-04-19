# SoftwareSim3d/src/simulation/workflow_manager.py

import asyncio
import logging
import uuid
import os
import re
import time
import math
from typing import Dict, Any, Optional, List, Set, Callable, Awaitable, Tuple

from .task import Task #
from ..agent_base import Agent #
from ..agents.ceo_agent import CEOAgent #
from ..agents.product_manager_agent import ProductManagerAgent #
from ..agents.coder_agent import CoderAgent # # Coordinator
from ..agents.html_agent import HTMLAgent # Specialist
from ..agents.css_agent import CSSAgent   # Specialist
from ..agents.js_agent import JSAgent     # Specialist
from ..agents.marketer_agent import MarketerAgent #
from ..agents.qa_agent import QAAgent #
from ..agents.messenger_agent import MessengerAgent #
from ..llm_integration.api_clients import LLMService #

logger = logging.getLogger(__name__)

EmitAgentUpdateCallback = Callable[[str, Dict[str, Any]], None]
RequestUserInputCallback = Callable[[str, str], None]
EmitTaskUpdateCallback = Callable[[str, Dict[str, Any]], None]
EmitFinalOutputCallback = Callable[[str, bool], None]

AGENT_SPEED = 5.0 # Units per second (adjust as needed)

class WorkflowManager:
    # Define zone coordinates (ensure consistency with frontend if visualization used)
    ZONE_COORDINATES = {
        "CEO_OFFICE": (0, 0.5, -24), # Backend Z is negative into screen
        "PM_DESK": (-30, 0.5, -10),
        "MKT_DESK": (30, 0.5, -10),
        "CODER_DESK": (30, 0.5, 15),
        "QA_DESK": (35, 0.5, 15),
        # New Specialist Desk Zones (Z coordinates inverted from frontend)
        "HTML_DESK": (20, 0.5, 15),  # Near Coder
        "CSS_DESK": (25, 0.5, 25),   # Near Coder
        "JS_DESK": (35, 0.5, 25),    # Near Coder
        "MESSENGER_STATION": (5, 0.5, -20), # Near CEO office entrance
        "SAVE_ZONE": (35, 0.1, -25), # Low Y for floor zones
        "INTERNET_ZONE": (-35, 0.1, -25),
        "WATER_COOLER_ZONE": (30, 0.1, 20),
        "MEETING_ROOM_CENTER": (0, 0.5, -15),
        # Add placeholders if zones exist but aren't used yet
        "IMAGE_GEN_ZONE": (-20, 0.1, -25),
        "CODE_EXEC_ZONE": (20, 0.1, -25),
    }

    def __init__(self,
                 llm_service: LLMService,
                 loop: asyncio.AbstractEventLoop,
                 llm_agent_configs: Optional[Dict[str, Dict[str, str]]] = None):
        self.llm_service = llm_service #[cite: uploaded:SoftwareSim3d/src/llm_integration/api_clients.py]
        self.loop = loop
        self.llm_agent_configs = llm_agent_configs if llm_agent_configs else {}
        self.agents: Dict[str, Agent] = {} #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
        self.agent_message_queues: Dict[str, asyncio.Queue] = {}
        self.tasks: Dict[str, Task] = {} #[cite: uploaded:SoftwareSim3d/src/simulation/task.py]
        self.completed_task_ids: Set[str] = set() # Track completed tasks for dependency checks
        self.saved_outputs: Dict[str, str] = {} # task_id -> absolute output path
        self.simulation_complete: bool = False
        self.simulation_success: Optional[bool] = None
        self.final_output: Optional[str] = None
        self.project_name: Optional[str] = None
        self.max_iterations: int = 2000 # Prevent infinite loops
        self.current_iteration: int = 0
        self.emit_agent_update: Optional[EmitAgentUpdateCallback] = None
        self.emit_task_update: Optional[EmitTaskUpdateCallback] = None
        self.request_user_input: Optional[RequestUserInputCallback] = None
        self.emit_final_output: Optional[EmitFinalOutputCallback] = None
        # Determine base output dir relative to this file's location
        self.base_output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'output'))
        os.makedirs(self.base_output_dir, exist_ok=True)
        self._initialize_agents() # Initialize agents upon creation
        logger.info(f"WorkflowManager initialized. Output dir: {self.base_output_dir}")

    def _initialize_agents(self):
        logger.info("Initializing agents...")
        agent_roles_classes = {
            "CEO": CEOAgent,
            "Product Manager": ProductManagerAgent,
            "Marketer": MarketerAgent,
            "Coder": CoderAgent, # Coordinator
            "HTML Specialist": HTMLAgent, # New
            "CSS Specialist": CSSAgent,   # New
            "JavaScript Specialist": JSAgent, # New
            "QA": QAAgent,
            "Messenger": MessengerAgent
        }
        agent_ids = {
            "CEO": "ceo-01", "Product Manager": "pm-01", "Marketer": "mkt-01",
            "Coder": "coder-01", "HTML Specialist": "html-01", "CSS Specialist": "css-01",
            "JavaScript Specialist": "js-01", "QA": "qa-01", "Messenger": "msgr-01"
        }
        # Updated specialist desks
        agent_positions = {
            "CEO": ("CEO_OFFICE", "CEO_OFFICE"), 
            "Product Manager": ("MEETING_ROOM_CENTER", "PM_DESK"),
            "Marketer": ("MEETING_ROOM_CENTER", "MKT_DESK"), 
            "Coder": ("CODER_DESK", "CODER_DESK"),
            "HTML Specialist": ("HTML_DESK", "HTML_DESK"), 
            "CSS Specialist": ("CSS_DESK", "CSS_DESK"),
            "JavaScript Specialist": ("JS_DESK", "JS_DESK"), 
            "QA": ("QA_DESK", "QA_DESK"),
            "Messenger": ("MESSENGER_STATION", "MESSENGER_STATION")
        }
        # Tools - Specialists likely don't need tools initially
        role_tools = {
            "CEO": set(), "Product Manager": {'file_read', 'file_write'},
            "Marketer": {'internet_search', 'file_write'}, "Coder": {'file_read', 'file_write'}, # Coordinator still needs tools
            "HTML Specialist": set(), "CSS Specialist": set(), "JavaScript Specialist": set(),
            "QA": {'file_read'}, "Messenger": set()
        }
        tool_zones_map = { 'internet_search': 'INTERNET_ZONE', 'file_read': 'SAVE_ZONE', 'file_write': 'SAVE_ZONE' }

        # --- Role Specific Dependencies ---
        manager_ids = { "Product Manager": agent_ids["Product Manager"], "Marketer": agent_ids["Marketer"], "Coder": agent_ids["Coder"] }
        ceo_id = agent_ids["CEO"]
        messenger_id = agent_ids["Messenger"]
        coder_lead_id = agent_ids["Coder"] # Coordinator ID
        qa_id = agent_ids["QA"]
        html_agent_id = agent_ids["HTML Specialist"]
        css_agent_id = agent_ids["CSS Specialist"]
        js_agent_id = agent_ids["JavaScript Specialist"]
        # --- End Role Specific Dependencies ---

        default_llm_type, default_llm_model = self._get_default_llm_config()

        for role, AgentClass in agent_roles_classes.items():
            agent_id = agent_ids[role]
            msg_queue = asyncio.Queue(); self.agent_message_queues[agent_id] = msg_queue
            agent_config_from_input = self.llm_agent_configs.get(role)
            
            # MODIFIED: Use the same LLM provider for all agents
            # For specialists, use the same LLM type as Coder instead of OpenAI
            if role in ["HTML Specialist", "CSS Specialist", "JavaScript Specialist"]:
                coder_config = self.llm_agent_configs.get("Coder")
                if coder_config and coder_config.get("type"):
                    agent_config_from_input = coder_config
            
            llm_type, llm_model_name = self._get_agent_llm_config(role, agent_config_from_input, default_llm_type, default_llm_model)
            init_pos_key, desk_pos_key = agent_positions[role]
            init_pos = self.ZONE_COORDINATES.get(init_pos_key, (0, 0.5, 0))
            desk_pos = self.ZONE_COORDINATES.get(desk_pos_key, (0, 0.5, 0))

            try:
                agent_init_args = {
                    'message_queue': msg_queue, 'broadcast_callback': self._route_message,
                    'loop': self.loop, 'initial_position': init_pos, 'target_desk_position': desk_pos,
                    'llm_service': self.llm_service, 'llm_type': llm_type, 'llm_model_name': llm_model_name,
                    'available_tools': role_tools.get(role, set()), 'required_tool_zones': tool_zones_map,
                    'zone_coordinates_map': self.ZONE_COORDINATES, # Pass the full map
                }

                # Add role-specific arguments
                if role == "CEO": agent_init_args.update({'manager_ids': manager_ids, 'messenger_id': messenger_id})
                elif role == "Messenger": agent_init_args['ceo_agent_id'] = ceo_id
                elif role == "QA": agent_init_args.update({'coder_lead_id': coder_lead_id, 'ceo_agent_id': ceo_id})
                # --- Pass Specialist IDs to Coder ---
                elif role == "Coder":
                    agent_init_args.update({
                        'ceo_agent_id': ceo_id, 'qa_agent_id': qa_id,
                        'html_agent_id': html_agent_id, 'css_agent_id': css_agent_id, 'js_agent_id': js_agent_id
                    })
                # --- Pass Coder Lead ID to Specialists ---
                elif role in ["HTML Specialist", "CSS Specialist", "JavaScript Specialist"]:
                    agent_init_args['coder_lead_id'] = coder_lead_id

                agent = AgentClass(agent_id=agent_id, role=role, **agent_init_args)
                self.agents[agent_id] = agent
                logger.info(f"Initialized agent: {agent_id} ({role}) LLM: {llm_type or 'N/A'} ({llm_model_name or 'default'})")

            except Exception as e:
                logger.error(f"Failed to initialize agent {agent_id} ({role}): {e}", exc_info=True)
                raise

    def _get_default_llm_config(self) -> Tuple[Optional[str], Optional[str]]:
         # Prioritize available clients
         if self.llm_service.openai_client: return "openai", "gpt-4o" 
         elif self.llm_service.google_client: return "gemini", "gemini-2.5-pro-preview-03-25" 
         elif self.llm_service.anthropic_client: return "anthropic", "claude-3-7-sonnet-20250219" 
         else: return None, None # No clients configured

    def _get_agent_llm_config(self, role: str, config: Optional[Dict[str, str]], default_type: Optional[str], default_model: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
         if role == "Messenger": return None, None # Messenger doesn't use LLM

         llm_type_from_config = config.get("type") if isinstance(config, dict) else None
         llm_model_from_config = config.get("model") if isinstance(config, dict) else None

         # Use config if valid, otherwise use default
         llm_type = llm_type_from_config if llm_type_from_config in ["gemini", "openai", "anthropic"] else default_type
         llm_model = llm_model_from_config # User can specify empty string to force default

         # If model is empty or None, use the default model for the selected type
         if not llm_model:
             model_map = {"gemini": "gemini-1.5-flash", "openai": "gpt-4o", "anthropic": "claude-3-7-sonnet-20250219"}
             llm_model = model_map.get(llm_type, default_model) # Fallback to overall default if type unknown

         if not llm_type: return None, None # No LLM configured or available

         return llm_type, llm_model

    def register_websocket_callbacks(self, emit_agent_update: EmitAgentUpdateCallback, emit_task_update: EmitTaskUpdateCallback, request_user_input: RequestUserInputCallback, emit_final_output: EmitFinalOutputCallback):
        self.emit_agent_update = emit_agent_update
        self.emit_task_update = emit_task_update
        self.request_user_input = request_user_input
        self.emit_final_output = emit_final_output
        # Register callback for all initialized agents
        for agent_id, agent in self.agents.items():
             if hasattr(agent, 'register_state_update_callback'):
                 agent.register_state_update_callback(self._handle_agent_state_change) 
                 logger.debug(f"Registered state update callback for {agent_id}")
             else:
                  logger.warning(f"Agent {agent_id} does not have 'register_state_update_callback' method.")
        logger.info("WebSocket callbacks registered.")

    def _handle_agent_state_change(self, agent_id: str, state: Dict[str, Any]):
        """Callback triggered when an agent's internal state changes."""
        agent = self.agents.get(agent_id)
        if not agent or not self.emit_agent_update:
             # Log if agent not found, maybe it failed initialization?
             if not agent: logger.warning(f"State change received for unknown agent_id: {agent_id}")
             return

        # --- Send state update to frontend ---
        state_with_pos = state.copy()
        current_pos_backend = agent.get_state('position', agent.initial_position) 
        state_with_pos['position'] = current_pos_backend
        state_with_pos['role'] = agent.role 
        self.emit_agent_update(agent_id, state_with_pos)

        # --- Handle Movement Simulation ---
        status = state.get('status')
        if status == 'moving_to_zone':
            current_target_pos = agent.get_state('target_position') 
            if not current_target_pos: # Should not happen if moving
                 logger.warning(f"Agent {agent_id} in moving_to_zone status but no target_position found in state.")
                 return

            # Prevent duplicate movement timers
            if agent.internal_state.get('_movement_in_progress_to') != current_target_pos:
                distance = math.dist(current_pos_backend, current_target_pos)
                travel_time = max(0.5, distance / AGENT_SPEED if AGENT_SPEED > 0 else 0.5) # Min 0.5 sec travel
                target_zone_name = state.get('target_zone', 'Unknown Zone')
                logger.info(f"Agent {agent_id} started move to {target_zone_name} at {current_target_pos}. Est. Time: {travel_time:.2f}s")
                agent.internal_state['_movement_in_progress_to'] = current_target_pos

                async def delayed_arrival_sender(delay, agent_id_to_notify, zone_to_arrive, final_position):
                    await asyncio.sleep(delay)
                    current_agent = self.agents.get(agent_id_to_notify)
                    # Check agent exists and is still targeting the same place
                    if current_agent and current_agent.internal_state.get('_movement_in_progress_to') == final_position:
                        logger.info(f"Agent {agent_id_to_notify} finished move to {zone_to_arrive}. Sending arrival message.")
                        current_agent.internal_state.pop('_movement_in_progress_to', None)
                        current_agent.update_state({'position': final_position}, trigger_callback=False) 
                        await self._send_arrival_message(agent_id_to_notify, zone_to_arrive)
                    else: logger.debug(f"Agent {agent_id_to_notify}'s move to {zone_to_arrive} cancelled or agent removed.")

                self.loop.create_task(delayed_arrival_sender(travel_time, agent_id, target_zone_name, current_target_pos))

    async def _send_arrival_message(self, agent_id: str, zone_name: str):
        """Sends an internal message to the agent confirming arrival."""
        arrival_message = {'sender_id': 'workflow_manager', 'recipient_id': agent_id, 'content': {'type': 'arrived_at_zone', 'zone_name': zone_name}}
        try: await self._route_message(arrival_message)
        except Exception as e: logger.error(f"Error routing arrival message for {agent_id} to {zone_name}: {e}", exc_info=True)

    async def _route_message(self, message: Dict[str, Any]):
        """Routes messages between agents or to the manager."""
        recipient_id = message.get('recipient_id'); sender_id = message.get('sender_id')
        content_type = message.get('content', {}).get('type', 'unknown'); logger.debug(f"Routing message from {sender_id} to {recipient_id}. Type: {content_type}")
        if recipient_id == 'workflow_manager':
             if self.loop == asyncio.get_running_loop(): self.loop.create_task(self._handle_manager_message(sender_id, message.get('content', {})))
             else: asyncio.run_coroutine_threadsafe(self._handle_manager_message(sender_id, message.get('content', {})), self.loop)
        elif recipient_id in self.agent_message_queues:
             try: await self.agent_message_queues[recipient_id].put(message)
             except Exception as e: logger.error(f"Error adding message to {recipient_id}'s queue: {e}", exc_info=True)
        else: logger.warning(f"Cannot route message: Unknown recipient_id '{recipient_id}' from sender '{sender_id}'")

    async def _handle_manager_message(self, sender_id: str, content: Dict[str, Any]):
        """Handles messages directed to the WorkflowManager."""
        msg_type = content.get('type'); logger.info(f"Manager handling message type '{msg_type}' from agent {sender_id}.")
        agent_instance = self.agents.get(sender_id); agent_role = agent_instance.role if agent_instance else "UnknownRole" 
        try:
            if msg_type == 'request_tool_use':
                tool_name = content.get('tool_name'); params = content.get('parameters', {}); task_id = content.get('task_id')
                tool_result = await self._execute_backend_tool(sender_id, agent_role, tool_name, params, task_id)
                response_message = {'sender_id': 'workflow_manager', 'recipient_id': sender_id, 'content': { 'type': 'tool_result', 'tool_name': tool_name, **tool_result } }
                await self._route_message(response_message)
            elif msg_type == 'task_completion_update':
                task_id = content.get('task_id'); status = content.get('status'); result = content.get('result')
                if task_id and task_id in self.tasks:
                    task = self.tasks[task_id]; task.update_status(status); task.result = result 
                    logger.info(f"Task {task_id} ('{task.description[:30]}...') updated to status: {status} by agent {sender_id}.") 
                    if status in ['completed', 'failed']: self.completed_task_ids.add(task_id)
                    if self.emit_task_update: self.emit_task_update(task_id, task.to_dict()) 
                else: logger.warning(f"Received completion update for unknown/missing task_id: {task_id}")
            elif msg_type == 'delegate_sub_tasks': await self._delegate_tasks_from_ceo(content.get('tasks_to_delegate', []))
            elif msg_type == 'request_user_input':
                 if self.request_user_input:
                     task_id = content.get('originating_task_id'); question = content.get('question')
                     if task_id and task_id in self.tasks: self.tasks[task_id].update_status('waiting_user_input'); #[cite: uploaded:SoftwareSim3d/src/simulation/task.py]
                     if self.emit_task_update: self.emit_task_update(task_id, self.tasks[task_id].to_dict()) #[cite: uploaded:SoftwareSim3d/src/simulation/task.py]
                     self.request_user_input(task_id, question)
                 else: logger.error("Cannot forward user input request: UI callback not registered.")
            elif msg_type == 'request_ceo_evaluation': await self._create_ceo_evaluation_task(sender_id, content.get('triggering_task_id'), content.get('result_info'))
            elif msg_type == 'ui_simulation_end':
                 if self.emit_final_output:
                      success = content.get('success', False); message = content.get('message', 'Simulation ended.')
                      logger.info(f"Received simulation end signal from {sender_id}. Success: {success}. Message: {message}")
                      self.simulation_complete = True; self.simulation_success = success; self.final_output = message
                 else: logger.error("Cannot forward simulation end signal: UI callback not registered.")
            else: logger.warning(f"WorkflowManager received unhandled message type '{msg_type}' from {sender_id}.")
        except Exception as e: logger.error(f"Error handling manager message from {sender_id} (type {msg_type}): {e}", exc_info=True)

    async def _delegate_tasks_from_ceo(self, delegation_list: List[Dict]):
         """Creates and assigns tasks based on CEO's delegation request."""
         logger.info(f"Manager received request to delegate {len(delegation_list)} tasks from CEO.")
         for item in delegation_list:
              target_agent_id = item.get('target_agent_id'); task_data = item.get('task_data'); assigned_role = task_data.get('assigned_to_role')
              if not target_agent_id or not task_data or target_agent_id not in self.agents or not assigned_role: logger.error(f"Skipping invalid delegation item: Target={target_agent_id}, Data={task_data is not None}, Role={assigned_role}"); continue
              new_task = Task(description=task_data.get('description', '...'), task_type=task_data.get('task_type', 'generic'), details=task_data.get('details', {}), assigned_to_role=assigned_role, originating_task_id=task_data.get('details', {}).get('originating_task_id'))
              self.tasks[new_task.task_id] = new_task; 
              logger.info(f"Created new task {new_task.task_id} for {assigned_role} ({target_agent_id}): '{new_task.description[:40]}...'") 
              task_message = {'sender_id': 'workflow_manager', 'recipient_id': target_agent_id, 'content': {'type': 'new_task', 'task_data': new_task.to_dict()}} 
              await self._route_message(task_message)
              if self.emit_task_update: self.emit_task_update(new_task.task_id, new_task.to_dict()) 

    async def _create_ceo_evaluation_task(self, triggering_agent_id: str, triggering_task_id: Optional[str], result_info: Optional[str]):
        """Creates a task for the CEO to evaluate progress."""
        ceo_agent = next((a for a in self.agents.values() if isinstance(a, CEOAgent)), None) 
        if not ceo_agent: logger.error("Cannot create evaluation task: CEO agent not found."); return
        project_saved_outputs = { tid: os.path.basename(path) for tid, path in self.saved_outputs.items() if tid in self.tasks }
        original_request = "[Original request unavailable]"
        if triggering_task_id and triggering_task_id in self.tasks: original_request = self.tasks[triggering_task_id].details.get('original_request', original_request) 
        else: first_task = next(iter(self.tasks.values()), None); original_request = first_task.details.get('original_request', original_request) if first_task else original_request 
        eval_details = {'user_request': original_request, 'project_name': self.project_name, 'saved_outputs': project_saved_outputs, 'triggering_agent_id': triggering_agent_id, 'triggering_task_id': triggering_task_id, 'last_output_info': result_info}
        eval_task = Task(description=f"Evaluate project progress for '{self.project_name}' triggered by {triggering_agent_id}", task_type="evaluate_progress", details=eval_details, assigned_to_role="CEO") 
        self.tasks[eval_task.task_id] = eval_task; 
        logger.info(f"Created CEO evaluation task {eval_task.task_id}") 
        task_message = {'sender_id': 'workflow_manager', 'recipient_id': ceo_agent.agent_id, 'content': {'type': 'new_task', 'task_data': eval_task.to_dict()}} 
        await self._route_message(task_message)
        if self.emit_task_update: self.emit_task_update(eval_task.task_id, eval_task.to_dict()) #[cite: uploaded:SoftwareSim3d/src/simulation/task.py]

    async def _execute_backend_tool(self, agent_id: str, agent_role: str, tool_name: str, params: Dict[str, Any], task_id: Optional[str]) -> Dict[str, Any]:
        """Executes backend tools like file I/O or simulated search."""
        logger.info(f"Executing tool '{tool_name}' for agent {agent_id} ({agent_role}). Task context: {task_id or 'N/A'}")
        result = {'status': 'error', 'result': f'Unknown tool: {tool_name}'}
        try:
            if tool_name == 'file_write': result = self._tool_file_write(agent_id, agent_role, params.get('filename'), params.get('content'), task_id)
            elif tool_name == 'file_read': result = self._tool_file_read(agent_id, params.get('filename'))
            elif tool_name == 'internet_search': result = await self._tool_internet_search(params.get('query'))
            else: logger.error(f"Agent {agent_id} requested unknown tool: {tool_name}")
        except SecurityException as se: logger.error(f"Security error executing tool '{tool_name}' for {agent_id}: {se}"); result = {'status': 'error', 'result': f"Security error: {se}"}
        except Exception as e: logger.error(f"Error executing tool '{tool_name}' for {agent_id}: {e}", exc_info=True); result = {'status': 'error', 'result': f"Tool exception: {e}"}
        if 'status' not in result: result['status'] = 'error'
        if 'result' not in result: result['result'] = "Unknown tool error."
        return result

    def _tool_file_write(self, sender_id: str, sender_role: str, relative_filename: Optional[str], content: Optional[str], task_id: Optional[str]) -> Dict[str, Any]:
        """Handles the file_write tool execution with flexible path handling."""
        if not relative_filename or content is None:
            return {'status': 'error', 'result': 'Missing filename or content.'}
        logger.info(f"File write request from {sender_id} ({sender_role}) for filename: {relative_filename}")
        try:
            # --- Modified Path Handling ---
            # Sanitize each part of the provided relative path
            path_parts = [self._sanitize_filename(part) for part in relative_filename.replace("\\", "/").split('/') if part and part != '.']

            if not path_parts:
                raise ValueError("Invalid relative filename structure after sanitization.")

            # Construct the full path relative to the base output directory
            # The agent is now responsible for providing the full desired relative path structure
            # e.g., "MyProject/about.html" or "MyProject/css/style.css"
            output_path = os.path.join(self.base_output_dir, *path_parts)
            full_dir = os.path.dirname(output_path)
            safe_basename = os.path.basename(output_path) # Already sanitized as part of path_parts

            if not safe_basename:
                 raise ValueError("Invalid filename component.")
            logger.info(f"Sanitized filename: {safe_basename}")
            # --- Security Check: Ensure path stays within base_output_dir ---
            abs_output_path = os.path.abspath(output_path)
            abs_base_output_dir = os.path.abspath(self.base_output_dir)
            if not abs_output_path.startswith(abs_base_output_dir):
                raise SecurityException(f"Path traversal attempt detected: '{relative_filename}' resolved to '{abs_output_path}' which is outside base '{abs_base_output_dir}'")
            # --- End Security Check ---

            # Create directories if they don't exist
            os.makedirs(full_dir, exist_ok=True)
            logger.info(f"Writing file requested by {sender_id}: {abs_output_path}")

            # Write the file content
            with open(abs_output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"File written by {sender_id}: {abs_output_path}")

            # Store the absolute path if needed, keyed by task ID
            if task_id:
                # Store multiple saved files per task if necessary (e.g., using a list or dict)
                # For simplicity here, we'll just store the last saved path for the task
                self.saved_outputs[task_id] = abs_output_path

            # Return the *relative path* used, as agents work with relative paths
            # Reconstruct the sanitized relative path
            reconstructed_relative_path = "/".join(path_parts)

            return {
                'status': 'success',
                'result': f'File written: {safe_basename}',
                'filename': reconstructed_relative_path # Return the sanitized relative path
            }
        except SecurityException as se:
             logger.error(f"Security error writing file '{relative_filename}' for {sender_id}: {se}")
             return {'status': 'error', 'result': f"Security Error: {se}"}
        except Exception as e:
            logger.error(f"File write failed '{relative_filename}' for {sender_id}: {e}", exc_info=True)
            return {'status': 'error', 'result': f"Write error: {e}"}

        
    def _tool_file_read(self, agent_id: str, relative_filename: Optional[str]) -> Dict[str, Any]:
        """Handles the file_read tool execution with robust path handling."""
        if not relative_filename: return {'status': 'error', 'result': 'Missing filename.'}
        try:
            path_parts = [self._sanitize_filename(part) for part in relative_filename.replace("\\", "/").split('/') if part and part != '.']
            if not path_parts: raise ValueError("Invalid relative filename.")
            input_path = os.path.join(self.base_output_dir, *path_parts)
            if not os.path.abspath(input_path).startswith(os.path.abspath(self.base_output_dir)): raise SecurityException(f"Path traversal attempt: {input_path}")
            if not os.path.exists(input_path) or not os.path.isfile(input_path): logger.warning(f"File not found for read by {agent_id}: {input_path}"); return {'status': 'error', 'result': f'File not found: {relative_filename}'}
            logger.debug(f"Reading file: {input_path}")
            with open(input_path, 'r', encoding='utf-8') as f: content = f.read()
            logger.info(f"File read by {agent_id}: {input_path}")
            return { 'status': 'success', 'result': 'File read.', 'content': content, 'filename': relative_filename }
        except SecurityException as se: logger.error(f"Security error reading '{relative_filename}' for {agent_id}: {se}"); return {'status': 'error', 'result': f"Security error: {se}"}
        except Exception as e: logger.error(f"File read failed '{relative_filename}' for {agent_id}: {e}", exc_info=True); return {'status': 'error', 'result': f"Read error: {e}"}

    async def _tool_internet_search(self, query: Optional[str]) -> Dict[str, Any]:
        """Handles the internet_search tool execution."""
        if not query: return {'status': 'error', 'result': 'Missing query.'}
        logger.warning("Simulating internet search failure for query: %s", query)
        await asyncio.sleep(1.0)
        return { 'status': 'error', 'result': 'Internet search feature currently unavailable.' }

    # --- Simulation Lifecycle ---
    async def start_simulation(self, user_request: str):
        """Starts the simulation workflow."""
        logger.info(f"Starting simulation with request: '{user_request}'")
        self.current_iteration = 0; self.simulation_complete = False; self.simulation_success = None; self.tasks = {}; self.completed_task_ids = set(); self.saved_outputs = {} #[cite: uploaded:SoftwareSim3d/src/simulation/task.py]
        sanitized_req = self._sanitize_filename(user_request); self.project_name = "_".join(sanitized_req.split('_')[:5])[:40] if sanitized_req else "sim_project"; self.project_name = self.project_name or "sim_project"; logger.info(f"Derived project name: '{self.project_name}'")

        # Reset and start all agents
        for agent_id, agent in self.agents.items():
            agent.current_task = None; agent.task_context = {}; #[cite: uploaded:SoftwareSim3d/src/agent_base.py] #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
            agent.update_state({'status': 'idle', 'position': agent.initial_position, 'target_position': agent.target_desk_position, 'current_zone': None, 'target_zone': None, 'current_action': None, 'current_idle_sub_state': None, 'last_error': None, 'progress': 0.0}, trigger_callback=False) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
            if self.emit_agent_update: initial_state = agent.internal_state.copy(); initial_state['position'] = agent.initial_position; initial_state['role'] = agent.role; self.emit_agent_update(agent_id, initial_state) #[cite: uploaded:SoftwareSim3d/src/agent_base.py] #[cite: uploaded:SoftwareSim3d/src/agent_base.py] #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
            agent.start() #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
        await asyncio.sleep(0.1)

        # Send initial request to Messenger
        messenger = next((a for a in self.agents.values() if isinstance(a, MessengerAgent)), None) #[cite: uploaded:SoftwareSim3d/src/agents/messenger_agent.py]
        if messenger:
            initial_message = {'sender_id': 'user_interface', 'recipient_id': messenger.agent_id, 'content': {'type': 'user_request', 'request': user_request, 'project_name': self.project_name}}
            await self._route_message(initial_message); logger.info(f"Initial request sent to Messenger ({messenger.agent_id}).")
        else:
            logger.error("Cannot start simulation: Messenger agent not found."); self.simulation_complete = True; self.simulation_success = False; self.final_output = "Error: Messenger agent not found."
            if self.emit_final_output: self.emit_final_output(self.final_output, self.simulation_success); await self.stop_simulation(); return

        # Main Simulation Loop
        iteration_log_interval = 20
        while not self.simulation_complete and self.current_iteration < self.max_iterations:
            self.current_iteration += 1
            
            # Log agent and task status periodically
            if self.current_iteration % iteration_log_interval == 0:
                logger.info(f"Sim Iteration: {self.current_iteration}/{self.max_iterations}")
                
                # Log active tasks
                active_tasks = [t for t in self.tasks.values() if t.status not in ['completed', 'failed']]
                logger.info(f"Active tasks: {len(active_tasks)}")
                
                # Log agent statuses (helps debug stalls)
                for agent_id, agent in self.agents.items():
                    if agent_id.startswith(('html', 'css', 'js', 'coder')):  # Only log specialists and coder
                        status = agent.get_state('status')
                        action = agent.get_state('current_action')
                        task_id = agent.current_task.get('task_id') if agent.current_task else None
                        logger.info(f"Agent {agent_id}: Status={status}, Action={action}, Task={task_id}")
            
            await asyncio.sleep(0.5) # Check interval

        if not self.simulation_complete: logger.warning(f"Sim stopped: Max iterations ({self.max_iterations}) reached."); self.simulation_complete = True; self.simulation_success = False; self.final_output = f"Stopped after {self.max_iterations} iterations."
        if self.emit_final_output and self.final_output is not None: logger.info(f"Emitting final output. Success: {self.simulation_success}"); self.emit_final_output(self.final_output, self.simulation_success is True)
        logger.info(f"Simulation Logic Ended (Project: {self.project_name}). Cleaning up...")
        await self.stop_simulation()

    async def handle_user_response(self, originating_task_id: str, user_response: str):
        """Handles clarification responses from the user."""
        logger.info(f"Received user response for task {originating_task_id}: '{user_response[:50]}...'")
        messenger = next((a for a in self.agents.values() if isinstance(a, MessengerAgent)), None) #[cite: uploaded:SoftwareSim3d/src/agents/messenger_agent.py]
        if messenger:
             response_message = {'sender_id': 'user_interface', 'recipient_id': messenger.agent_id, 'content': {'type': 'user_clarification_response', 'originating_task_id': originating_task_id, 'response': user_response}}
             await self._route_message(response_message); logger.info(f"User response forwarded to Messenger ({messenger.agent_id}).")
             if originating_task_id and originating_task_id in self.tasks: task = self.tasks[originating_task_id]; task.update_status('in_progress'); logger.info(f"Task {originating_task_id} status updated to in_progress after user response."); #[cite: uploaded:SoftwareSim3d/src/simulation/task.py] #[cite: uploaded:SoftwareSim3d/src/simulation/task.py]
             if self.emit_task_update and originating_task_id in self.tasks: self.emit_task_update(originating_task_id, self.tasks[originating_task_id].to_dict()) #[cite: uploaded:SoftwareSim3d/src/simulation/task.py]
        else: logger.error("Cannot handle user response: Messenger agent not found.")

    async def stop_simulation(self):
        """Stops all agent tasks gracefully."""
        logger.info("Attempting to stop all agents...")
        for agent in self.agents.values():
             if hasattr(agent, 'stop'): agent.stop() #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
        await asyncio.sleep(0.5)
        join_tasks = [agent.join() for agent_id, agent in self.agents.items() if hasattr(agent, 'join') and agent._main_task_handle] #[cite: uploaded:SoftwareSim3d/src/agent_base.py] #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
        if join_tasks: logger.info(f"Waiting for {len(join_tasks)} agent tasks to join..."); results = await asyncio.gather(*join_tasks, return_exceptions=True); logger.info("Agent join procedures complete."); # Log results/errors if needed
        else: logger.info("No active agent tasks found to join.")

    def _sanitize_filename(self, name: str) -> str:
        """Removes or replaces characters unsafe for filenames/paths."""
        if not isinstance(name, str): name = "invalid_name"
        # Allow forward slash for directories, remove backslashes
        name = name.replace("\\", "/")
        # Remove other problematic characters for filenames/directory names
        name = re.sub(r'[<>:"|?*]+', '', name)
        # Replace whitespace sequences with a single underscore
        name = re.sub(r'\s+', '_', name)
        # Remove leading/trailing underscores/slashes after replacements
        name = name.strip('_/')
        # Limit total length if necessary (less critical for components, but good practice)
        # max_len = 100
        # if len(name) > max_len: name = name[:max_len]
        # Handle empty names after sanitization
        if not name: name = "sanitized_empty_name"
        # logger.debug(f"Sanitized path component: '{name}'") # Optional debug
        return name

# Custom exception for security checks
class SecurityException(Exception): pass