# SoftwareSim3d/src/agents/ceo_agent.py

import json
import logging
import re
import asyncio
from typing import Dict, Any, Optional, List, Callable, Awaitable, Tuple, Set

# Assuming Agent, Task are correctly imported from project structure
from ..agent_base import Agent #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
from ..simulation.task import Task #[cite: uploaded:SoftwareSim3d/src/simulation/task.py]

# Assuming WorkflowManager is accessible for agent lookup
# from ..simulation.workflow_manager import WorkflowManager # Import if type hinting needed

logger = logging.getLogger(__name__)

# Define status strings directly (as per task.py)
STATUS_PENDING = 'pending'
STATUS_COMPLETED = 'completed'
STATUS_FAILED = 'failed'
# Add other statuses as needed


class CEOAgent(Agent): # Inherit from Agent
    """
    The CEO agent manages the overall project, decomposes high-level requests,
    delegates tasks to team leads via the WorkflowManager, and performs final evaluation.
    """

    def __init__(self,
                 agent_id: str,
                 role: str, # Accept role POSITIONAL
                 message_queue: asyncio.Queue,
                 broadcast_callback: Callable[[Dict[str, Any]], Awaitable[None]],
                 loop: asyncio.AbstractEventLoop,
                 initial_position: Tuple[float, float, float],
                 target_desk_position: Tuple[float, float, float],
                 # Specific CEO args (passed via kwargs from WorkflowManager)
                 manager_ids: Dict[str, str],
                 messenger_id: str,
                 # Accept other args via kwargs
                 **kwargs):

        # --- REVISED super().__init__ CALL ---
        # Pass base positional args directly.
        # Pass ALL other args needed by base class via **kwargs.
        # DO NOT pass args like llm_service explicitly if they are in kwargs.
        super().__init__(
            agent_id=agent_id,
            role=role,
            message_queue=message_queue,
            broadcast_callback=broadcast_callback,
            loop=loop,
            initial_position=initial_position,
            target_desk_position=target_desk_position,
            # --- REMOVED explicit kwargs like llm_service, llm_type, tools etc. ---
            # --- Rely solely on **kwargs to pass them to the base __init__ ---
            **kwargs # Pass all remaining keyword arguments
        )
        # --- END REVISION ---

        # Store CEO-specific attributes (received positionally or via kwargs)
        # Ensure manager_ids and messenger_id are retrieved correctly based on how
        # WorkflowManager passes them (currently assumes they are in kwargs)
        self.manager_ids = manager_ids # Assuming passed correctly in kwargs
        self.messenger_id = messenger_id # Assuming passed correctly in kwargs
        self.project_name: Optional[str] = None
        self.original_request: Optional[str] = None
        # task_context is initialized in the base class

        logger.info(f"CEOAgent {self.agent_id} initialized. Managers: {list(self.manager_ids.keys())}, Messenger: {self.messenger_id}")


    # --- Context Management ---
    def _cleanup_task_context(self):
        """Removes the context for the current task ID if it exists."""
        if self.current_task and self.current_task.get('task_id') in self.task_context:
            task_id = self.current_task['task_id']
            del self.task_context[task_id]
            logger.debug(f"{self.agent_id}: Cleaned up context for task {task_id}.")

    # --- Message Handling ---
    async def _handle_message(self, message: Dict[str, Any]):
        """Processes an incoming message from the agent's queue."""
        sender_id = message.get('sender_id', 'Unknown')
        content = message.get('content', {})
        message_type = content.get('type', 'unknown')
        logger.debug(f"CEO {self.agent_id} received message type '{message_type}' from {sender_id}")

        if message_type == 'new_task':
            await self.assign_task(content.get('task_data', {})) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
        elif message_type == 'agent_message':
            await self._handle_agent_specific_message(sender_id, content.get('message_data'))
        else:
            # Let base class handle tool_result, arrived_at_zone, stop_agent, etc.
            await super()._handle_message(message) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]

    async def _handle_agent_specific_message(self, sender_id: Optional[str], message_data: Dict[str, Any]):
        """Processes messages received directly from other agents (e.g., via Messenger)."""
        data_type = message_data.get('type')
        logger.info(f"CEO {self.agent_id}: Received agent message from {sender_id or 'Unknown'} of type {data_type}.")

        if data_type == 'user_request':
            await self._handle_user_request_from_messenger(message_data)
        elif data_type == 'qa_approved':
            await self._handle_qa_approval(sender_id, message_data)
        else:
            logger.warning(f"CEO {self.agent_id}: Received unhandled agent message type: {data_type} from {sender_id}")

    async def _handle_user_request_from_messenger(self, message_data: Dict[str, Any]):
        """Processes an incoming user request relayed by the messenger."""
        self.project_name = message_data.get('project_name', f'Project_{self._generate_id(4)}')
        self.original_request = message_data.get('request')
        task_id = f"task_decomp_{self.agent_id}_{message_data.get('request_id', self._generate_id(4))}"

        if not self.original_request:
            logger.error(f"CEO {self.agent_id}: Received user request message via Messenger without 'request' data.")
            return

        logger.info(f"CEO {self.agent_id}: Received user request for project '{self.project_name}': '{self.original_request[:50]}...'")
        self.update_state({'current_action': 'received_request', 'project_name': self.project_name}) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]

        initial_task_details = {
             'original_request': self.original_request,
             'project_name': self.project_name
        }
        await self.assign_task({ #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
             'task_id': task_id,
             'description': f"Decompose user request: {self.original_request}",
             'task_type': 'decompose_request',
             'details': initial_task_details
        })
        logger.debug(f"CEO {self.agent_id}: Assigned initial decomposition task {task_id} to self.")


    async def _handle_qa_approval(self, sender_id: Optional[str], message_data: Dict[str, Any]):
         """Processes QA approval message."""
         original_code_task_id = message_data.get('original_code_task_id', 'Unknown Original Task')
         project_name_for_task = message_data.get('project_name', self.project_name or 'Unknown Project')
         approved_filename = message_data.get('filename')

         logger.info(f"CEO {self.agent_id}: Received QA approval from {sender_id} regarding original coder task {original_code_task_id}. Project '{project_name_for_task}' considered complete.")

         final_approval_task_id = f"final_approval_{original_code_task_id}"
         task_details = {
             'original_task_id': original_code_task_id,
             'project_name': project_name_for_task,
             'approved_filename': approved_filename,
             'qa_approval_received': True
         }
         await self.assign_task({ #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
             'task_id': final_approval_task_id,
             'description': f"Final approval and notification for project '{project_name_for_task}' based on QA result.",
             'task_type': 'notify_completion',
             'details': task_details
         })
         logger.debug(f"CEO {self.agent_id}: Assigned final approval task {final_approval_task_id} to self.")

    # --- Action Decision Logic ---
    async def _decide_next_action(self) -> Optional[Dict[str, Any]]:
        """Determines the next logical step based on task type and context step."""
        if not self.current_task:
            return {'action': 'wait'} #[cite: uploaded:SoftwareSim3d/src/agent_base.py]

        task = self.current_task
        task_id = task.get('task_id')
        if not task_id:
             logger.error(f"CEO {self.agent_id}: Current task has no ID. Cannot proceed.")
             self.current_task = None
             return {'action': 'wait'} #[cite: uploaded:SoftwareSim3d/src/agent_base.py]

        if task_id not in self.task_context:
             self.task_context[task_id] = {'step': 'start'}
        context = self.task_context[task_id]

        task_type = task.get('task_type')
        step = context.get('step', 'start')
        logger.debug(f"CEO {self.agent_id}: Deciding action for task {task_id} (Type: {task_type}) at step '{step}'. Context Keys: {list(context.keys())}")

        if step == 'error':
             return {'action': 'fail_task', 'error': context.get('error_details', 'Task entered error state.')} #[cite: uploaded:SoftwareSim3d/src/agent_base.py]

        if task_type == 'decompose_request':
            if step == 'start':
                prompt = self._get_decomposition_prompt_internal(task.get('details',{}).get('original_request'))
                return {'action': 'use_llm', 'prompt': prompt} #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
            elif step == 'delegate_tasks':
                 return {'action': 'wait'} #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
            elif step == 'delegation_complete':
                 logger.info(f"CEO {self.agent_id}: Decomposition task {task_id} completed.")
                 return {'action': 'complete_task', 'result': 'Decomposition and delegation completed.'} #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
            else:
                return {'action': 'wait'} #[cite: uploaded:SoftwareSim3d/src/agent_base.py]

        elif task_type == 'notify_completion':
            if step == 'start' and task.get('details', {}).get('qa_approval_received'):
                original_task_id = task.get('details',{}).get('original_task_id', 'Unknown')
                project_name = task.get('details',{}).get('project_name', 'the project')
                message_data = {
                    'type': 'simulation_end',
                    'project_name': project_name,
                    'original_task_id': original_task_id,
                    'success': True,
                    'message': f"Project '{project_name}' has been successfully completed and approved by QA & CEO."
                }
                if not self.messenger_id:
                     return {'action': 'fail_task', 'error': "Messenger ID not configured."} #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
                context['step'] = 'notifying_messenger'
                self.task_context[task_id] = context
                return { #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
                    'action': 'send_message_to_agent',
                    'target_agent_id': self.messenger_id,
                    'message_data': message_data
                 }
            elif step == 'notifying_messenger':
                 logger.debug(f"CEO {self.agent_id}: Waiting for messenger notification send confirmation.")
                 return {'action': 'wait'} #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
            elif self.get_state('current_action') == 'message_sent': #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
                 logger.info(f"CEO {self.agent_id}: Final completion notification sent to messenger.")
                 return {'action': 'complete_task', 'result': f"Notified messenger for project {task.get('details',{}).get('project_name')}"} #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
            else:
                logger.warning(f"CEO {self.agent_id}: Final approval task {task_id} in step '{step}', waiting for QA approval or send confirmation.")
                return {'action': 'wait'} #[cite: uploaded:SoftwareSim3d/src/agent_base.py]

        else:
            logger.warning(f"CEO {self.agent_id}: Task {task_id} (Type: {task_type}) not handled. Waiting.")
            return {'action': 'wait'} #[cite: uploaded:SoftwareSim3d/src/agent_base.py]


    # --- Abstract Method Implementations ---
    def get_prompt(self, task_details: Dict[str, Any], context: Dict[str, Any]) -> Optional[str]:
        """Implements abstract method. Returns prompt based on task type."""
        task_type = task_details.get('task_type')
        if task_type == 'decompose_request':
            original_request = task_details.get('details', {}).get('original_request')
            return self._get_decomposition_prompt_internal(original_request)
        else:
            logger.debug(f"CEO {self.agent_id}: get_prompt called for task type '{task_type}' - no LLM needed.")
            return None

    async def _process_llm_response(self, llm_response: str):
        """Processes LLM response, assuming it's for decomposition."""
        if not self.current_task:
             logger.error(f"CEO {self.agent_id}: Cannot process LLM response, no active task."); return
        task_id = self.current_task.get('task_id')
        if task_id not in self.task_context:
            logger.error(f"CEO {self.agent_id}: Cannot process LLM response, context missing for task {task_id}."); return
        context = self.task_context[task_id]; task_type = self.current_task.get('task_type')

        if task_type == 'decompose_request':
             logger.info(f"CEO {self.agent_id}: Received LLM response for task {task_id} (decomposition).")
             logger.debug(f"CEO {self.agent_id} Raw LLM decomposition response for {task_id}: {llm_response}")
             decomposed_tasks_list = []
             try:
                 json_match = re.search(r'\{[\s\S]*\}', llm_response)
                 if not json_match: raise ValueError("No JSON object found in LLM response.")
                 parsed_response = json.loads(json_match.group(0)); raw_tasks = parsed_response.get('tasks', [])
                 if not isinstance(raw_tasks, list) or not all(isinstance(t, dict) and 'role' in t and 'description' in t for t in raw_tasks):
                      logger.warning("LLM decomposition has invalid structure, attempting basic fix...")
                      fixed_tasks = []; default_role = "ProductManager"
                      for i, item in enumerate(raw_tasks):
                           if isinstance(item, dict):
                                role = item.get("role") or default_role; desc = item.get("description") or f"Default task {i+1}"; fixed_tasks.append({"role": role, "description": desc}); default_role = "Marketer"
                           else: fixed_tasks.append({"role": default_role, "description": str(item)})
                      if fixed_tasks: raw_tasks = fixed_tasks
                      else: raise ValueError("Parsed 'tasks' key is not a list of valid task dictionaries.")
                 if not raw_tasks:
                      logger.warning(f"CEO {self.agent_id}: LLM decomposition was empty. Using default.")
                      decomposed_tasks_list = self._default_decomposition(self.current_task.get('details',{}).get('original_request'))
                 else:
                      logger.info(f"CEO {self.agent_id}: Successfully parsed {len(raw_tasks)} sub-tasks."); decomposed_tasks_list = raw_tasks
             except (json.JSONDecodeError, ValueError) as e:
                 logger.error(f"CEO {self.agent_id}: Failed to parse LLM decomposition: {e}. Using default."); decomposed_tasks_list = self._default_decomposition(self.current_task.get('details',{}).get('original_request'))

             context['decomposed_tasks'] = decomposed_tasks_list; context['step'] = 'delegate_tasks'
             self.task_context[task_id] = context
             self.update_state({'current_action': 'processed_llm_response', 'current_thoughts': 'LLM response processed (sub_tasks).'}) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
             await self._execute_delegate_tasks(self.current_task, context) # Trigger delegation
        else:
            logger.warning(f"CEO {self.agent_id}: Received LLM response for task {task_id} (type '{task_type}'). Ignoring.")

    async def _process_tool_result(self, tool_name: str, result: Any):
        """Processes results from tool usage (CEO currently uses no tools)."""
        if not self.current_task: logger.error(f"CEO {self.agent_id}: Cannot process tool result, no active task."); return
        task_id = self.current_task.get('task_id')
        if task_id not in self.task_context: logger.error(f"CEO {self.agent_id}: Cannot process tool result, context missing."); return
        context = self.task_context[task_id]
        logger.warning(f"CEO {self.agent_id}: Received unhandled tool result '{tool_name}'. Result: {result}")
        success = isinstance(result, dict) and result.get('status') == 'success'
        self.update_state({ #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
            'current_action': f'processed_{tool_name}_result',
            'current_thoughts': f"Tool {tool_name} result ({'Success' if success else 'Failure'})." })
        if not success: context['step'] = 'error'; context['error_details'] = f"Tool '{tool_name}' failed: {result.get('result') if isinstance(result, dict) else result}"; self.task_context[task_id] = context; logger.error(f"CEO {self.agent_id}: {context['error_details']}")

    # --- Helper Methods (Specific to CEO) ---
    def _get_decomposition_prompt_internal(self, user_request: str) -> str:
        prompt = f"""
        Analyze the following high-level user request for a software project:
        "{user_request}"

        Your primary goal is to break this down into initial, high-level tasks for the appropriate roles, considering if it's a single-page or multi-page website request.

        **Instructions:**
        1. **Identify Project Type:** Determine if the request likely implies a single page or multiple pages (e.g., mentioning "about page", "contact section", "multi-page site").
        2. **Decompose Tasks:**
           - **If Multi-Page:** Generate specific tasks for the Product Manager for EACH logical page identified or implied (e.g., Homepage, About, Contact, Services). The description should be like "Define initial specs for the About page". Also, include initial tasks for Marketer (research) and Coder (setup).
           - **If Single-Page (or unclear):** Generate initial tasks for Marketer, Product Manager (overall specs), and Coder as before.
        3. **Specify Roles:** Use standard roles: "Marketer", "ProductManager", "Coder".
        4. **Task Goal:** For each task, imply the primary goal (e.g., market research, define specs, setup structure).
        5. **Constraints:** Base tasks *only* on the user request for now.

        **Output Format:**
        Output ONLY as a single, valid JSON object. Adhere strictly to the following format:
        {{
          "tasks": [
            {{
              "role": "Marketer",
              "description": "Concise task description for Marketer (e.g., Research target audience for a website about {user_request})."
            }},
            {{
              "role": "ProductManager",
              "description": "Concise task description for Product Manager (e.g., Define initial specs for the Homepage)."
              // Add more ProductManager tasks here if multi-page
            }},
             {{
              "role": "ProductManager",
              "description": "Define initial specs for the About Page."
              // If multi-page, example only
            }},
            {{
              "role": "Coder",
              "description": "Concise task description for Coder (e.g., Set up basic project structure)."
            }}
            // Include ONLY relevant roles/tasks needed for the *first step*.
          ]
        }}

        Do not include explanations, greetings, comments, or any text outside the JSON structure. Ensure the JSON is well-formed.

        User Request: "{user_request}"

        JSON Output:
        """
        return prompt.strip()


    def _default_decomposition(self, user_request: str) -> List[Dict]:
        """Provides a fallback decomposition, ensuring original request is included."""
        logger.warning(f"CEO {self.agent_id}: Using default task decomposition.")
        # --- MODIFIED: Ensure original request is included ---
        return [
            {"role": "Marketer", "description": f"Perform initial market analysis for: '{user_request}'"},
            {"role": "ProductManager", "description": f"Define initial specs for: '{user_request}'"}, # Corrected role name if needed
            {"role": "Coder", "description": "Prepare initial project setup."}
            # You might adjust the default roles/descriptions based on your most common fallback needs
        ]

    async def _execute_delegate_tasks(self, task: Dict[str, Any], context: Dict[str, Any]):
        """Delegates the decomposed tasks via the WorkflowManager, ensuring original_request is included."""
        task_id = task.get('task_id')
        data = task.get('details', {})
        decomposed_tasks = context.get('decomposed_tasks', [])
        if not decomposed_tasks:
            logger.error(f"CEO {self.agent_id}: Decomposed tasks missing for delegation.")
            context['step'] = 'error'
            context['error_details'] = 'Decomposed tasks missing.'
            self.task_context[task_id] = context
            return

        logger.info(f"CEO {self.agent_id}: Delegating {len(decomposed_tasks)} sub-tasks for main task {task_id}")
        self.update_state({'current_action': 'delegating', 'current_thoughts': f'Sending {len(decomposed_tasks)} tasks.'}) #[cite: Sims/src/src/agent_base.py]

        # --- MODIFIED: Retrieve original_request from the current task's details ---
        # Make sure self.original_request is correctly populated when the CEO agent
        # first receives the task (e.g., in _handle_user_request_from_messenger)
        # or retrieve it from the current task's details if that's where it's stored.
        # Assuming self.original_request holds the initial request string.
        # If not, you might need: original_request = data.get('original_request')
        original_request = self.original_request # Ensure this is correctly set elsewhere
        # --- END MODIFICATION ---

        project_name = data.get('project_name')
        delegation_list = []
        delegation_failed = False

        task_type_map = {
            "Marketer": "develop_strategy",
            "ProductManager": "define_specifications", # Assuming this is the key used in manager_ids
            "Product Manager": "define_specifications", # Handle potential space
            "Coder": "write_code"
            # Add mappings for other roles if needed
        }

        for sub_task_info in decomposed_tasks:
            role = sub_task_info.get('role')
            sub_task_desc = sub_task_info.get('description')

            # --- Normalize role for lookups ---
            normalized_role = role
            if role == "ProductManager": normalized_role = "Product Manager"
            # Add other normalizations if necessary
            # --- End Normalization ---

            sub_task_type = task_type_map.get(normalized_role, "generic_task")

            if not role or not sub_task_desc:
                logger.warning(f"CEO Skipping invalid sub-task: {sub_task_info}")
                continue

            target_agent_id = self.manager_ids.get(normalized_role)
            if not target_agent_id:
                logger.error(f"CEO {self.agent_id}: Could not find agent ID for role '{role}' (normalized to '{normalized_role}').")
                delegation_failed = True
                break # Stop delegation if an agent ID is missing

            # --- MODIFIED: Add original_request to sub_task_data details ---
            sub_task_data = {
                'description': sub_task_desc,
                'task_type': sub_task_type,
                'details': {
                    'original_request': original_request, # Add the original request here
                    'project_name': project_name,
                    'originating_task_id': task_id # Keep track of the CEO's decomposition task
                },
                'assigned_to_role': role # Use the role name from the LLM response for the task assignment itself
            }
            # --- END MODIFICATION ---
            delegation_list.append({'target_agent_id': target_agent_id, 'task_data': sub_task_data})

        if delegation_failed:
            context['step'] = 'error'
            # Ensure the error detail uses the correct role variable from the loop context
            context['error_details'] = f"Cannot find agent ID for role {role} (normalized: {normalized_role})."
            self.task_context[task_id] = context
            return

        if delegation_list:
            delegation_message = {'type': 'delegate_sub_tasks', 'tasks_to_delegate': delegation_list}
            try:
                await self._send_message_to_manager(delegation_message) #[cite: Sims/src/src/agent_base.py]
                logger.info(f"CEO {self.agent_id}: Sent delegation request to WorkflowManager.")
                context['step'] = 'delegation_complete' # Move to next step upon successful send
                self.task_context[task_id] = context
                self.update_state({'current_action': 'delegation_sent'}) #[cite: Sims/src/src/agent_base.py]
            except Exception as e:
                logger.error(f"CEO {self.agent_id}: Failed to send delegation message: {e}", exc_info=True)
                context['step'] = 'error'
                context['error_details'] = f"Failed delegation send: {e}"
                self.task_context[task_id] = context
        else:
            logger.warning(f"CEO {self.agent_id}: No valid sub-tasks to delegate for task {task_id}.")
            context['step'] = 'delegation_complete' # Mark as complete even if nothing to delegate
            self.task_context[task_id] = context

    async def _send_error_to_messenger(self, error_message: str):
        """Sends an error message back to the Messenger agent."""
        if not self.messenger_id: logger.error(f"CEO {self.agent_id}: Messenger ID not configured."); return
        try:
            error_payload = {'type': 'error_notification', 'source_agent': self.agent_id, 'message': error_message, 'project_name': self.project_name or "[Unknown Project]"}
            await self._send_message_to_agent(self.messenger_id, {'type': 'agent_message', 'message_data': error_payload}) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
            logger.info(f"CEO {self.agent_id}: Sent error notification to Messenger.")
        except Exception as e:
            logger.error(f"CEO {self.agent_id}: Failed to send error message to Messenger: {e}", exc_info=True)

    async def _send_message_to_agent(self, target_agent_id: str, message_data: Any):
        """Helper to send message via broadcast callback, ensuring proper structure."""
        # Pass the actual message data directly to the base class sender
        await super()._send_message_to_agent(target_agent_id, message_data)
        # Base class's sender handles logging and exceptions
        # We can update state here if needed *after* the send is attempted
        self.update_state({'current_action': 'message_sent'})


    def _generate_id(self, length=8):
        import random, string
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))