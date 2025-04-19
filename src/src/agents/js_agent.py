# SoftwareSim3d/src/agents/js_agent.py

import asyncio
import logging
import re
import time
from typing import Optional, Dict, Any, Callable, Awaitable, Tuple
import uuid
# --- CORRECTED IMPORT ---
from ..agent_base import Agent, STATUS_IDLE, STATUS_WORKING # Import base and statuses

logger = logging.getLogger(__name__)

class JSAgent(Agent):
    """Specialized agent focusing on JavaScript functionality, including fixes."""
    def __init__(self, agent_id, role, *args, **kwargs):
         # --- CORRECTED INIT --- Ensure necessary base class args are passed
        super().__init__(agent_id=agent_id, role=role, *args, **kwargs)
        self.coder_lead_id = kwargs.get('coder_lead_id', 'coder-01')
        logger.info(f"JSAgent {self.agent_id} initialized, reporting to {self.coder_lead_id}.")

    def get_prompt(self, task_details: Dict[str, Any], context: Dict[str, Any]) -> Optional[str]:
        """Generates the prompt for the LLM based on task type for JavaScript."""
        task_type = task_details.get('task_type')
        specs = context.get('specifications_content', 'No specifications provided.')
        html_structure = context.get('html_structure', '')  # To provide styling context if needed.
        page_context_name = task_details.get('target_page_context', 'the webpage')
        logger.info(f"{self.agent_id}: Generating JS prompt for page context '{page_context_name}'")
        
        original_request = context.get('original_request')
        if not original_request:
            original_request = "[Original request not provided]"
        topic = original_request.split("about")[-1].strip() if "about" in original_request else "the requested topic"
        
        if task_type == 'generate_js':
            prompt = f"""You are an expert JavaScript Specialist agent creating the initial JavaScript logic for a specific section of a web application related to "{page_context_name}".
    The overall topic is "{topic}".
    Below are the detailed specifications and the relevant HTML structure. Your task is to generate JavaScript code that implements the required logic as specified.

    --- SPECIFICATIONS START (Review JavaScript requirements for "{page_context_name}") ---
    {specs}
    --- SPECIFICATIONS END ---

    --- RELEVANT HTML STRUCTURE (for context) ---
    {html_structure}
    --- HTML STRUCTURE END ---

    Your response should consist ONLY of the raw JavaScript code necessary for the functionality described, without additional commentary or formatting tags.
    """
            return prompt.strip()

        elif task_type == 'fix_js_logic':
            qa_feedback = context.get('qa_feedback', 'No specific feedback provided.')
            current_js = context.get('current_code', '// Current JavaScript code not provided.')
            prompt = f"""You are an expert JavaScript Specialist agent tasked with fixing JavaScript logic for the "{page_context_name}" section.
    The overall topic is "{topic}".
    You have received QA feedback on your previously generated JavaScript.
    Your goal is to update the current JavaScript code to address the feedback while still conforming to the original specifications.

    --- ORIGINAL SPECIFICATIONS (Review relevant JavaScript requirements for "{page_context_name}") ---
    {specs}
    --- SPECIFICATIONS END ---

    --- QA FEEDBACK ---
    {qa_feedback}
    --- QA FEEDBACK END ---

    --- CURRENT JAVASCRIPT CODE TO FIX ---
    {current_js}
    --- CURRENT JAVASCRIPT CODE END ---

    Generate ONLY the corrected JavaScript code needed to address the feedback. Do not include any additional text or formatting.
    """
            return prompt.strip()

        else:
            logger.warning(f"{self.agent_id}: get_prompt called with unknown task_type: {task_type}")
            return None


    async def _decide_next_action(self) -> Optional[Dict[str, Any]]:
        """Decides action based on current task (generate or fix JS)."""
        if not self.current_task:
            return {'action': 'wait'}

        task_id = self.current_task.get('task_id')
        if not task_id:
             logger.error(f"{self.agent_id}: Current task has no ID"); return {'action': 'wait'}

        context = self.task_context.setdefault(task_id, {'step': 'start'})
        task_type = self.current_task.get('task_type')
        details = self.current_task.get('details', {})

        # Check for error state
        if context.get('generation_failed') or context.get('fix_failed'):
            return {'action': 'fail_task', 'error': context.get('error_details', 'JavaScript generation/fix failed previously')}

        # --- Generate JS Flow ---
        if task_type == 'generate_js':
            # Wait for HTML context if needed
            if not context.get('html_structure') and not context.get('prompt_generated'):
                # [ Existing wait/timeout logic for HTML structure ]
                wait_start = context.get('wait_start_time')
                if not wait_start:
                     context['wait_start_time'] = time.time(); self.task_context[task_id] = context
                     logger.info(f"{self.agent_id}: Waiting for HTML structure context for task {task_id}")
                else:
                    elapsed = time.time() - wait_start
                    if elapsed > 120: # Timeout
                        logger.warning(f"{self.agent_id}: Timed out waiting for HTML after {elapsed:.1f}s")
                        context['html_structure'] = "/* Fallback - HTML structure not received */"; logger.info(f"{self.agent_id}: Using fallback HTML to proceed")
                    elif not context.get('last_wait_log') or time.time() - context.get('last_wait_log') > 30:
                        logger.info(f"{self.agent_id}: Still waiting for HTML structure for {elapsed:.1f}s"); context['last_wait_log'] = time.time()
                if not context.get('html_structure'): return {'action': 'wait'} # Still waiting

            # Call LLM if ready
            if not context.get('llm_called'):
                prompt = self.get_prompt(self.current_task, context)
                if prompt:
                    context['llm_called'] = True; context['llm_call_time'] = time.time(); context['prompt_generated'] = True
                    self.task_context[task_id] = context
                    return {'action': 'use_llm', 'prompt': prompt}
                else: return {'action': 'fail_task', 'error': 'Could not generate JS generation prompt.'}

        # --- Fix JS Flow ---
        elif task_type == 'fix_js_logic':
             # Context (specs, feedback, current code) should be provided by Coder
            if not context.get('llm_called'):
                 # Verify necessary context exists
                 if not context.get('specifications_content') or not context.get('qa_feedback') or not context.get('current_js_code'):
                      # Wait briefly for context, then fail
                      if not context.get('fix_context_wait_start'):
                           context['fix_context_wait_start'] = time.time(); logger.warning(f"{self.agent_id}: Waiting for missing context for fix task {task_id}."); return {'action': 'wait'}
                      elif time.time() - context.get('fix_context_wait_start', time.time()) > 15:
                           logger.error(f"{self.agent_id}: Failed fix task {task_id} due to missing context after wait."); return {'action': 'fail_task', 'error': 'Missing context for JS fix.'}
                      else: return {'action': 'wait'}

                 prompt = self.get_prompt(self.current_task, context)
                 if prompt:
                      context['llm_called'] = True; context['llm_call_time'] = time.time()
                      self.task_context[task_id] = context
                      return {'action': 'use_llm', 'prompt': prompt}
                 else: return {'action': 'fail_task', 'error': 'Could not generate JS fix prompt.'}

        # --- Common: Completion/Waiting for LLM ---
        if context.get('code_generated') or context.get('fix_generated'):
            return {'action': 'complete_task', 'result': 'JavaScript generation/fix complete and sent.'}

        if context.get('llm_call_time') and not (context.get('code_generated') or context.get('fix_generated')):
            # [ Existing LLM timeout logic ]
            elapsed = time.time() - context.get('llm_call_time')
            if elapsed > 120: logger.warning(f"{self.agent_id}: LLM call timed out for task {task_id}"); return {'action': 'fail_task', 'error': 'LLM call timed out'}
            if not context.get('last_wait_log') or time.time() - context.get('last_wait_log') > 30:
                logger.info(f"{self.agent_id}: Waiting for LLM response for {elapsed:.1f}s (task {task_id})"); context['last_wait_log'] = time.time()

        # Default wait
        return {'action': 'wait'}


    async def _process_llm_response(self, llm_response: str):
        """Processes LLM response, includes original_coder_task_id in reply."""
        if not self.current_task or not self.current_task.get('task_id'): return
        task_id = self.current_task['task_id']
        context = self.task_context.get(task_id, {})
        task_type = context.get('task_type', self.current_task.get('task_type'))
        original_coder_task_id = context.get('original_coder_task_id')

        is_fix_task = 'fix_' in task_type if task_type else False
        log_prefix = "fix" if is_fix_task else "generation"
        logger.info(f"{self.agent_id}: Received LLM response for {log_prefix}.")

        # --- CORRECTED: Determine agent_type using self.role ---
        agent_type = 'unknown'
        # Check the agent's role attribute instead of using isinstance
        if self.role == "HTML Specialist":
            agent_type = 'html'
        elif self.role == "CSS Specialist":
            agent_type = 'css'
        elif self.role == "JavaScript Specialist":
            agent_type = 'js'
        # --- END CORRECTION ---

        # Check for LLM errors
        if llm_response.startswith("Error:"):
            logger.error(f"{self.agent_id}: LLM error detected: {llm_response}")
            error_type_msg = f'{agent_type}_fix_failed' if is_fix_task else f'{agent_type}_generation_failed'
            error_message = {'type': error_type_msg, 'original_coder_task_id': original_coder_task_id, 'error_message': llm_response, 'source_agent_id': self.agent_id, 'source_task_id': task_id}
            await self._send_message_to_agent(self.coder_lead_id, {'type': 'agent_message', 'message_data': error_message})
            context['generation_failed' if not is_fix_task else 'fix_failed'] = True
            context['error_details'] = llm_response; self.task_context[task_id] = context
            return

        processed_code = self._cleanup_llm_code_output(llm_response)

        # Handle specific cases (e.g., no JS needed)
        if agent_type == 'js' and processed_code.strip() == "// No JavaScript required.":
            processed_code = ""; logger.info(f"{self.agent_id}: LLM indicated no JavaScript required.")
        elif not processed_code.strip() and not is_fix_task: # Fallback for empty initial generation
             logger.warning(f"{self.agent_id}: Generated {agent_type} is empty during initial generation.")
             fallback_map = {'html': '<div>Error</div>', 'css': '/* Error */', 'js': '// Error'}
             processed_code = fallback_map.get(agent_type, '// Error')
             context['used_fallback'] = True

        # Store result and mark completion step
        if is_fix_task: context[f'fixed_{agent_type}'] = processed_code; context['fix_generated'] = True
        else: context[f'generated_{agent_type}'] = processed_code; context['code_generated'] = True

        # Prepare message to Coder
        message_data = {
            'original_coder_task_id': original_coder_task_id, # Include the ID retrieved from context
            'source_agent_id': self.agent_id,
            'source_task_id': task_id # Specialist's own task ID
        }
        # Use agent_type determined above for message type and code key
        if is_fix_task:
             message_data['type'] = f'updated_{agent_type}{"_styles" if agent_type == "css" else ("_logic" if agent_type == "js" else "_component")}_ready'
             message_data['component_type'] = f'{agent_type}{"_styles" if agent_type == "css" else ("_logic" if agent_type == "js" else "_structure")}'
             message_data['fixed_code'] = processed_code
             logger.info(f"{self.agent_id}: Sending updated {agent_type} back to {self.coder_lead_id}.")
        else: # Initial generation
             message_data['type'] = f'{agent_type}{"_styles" if agent_type == "css" else ("_logic" if agent_type == "js" else "_component")}_ready'
             message_data['component_name'] = context.get('component_name', 'unknown')
             # Use agent_type determined above for the code key
             message_data[f'{agent_type}_code'] = processed_code
             logger.info(f"{self.agent_id}: Sending initial {agent_type} back to {self.coder_lead_id}.")

        await self._send_message_to_agent(self.coder_lead_id, {'type': 'agent_message', 'message_data': message_data})
        self.update_state({'current_action': 'message_sent'})
        self.task_context[task_id] = context

    async def _process_tool_result(self, tool_name: str, result: Any):
        logger.warning(f"{self.agent_id} does not use tools, but received result for {tool_name}")
        pass # JS agent likely doesn't use tools


    async def _handle_agent_specific_message(self, sender_id: str, message_data: Any):
        """Handles task assignment (create or fix) and context updates from Coder lead."""
        # ... (previous checks and type determination) ...
        if not isinstance(message_data, dict): logger.warning(f"{self.agent_id} received non-dict message from {sender_id}"); return
        msg_type = message_data.get('type'); logger.info(f"{self.agent_id}: Processing message type '{msg_type}' from {sender_id}")
        task_type_str = None; task_prefix = None
        # ...(task type mapping logic)...
        if msg_type == 'create_html_structure': task_type_str, task_prefix = 'generate_html', 'html_task'
        elif msg_type == 'create_css_styles': task_type_str, task_prefix = 'generate_css', 'css_task'
        elif msg_type == 'create_js_logic': task_type_str, task_prefix = 'generate_js', 'js_task'
        elif msg_type == 'fix_html_component': task_type_str, task_prefix = 'fix_html_component', 'html_fix'
        elif msg_type == 'fix_css_styles': task_type_str, task_prefix = 'fix_css_styles', 'css_fix'
        elif msg_type == 'fix_js_logic': task_type_str, task_prefix = 'fix_js_logic', 'js_fix'


        if task_type_str: # Handle Create or Fix Task
            new_task_id = f"{task_prefix}_{uuid.uuid4().hex[:8]}"

            # --- START CORRECTED EXTRACTION ---
            # Get the inner message_data dictionary sent by the Coder
            inner_message_data = message_data.get('message_data', {})
            # Now extract details, component_name, etc., from the inner dictionary
            details_dict = inner_message_data.get('details', {})
            component_name = inner_message_data.get('component_name', 'unknown_component') # Get from inner dict

            # Extract fields *from the details_dict*
            original_coder_task_id = details_dict.get('original_coder_task_id')
            original_request = details_dict.get('original_request') # Should now be correct
            specs = details_dict.get('specs')
            target_page_context = details_dict.get('target_page_context') # Also useful
            # --- END CORRECTED EXTRACTION ---

            # Logging should now show the correct request
            logger.info(f"{self.agent_id}: Creating new {task_type_str} task '{new_task_id}' for component '{component_name}' (Page: {target_page_context}), linked to coder task '{original_coder_task_id}'")
            logger.info(f"{self.agent_id}: Received original_request: '{original_request}'") # Verify this logs correctly now

            # *** Set context BEFORE assigning task ***
            context = self.task_context.setdefault(new_task_id, {})
            context['specifications_content'] = specs if specs else 'No specifications provided.'
            context['original_coder_task_id'] = original_coder_task_id
            context['original_request'] = original_request # Store the correctly extracted value
            context['component_name'] = component_name
            context['target_page_context'] = target_page_context # Store page context
            context['task_type'] = task_type_str
            # ... (add fix-specific context if needed) ...
            if 'fix_' in task_type_str:
                 context['qa_feedback'] = inner_message_data.get('qa_feedback', 'No feedback provided.') # Get from inner_message_data
                 context['current_code'] = inner_message_data.get('current_code', '') # Get from inner_message_data

            if task_type_str in ['generate_css', 'generate_js']: context['status'] = 'waiting_for_html'
            logger.info(f"{self.agent_id}: Context CREATED for task {new_task_id}. Keys: {list(context.keys())}")
            # --- End Context Setting ---

            # Assign task using the details received
            task_to_assign = {
                'task_id': new_task_id,
                'description': f"{'Generate' if 'generate' in task_type_str else 'Fix'} {task_prefix.split('_')[0].upper()} ... from {sender_id}",
                'task_type': task_type_str,
                'details': details_dict, # Pass the original details dict - Base Agent will re-extract if needed
                'assigned_to_role': self.role
            }
            await self.assign_task(task_to_assign) # Base Agent assign_task will log extraction again
            logger.info(f"{self.agent_id}: Assigned task {new_task_id} to self")

            # ... (Send acknowledgment) ...
            ack_message = {'type': 'task_received', 'new_task_id': new_task_id, 'original_coder_task_id': original_coder_task_id, 'status': 'processing'}
            try: await self._send_message_to_agent(self.coder_lead_id, {'type': 'agent_message', 'message_data': ack_message})
            except Exception as e: logger.error(f"{self.agent_id}: Failed to send acknowledgment: {e}")


        elif msg_type == 'update_task_context':
             # ... (Existing update_task_context logic - should work now if task ID is stored correctly) ...
            original_coder_task_id_from_update = message_data.get('original_coder_task_id'); html_content = message_data.get('html_code')
            logger.info(f"{self.agent_id}: Received HTML update for original task ID '{original_coder_task_id_from_update}'")
            if not original_coder_task_id_from_update or html_content is None: logger.warning(f"{self.agent_id}: Invalid context update message: {message_data}"); return
            target_task_id = None
            for tid, ctx in self.task_context.items():
                if isinstance(ctx, dict) and ctx.get('original_coder_task_id') == original_coder_task_id_from_update:
                    target_task_id = tid; logger.info(f"{self.agent_id}: Found matching task '{target_task_id}' for context update."); break
            if target_task_id:
                context = self.task_context[target_task_id]
                if context.get('status') == 'waiting_for_html':
                    context['html_structure'] = html_content; context['status'] = 'html_received'
                    logger.info(f"{self.agent_id}: Updated task '{target_task_id}' context with HTML.")
                    self.task_context[target_task_id] = context
                    if self.current_task and self.current_task.get('task_id') == target_task_id and self.get_state('current_action') == 'waiting': self.update_state({'current_action': 'html_context_received'})
                else: logger.warning(f"{self.agent_id}: Received HTML update for task '{target_task_id}', but status was '{context.get('status')}' not 'waiting_for_html'. Ignoring update.")
            else: logger.warning(f"{self.agent_id}: No matching task found for context update with original_coder_task_id '{original_coder_task_id_from_update}'.")

        else:
            logger.warning(f"{self.agent_id} received unhandled message type '{msg_type}' from {sender_id}")



    # --- Helper Methods ---
    async def _trigger_llm_call(self, task_id: str, prompt: str):
        """Helper to trigger LLM call, adapting thought based on task"""
        try:
            task_type = self.task_context.get(task_id, {}).get('task_type', 'unknown')
            action_desc = "Generating" if task_type == 'generate_js' else "Fixing"
            self.update_state({'current_action': 'calling_llm', 'current_thoughts': f'{action_desc} JS for task {task_id}'})
            await self.execute_action({'action': 'use_llm', 'prompt': prompt})
        except Exception as e:
            logger.error(f"{self.agent_id}: Error triggering LLM call: {e}", exc_info=True)
            if task_id in self.task_context:
                 self.task_context[task_id]['llm_error'] = str(e)
                 self.task_context[task_id]['generation_failed' if task_type == 'generate_js' else 'fix_failed'] = True


    def _cleanup_llm_code_output(self, raw_output: str) -> str:
        # [ Existing cleanup logic - seems okay ]
        cleaned = raw_output.strip(); cleaned = re.sub(r'^```(?:javascript|js)?\s*\n', '', cleaned, flags=re.MULTILINE); cleaned = re.sub(r'\n```\s*$', '', cleaned)
        cleaned = re.sub(r'<script[^>]*>|</script>', '', cleaned) # Remove script tags
        return cleaned.strip()

    # --- ADDED HELPER (copy from Coder/CSS Agent) ---
    async def _send_message_to_agent(self, target_agent_id: str, message_data: Any):
        """Helper to send message via broadcast callback, ensuring proper structure."""
        # Pass the actual message data directly to the base class sender
        await super()._send_message_to_agent(target_agent_id, message_data)
        # Base class's sender handles logging and exceptions
        # We can update state here if needed *after* the send is attempted
        self.update_state({'current_action': 'message_sent'})