# SoftwareSim3d/src/agents/html_agent.py

import asyncio
import logging
import re
import time
from typing import Optional, Dict, Any, Callable, Awaitable, Tuple
import uuid
# --- CORRECTED IMPORT ---
from ..agent_base import Agent, STATUS_IDLE, STATUS_WORKING # Import base and statuses

logger = logging.getLogger(__name__)

class HTMLAgent(Agent):
    """Specialized agent focusing on HTML structure generation and fixes."""
    def __init__(self, agent_id, role, *args, **kwargs):
        # --- CORRECTED INIT --- Ensure necessary base class args are passed
        super().__init__(agent_id=agent_id, role=role, *args, **kwargs)
        self.coder_lead_id = kwargs.get('coder_lead_id', 'coder-01')
        logger.info(f"HTMLAgent {self.agent_id} initialized, reporting to {self.coder_lead_id}.")


    def get_prompt(self, task_details: Dict[str, Any], context: Dict[str, Any]) -> Optional[str]:
        """Generates the prompt for the LLM based on task type (generate or fix HTML)."""
        task_type = task_details.get('task_type')
        specs = context.get('specifications_content', 'No specifications provided.')
        
        # Get the page context name; use a fallback if not provided.
        page_context_name = task_details.get('target_page_context', 'the webpage')
        
        # Safely extract original_request from context,
        # using a fallback if the value is None or empty.
        original_request = context.get('original_request') or '[Original request not provided]'
        
        # Attempt to extract the topic by splitting on "about".
        # (If "about" is not found, use a fallback string.)
        topic = original_request.split("about")[-1].strip() if "about" in original_request else "the requested topic"
        
        logger.info(f"{self.agent_id}: Generating HTML prompt for page '{page_context_name}' on topic '{topic}'")
        
        if task_type == 'generate_html':
            prompt = f"""You are an expert HTML Specialist agent creating the initial HTML structure for a specific webpage section or page within a larger web application.
        The original user request topic was: "{topic}"
        The specific page/section you are building is: "{page_context_name}"

        I am providing you with detailed specifications for this project. Your task is to:
        1. Carefully read the specifications, focusing on sections relevant to "{page_context_name}".
        2. Generate the HTML structure precisely as specified for "{page_context_name}" (sections, IDs, classes, semantic tags).
        3. **Crucially:** Populate the generated structure with relevant *placeholder content* (headings, paragraphs, list items, image alt text, etc.) specifically about **{topic}** and relevant to **{page_context_name}**. Do NOT use generic placeholders. Use specific placeholders (e.g., "About Our Car Site", "Contact Form", "Sedan Specifications Section", "Image of a Blue Sedan").

        --- SPECIFICATIONS START (Review relevant sections for "{page_context_name}") ---
        {specs}
        --- SPECIFICATIONS END ---

        Your goal is to create the specific HTML structure for "{page_context_name}" defined in the specs, filled with *topic-specific* placeholder content.

        Respond ONLY with the raw HTML code for the requested structure. Do NOT include any CSS, JavaScript, <style>, <script>, <!DOCTYPE>, <html>, <head>, or <body> tags. Start directly with the first structural element relevant to "{page_context_name}".
        """
            return prompt.strip()

        elif task_type == 'fix_html_component':
            qa_feedback = context.get('qa_feedback', 'No specific feedback provided.')
            current_html = context.get('current_code', '')  # Use 'current_code' from Coder delegation
            prompt = f"""You are an expert HTML Specialist agent fixing the structure of a web application component for the page/section: "{page_context_name}".
        The original user request topic was: "{topic}"
        You previously generated HTML which has received feedback from QA. Your task is to fix the HTML based on the feedback and original specifications, ensuring content remains relevant to **{topic}** and the **{page_context_name}**.

        --- ORIGINAL SPECIFICATIONS (Review relevant sections for "{page_context_name}") ---
        {specs}
        --- SPECIFICATIONS END ---

        --- QA FEEDBACK ---
        {qa_feedback}
        --- QA FEEDBACK END ---

        --- CURRENT HTML CODE TO FIX ---
        {current_html}
        --- CURRENT HTML CODE END ---

        Please review the QA feedback, original specs, and current HTML structure.
        Your task is to generate ONLY the corrected HTML structure section(s) or the full corrected structure needed to address the QA feedback for "{page_context_name}", adhering to the original specifications and ensuring placeholders are relevant to **{topic}**.
        - Focus only on the structural/semantic issues mentioned in the QA feedback.
        - Ensure corrected code is valid HTML relevant to **{topic}** and **{page_context_name}**.
        - Do NOT use generic placeholders.

        Do NOT include: Any CSS, JavaScript, <style>, <script>, <!DOCTYPE>, <html>, <head>, or <body> tags.
        Respond ONLY with the raw corrected HTML structure. If no changes are needed, respond with the original HTML code.
        """
            return prompt.strip()

        else:
            logger.warning(f"{self.agent_id}: get_prompt called with unknown task_type: {task_type}")
            return None



    async def _decide_next_action(self) -> Optional[Dict[str, Any]]:
        """Decides action based on current task (generate or fix HTML)."""
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
            return {'action': 'fail_task', 'error': context.get('error_details', 'HTML generation/fix failed previously')}

        # --- Generate or Fix HTML Flow ---
        # HTML agent doesn't wait for other components' context.
        if task_type in ['generate_html', 'fix_html_component']:
            # Call LLM if ready
            if not context.get('llm_called'):
                 # Verify necessary context exists (especially for fixes)
                 if task_type == 'fix_html_component':
                      # --- Corrected context key ---
                      if not context.get('specifications_content') or not context.get('qa_feedback') or not context.get('current_html_code'):
                           # Wait briefly for context, then fail
                           if not context.get('fix_context_wait_start'):
                                context['fix_context_wait_start'] = time.time(); logger.warning(f"{self.agent_id}: Waiting for missing context for fix task {task_id}."); return {'action': 'wait'}
                           elif time.time() - context.get('fix_context_wait_start', time.time()) > 15:
                                logger.error(f"{self.agent_id}: Failed fix task {task_id} due to missing context after wait."); return {'action': 'fail_task', 'error': 'Missing context for HTML fix.'}
                           else: return {'action': 'wait'}

                 prompt = self.get_prompt(self.current_task, context)
                 if prompt:
                     context['llm_called'] = True; context['llm_call_time'] = time.time()
                     self.task_context[task_id] = context
                     return {'action': 'use_llm', 'prompt': prompt}
                 else: return {'action': 'fail_task', 'error': f'Could not generate prompt for {task_type}.'}

        # --- Common: Completion/Waiting for LLM ---
        if context.get('code_generated') or context.get('fix_generated'):
            return {'action': 'complete_task', 'result': 'HTML generation/fix complete and sent.'}

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
        pass # HTML agent likely doesn't use tools

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
            action_desc = "Generating" if task_type == 'generate_html' else "Fixing"
            self.update_state({'current_action': 'calling_llm', 'current_thoughts': f'{action_desc} HTML for task {task_id}'})
            await self.execute_action({'action': 'use_llm', 'prompt': prompt})
        except Exception as e:
            logger.error(f"{self.agent_id}: Error triggering LLM call: {e}", exc_info=True)
            if task_id in self.task_context:
                 self.task_context[task_id]['llm_error'] = str(e)
                 self.task_context[task_id]['generation_failed' if task_type == 'generate_html' else 'fix_failed'] = True


    def _cleanup_llm_code_output(self, raw_output: str) -> str:
        # [ Existing cleanup logic - seems okay ]
        cleaned = raw_output.strip(); cleaned = re.sub(r'^```(?:html)?\s*\n', '', cleaned, flags=re.MULTILINE); cleaned = re.sub(r'\n```\s*$', '', cleaned)
        if cleaned.startswith("<html") and not cleaned.lower().startswith("<!doctype"):
            logger.info(f"{self.agent_id}: Removing full HTML wrapper from LLM output.")
            body_match = re.search(r'<body[^>]*>(.*?)</body>', cleaned, re.DOTALL);
            if body_match: cleaned = body_match.group(1).strip()
        return cleaned.strip()

    # --- ADDED HELPER (copy from Coder/CSS Agent) ---
    async def _send_message_to_agent(self, target_agent_id: str, message_data: Any):
        """Helper to send message via broadcast callback, ensuring proper structure."""
        # Pass the actual message data directly to the base class sender
        await super()._send_message_to_agent(target_agent_id, message_data)
        # Base class's sender handles logging and exceptions
        # We can update state here if needed *after* the send is attempted
        self.update_state({'current_action': 'message_sent'})