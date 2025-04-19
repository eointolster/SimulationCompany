# SoftwareSim3d/src/agent_base.py
# Create a 3 page website about Javascript with demos and explanations, make is beautiful and sohisticated
import abc
import asyncio
import logging
import random
import time # Using time for simple state delays initially
from typing import Optional, Dict, Any, Callable, Awaitable, Tuple, List, Set
import concurrent.futures # Added import for join fix

# Type hinting imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    # Ensure correct relative path if structure changes
    from .llm_integration.api_clients import LLMService #
    StateUpdateCallback = Callable[[str, Dict[str, Any]], None]

logger = logging.getLogger(__name__)

# Define standard agent states
STATUS_IDLE = 'idle'
STATUS_WORKING = 'working' # General task processing / LLM thinking
STATUS_MOVING_TO_ZONE = 'moving_to_zone' # Generic movement state
STATUS_USING_TOOL_IN_ZONE = 'using_tool_in_zone' # Actively using a tool at location
STATUS_WAITING_RESPONSE = 'waiting_response' # Waiting for another agent or user
STATUS_MEETING = 'meeting' # Could be CEO meeting or internal team meeting
STATUS_FAILED = 'failed'

# Extended idle states (optional visualization detail)
IDLE_AT_DESK = 'idle_at_desk'
IDLE_AT_WATER_COOLER = 'at_water_cooler'
IDLE_WANDERING = 'wandering'

# Default timeout for waiting on dependencies
DEFAULT_DEPENDENCY_TIMEOUT = 120.0 # seconds

class Agent(abc.ABC):
    def __init__(self,
                 agent_id: str,
                 role: str,
                 llm_service: Optional['LLMService'], #
                 llm_type: Optional[str],
                 llm_model_name: Optional[str],
                 message_queue: asyncio.Queue,
                 broadcast_callback: Callable[[Dict[str, Any]], Awaitable[None]],
                 loop: asyncio.AbstractEventLoop,
                 initial_position: Tuple[float, float, float],
                 target_desk_position: Tuple[float, float, float],
                 available_tools: Optional[Set[str]] = None,
                 required_tool_zones: Optional[Dict[str, str]] = None,
                 zone_coordinates_map: Optional[Dict[str, Tuple[float, float, float]]] = None,
                 **kwargs): # Accept remaining kwargs silently if needed
        self.agent_id = agent_id
        self.role = role
        self.llm_service = llm_service #
        self.llm_type = llm_type
        self.llm_model_name = llm_model_name
        self.message_queue = message_queue
        self.broadcast_callback = broadcast_callback
        self.loop = loop
        self.initial_position = initial_position
        self.target_desk_position = target_desk_position
        self.available_tools = available_tools if available_tools is not None else set()
        self.required_tool_zones = required_tool_zones if required_tool_zones is not None else {}
        # Store zone coordinates locally for quicker access
        self.zone_coordinates = zone_coordinates_map if zone_coordinates_map is not None else {}
        self.current_task: Optional[Dict[str, Any]] = None
        self.task_context: Dict[str, Any] = {}
        self.internal_state: Dict[str, Any] = {
            'status': STATUS_IDLE, 'progress': 0.0, 'last_error': None,
            'current_action': None, 'current_thoughts': 'Initializing...',
            'current_zone': None, 'target_zone': None, 'target_position': target_desk_position,
            'state_timer': 0.0, 'current_idle_sub_state': None,
             'position': initial_position # Ensure position is part of initial state
        }
        self.state_update_callback: Optional['StateUpdateCallback'] = None
        self._is_running = True
        self._main_task_handle: Optional[asyncio.Future] = None # Use Future for threadsafe tasks

        llm_info_str = f"LLM: {self.llm_type} ({self.llm_model_name or 'default'})" if self.llm_service and self.llm_type else "No LLM assigned"
        logger.info(f"Agent {self.agent_id} ({self.role}) initialized. {llm_info_str}. Tools: {self.available_tools}. Desk: {self.target_desk_position}")

    def register_state_update_callback(self, callback: 'StateUpdateCallback'):
        self.state_update_callback = callback

    @abc.abstractmethod
    def get_prompt(self, task_details: Dict[str, Any], context: Dict[str, Any]) -> Optional[str]: pass

    @abc.abstractmethod
    async def _decide_next_action(self) -> Optional[Dict[str, Any]]: pass

    @abc.abstractmethod
    async def _process_llm_response(self, llm_response: str): pass

    @abc.abstractmethod
    async def _process_tool_result(self, tool_name: str, result: Any): pass

    # --- State Management ---
    def update_state(self, updates: Dict[str, Any], trigger_callback: bool = True):
        state_changed = False
        for key, value in updates.items():
            if self.internal_state.get(key) != value:
                self.internal_state[key] = value
                state_changed = True
        if 'status' in updates: self._update_thoughts_on_status_change(updates['status'])
        if state_changed and trigger_callback and self.state_update_callback:
            current_state_copy = self.internal_state.copy()
            if 'target_position' not in current_state_copy: current_state_copy['target_position'] = self.get_state('target_position', self.target_desk_position)
            # Ensure position is always included
            if 'position' not in current_state_copy: current_state_copy['position'] = self.get_state('position', self.initial_position)
            try: self.state_update_callback(self.agent_id, current_state_copy)
            except Exception as e: logger.error(f"Error calling state_update_callback for agent {self.agent_id}: {e}")

    def get_state(self, key: str, default: Any = None) -> Any: return self.internal_state.get(key, default)
    def get_thoughts(self) -> str: return self.get_state('current_thoughts', "No thoughts available.")

    def _update_thoughts_on_status_change(self, new_status: str):
        """ Auto-update thoughts based on primary status. """
        task_desc = self.current_task.get('description', '...') if self.current_task else '...'
        last_error_state = self.get_state('last_error')
        error_text = str(last_error_state) if last_error_state is not None else '...'
        safe_error_snippet = error_text[:50] + ('...' if len(error_text) > 50 else '')

        thought_map = {
            STATUS_IDLE: f"{self.role} ({self.agent_id}) is now idle.",
            STATUS_WORKING: f"{self.role} ({self.agent_id}) is working on: {task_desc[:40]}{'...' if len(task_desc)>40 else ''}.",
            STATUS_MOVING_TO_ZONE: f"{self.role} ({self.agent_id}) is heading to {self.get_state('target_zone', 'destination')}.",
            STATUS_USING_TOOL_IN_ZONE: f"{self.role} ({self.agent_id}) is using {self.get_state('current_action','tool')} at {self.get_state('current_zone','zone')}.",
            STATUS_WAITING_RESPONSE: f"{self.role} ({self.agent_id}) is waiting for a response.",
            STATUS_MEETING: f"{self.role} ({self.agent_id}) is in a meeting.",
            STATUS_FAILED: f"{self.role} ({self.agent_id}) encountered an error: {safe_error_snippet}",
        }
        idle_sub_state = self.get_state('current_idle_sub_state')
        if new_status == STATUS_IDLE:
             if idle_sub_state == IDLE_AT_WATER_COOLER: thoughts = f"{self.role} ({self.agent_id}) is at the water cooler."
             elif idle_sub_state == IDLE_WANDERING: thoughts = f"{self.role} ({self.agent_id}) is wandering near their desk."
             else: thoughts = f"{self.role} ({self.agent_id}) is thinking at their desk." # Default idle thought
        else: thoughts = thought_map.get(new_status, f"{self.role} ({self.agent_id}) is now {new_status}.")
        if self.internal_state.get('current_thoughts') != thoughts: self.internal_state['current_thoughts'] = thoughts


    async def assign_task(self, task: Dict[str, Any]):
        """Assigns a new task and updates agent status."""
        task_id = task.get('task_id', 'N/A') # Get task_id early for context access

        # --- ADDED LOGGING: Log the entire received task ---
        logger.info(f"Agent {self.agent_id} received raw task data for task_id {task_id}: {task}")
        # --- END ADDED LOGGING ---

        # Check if already processing the same task_id
        if self.current_task and self.current_task.get('task_id') == task_id:
            logger.warning(f"Agent {self.agent_id} re-assigned same task {task_id}. Ignoring.")
            return

        if self.get_state('status') != STATUS_IDLE:
            logger.warning(f"Agent {self.agent_id} received task {task_id} while status is '{self.get_state('status')}'. Overwriting current task.")
            # If overwriting, maybe cleanup old task context?
            if self.current_task:
                 old_task_id = self.current_task.get('task_id')
                 if old_task_id and old_task_id != task_id and old_task_id in self.task_context:
                      logger.info(f"Cleaning up context for overwritten task {old_task_id}")
                      del self.task_context[old_task_id]


        # --- Assign Task ---
        self.current_task = task # Assign the new task dict
        logger.info(f"Agent {self.agent_id} assigned Task: {task_id} - {task.get('description','No Description')}")

        # --- MODIFIED: Ensure context exists and store FULL details ---
        context = self.task_context.setdefault(task_id, {})
        task_details = task.get('details', {}) # Get the details dict from incoming task data

        # *** Log details dictionary ***
        logger.info(f"Agent {self.agent_id} task {task_id} received details: {task_details}")

        # *** Store the entire details dictionary in the context ***
        context['details'] = task_details
        # Also store original_request directly for convenience if needed elsewhere
        context['original_request'] = task_details.get('original_request')

        # *** Log confirmation ***
        logger.debug(f"Task {task_id} context for Agent {self.agent_id} UPDATED with details: {context.get('details')}")
        # --- END MODIFICATION ---

        # Update agent state to start working on the new task
        self.update_state({
            'status': STATUS_WORKING, 'progress': 0.0, 'last_error': None,
            'current_action': 'starting_task', 'current_idle_sub_state': None,
            'state_timer': 0.0, 'wait_start_time': None # Reset wait timer
        })

    async def _execute_llm_task(self, prompt: str) -> Optional[str]:
        """Helper to call LLM service, returns response or None on error."""
        if not prompt: logger.error(f"Agent {self.agent_id} ({self.role}): LLM task called with empty prompt."); self.update_state({'last_error': 'LLM called with empty prompt.'}); return None
        if not self.llm_service or not self.llm_type: logger.error(f"Agent {self.agent_id} ({self.role}): LLM service or type not available."); self.update_state({'last_error': 'LLM service unavailable.'}); return None
        self.update_state({ 'current_thoughts': f"Consulting LLM ({self.llm_type})...", 'current_action': 'executing_llm' })
        llm_result = await self.llm_service.generate( llm_type=self.llm_type, prompt=prompt, model_name=self.llm_model_name ) #
        if llm_result is None or llm_result.startswith("Error:"):
             error_msg = f"LLM call failed for agent {self.agent_id}: {llm_result or 'No response'}"; logger.error(error_msg)
             self.update_state({ 'current_thoughts': error_msg, 'last_error': error_msg, 'current_action': 'processed_llm_response' })
             if self.current_task: self.task_context[self.current_task.get('task_id')]['llm_result_type'] = 'error' # Mark error type in context
             return None
        else:
            self.update_state({ 'current_thoughts': "Received LLM response.", 'current_action': 'processing_llm_response' });
            return llm_result



    async def _execute_tool(self, tool_name: str, params: Dict[str, Any]) -> bool:
        """
        Enhanced tool execution with strict zone enforcement and auto–move.
        Returns True if the request is sent successfully; otherwise, handles errors or movement as needed.
        """
        # Check if the requested tool is available.
        if tool_name not in self.available_tools:
            logger.error(f"Agent {self.agent_id} attempted to use unavailable tool: {tool_name}")
            self.update_state({'last_error': f'Tool {tool_name} not available.'})
            return False

        # Enforce that the tool can only be used in its required zone.
        required_zone = self.required_tool_zones.get(tool_name)
        current_zone = self.get_state('current_zone')
        if required_zone and current_zone != required_zone:
            logger.warning(f"Agent {self.agent_id} is not in the required zone '{required_zone}' for tool '{tool_name}'. Current zone: {current_zone or 'None'}.")
            self.update_state({'last_error': f"Cannot use {tool_name} outside zone {required_zone}."})
            # Attempt to auto–move to the correct zone if possible.
            zone_coords_to_move = self.zone_coordinates.get(required_zone) if self.zone_coordinates else None
            if zone_coords_to_move:
                logger.info(f"Agent {self.agent_id} auto–moving to zone '{required_zone}' to use tool '{tool_name}'.")
                await self._move_to_zone(required_zone, zone_coords_to_move)
            else:
                logger.error(f"Agent {self.agent_id} cannot auto–move because coordinates for '{required_zone}' are missing.")
                await self._fail_current_task(f"Missing coordinates for zone {required_zone} for tool {tool_name}.")
            return False

        # If in the correct zone (or no zone is required), proceed.
        logger.info(f"Agent {self.agent_id} is using tool '{tool_name}' in zone '{current_zone or 'current location'}'.")
        self.update_state({
            'status': STATUS_WORKING,
            'current_action': f'using_{tool_name}',
            'current_thoughts': f"Executing tool {tool_name}..."
        })

        message_content = {
            'type': 'request_tool_use',
            'tool_name': tool_name,
            'parameters': params,
            'task_id': self.current_task.get('task_id') if self.current_task else None
        }
        try:
            await self._send_message_to_manager(message_content)
            return True
        except Exception as e:
            error_msg = f"Error sending tool request for {tool_name}: {e}"
            logger.error(f"Agent {self.agent_id}: {error_msg}", exc_info=True)
            self.update_state({'last_error': error_msg, 'status': STATUS_FAILED})
            return False


    async def _move_to_zone(self, zone_name: str, target_position: Tuple[float, float, float]):
         """Initiates movement towards a specified zone. Target position MUST be provided."""
         if not target_position: logger.error(f"Agent {self.agent_id} cannot move to zone {zone_name}: Target position unknown."); await self._fail_current_task(f"Unknown coordinates for zone {zone_name}"); return

         # Ensure current position is available in state
         current_position = self.get_state('position', self.initial_position)
         if not current_position:
              logger.error(f"Agent {self.agent_id} cannot determine current position to start move to {zone_name}.")
              await self._fail_current_task(f"Cannot determine current position for move.")
              return

         # Check if already at or very close to target
         if abs(current_position[0] - target_position[0]) < 0.1 and \
            abs(current_position[1] - target_position[1]) < 0.1 and \
            abs(current_position[2] - target_position[2]) < 0.1:
              logger.debug(f"Agent {self.agent_id} already at or near target {zone_name}. Skipping move.")
              # If skipping move, ensure state reflects being in the zone
              if self.get_state('current_zone') != zone_name:
                   self.update_state({
                       'status': STATUS_WORKING, # Or IDLE if no task? Assume WORKING for now.
                       'current_zone': zone_name,
                       'target_zone': None,
                       'position': target_position, # Ensure position is accurate
                       'current_action': 'already_at_zone'
                   })
                   # Manually trigger arrival handling if needed by subclass logic
                   await self._handle_arrival(zone_name)
              return # Don't proceed with move logic

         # Initiate the move if not already there
         logger.info(f"Agent {self.agent_id} starting move to zone: {zone_name} at {target_position}")
         self.update_state({
             'status': STATUS_MOVING_TO_ZONE,
             'target_zone': zone_name,
             'target_position': target_position,
             'current_zone': None, # Clear current zone when moving
             'current_action': f'moving_to_{zone_name.lower().replace(" ","_")}',
             'current_thoughts': f"Heading to {zone_name}."
         })
         # WorkflowManager listens for the state change and handles the timer/arrival message

    # --- Communication ---
    async def _send_message_to_manager(self, message_content: Dict[str, Any]):
        message = { 'sender_id': self.agent_id, 'recipient_id': 'workflow_manager', 'content': message_content }
        try: await self.broadcast_callback(message); logger.debug(f"Agent {self.agent_id} sent message to manager: Type {message_content.get('type', 'N/A')}")
        except Exception as e: logger.error(f"Agent {self.agent_id} failed to send message to manager: {e}", exc_info=True); raise

    async def _send_message_to_agent(self, target_agent_id: str, message_content: Dict[str, Any]):
        message = { 'sender_id': self.agent_id, 'recipient_id': target_agent_id, 'content': message_content }
        try: await self.broadcast_callback(message); logger.debug(f"Agent {self.agent_id} sent message to agent {target_agent_id}: Type {message_content.get('type', 'N/A')}")
        except Exception as e: logger.error(f"Agent {self.agent_id} failed to send message to agent {target_agent_id}: {e}", exc_info=True); raise

    # async def _handle_message(self, message: Dict[str, Any]):
    #     """Processes an incoming message from the agent's queue."""
    #     sender_id = message.get('sender_id', 'Unknown')
    #     content = message.get('content', {})
    #     message_type = content.get('type', 'unknown')

    #     # --- ADD THIS NEW DEBUG LOG ---
    #     logger.info(f"BASE HANDLER ({self.agent_id}): Extracted message_type='{message_type}' (type: {type(message_type)}) from sender {sender_id}")
    #     # --- END NEW DEBUG LOG ---

    #     logger.debug(f"Agent {self.agent_id} received message type '{message_type}' from {sender_id}") # Existing debug

    #     if message_type == 'new_task':
    #         await self.assign_task(content.get('task_data', {}))
    #     elif message_type == 'tool_result':
    #         # ... (rest of the function remains the same) ...
    #         tool_name = content.get('tool_name'); result_dict = content
    #         self.update_state({'status': STATUS_WORKING, 'current_action': f'processing_{tool_name}_result'})
    #         await self._process_tool_result(tool_name, result_dict)
    #     elif message_type == 'arrived_at_zone':
    #         zone_name = content.get('zone_name')
    #         logger.info(f"Agent {self.agent_id} officially arrived at zone: {zone_name}")
    #         self.update_state({ 'current_zone': zone_name, 'status': STATUS_WORKING, 'target_zone': None, 'current_action': 'arrived' })
    #         await self._handle_arrival(zone_name)
    #     elif message_type == 'agent_message':
    #         logger.info(f"DEBUG BASE HANDLER ({self.agent_id} - {self.role}): Calling _handle_agent_specific_message for message from {sender_id}. Self type: {type(self)}")
    #         await self._handle_agent_specific_message(sender_id, content.get('message_data'))
    #     elif message_type == 'stop_agent':
    #         logger.info(f"Agent {self.agent_id} received stop signal."); self.stop()
    #     else:
    #         await self._handle_subclass_message(message_type, content, sender_id)

    async def _handle_message(self, message: Dict[str, Any]):
        """Processes an incoming message from the agent's queue, routing appropriately."""
        sender_id = message.get('sender_id', 'Unknown')
        content = message.get('content', {})
        
        # --- Integrated Routing Logic ---
        # Check if the message is from another agent first
        is_from_another_agent = sender_id != 'workflow_manager' and sender_id != 'user_interface'
        
        # Extract inner type (primarily for manager messages or logging)
        inner_message_type = content.get('type', 'unknown')
        
        logger.info(f"BASE HANDLER ({self.agent_id}): Received message from {sender_id}. IsAgentMsg={is_from_another_agent}. InnerType='{inner_message_type}'")

        try:
            if is_from_another_agent:
                # Route direct agent-to-agent messages to the specific handler
                # Pass the entire 'content' dict as message_data
                logger.info(f"DEBUG BASE HANDLER ({self.agent_id} - {self.role}): Routing direct message from {sender_id} to _handle_agent_specific_message.")
                await self._handle_agent_specific_message(sender_id, content)
                
            # Handle messages FROM Workflow Manager or UI based on INNER type
            elif inner_message_type == 'new_task':
                await self.assign_task(content.get('task_data', {}))
            elif inner_message_type == 'tool_result':
                tool_name = content.get('tool_name'); result_dict = content # Pass the whole content as result_dict
                self.update_state({'status': STATUS_WORKING, 'current_action': f'processing_{tool_name}_result'})
                await self._process_tool_result(tool_name, result_dict)
            elif inner_message_type == 'arrived_at_zone':
                zone_name = content.get('zone_name')
                logger.info(f"Agent {self.agent_id} officially arrived at zone: {zone_name}")
                # Update state *before* calling arrival handler
                self.update_state({ 'current_zone': zone_name, 'status': STATUS_WORKING, 'target_zone': None, 'current_action': 'arrived' })
                await self._handle_arrival(zone_name) # Use the arrival helper method
            elif inner_message_type == 'stop_agent':
                logger.info(f"Agent {self.agent_id} received stop signal."); self.stop()
                
            # Handle other specific manager/system message types if needed
            # elif inner_message_type == 'some_other_manager_type':
            #     # Handle it
            #     pass
                
            else:
                # If it wasn't from another agent and wasn't a known manager type,
                # treat it as a potential subclass message or log as unhandled.
                # This replaces the previous _handle_subclass_message placeholder call.
                logger.warning(f"Agent {self.agent_id} received unhandled message type '{inner_message_type}' from sender '{sender_id}'. Content: {content}")
                # Optionally, add specific handling for types expected by subclasses here,
                # or rely on _handle_agent_specific_message for all inter-agent comms.

        except Exception as e:
            # Catch errors during message handling itself
            logger.error(f"Agent {self.agent_id} error directly within _handle_message (Type: {inner_message_type}): {e}", exc_info=True)
            # Fail the current task if an error occurs during handling
            await self._fail_current_task(f"Error handling message type {inner_message_type}: {e}")



    # --- Added _handle_arrival ---
    async def _handle_arrival(self, zone: str):
        """Placeholder for subclasses to implement logic upon arriving at a zone."""
        logger.debug(f"Agent {self.agent_id} base _handle_arrival called for zone: {zone}. Subclass should implement specifics.")
        # Default: Ensure agent isn't stuck in moving state if subclass doesn't override fully
        if self.get_state('status') == STATUS_MOVING_TO_ZONE:
             self.update_state({'status': STATUS_WORKING, 'current_action': 'arrived_idle'})

    async def _handle_agent_specific_message(self, sender_id: str, message_data: Any):
         """Placeholder for subclasses to handle direct messages from other agents."""
         logger.warning(f"Agent {self.agent_id} received unhandled agent message from {sender_id}: Type {message_data.get('type') if isinstance(message_data, dict) else 'Unknown'}")

    async def _handle_subclass_message(self, message_type: str, content: Dict[str, Any], sender_id: str):
         """Placeholder for subclasses to potentially handle more manager message types."""
         logger.warning(f"Agent {self.agent_id} received unhandled message type: {message_type} from {sender_id}")

    async def run(self):
        """The main execution loop for the agent."""
        logger.info(f"{self.agent_id} ({self.role}) starting run loop.")
        last_state_time = self.loop.time()

        while self._is_running:
            current_time = self.loop.time(); delta_time = current_time - last_state_time; last_state_time = current_time

            # Process Incoming Messages
            message_processed_this_cycle = False
            try:
                message = self.message_queue.get_nowait() # Use get_nowait for non-blocking check
                if message:
                    await self._handle_message(message); self.message_queue.task_done()
                    message_processed_this_cycle = True
            except asyncio.QueueEmpty: pass # No message is normal
            except asyncio.CancelledError: logger.info(f"{self.agent_id} run loop task cancelled."); break
            except Exception as e: logger.error(f"Agent {self.agent_id} error handling message: {e}", exc_info=True); await self._fail_current_task(f"Error handling message: {e}")

            # Core Decision Logic - Only if not currently moving or actively using a tool waiting for result
            current_status = self.get_state('status')
            # Decide if agent is in a state where it should make a decision
            # It should decide if IDLE, or WORKING *unless* it just executed something and is waiting
            # Avoid deciding immediately after sending a tool request or LLM call
            is_waiting_for_response = self.get_state('current_action') in ['executing_llm', f'ready_to_use_{self.get_state("last_tool_used")}'] # Example check

            if current_status in [STATUS_IDLE, STATUS_WORKING] and not is_waiting_for_response:
                 try:
                    # logger.debug(f"{self.agent_id} calling _decide_next_action... (Status: {current_status}, Action: {self.get_state('current_action')})")
                    action_decision = await self._decide_next_action()
                    # Execute action immediately if decided
                    await self.execute_action(action_decision) # Renamed from _execute_action for clarity
                 except Exception as e: logger.error(f"Agent {self.agent_id} error in decision/action execution: {e}", exc_info=True); await self._fail_current_task(f"Error in decision logic: {e}")
            # --- Idle Action Trigger ---
            elif current_status == STATUS_IDLE and not self.get_state('current_idle_sub_state'): # removed state_timer check
                 if random.random() < 0.01: await self._perform_idle_action()

            await asyncio.sleep(0.1) # Main loop sleep
        logger.info(f"{self.agent_id} ({self.role}) run loop stopped.")

    async def execute_action(self, action: Optional[Dict[str, Any]]): # Renamed from _execute_action
        """ Executes the action decided by _decide_next_action """
        if not action or not action.get('action'): return
        action_type = action.get('action');
        if action_type != 'wait': logger.info(f"Agent {self.agent_id} executing action: {action_type}")

        try:
            if action_type == 'use_llm':
                prompt = action.get('prompt')
                # Update state *before* calling LLM
                self.update_state({'current_action': 'executing_llm'})
                llm_response = await self._execute_llm_task(prompt)
                if llm_response is not None:
                     # Update state *before* processing response
                     self.update_state({'current_action': 'processing_llm_response'})
                     await self._process_llm_response(llm_response)
                # Error state updated within _execute_llm_task if it fails
            elif action_type == 'use_tool':
                tool_name = action.get('tool_name'); params = action.get('params', {})
                self.update_state({'last_tool_used': tool_name}) # Store last tool for wait check
                await self._execute_tool(tool_name, params) # Sends request, waits for result message via queue
            elif action_type == 'move_to_zone':
                zone_name = action.get('zone_name')
                # Use the agent's own method to get coordinates
                zone_coords = None
                if hasattr(self, 'get_zone_position'): zone_coords = self.get_zone_position(zone_name)
                elif hasattr(self, 'zone_coordinates'): zone_coords = self.zone_coordinates.get(zone_name) # Fallback
                if zone_coords: await self._move_to_zone(zone_name, zone_coords)
                else: await self._fail_current_task(f"Could not find coordinates for zone {zone_name}")
            elif action_type == 'send_message_to_agent':
                target_id = action.get('target_agent_id'); msg_data = action.get('message_data')
                if target_id and msg_data:
                    await self._send_message_to_agent(target_id, msg_data)
                    self.update_state({'current_action': 'message_sent'})
                else: await self._fail_current_task("Missing target agent ID or message data for sending.")
            elif action_type == 'complete_task': await self._complete_current_task(action.get('result'))
            elif action_type == 'fail_task': await self._fail_current_task(action.get('error', 'Unknown error'))
            elif action_type == 'wait':
                 # Only log wait if it's a new decision, not just default state
                 if self.get_state('current_action') != 'waiting':
                      logger.debug(f"Agent {self.agent_id} decided to wait (Reason: {action.get('reason','None')}).")
                 self.update_state({'current_action': 'waiting'})
            else: logger.warning(f"Agent {self.agent_id} decided unknown action: {action_type}"); self.update_state({'current_action': f'unknown_{action_type}'})
        except Exception as e: logger.error(f"Agent {self.agent_id} failed during action execution ({action_type}): {e}", exc_info=True); await self._fail_current_task(f"Error executing action {action_type}: {e}")

    async def _fail_current_task(self, error_message: str):
        """Marks the current task as failed and notifies manager."""
        task_id = self.current_task.get('task_id', 'N/A') if self.current_task else 'N/A'
        if task_id != 'N/A':
            logger.error(f"Agent {self.agent_id} failing Task: {task_id} - Error: {error_message}")
            failure_message = { 'type': 'task_completion_update', 'task_id': task_id, 'status': STATUS_FAILED, 'result': error_message }
            try: await self._send_message_to_manager(failure_message)
            except Exception as send_e: logger.error(f"Failed to send failure notification for task {task_id}: {send_e}")
        else: logger.warning(f"Agent {self.agent_id} tried to fail task but has no current task ID. Error: {error_message}")
        self.current_task = None; # Clear task context? Maybe keep for debugging? self.task_context = {}
        self.update_state({ 'status': STATUS_IDLE, 'last_error': error_message, 'current_thoughts': f"Task failed: {error_message}", 'current_action': None, 'progress': 0.0 })

    async def _complete_current_task(self, result: Any):
        """Marks the current task as complete and notifies manager."""
        task_id = self.current_task.get('task_id', 'N/A') if self.current_task else 'N/A'
        if task_id != 'N/A':
            logger.info(f"Agent {self.agent_id} completing Task: {task_id}")
            completion_message = { 'type': 'task_completion_update', 'task_id': task_id, 'status': 'completed', 'result': result }
            try: await self._send_message_to_manager(completion_message)
            except Exception as send_e: logger.error(f"Failed to send completion notification for task {task_id}: {send_e}")
        else: logger.warning(f"Agent {self.agent_id} tried to complete task but has no current task ID.")
        self.current_task = None; # Clear task context? self.task_context = {}
        self.update_state({ 'status': STATUS_IDLE, 'progress': 1.0, 'current_thoughts': f"Task completed.", 'current_action': None, })

    async def _ask_user_for_input(self, question: str):
         """ Sends request for user input via WorkflowManager -> UI """
         if not self.current_task: logger.error("Agent tried to ask user input without an active task."); return
         task_id = self.current_task.get('task_id'); logger.info(f"Agent {self.agent_id} requesting user input for task {task_id}: {question}"); self.update_state({'status': STATUS_WAITING_RESPONSE, 'current_action': 'waiting_user'})
         message = { 'type': 'ui_request_user_input', 'question': question, 'originating_task_id': task_id }
         await self._send_message_to_manager(message)

    async def _perform_idle_action(self):
        """Chooses and initiates a random idle action."""
        if self.get_state('status') != STATUS_IDLE or self.get_state('current_idle_sub_state'): return
        possible_actions = [IDLE_AT_WATER_COOLER, IDLE_WANDERING, IDLE_AT_DESK]
        chosen_action = random.choice(possible_actions); action_duration = random.uniform(3.0, 8.0)
        logger.info(f"Agent {self.agent_id} starting idle action: {chosen_action} for {action_duration:.1f}s");
        # Update state *before* move, timer handled by external logic or simply visual
        self.update_state({'current_idle_sub_state': chosen_action})
        if chosen_action == IDLE_AT_WATER_COOLER:
            # Use standard move action
            await self.execute_action({'action': 'move_to_zone', 'zone_name': 'WATER_COOLER_ZONE'})
        # No explicit timer state needed if idle state implies temporary pause

    # --- Lifecycle ---
    def start(self):
        if not self._main_task_handle or self._main_task_handle.done():
            self._is_running = True
            async def run_wrapper(): await self.run()
            self._main_task_handle = asyncio.run_coroutine_threadsafe(run_wrapper(), self.loop)
            logger.info(f"Agent {self.agent_id} main loop start requested.")
        else: logger.warning(f"Agent {self.agent_id} start called but agent is already running.")

    def stop(self):
        self._is_running = False
        if self._main_task_handle and not self._main_task_handle.done():
             try: self.loop.call_soon_threadsafe(self._main_task_handle.cancel)
             except Exception as e: logger.error(f"Error trying to cancel task future for agent {self.agent_id}: {e}")

    async def join(self):
        """Waits for the agent's main task (Future) to complete."""
        if self._main_task_handle and isinstance(self._main_task_handle, concurrent.futures.Future):
             future = self._main_task_handle; logger.debug(f"Agent {self.agent_id} attempting join via Future.result()...")
             try:
                  # Use run_in_executor for compatibility if loop is different thread
                  await asyncio.wait_for(self.loop.run_in_executor(None, future.result), timeout=7.0)
                  logger.info(f"Agent {self.agent_id} main task joined successfully.")
             except asyncio.CancelledError: logger.info(f"Agent {self.agent_id}'s main task was cancelled.")
             except asyncio.TimeoutError: logger.warning(f"Agent {self.agent_id} main task join timed out after 7s.")
             except concurrent.futures.TimeoutError: logger.warning(f"Agent {self.agent_id} main task join timed out (concurrent).") # If future.result times out internally
             except Exception as e: logger.error(f"Agent {self.agent_id} join encountered exception: {e}", exc_info=False)
        else: logger.debug(f"Agent {self.agent_id} join called but no valid task handle.")