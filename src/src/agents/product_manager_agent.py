# SoftwareSim3d/src/agents/product_manager_agent.py
import re
import asyncio
import logging
from typing import Optional, Dict, Any, Callable, Awaitable, Tuple, Set, List # Added List
import os
import time
from ..agent_base import Agent, STATUS_IDLE, STATUS_WORKING, STATUS_MOVING_TO_ZONE, STATUS_USING_TOOL_IN_ZONE, STATUS_WAITING_RESPONSE, STATUS_FAILED, DEFAULT_DEPENDENCY_TIMEOUT
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..llm_integration.api_clients import LLMService

logger = logging.getLogger(__name__)

class ProductManagerAgent(Agent):
    def __init__(self,
                 agent_id: str,
                 message_queue: asyncio.Queue,
                 broadcast_callback: Callable[[Dict[str, Any]], Awaitable[None]],
                 loop: asyncio.AbstractEventLoop,
                 initial_position: Tuple[float, float, float],
                 target_desk_position: Tuple[float, float, float],
                 **kwargs):

        super().__init__(
            agent_id=agent_id,
            role="Product Manager",
            llm_service=kwargs.get('llm_service'),
            llm_type=kwargs.get('llm_type'),
            llm_model_name=kwargs.get('llm_model_name'),
            message_queue=message_queue,
            broadcast_callback=broadcast_callback,
            loop=loop,
            initial_position=initial_position,
            target_desk_position=target_desk_position,
            available_tools=kwargs.get('available_tools'),
            required_tool_zones=kwargs.get('required_tool_zones'),
            zone_coordinates_map=kwargs.get('zone_coordinates_map')
        )
        # --- ADDED: Internal Task Queue ---
        self.task_queue: List[Dict[str, Any]] = []
        # --- END ADDED ---
        logger.info(f"ProductManagerAgent {self.agent_id} initialized.")

    # --- MODIFIED: assign_task adds to queue ---
    async def assign_task(self, task: Dict[str, Any]):
        """
        Enqueue a new task and immediately begin processing if the agent is idle.
        """
        task_id = task.get('task_id', 'N/A')
        logger.info(f"ProductManagerAgent {self.agent_id} received task {task_id}: {task}")

        # Add the new task to the internal queue.
        self.task_queue.append(task)
        logger.info(f"Task {task_id} added to queue (current queue size: {len(self.task_queue)}).")

        # If the agent is idle, start processing the task immediately.
        if self.get_state('status') == STATUS_IDLE:
            logger.info(f"Agent {self.agent_id} is idle. Starting next task from queue.")
            next_task = self.task_queue.pop(0)
            next_task_id = next_task.get('task_id', 'N/A')
            # Initialize the context for the new task.
            context = self.task_context.setdefault(next_task_id, {})
            context['details'] = next_task.get('details', {})
            context['original_request'] = context['details'].get('original_request')
            self.task_context[next_task_id] = context
            self.current_task = next_task
            logger.info(f"Agent {self.agent_id} started task {next_task_id}.")
            self.update_state({
                'status': STATUS_WORKING,
                'progress': 0.0,
                'last_error': None,
                'current_action': 'starting_task',
                'current_idle_sub_state': None,
                'state_timer': 0.0,
                'wait_start_time': None
            })
        else:
            logger.info(f"Agent {self.agent_id} is busy; task {task_id} remains queued.")

    def get_prompt(self, task_details: Dict[str, Any], context: Dict[str, Any]) -> Optional[str]:
        # ...(prompt generation logic remains the same)...
        task_type = task_details.get('task_type')
        details = task_details.get('details', {})
        ceo_description = details.get('ceo_task_description', task_details.get('description', 'Define product specifications.')) # Use task description as fallback

        # Retrieve original_request from context (should be set by assign_task)
        original_request = context.get('original_request', '[Original request not provided]')

        project_name = details.get('project_name', '[Unknown Project]')
        marketing_report = context.get('marketing_report_content', 'Marketing report not available.')

        if task_type == 'define_specifications':
            logger.debug(f"ProductManagerAgent {self.agent_id} using original_request: {original_request}")
            # The prompt asking for page-specific details is good
            prompt = f"""You are a Product Manager simulation agent for project '{project_name}'.
The original user request was: "{original_request}"
Your specific task assigned by the CEO is: "{ceo_description}"

Using the marketing report below (if available):
{marketing_report}

**Your Goal:** Create detailed webpage specifications based on the CEO's task and the original user request.

**Instructions:**
1.  **Analyze Request:** Determine if the request implies a single page or multiple pages (e.g., "Homepage", "About Page", "Contact Us").
2.  **Structure Specifications:** Organize the specs clearly.
3.  **Detail Each Page:**
    * **If Multi-Page:** Create a distinct section in the Markdown for EACH logical page identified or implied (e.g., `## Homepage Specifications`, `## About Page Specifications`).
    * **For Each Page (or the single page):** Define the following:
        * `Key Sections:` List the main content areas/divs required for that specific page.
        * `Features:` Describe interactive elements or specific functionalities needed *on that page*.
        * `HTML Structure Guidance:` Suggest semantic tags and basic layout structure *for that page*.
        * `CSS Styling Guidance:` Describe the desired look, feel, colors, fonts, and layout *for that page*.
        * `JavaScript Interaction Guidance:` Detail *all* required dynamic behaviors, animations, form validations, or API interactions *for that page*.
        * `Content Placeholders:` Suggest *topic-specific* placeholder text relevant to the original request for headings and paragraphs *on that page*.
    * **Navigation (If Multi-Page):** Specify how users will navigate between the different pages (e.g., header navigation links).

Respond ONLY with the structured webpage specifications in Markdown format. Do not include introductory sentences or explanations outside the specification structure itself.
"""
            return prompt.strip()

        logger.warning(f"ProductManagerAgent {self.agent_id} received unknown task type '{task_type}' for prompt generation.")
        return None


    # --- MODIFIED: _decide_next_action processes queue and prevents resend ---
    async def _decide_next_action(self) -> Optional[Dict[str, Any]]:
        """Decides the next action based on the current task or picks the next task from the queue."""
        last_error = self.get_state('last_error')
        if last_error:
            logger.error(f"PM {self.agent_id}: Handling previous error: {last_error}. Failing current task if any.")
            if self.current_task:
                task_id = self.current_task.get('task_id')
                error_msg = f"Failing task {task_id} due to error: {last_error}"
                self.update_state({'last_error': None})
                await self._fail_current_task(error_msg)
                return await self._check_and_start_next_task()
            else:
                self.update_state({'last_error': None})
                return {'action': 'wait'}
        # logger.info(f"PM {self.agent_id} checking current task and queue. Current task: {self.current_task}, Queue size: {len(self.task_queue)}")
        if not self.current_task:
            return await self._check_and_start_next_task()

        task_id = self.current_task.get('task_id')
        if not task_id:
            logger.error(f"{self.agent_id}: Current task missing an ID. Clearing task.")
            self.current_task = None
            return await self._check_and_start_next_task()
        logger.debug(f"PM {self.agent_id} processing task {task_id}.")
        context = self.task_context.get(task_id, {})
        if not context:
            logger.error(f"PM {self.agent_id}: Context missing for task {task_id}. Failing task.")
            await self._fail_current_task(f"Context missing for task {task_id}")
            return await self._check_and_start_next_task()

        task_type = self.current_task.get('task_type')
        task_details = context.get('details', {})
        project_name = task_details.get('project_name', 'default_project')
        current_action = self.get_state('current_action')
        current_zone = self.get_state('current_zone')
        current_status = self.get_state('status')
        # logger.info(f"PM {self.agent_id} current action: {current_action}, zone: {current_zone}, status: {current_status}")
        # Check for marketing report dependency.
        marketing_filename_rel = self.internal_state.get('marketing_report_filename_' + project_name)
        if not marketing_filename_rel and task_type == 'define_specifications':
            wait_start = context.get('wait_start_time')
            if wait_start is None:
                context['wait_start_time'] = time.time()
                self.task_context[task_id] = context
                logger.info(f"PM {self.agent_id} waiting for marketing report for task {task_id} (Project: {project_name}). Starting timer.")
                self.update_state({'current_action': 'waiting_dependency'})
            elif time.time() - wait_start > DEFAULT_DEPENDENCY_TIMEOUT:
                error_msg = f"Dependency timeout waiting for marketing report for task {task_id} (Project: {project_name})."
                logger.error(f"PM {self.agent_id}: {error_msg}")
                await self._fail_current_task(error_msg)
                return await self._check_and_start_next_task()
            return {'action': 'wait'}

        # 2. If the marketing report file is known but its content is not yet read.
        needs_report_content = marketing_filename_rel and 'marketing_report_content' not in context and not context.get('read_successful')
        report_read_successful = context.get('read_successful', False) or (marketing_filename_rel is None)
        # 3. If specifications have not yet been generated.
        specs_generated = 'specifications_content' in context
        save_status = context.get('save_successful')
        needs_saving = specs_generated and save_status is None
        notification_status = context.get('notification_sent')
        needs_notification = save_status is True and notification_status is not True
        at_desk = current_zone == 'Desk'
        moving_to_desk = current_status == STATUS_MOVING_TO_ZONE and self.get_state('target_zone') == 'Desk'

        logger.info(f"PM Decide Check: Task {task_id}, Type {task_type}, Status {current_status}, Action {current_action}, Zone {current_zone}, ReportNeeded {needs_report_content}, ReportOK {report_read_successful}, SpecsGen {specs_generated}, SaveNeeded {needs_saving}, NotifyNeeded {needs_notification}")

        # Decision flow
        if not marketing_filename_rel and task_type == 'define_specifications':
            # Still waiting for marketing report filename.
            return {'action': 'wait'}
        elif needs_report_content:
            logger.info(f"PM {self.agent_id} needs to read marketing report '{marketing_filename_rel}' for task {task_id}.")
            if 'file_read' not in self.available_tools:
                await self._fail_current_task(f"'file_read' tool unavailable for task {task_id}.")
                return await self._check_and_start_next_task()
            required_zone = self.required_tool_zones.get('file_read')
            if required_zone and current_zone != required_zone:
                if current_status != STATUS_MOVING_TO_ZONE:
                    logger.info(f"PM {self.agent_id} moving to {required_zone} to read marketing report for task {task_id}.")
                    return {'action': 'move_to_zone', 'zone_name': required_zone}
                return {'action': 'wait'}
            else:
                if self.get_state('current_action') == f'ready_to_use_file_read':
                    logger.debug(f"PM {self.agent_id} waiting for file_read result for task {task_id}.")
                    return {'action': 'wait'}
                logger.info(f"PM {self.agent_id} initiating file read for marketing report '{marketing_filename_rel}' (Task: {task_id}).")
                return {'action': 'use_tool', 'tool_name': 'file_read', 'params': {'filename': marketing_filename_rel}}
        elif report_read_successful and not specs_generated:
            if at_desk or (current_status == STATUS_WORKING and current_action == 'arrived'):
                logger.info(f"PM {self.agent_id} ready to generate specifications for task {task_id}.")
                prompt = self.get_prompt(self.current_task, context)
                if prompt:
                    if self.get_state('current_action') == 'executing_llm':
                        logger.debug(f"PM {self.agent_id} waiting for LLM response for task {task_id}.")
                        return {'action': 'wait'}
                    logger.info(f"PM {self.agent_id} initiating LLM call for task {task_id}.")
                    return {'action': 'use_llm', 'prompt': prompt}
                else:
                    await self._fail_current_task(f"Could not generate LLM prompt for task {task_id}.")
                    return await self._check_and_start_next_task()
            elif moving_to_desk:
                return {'action': 'wait'}
            else:
                if current_status != STATUS_MOVING_TO_ZONE:
                    logger.info(f"PM {self.agent_id} moving to Desk to generate specifications for task {task_id}.")
                    await self._move_to_zone("Desk", self.target_desk_position)
                return {'action': 'wait'}
        elif needs_saving:
            specs_content = context.get('specifications_content')
            if not specs_content:
                await self._fail_current_task(f'Generated specs missing for task {task_id}.')
                return await self._check_and_start_next_task()
            if 'file_write' not in self.available_tools:
                await self._fail_current_task(f'file_write tool unavailable for task {task_id}.')
                logger.info(f"PM {self.agent_id} file_write tool unavailable for task {task_id}.")
                return await self._check_and_start_next_task()
            required_zone_fw = self.required_tool_zones.get('file_write')
            if required_zone_fw and current_zone != required_zone_fw:
                if current_status != STATUS_MOVING_TO_ZONE:
                    logger.info(f"PM {self.agent_id} moving to {required_zone_fw} to save specs for task {task_id}.")
                    return {'action': 'move_to_zone', 'zone_name': required_zone_fw}
                return {'action': 'wait'}
            else:
                if self.get_state('current_action') not in [f'ready_to_use_file_write', 'executing_tool']:
                    logger.info(f"PM {self.agent_id} deciding to save specifications for task {task_id}.")
                    page_context_name = task_details.get('page_name', task_details.get('description', f"task_{task_id[:8]}"))
                    specifications_filename = f"{project_name}/ProductManager/specs_{self._sanitize_filename(page_context_name)}.md"
                    return {'action': 'use_tool', 'tool_name': 'file_write', 'params': {'filename': specifications_filename, 'content': specs_content}}
                else:
                    logger.debug(f"PM {self.agent_id} already processing file_write for task {task_id}, waiting.")
                    return {'action': 'wait'}
        elif needs_notification:
            if at_desk or (current_status == STATUS_WORKING and current_action == 'arrived'):
                logger.info(f"PM {self.agent_id} specs saved, now notifying Coder for task {task_id}.")
                coder_agent_id = "coder-01"
                specifications_filename = context.get('saved_filename')
                if not specifications_filename:
                    await self._fail_current_task(f'Saved filename missing after save for task {task_id}.')
                    return await self._check_and_start_next_task()
                originating_ceo_task_id = context.get('details', {}).get('originating_task_id')
                original_request_for_coder = context.get('original_request')
                page_name_for_coder = context.get('details', {}).get('page_name', context.get('details', {}).get('description', 'main_page'))
                message_to_coder = {
                    'type': 'task_dependency_ready',
                    'dependency_type': 'specifications',
                    'saved_filename': specifications_filename,
                    'details': {
                        'originating_task_id': originating_ceo_task_id,
                        'original_request': original_request_for_coder,
                        'page_name': page_name_for_coder
                    }
                }
                context['notification_sent'] = True
                self.task_context[task_id] = context
                logger.info(f"PM {self.agent_id} sending specs filename '{specifications_filename}' to Coder for task {task_id}.")
                return {'action': 'send_message_to_agent', 'target_agent_id': coder_agent_id, 'message_data': message_to_coder}
            elif moving_to_desk:
                return {'action': 'wait'}
            else:
                if current_status != STATUS_MOVING_TO_ZONE:
                    logger.info(f"PM {self.agent_id} moving to Desk to notify Coder for task {task_id}.")
                    await self._move_to_zone("Desk", self.target_desk_position)
                return {'action': 'wait'}
        elif notification_status is True:
            logger.info(f"PM {self.agent_id} notification sent for task {task_id}. Completing task.")
            final_msg = f"Specifications saved as {context.get('saved_filename','N/A')}"
            await self._complete_current_task(final_msg)
            return await self._check_and_start_next_task()
        else:
            logger.debug(f"PM {self.agent_id} fallback wait for task {task_id}. Status: {current_status}, Action: {current_action}")
            return {'action': 'wait'}

    # --- ADDED: Helper to check queue and start next task ---
    async def _check_and_start_next_task(self) -> Dict[str, Any]:
        """Checks the queue and starts the next task if available and agent is idle."""
        if self.task_queue and self.get_state('status') == STATUS_IDLE:
            next_task = self.task_queue.pop(0)
            task_id = next_task.get('task_id')
            logger.info(f"Agent {self.agent_id} starting next task {task_id} from queue. Queue size: {len(self.task_queue)}")

            # Initialize context for the new task
            context = self.task_context.setdefault(task_id, {})
            task_details = next_task.get('details', {})
            context['details'] = task_details
            context['original_request'] = task_details.get('original_request')
            logger.info(f"Task {task_id} context for Agent {self.agent_id} INITIALIZED with details: {context.get('details')}")
            self.task_context[task_id] = context # Save context immediately

            self.current_task = next_task
            self.update_state({
                'status': STATUS_WORKING, 'progress': 0.0, 'last_error': None,
                'current_action': 'starting_task', 'current_idle_sub_state': None,
                'state_timer': 0.0, 'wait_start_time': None
            })
            # The main loop will call _decide_next_action again
            return {'action': 'wait'} # Return wait to allow decision loop to process the new task
        else:
            # If queue is empty or agent is not idle, just wait
            if self.get_state('status') != STATUS_IDLE:
                 logger.info(f"PM {self.agent_id} cannot start next task, not idle (Status: {self.get_state('status')}).")
            elif not self.task_queue:
                 logger.debug(f"PM {self.agent_id} task queue is empty.")
            return {'action': 'wait'}
    # --- END ADDED ---


    async def _process_llm_response(self, llm_response: str):
        # ...(LLM processing remains the same)...
        logger.info(f"PM processing LLM specs response.")
        if not self.current_task: logger.error(f"{self.agent_id} Cannot process LLM response, no current task."); return
        task_id = self.current_task['task_id']
        context = self.task_context.setdefault(task_id, {})

        cleaned_specs = llm_response.strip()
        if cleaned_specs.startswith("```markdown"): cleaned_specs = cleaned_specs[len("```markdown"):].strip()
        if cleaned_specs.endswith("```"): cleaned_specs = cleaned_specs[:-len("```")].strip()

        logger.info(f"PM {self.agent_id} LLM response processed for task {task_id}.")
        context['specifications_content'] = cleaned_specs
        self.task_context[task_id] = context # Save updated context
        self.update_state({'current_action': 'processed_llm_response', 'current_thoughts': 'LLM specs processed, ready to save.'})

    async def _process_tool_result(self, tool_name: str, result: Any):
        # ...(Tool result processing remains largely the same)...
        if not self.current_task: logger.error(f"{self.agent_id} Cannot process tool result, no current task."); return
        task_id = self.current_task['task_id']
        context = self.task_context.setdefault(task_id, {})
        logger.info(f"PM processing result for tool '{tool_name}'. Task: {task_id}")
        move_back_to_desk = False; success = False; thought = f'Processed tool {tool_name}'

        if tool_name == 'file_read':
            if isinstance(result, dict) and result.get('status') == 'success':
                read_filename = result.get('filename', 'unknown file')
                self.task_context[task_id]['marketing_report_content'] = result.get('content', '')
                self.task_context[task_id]['read_successful'] = True
                move_back_to_desk = True
                logger.info(f"Marketing report read: {read_filename}")
                logger.info(f"PM {self.agent_id} marketing report content: {self.task_context[task_id]['marketing_report_content']}")
                thought = 'Report read. Returning to Desk.'
                success = True
            else:
                error_msg = f"File read failed: {result.get('result') if isinstance(result,dict) else result}"
                logger.error(f"PM {self.agent_id}: {error_msg}")
                self.task_context[task_id]['read_successful'] = False
                self.update_state({'last_error': error_msg}) # Set error state
                # Do not automatically fail task here, let decide_next_action handle failure
                return

        elif tool_name == 'file_write':
            if isinstance(result, dict) and result.get('status') == 'success':
                saved_filename_rel = result.get('filename')
                logger.info(f"Specs write successful: {saved_filename_rel}")
                self.task_context[task_id]['save_successful'] = True
                self.task_context[task_id]['saved_filename'] = saved_filename_rel
                move_back_to_desk = True
                thought = 'Specs saved. Returning to Desk.'
                success = True
            else:
                error_msg = f"File write failed: {result.get('result') if isinstance(result,dict) else result}"
                logger.error(f"PM {self.agent_id}: {error_msg}")
                self.task_context[task_id]['save_successful'] = False
                self.update_state({'last_error': error_msg}) # Set error state
                # Do not automatically fail task here
                return
        else:
             logger.warning(f"PM received result for unhandled tool: {tool_name}")
             thought = f"Processed unhandled tool {tool_name}"

        # Save context changes before updating state/moving
        self.task_context[task_id] = context

        self.update_state({'status': STATUS_WORKING, 'current_action': f'processed_{tool_name}_result', 'current_thoughts': thought})
        if move_back_to_desk and self.get_state('current_zone') != 'Desk':
              if not (self.get_state('status') == STATUS_MOVING_TO_ZONE and self.get_state('target_zone') == 'Desk'):
                   await self._move_to_zone("Desk", self.target_desk_position)


    async def _handle_agent_specific_message(self, sender_id: str, message_data: Any):
        """Handles messages specifically relevant to the PM agent."""
        # Check if the message is wrapped in an outer 'agent_message'
        if isinstance(message_data, dict) and 'message_data' in message_data:
            message_data = message_data['message_data']
            logger.info(f"PM {self.agent_id} received wrapped message from {sender_id}: {message_data}")
        if not isinstance(message_data, dict):
            logger.error(f"PM {self.agent_id} received invalid message format from {sender_id}: {message_data}")
            await super()._handle_agent_specific_message(sender_id, message_data)
            return

        msg_type = message_data.get('type')
        dependency_type = message_data.get('dependency_type')
        saved_filename = message_data.get('saved_filename')

        if msg_type == 'task_dependency_ready' and dependency_type == 'marketing_strategy':
            logger.info(f"PM {self.agent_id} received marketing report filename: {saved_filename} from {sender_id}")

            # --- Store the report filename in the internal state ---
            project_name_from_details = message_data.get('details', {}).get(
                'project_name',
                self.current_task.get('details', {}).get('project_name') if self.current_task else None
            )
            if project_name_from_details:
                key = 'marketing_report_filename_' + project_name_from_details
                self.internal_state[key] = saved_filename
                logger.info(f"Stored marketing filename '{saved_filename}' in internal state for project '{project_name_from_details}'.")
            else:
                logger.warning("Could not determine project name to store marketing filename in internal state.")

            # --- Locate the task waiting for this dependency ---
            target_task_id = None
            if self.current_task and self.current_task.get('task_id'):
                current_task_id = self.current_task['task_id']
                if not self.task_context.get(current_task_id, {}).get('marketing_dependency_received'):
                    target_task_id = current_task_id
            else:
                for task in self.task_queue:
                    task_id_in_queue = task.get('task_id')
                    if task_id_in_queue and not self.task_context.get(task_id_in_queue, {}).get('marketing_dependency_received'):
                        task_proj = task.get('details', {}).get('project_name')
                        if task_proj == project_name_from_details or not project_name_from_details:
                            target_task_id = task_id_in_queue
                            break

            if target_task_id:
                context = self.task_context.setdefault(target_task_id, {})
                context.setdefault('details', {})['marketing_report_filename'] = saved_filename
                context['marketing_dependency_received'] = True
                context.pop('wait_start_time', None)  # Clear any waiting timer
                self.task_context[target_task_id] = context
                logger.info(f"Marked marketing dependency received for task {target_task_id}.")
                if self.current_task and self.current_task.get('task_id') == target_task_id and \
                self.get_state('current_action') == 'waiting_dependency':
                    self.update_state({
                        'current_action': 'processing_dependency',
                        'current_thoughts': "Received marketing filename."
                    })
            else:
                logger.warning(f"PM received marketing strategy filename '{saved_filename}', but no task was found waiting for it.")
        else:
            await super()._handle_agent_specific_message(sender_id, message_data)

    async def _send_message_to_agent(self, target_agent_id: str, message_data: Any):
         # Corrected: Pass message_data directly to base class method
         await super()._send_message_to_agent(target_agent_id, message_data)
         # Base class's sender handles logging and exceptions
         self.update_state({'current_action': 'message_sent'})

    # --- Add _complete_current_task and _fail_current_task ---
    async def _complete_current_task(self, result: Optional[str] = None):
        """Marks the current task as complete and notifies manager."""
        task_id = self.current_task.get('task_id', 'N/A') if self.current_task else 'N/A'
        if task_id != 'N/A':
            logger.info(f"Agent {self.agent_id} completing Task: {task_id}")
            completion_message = { 'type': 'task_completion_update', 'task_id': task_id, 'status': 'completed', 'result': result }
            try: await self._send_message_to_manager(completion_message)
            except Exception as send_e: logger.error(f"Failed to send completion notification for task {task_id}: {send_e}")
            # Cleanup context for the completed task
            if task_id in self.task_context: del self.task_context[task_id]; logger.debug(f"Cleaned context for completed task {task_id}.")
        else: logger.warning(f"Agent {self.agent_id} tried to complete task but has no current task ID.")

        self.current_task = None # Clear current task
        self.update_state({ 'status': STATUS_IDLE, 'progress': 0.0, 'current_thoughts': f"Task {task_id} completed.", 'current_action': None })
        # Do NOT automatically start next task here, let _decide_next_action handle it


    async def _fail_current_task(self, error_message: str):
        """Marks the current task as failed and notifies manager."""
        task_id = self.current_task.get('task_id', 'N/A') if self.current_task else 'N/A'
        if task_id != 'N/A':
            logger.error(f"Agent {self.agent_id} failing Task: {task_id} - Error: {error_message}")
            failure_message = { 'type': 'task_completion_update', 'task_id': task_id, 'status': STATUS_FAILED, 'result': error_message }
            try: await self._send_message_to_manager(failure_message)
            except Exception as send_e: logger.error(f"Failed to send failure notification for task {task_id}: {send_e}")
            # Cleanup context for the failed task
            if task_id in self.task_context: del self.task_context[task_id]; logger.debug(f"Cleaned context for failed task {task_id}.")
        else: logger.warning(f"Agent {self.agent_id} tried to fail task but has no current task ID. Error: {error_message}")

        self.current_task = None # Clear current task
        self.update_state({ 'status': STATUS_IDLE, 'last_error': error_message, 'current_thoughts': f"Task failed: {error_message}", 'current_action': None, 'progress': 0.0 })
        # Do NOT automatically start next task here, let _decide_next_action handle it

    # --- ADDED: Filename Sanitization Helper ---
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
        # Optional: Limit component length if needed
        # max_len = 60
        # if len(name) > max_len: name = name[:max_len]
        # Handle empty names after sanitization
        if not name: name = "sanitized_empty_name"
        # logger.debug(f"Sanitized path component: '{name}'") # Optional debug
        return name
    # --- END ADDED ---