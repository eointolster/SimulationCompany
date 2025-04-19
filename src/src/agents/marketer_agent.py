# SoftwareSim3d/src/agents/marketer_agent.py

import asyncio
import logging
from typing import Optional, Dict, Any, Callable, Awaitable, Tuple, Set
import os
import time # Needed if adding timeouts, but not strictly required for Marketer now
# Import base class and constants
from ..agent_base import Agent, STATUS_IDLE, STATUS_WORKING, STATUS_MOVING_TO_ZONE, STATUS_USING_TOOL_IN_ZONE, STATUS_WAITING_RESPONSE, STATUS_FAILED #[cite: uploaded:SoftwareSim3d/src/agent_base.py]

# Type hinting imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..llm_integration.api_clients import LLMService #[cite: uploaded:SoftwareSim3d/src/llm_integration/api_clients.py]

logger = logging.getLogger(__name__)

class MarketerAgent(Agent):
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
            role="Marketer",
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
        ) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
        #logger.info(f"MarketerAgent {self.agent_id} initialized.")
        

    def get_prompt(self, task_details: Dict[str, Any], context: Dict[str, Any]) -> Optional[str]:
        task_type = task_details.get('task_type')
        details = task_details.get('details', {})
        ceo_description = details.get('ceo_task_description', 'Develop marketing strategy.')
        project_name = details.get('project_name', '[Unknown Project]')

        # --- MODIFIED: Retrieve original_request from context ---
        # This relies on the Base Agent's assign_task correctly storing it
        original_request = context.get('original_request', '[Original request not in context]')
        # --- END MODIFICATION ---

        search_results = context.get('search_results')
        search_failed = context.get('search_failed', False)

        if task_type == 'develop_strategy':
            context_section = ""
            if search_results:
                 context_section = f"\n\n--- INTERNET RESEARCH FINDINGS ---\n{search_results}\n--- END FINDINGS ---"
            elif search_failed:
                 context_section = "\n\nNOTE: Internet research was attempted but failed. Proceed using general knowledge."

            # --- MODIFIED: Use original_request in the prompt ---
            # Optional: Add logging to verify the request is present
            logger.debug(f"MarketerAgent {self.agent_id} using original_request: {original_request}")

            prompt = f"""You are a Marketer simulation agent for project '{project_name}'.
Task based on request ('{original_request}'): "{ceo_description}"{context_section}

Develop a detailed marketing strategy in Markdown. Focus on target audience, key messaging, and potential channels based on the original request: '{original_request}'.
{context_section}

Respond ONLY with the structured strategy in Markdown."""
            # --- END MODIFICATION ---
            return prompt.strip()

        logger.warning(f"MarketerAgent {self.agent_id} received unknown task type '{task_type}' for prompt generation.")
        return None


    async def _decide_next_action(self) -> Optional[Dict[str, Any]]:
        """Decides the next action for the Marketer agent based on the current task context."""
        if not self.current_task:
            return {'action': 'wait'}

        task_id = self.current_task.get('task_id')
        if not task_id:
            logger.error(f"{self.agent_id}: Task missing ID.")
            return {'action': 'wait'}

        context = self.task_context.get(task_id, {})
        if not context:
            logger.error(f"Marketer {self.agent_id}: Context missing for task {task_id}. Waiting.")
            return {'action': 'wait'}

        task_details = self.current_task.get('details', {})
        project_name = task_details.get('project_name', 'default_project')
        current_action = self.get_state('current_action')
        current_zone = self.get_state('current_zone')
        current_status = self.get_state('status')
        search_attempt_complete = context.get('search_attempt_complete', False)
        search_in_progress = context.get('search_in_progress', False)
        needs_search = not search_attempt_complete and not search_in_progress
        at_desk = current_zone == 'Desk'
        needs_strategy_generation = search_attempt_complete and 'marketing_strategy' not in context
        strategy_generated = 'marketing_strategy' in context
        save_status = context.get('save_successful')
        needs_saving = strategy_generated and save_status is not True
        notification_status = context.get('notification_sent')
        needs_notification = save_status is True and notification_status is not True
        moving_to_desk = current_status == STATUS_MOVING_TO_ZONE and self.get_state('target_zone') == 'Desk'

        # Decision Flow
        if needs_search:
            if 'internet_search' in self.available_tools:
                internet_zone = self.required_tool_zones.get('internet_search')
                if current_zone != internet_zone and not (current_status == STATUS_MOVING_TO_ZONE and self.get_state('target_zone') == internet_zone):
                    return {'action': 'move_to_zone', 'zone_name': internet_zone}
                elif current_zone == internet_zone or not internet_zone:
                    original_request_for_query = task_details.get('original_request', '[Original request not available]')
                    query = f"Marketing strategy ideas for {original_request_for_query}"
                    context['search_in_progress'] = True
                    self.task_context[task_id] = context
                    return {'action': 'use_tool', 'tool_name': 'internet_search', 'params': {'query': query}}
                else:
                    return {'action': 'wait'}
            else:
                context['search_failed'] = True
                context['search_attempt_complete'] = True
                context['search_in_progress'] = False
                self.task_context[task_id] = context
                if current_zone != 'Desk':
                    if current_status != STATUS_MOVING_TO_ZONE:
                        await self._move_to_zone("Desk", self.target_desk_position)
                    return {'action': 'wait'}
                else:
                    self.update_state({'current_action': 'processed_search_failure_explicit'})
                    return {'action': 'wait'}
        elif search_attempt_complete:
            if needs_strategy_generation:
                if at_desk or (current_status == STATUS_WORKING and current_action == 'arrived'):
                    prompt = self.get_prompt(self.current_task, context)
                    if prompt:
                        return {'action': 'use_llm', 'prompt': prompt}
                    else:
                        return {'action': 'fail_task', 'error': 'Could not generate LLM prompt.'}
                elif moving_to_desk:
                    return {'action': 'wait'}
                else:
                    if current_status != STATUS_MOVING_TO_ZONE:
                        await self._move_to_zone("Desk", self.target_desk_position)
                    return {'action': 'wait'}
            elif needs_saving:
                strategy_content = context.get('marketing_strategy')
                if not strategy_content:
                    return {'action': 'fail_task', 'error': 'Generated strategy missing.'}
                if 'file_write' not in self.available_tools:
                    return {'action': 'fail_task', 'error': 'file_write tool unavailable.'}
                required_zone_fw = self.required_tool_zones.get('file_write')
                if required_zone_fw and current_zone != required_zone_fw:
                    return {'action': 'move_to_zone', 'zone_name': required_zone_fw}
                elif current_zone == required_zone_fw or not required_zone_fw:
                    if self.get_state('current_action') not in [f'ready_to_use_file_write', 'executing_tool']:
                        report_filename = f"{project_name}/Marketer/strategy_{task_id[:8]}.md"
                        return {'action': 'use_tool', 'tool_name': 'file_write', 'params': {'filename': report_filename, 'content': strategy_content}}
                    else:
                        return {'action': 'wait'}
                else:
                    return {'action': 'wait'}
            elif needs_notification:
                if at_desk or (current_status == STATUS_WORKING and current_action == 'arrived'):
                    pm_agent_id = "pm-01"
                    report_filename = context.get('saved_filename')
                    if not report_filename:
                        return {'action': 'fail_task', 'error': 'Saved filename missing after save.'}
                    message_to_pm = {'type': 'task_dependency_ready', 'dependency_type': 'marketing_strategy', 'saved_filename': report_filename}
                    context['notification_sent'] = True
                    self.task_context[task_id] = context
                    self.internal_state['next_action_after_message'] = {'action': 'complete_task', 'result': f'Marketing strategy saved as {report_filename}'}
                    try:
                        await self._send_message_to_agent(pm_agent_id, message_to_pm)
                        logger.info(f"Marketer {self.agent_id} sent marketing report filename to PM: {report_filename}")
                        return {'action': 'wait'}
                    except Exception as e:
                        logger.error(f"Marketer {self.agent_id} failed to send notification: {e}", exc_info=True)
                        context['notification_sent'] = None
                        self.task_context[task_id] = context
                        self.update_state({'last_error': f'send_message_to_agent failed: {e}'})
                        return {'action': 'wait'}
                elif moving_to_desk:
                    return {'action': 'wait'}
                else:
                    if current_status != STATUS_MOVING_TO_ZONE:
                        await self._move_to_zone("Desk", self.target_desk_position)
                    return {'action': 'wait'}
            elif current_action == 'message_sent' and self.internal_state.get('next_action_after_message'):
                action = self.internal_state.pop('next_action_after_message')
                return action
            else:
                logger.debug(f"Marketer {self.agent_id} fallback wait. Status: {current_status}, Action: {current_action}")
                return {'action': 'wait'}
        else:
            logger.debug(f"Marketer {self.agent_id}: End of decision logic reached. Waiting.")
            return {'action': 'wait'}

 
    async def _process_llm_response(self, llm_response: str):
        """Processes LLM response and stores the generated strategy in context."""
        task_id = self.current_task.get('task_id') if self.current_task else None
        if not task_id or task_id not in self.task_context:
             logger.error(f"Marketer: Cannot process LLM response, context missing for task {task_id}")
             return

        context = self.task_context.get(task_id, {}) # Use .get for safety
        logger.info(f"Marketer processing LLM strategy response for task {task_id}.")

        cleaned_strategy = llm_response.strip()
        # ... (cleaning logic) ...
        if cleaned_strategy.startswith("```markdown"): cleaned_strategy = cleaned_strategy[len("```markdown"):].strip()
        if cleaned_strategy.endswith("```"): cleaned_strategy = cleaned_strategy[:-len("```")].strip()

        # --- STORE THE RESULT IN CONTEXT ---
        context['marketing_strategy'] = cleaned_strategy
        logger.info(f"Marketer Task {task_id} context updated with 'marketing_strategy' key.")
        # --- END ---

        self.task_context[task_id] = context # Save the updated context
        logger.info(f"Marketer Task {task_id} context SAVED after adding 'marketing_strategy'. Keys: {list(self.task_context.get(task_id, {}).keys())}")

        self.update_state({'current_action': 'processed_llm_response', 'current_thoughts': 'LLM strategy processed, ready to save.'})


    async def _process_tool_result(self, tool_name: str, result: Any):
        """Processes tool results, clearing flags and setting save_successful."""
        task_id = self.current_task.get('task_id', 'N/A') if self.current_task else 'N/A'
        if not task_id or task_id not in self.task_context:
             logger.error(f"Marketer: Cannot process tool result for {tool_name}, context missing for task {task_id}")
             return

        context = self.task_context.get(task_id, {}) # Use .get for safety
        logger.info(f"Marketer processing tool result for '{tool_name}'. Task: {task_id}.")
        move_back_to_desk = False; current_action_update = f'processed_{tool_name}_result'; thought = f'Processed tool {tool_name}'

        if tool_name == 'internet_search':
            move_back_to_desk = True
            context['search_attempt_complete'] = True
            context['search_in_progress'] = False

            if isinstance(result, dict) and result.get('status') == 'success':
                context['search_results'] = result.get('content', 'No content.'); context['search_failed'] = False; current_action_update = 'processed_search_result'
            else:
                error_msg = result.get('result', 'Unknown search error') if isinstance(result, dict) else str(result)
                logger.warning(f"Internet search failed (tool result): {error_msg}"); context['search_results'] = None; context['search_failed'] = True; current_action_update = 'processed_search_failure'
            thought = f'Search processed ({current_action_update}). Returning to Desk.'
            logger.info(f"Marketer Task {task_id} Context *before* save in _process_tool_result (search): {context}")

        elif tool_name == 'file_write':
            context['search_in_progress'] = False # Clear just in case
            if isinstance(result, dict) and result.get('status') == 'success':
                saved_filename = result.get('filename')
                logger.info(f"File write successful: {saved_filename}")
                # --- SET SAVE SUCCESSFUL FLAG ---
                context['save_successful'] = True # Ensure this is set
                # --- END ---
                context['saved_filename'] = saved_filename; current_action_update = 'processed_save_result'; move_back_to_desk = True; thought = f'File write processed. Returning to desk.'
                logger.info(f"Marketer Task {task_id} Context *before* save in _process_tool_result (write): {context}")
            else:
                error_msg = result.get('result', 'Unknown file write error') if isinstance(result, dict) else str(result)
                logger.error(f"File write failed: {error_msg}"); context['save_successful'] = False; self.update_state({'last_error': f"File write failed: {error_msg}"})
                self.task_context[task_id] = context
                return

        else:
             logger.warning(f"MarketerAgent received result for unhandled tool: {tool_name}"); thought = f"Processed unhandled tool {tool_name}";
             context['search_in_progress'] = False

        # Save context changes before updating state/moving
        self.task_context[task_id] = context
        logger.info(f"Marketer Task {task_id} Context *after* save in _process_tool_result: {self.task_context.get(task_id)}") # Log after saving

        self.update_state({'status': STATUS_WORKING, 'current_action': current_action_update, 'current_thoughts': thought})
        if move_back_to_desk and self.get_state('current_zone') != 'Desk':
              if not (self.get_state('status') == STATUS_MOVING_TO_ZONE and self.get_state('target_zone') == 'Desk'):
                   await self._move_to_zone("Desk", self.target_desk_position)

    async def _send_message_to_agent(self, target_agent_id: str, message_data: Any):
        # Wrap the specific message data for agent-to-agent communication structure
        wrapped_message = {'type':'agent_message', 'message_data': message_data}
        await super()._send_message_to_agent(target_agent_id, wrapped_message) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
        self.update_state({'current_action': 'message_sent'}) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]