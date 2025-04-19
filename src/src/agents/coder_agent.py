# SoftwareSim3d/src/agents/coder_agent.py
# REWRITTEN VERSION (v2 - Fixing Abstract Method Error)

import asyncio
import logging
import re
import json
from typing import Optional, Dict, Any, Callable, Awaitable, Tuple, Set, List
import os
import time
import datetime
import uuid

# --- Assume Base Agent and Task imports are correct ---
from ..agent_base import Agent, STATUS_IDLE, STATUS_WORKING, STATUS_MOVING_TO_ZONE, STATUS_FAILED
from ..simulation.task import Task

logger = logging.getLogger(__name__)

DEFAULT_DEPENDENCY_TIMEOUT = 180 # Increased timeout
MAX_LLM_ATTEMPTS = 3
DEFAULT_CODE_FILENAME_BASE = "generated_code"
DEFAULT_CODE_EXT = ".html"
CODER_DESK_ZONE_NAME = "CODER_DESK"
SAVE_ZONE_NAME = "SAVE_ZONE"

# Required components for a page
REQUIRED_COMPONENTS = ['html_structure', 'css_styles', 'js_logic']

class CoderAgent(Agent):
    def __init__(self,
                 agent_id: str,
                 role: str,
                 message_queue: asyncio.Queue,
                 broadcast_callback: Callable[[Dict[str, Any]], Awaitable[None]],
                 loop: asyncio.AbstractEventLoop,
                 initial_position: Tuple[float, float, float],
                 target_desk_position: Tuple[float, float, float],
                 **kwargs):
        super().__init__(
            agent_id=agent_id, role=role, message_queue=message_queue,
            broadcast_callback=broadcast_callback, loop=loop, initial_position=initial_position,
            target_desk_position=target_desk_position, llm_service=kwargs.get('llm_service'),
            llm_type=kwargs.get('llm_type'), llm_model_name=kwargs.get('llm_model_name'),
            available_tools=kwargs.get('available_tools'), required_tool_zones=kwargs.get('required_tool_zones'),
            zone_coordinates_map=kwargs.get('zone_coordinates_map')
        )

        self.ceo_agent_id = kwargs.get('ceo_agent_id', "ceo-01")
        self.qa_agent_id = kwargs.get('qa_agent_id', "qa-01")
        self.html_agent_id = kwargs.get('html_agent_id', 'html-01')
        self.css_agent_id = kwargs.get('css_agent_id', 'css-01')
        self.js_agent_id = kwargs.get('js_agent_id', 'js-01')

        if not hasattr(self, 'zone_coordinates'): self.zone_coordinates = {}; logger.warning(f"{self.agent_id}: Initializing empty zone_coordinates.")
        if CODER_DESK_ZONE_NAME not in self.zone_coordinates: self.zone_coordinates[CODER_DESK_ZONE_NAME] = target_desk_position; logger.warning(f"Added {CODER_DESK_ZONE_NAME} position.")
        if SAVE_ZONE_NAME not in self.zone_coordinates: save_zone = (35, 0.1, -25); logger.warning(f"Using default {SAVE_ZONE_NAME} position: {save_zone}"); self.zone_coordinates[SAVE_ZONE_NAME] = save_zone

        logger.info(f"CoderAgent {self.agent_id} (Coordinator) initialized. Team: {self.html_agent_id}, {self.css_agent_id}, {self.js_agent_id}.")

    # --- Helper Methods (Sanitize, Get Zone Position, Send, etc.) ---
    def get_zone_position(self, zone_name: str) -> Optional[Tuple[float, float, float]]:
        """Gets coordinates for a named zone."""
        if hasattr(self, 'zone_coordinates') and self.zone_coordinates is not None:
            return self.zone_coordinates.get(zone_name)
        logger.error(f"{self.agent_id}: 'zone_coordinates' missing or None.")
        return None

    def _sanitize_filename(self, name: str) -> str:
        """Removes or replaces characters unsafe for filenames/paths."""
        if not isinstance(name, str): name = "invalid_name"
        name = name.replace("\\", "/") # Normalize slashes
        # Remove problematic characters for filenames/directory names
        name = re.sub(r'[<>:"|?*]+', '', name)
        # Replace whitespace sequences with a single underscore
        name = re.sub(r'\s+', '_', name)
        # Remove leading/trailing underscores/slashes after replacements
        name = name.strip('_/')
        # Optional: Limit component length if needed
        max_len = 60
        if len(name) > max_len: name = name[:max_len]
        # Handle empty names after sanitization
        if not name: name = "sanitized_empty_name"
        # logger.debug(f"{self.agent_id} Sanitized path component: '{name}'") # Optional debug
        return name

    async def send_dependency_to_specialist(self, specialist_role: str, component_data: Dict[str, Any]):
        """Formats and sends a task message to a specialist."""
        role_map = {
            "HTML Specialist": (self.html_agent_id, 'create_html_structure'),
            "CSS Specialist": (self.css_agent_id, 'create_css_styles'),
            "JavaScript Specialist": (self.js_agent_id, 'create_js_logic')
        }
        target_agent_id, message_type = role_map.get(specialist_role, (None, None))

        if not target_agent_id or not message_type:
            logger.error(f"{self.agent_id}: Cannot find agent or message type for role '{specialist_role}'.")
            return

        # Wrap the component_data inside a 'message_data' key as expected by the base message handler
        message_payload = {"type": message_type, "message_data": component_data}
        await self._send_message_to_agent(target_agent_id, message_payload) # Use the inherited sender
        logger.info(f"{self.agent_id}: Sent dependency message '{message_type}' to {specialist_role} ({target_agent_id}).")

    async def _send_message_to_agent(self, target_agent_id: str, message_data: Any):
        """Helper to send message via broadcast callback, ensuring proper structure."""
        # Pass the actual message data directly to the base class sender
        await super()._send_message_to_agent(target_agent_id, message_data)
        # Base class's sender handles logging and exceptions
        # We can update state here if needed *after* the send is attempted
        self.update_state({'current_action': 'message_sent'})

    async def _fail_task_with_error(self, error_msg: str):
        """Helper to consistently fail the current task."""
        logger.error(f"{self.agent_id}: {error_msg}")
        if self.current_task:
            task_id = self.current_task.get('task_id')
            if task_id and task_id in self.task_context:
                self.task_context[task_id]['step'] = 'error'
                self.task_context[task_id]['error_details'] = error_msg
            await self.execute_action({'action': 'fail_task', 'error': error_msg})
        else:
            self.update_state({'status': STATUS_FAILED, 'last_error': error_msg})

    # --- Overridden Abstract Methods ---

    def get_prompt(self, task_details: Dict[str, Any], context: Dict[str, Any]) -> Optional[str]:
        # Coder delegates prompt generation to specialists
        logger.debug(f"{self.agent_id}: get_prompt called, but Coder delegates this.")
        return None

    async def _process_llm_response(self, llm_response: str):
        # Coder delegates LLM calls
        logger.warning(f"{self.agent_id}: _process_llm_response called unexpectedly.")
        self.update_state({'current_action': 'processed_llm_response_ignored'})

    # --- Core Logic Rewrites ---

    async def assign_task(self, task: Dict[str, Any]):
        """Assigns a task, ensuring context initialization for multi-page structure."""
        task_id = task.get('task_id', f"task_{uuid.uuid4().hex[:8]}")
        task['task_id'] = task_id # Ensure task has an ID

        logger.info(f"Agent {self.agent_id} received raw task data for task_id {task_id}: {task}")

        if self.current_task and self.current_task.get('task_id') == task_id:
            logger.warning(f"Agent {self.agent_id} re-assigned same task {task_id}. Ignoring.")
            return

        if self.get_state('status') != STATUS_IDLE:
            logger.warning(f"Agent {self.agent_id} received task {task_id} while status is '{self.get_state('status')}'. Overwriting current task.")
            if self.current_task:
                old_task_id = self.current_task.get('task_id')
                if old_task_id and old_task_id != task_id and old_task_id in self.task_context:
                    logger.info(f"Cleaning up context for overwritten task {old_task_id}")
                    del self.task_context[old_task_id]

        self.current_task = task
        logger.info(f"Agent {self.agent_id} assigned Task: {task_id} - {task.get('description','No Description')}")

        # --- Initialize/Reset context with multi-page structures ---
        context = self.task_context.setdefault(task_id, {})
        context['step'] = 'start'
        context['page_specs'] = {}           # Stores {'page_name': {'filename': str, 'received': bool, 'read': bool, 'content': str}}
        context['page_components'] = {}      # Stores {'page_name': {'delegated': bool, 'delegation_time': float, 'received_components': {comp_key: code}, 'assembled': bool, 'saved': bool, 'files_to_save_map': {rel_path: content}, 'saved_files_map': {rel_path: bool}}}
        context['ordered_page_names'] = []   # Stores page names in the order they should be built
        context['current_page_index'] = 0    # Index for ordered_page_names
        context['pending_pages'] = []        # Queue for specs arriving out of order
        context['files_to_save_queue'] = [] # Queue for file saving actions { 'page_name': str, 'filename': str, 'content': str }
        context['last_log_time'] = 0         # For throttling logs
        context['notification_sent'] = None  # Reset notification status

        # Store details from the task assignment itself
        task_details = task.get('details', {})
        context['details'] = task_details
        context['original_request'] = task_details.get('original_request') # Ensure this is captured early
        context['project_name'] = task_details.get('project_name', f"Proj_{task_id[:4]}") # Generate project name if missing
        if not context['project_name']: context['project_name'] = f"Proj_{task_id[:4]}" # Ensure not empty

        logger.info(f"Task {task_id} context for Agent {self.agent_id} INITIALIZED. Keys: {list(context.keys())}")
        self.task_context[task_id] = context # Save initialized context
        # --- End context initialization ---

        self.update_state({
            'status': STATUS_WORKING, 'progress': 0.0, 'last_error': None,
            'current_action': 'starting_task', 'current_idle_sub_state': None,
            'state_timer': 0.0, 'wait_start_time': None
        })

    async def _handle_agent_specific_message(self, sender_id: str, message_data: Any):
        """Handles specs ready, QA feedback, or component ready/updated messages."""
        logger.info(f"DEBUG CODER HANDLER: Received from {sender_id}. Message Data: {message_data}")

        if not isinstance(message_data, dict):
            logger.warning(f"{self.agent_id} received non-dict message from {sender_id}")
            return

        # Look for the actual message data if it's wrapped (common pattern)
        inner_message_data = message_data
        if message_data.get('type') == 'agent_message' and 'message_data' in message_data:
             inner_message_data = message_data.get('message_data', {})
             if not isinstance(inner_message_data, dict): # Handle potential nesting issues
                 logger.error(f"Could not extract inner message_data dict from {sender_id}. Data: {message_data}")
                 return
        msg_type = inner_message_data.get('type')
        logger.info(f"{self.agent_id}: Processing message type '{msg_type}' from {sender_id}.")

        if msg_type == 'task_dependency_ready' and inner_message_data.get('dependency_type') == 'specifications':
            saved_filename = inner_message_data.get('saved_filename')
            pm_details = inner_message_data.get('details', {})
            originating_ceo_task_id_from_pm = pm_details.get('originating_task_id')
            page_name = pm_details.get('page_name', 'main_page') # Default if PM doesn't specify
            original_request = pm_details.get('original_request')

            logger.info(f"{self.agent_id}: Received specs notification from {sender_id} for page '{page_name}' (File: {saved_filename}, OrigCEO: {originating_ceo_task_id_from_pm})")

            # Find the Coder's task context associated with this originating CEO task
            target_coder_task_id = None
            if originating_ceo_task_id_from_pm:
                for tid, ctx in self.task_context.items():
                    # Match based on the CEO's originating task ID stored in the Coder's task details
                    if isinstance(ctx, dict) and ctx.get('details', {}).get('originating_task_id') == originating_ceo_task_id_from_pm:
                        target_coder_task_id = tid
                        logger.info(f"{self.agent_id}: Found matching Coder task '{target_coder_task_id}' for specs notification.")
                        break
            else:
                logger.warning(f"{self.agent_id}: Specs notification from PM did not contain originating CEO task ID.")
                # Try to use the *current* task if it's active and waiting for specs
                if self.current_task and self.task_context.get(self.current_task['task_id'], {}).get('step') == 'wait_for_first_spec':
                    target_coder_task_id = self.current_task.get('task_id')
                    logger.warning(f"{self.agent_id}: Using current task '{target_coder_task_id}' as target for specs notification.")

            if not target_coder_task_id:
                logger.warning(f"{self.agent_id}: Could not determine a target task context for specs notification. Ignoring.")
                return

            context = self.task_context.setdefault(target_coder_task_id, {})
            context.setdefault('page_specs', {})
            context.setdefault('ordered_page_names', [])
            context.setdefault('pending_pages', [])

            # Store the original request if it's not already set in the main context
            if original_request and not context.get('original_request'):
                context['original_request'] = original_request
                logger.info(f"{self.agent_id}: Stored original request in context for task {target_coder_task_id}.")

            # Check if this page's specs are already being processed or are queued
            current_page_index = context.get('current_page_index', 0)
            ordered_page_names = context.get('ordered_page_names', [])
            is_current_page = current_page_index < len(ordered_page_names) and \
                              ordered_page_names[current_page_index] == page_name
            is_already_ordered = page_name in context['ordered_page_names']
            is_pending = any(p.get('page_name') == page_name for p in context['pending_pages'])

            if is_already_ordered and context['page_specs'].get(page_name, {}).get('received'):
                logger.warning(f"{self.agent_id}: Received duplicate specs notification for page '{page_name}' in task {target_coder_task_id}. Ignoring.")
                return

            # Determine if this page should be processed now or queued
            # Process now if queue is empty and agent is idle/starting OR if it's the next expected page
            should_process_now = (not ordered_page_names and current_page_index == 0) or \
                                 (len(ordered_page_names) == current_page_index) # Add if no pages ordered yet or if we're at the end awaiting the next


            if should_process_now and not is_already_ordered:
                context['ordered_page_names'].append(page_name)
                context['page_specs'][page_name] = {'filename': saved_filename, 'received': True, 'read': False}
                context.pop('wait_start_time_for_any_specs', None) # Clear wait timer
                logger.info(f"{self.agent_id}: Added page '{page_name}' directly to ordered list (index {len(ordered_page_names)-1}) for task {target_coder_task_id}. Specs marked as received.")
                # Trigger state update if waiting
                if self.current_task and self.current_task.get('task_id') == target_coder_task_id and self.get_state('current_action') == 'waiting':
                     self.update_state({'current_action': 'processing_dependency', 'current_thoughts': f"Received specs for page {page_name}."})

            elif not is_already_ordered and not is_pending: # Queue it if working on a different page
                context['pending_pages'].append({'page_name': page_name, 'filename': saved_filename, 'original_request': original_request})
                logger.info(f"{self.agent_id}: Queued specs for page '{page_name}' as pending for task {target_coder_task_id}.")

            elif is_pending:
                # Specs arrived for a page already in the pending queue (rare, but possible)
                logger.warning(f"{self.agent_id}: Received specs for page '{page_name}' which was already pending. Updating info.")
                for p in context['pending_pages']:
                    if p['page_name'] == page_name:
                        p['filename'] = saved_filename
                        break
            elif is_already_ordered and not context['page_specs'].get(page_name, {}).get('received'):
                # Specs arrived for a page that is ordered but wasn't marked received yet
                context['page_specs'].setdefault(page_name, {})['filename'] = saved_filename
                context['page_specs'][page_name]['received'] = True
                logger.info(f"{self.agent_id}: Marked existing ordered page '{page_name}' specs as received for task {target_coder_task_id}.")
                if self.current_task and self.current_task.get('task_id') == target_coder_task_id and self.get_state('current_action') == 'waiting':
                     self.update_state({'current_action': 'processing_dependency', 'current_thoughts': f"Received specs for page {page_name}."})


            self.task_context[target_coder_task_id] = context # Save updated context

        elif msg_type in ['html_component_ready', 'css_styles_ready', 'js_logic_ready',
                          'updated_html_component_ready', 'updated_css_styles_ready', 'updated_js_logic_ready']:
            original_coder_task_id_from_msg = inner_message_data.get('original_coder_task_id')
            source_agent = inner_message_data.get('source_agent_id', 'Unknown Specialist')

            if not original_coder_task_id_from_msg:
                logger.error(f"{self.agent_id}: Received component message from {source_agent} without 'original_coder_task_id'. Discarding.")
                return

            # Ensure the message is for the Coder's *current* active task
            if not self.current_task or self.current_task.get('task_id') != original_coder_task_id_from_msg:
                logger.warning(f"{self.agent_id}: Received component message from {source_agent} for non-active task '{original_coder_task_id_from_msg}'. Current task is '{self.current_task.get('task_id') if self.current_task else None}'. Ignoring message.")
                return

            task_id = original_coder_task_id_from_msg
            context = self.task_context.setdefault(task_id, {})
            current_page_index = context.get('current_page_index', 0)
            ordered_page_names = context.get('ordered_page_names', [])

            if not (0 <= current_page_index < len(ordered_page_names)):
                 logger.error(f"{self.agent_id}: Cannot process component message for task {task_id}. Invalid page index {current_page_index} for ordered pages {ordered_page_names}.")
                 return

            page_name = ordered_page_names[current_page_index]
            page_components_info = context.setdefault('page_components', {}).setdefault(page_name, {})
            received_components = page_components_info.setdefault('received_components', {})

            type_map = {
                'html_component_ready': ('html_structure', 'html_code', False),
                'css_styles_ready': ('css_styles', 'css_code', False),
                'js_logic_ready': ('js_logic', 'js_code', False),
                'updated_html_component_ready': ('html_structure', 'fixed_code', True),
                'updated_css_styles_ready': ('css_styles', 'fixed_code', True),
                'updated_js_logic_ready': ('js_logic', 'fixed_code', True)
            }

            if msg_type in type_map:
                component_key, code_key, is_update = type_map[msg_type]
                received_code = inner_message_data.get(code_key, "")

                # Store the received code
                received_components[component_key] = received_code
                log_prefix = "updated" if is_update else "initial"
                logger.info(f"{self.agent_id}: Received and stored {log_prefix} '{component_key}' for page '{page_name}' from {source_agent} for task {task_id}. Length: {len(received_code)}")

                # Update delegation status
                delegated_components = page_components_info.setdefault('delegated_components', {})
                if component_key in delegated_components:
                    delegated_components[component_key]['status'] = 'fix_received' if is_update else 'received'

                # Forward HTML immediately if it's the initial one
                if not is_update and component_key == 'html_structure':
                    # Use task_id and page_name from *this* context
                    await self._forward_html_to_dependents(task_id, page_name, received_code)

                # Check if ALL components for *this page* are now received
                all_initial_received = all(comp in received_components for comp in REQUIRED_COMPONENTS)
                logger.info(f"Component status for page '{page_name}': Received={list(received_components.keys())}. All initial received={all_initial_received}.")

                # If waiting for components and all are now present, update step
                if context.get('step') == f'waiting_for_components_{page_name}' and all_initial_received:
                    logger.info(f"{self.agent_id}: All initial components received for page '{page_name}'. Setting step to ready_to_assemble.")
                    context['step'] = 'ready_to_assemble' # Generic step for decision logic
                    page_components_info['needs_assembly_at_desk'] = True # Flag for decision logic
                    # Trigger state update if agent was waiting
                    if self.get_state('current_action') == 'waiting':
                         self.update_state({'current_action': f'received_all_components_{page_name}'})

                self.task_context[task_id] = context # Save context

            else:
                logger.warning(f"{self.agent_id}: Could not map message type '{msg_type}' to a component key.")

        elif msg_type == 'qa_feedback':
            logger.info(f"{self.agent_id}: Received QA feedback from {sender_id}")
            original_code_task_id = inner_message_data.get('original_code_task_id')
            if original_code_task_id and original_code_task_id in self.task_context:
                 fix_context = self.task_context[original_code_task_id]
                 fix_context['qa_feedback_details'] = inner_message_data.get('feedback')
                 fix_context['file_to_fix'] = inner_message_data.get('failed_code_filename') # File needing fix
                 fix_context['specifications_filename'] = inner_message_data.get('specifications_filename') # Specs for context
                 fix_context['step'] = 'needs_fix_delegation' # Trigger fix flow
                 self.task_context[original_code_task_id] = fix_context # Update original task context
                 logger.info(f"{self.agent_id}: Marked task {original_code_task_id} as needing fix delegation based on QA feedback.")
                 if self.current_task and self.current_task.get('task_id') == original_code_task_id:
                      self.update_state({'current_action': 'processing_qa_feedback'})
            else:
                logger.error(f"{self.agent_id}: Received QA feedback but couldn't find original task context for {original_code_task_id}")

        else:
            logger.warning(f"{self.agent_id} received unhandled agent msg type '{msg_type}' from {sender_id}")

    async def _forward_html_to_dependents(self, task_id: str, page_name: str, html_code: str):
        """Forwards the initial HTML structure to CSS and JS agents for the specified page."""
        context = self.task_context.get(task_id)
        if not context: logger.error(f"Cannot forward HTML, context missing for task {task_id}"); return
        page_components_info = context.get('page_components', {}).get(page_name)
        if not page_components_info: logger.error(f"Cannot forward HTML, component info missing for page {page_name}"); return
        delegations = page_components_info.get('delegated_components', {})

        logger.info(f"{self.agent_id}: Forwarding HTML for page '{page_name}' to CSS/JS specialists.")

        # Send update to CSS Agent
        css_info = delegations.get('css_styles')
        if css_info and css_info.get('status') == 'pending_html':
            css_agent_id = css_info.get('agent_id')
            if css_agent_id:
                css_update_msg = {
                    'type': 'update_task_context',
                    'original_coder_task_id': task_id, # Coder's main task ID
                    'component_name': f"{page_name}_styles",
                    'html_code': html_code
                }
                await self._send_message_to_agent(css_agent_id, {'type': 'agent_message', 'message_data': css_update_msg})
                css_info['status'] = 'pending_css' # Update status
                logger.info(f"Forwarded HTML to CSS agent {css_agent_id} for page '{page_name}'.")
            else: logger.warning(f"CSS agent ID missing for page '{page_name}'.")

        # Send update to JS Agent
        js_info = delegations.get('js_logic')
        if js_info and js_info.get('status') == 'pending_html':
            js_agent_id = js_info.get('agent_id')
            if js_agent_id:
                js_update_msg = {
                    'type': 'update_task_context',
                    'original_coder_task_id': task_id, # Coder's main task ID
                    'component_name': f"{page_name}_script",
                    'html_code': html_code
                }
                await self._send_message_to_agent(js_agent_id, {'type': 'agent_message', 'message_data': js_update_msg})
                js_info['status'] = 'pending_js' # Update status
                logger.info(f"Forwarded HTML to JS agent {js_agent_id} for page '{page_name}'.")
            else: logger.warning(f"JS agent ID missing for page '{page_name}'.")

        self.task_context[task_id] = context # Save context with updated statuses

    async def _handle_component_timeout(self, task_id: str, page_name: str):
        """Generates fallback content for missing components for a specific page."""
        context = self.task_context.get(task_id)
        if not context: return
        page_components_info = context.setdefault('page_components', {}).setdefault(page_name, {})
        received = page_components_info.setdefault('received_components', {})
        delegated = page_components_info.get('delegated_components', {})

        missing_components = [comp for comp in REQUIRED_COMPONENTS if comp not in received]
        logger.warning(f"{self.agent_id}: Timeout waiting for components {missing_components} for page '{page_name}' (Task: {task_id}). Using fallbacks.")

        if 'html_structure' not in received:
            received['html_structure'] = f"<div><h1>Fallback HTML for {page_name}</h1><p>Component timed out.</p></div>"
            logger.info(f"Created fallback HTML for {page_name}")
        if 'css_styles' not in received:
            received['css_styles'] = f"/* Fallback CSS for {page_name}: Component timed out */"
            logger.info(f"Created fallback CSS for {page_name}")
        if 'js_logic' not in received:
            received['js_logic'] = f"// Fallback JS for {page_name}: Component timed out."
            logger.info(f"Created fallback JS for {page_name}")

        # Mark all delegated components as 'received' (even if via fallback)
        for comp_key in delegated:
            if comp_key in missing_components:
                delegated[comp_key]['status'] = 'received_fallback'

        # Update the main context step to allow assembly
        context['step'] = 'ready_to_assemble'
        page_components_info['needs_assembly_at_desk'] = True
        self.task_context[task_id] = context
        logger.info(f"{self.agent_id}: Applied fallbacks and set step to 'ready_to_assemble' for page '{page_name}'.")

    async def _coordinate_code_development(self, page_name: str):
        """Delegates coding tasks for a specific page to specialist agents (HTML, CSS, JS)."""
        if not self.current_task or not self.current_task.get('task_id'):
            logger.error(f"{self.agent_id}: Cannot coordinate, no current task or task ID.")
            return
        task_id = self.current_task['task_id']
        context = self.task_context.setdefault(task_id, {})
        page_specs_info = context.get('page_specs', {}).get(page_name, {})
        specs_content = page_specs_info.get('content')

        # Ensure original request is available in context.
        original_request = context.get('original_request')
        if not original_request:
            error_msg = f"Cannot coordinate: original_request missing from context for task {task_id}."
            logger.error(f"{self.agent_id}: {error_msg}")
            await self._fail_task_with_error(error_msg)
            return

        if not specs_content:
            await self._fail_task_with_error(f"Cannot coordinate development for page '{page_name}' (Task: {task_id}) without specifications content.")
            return

        logger.info(f"{self.agent_id}: Coordinating specialists for page '{page_name}' (Task: {task_id}) based on request: '{original_request[:50]}...'")

        # Initialize page-specific component tracking.
        page_components_info = context.setdefault('page_components', {}).setdefault(page_name, {})
        page_components_info['delegated_components'] = {}
        page_components_info['received_components'] = {}

        if page_components_info.get('delegated'):
            logger.warning(f"{self.agent_id}: Delegation for page '{page_name}' (Task {task_id}) already attempted. Skipping.")
            return

        # Build dependency details.
        component_details = {
            'original_coder_task_id': task_id, # Crucial for specialists to report back to the right task
            'original_request': original_request,
            'specs': specs_content,
            'target_page_context': page_name # Helps specialists focus
        }

        # Delegate tasks sequentially or based on dependencies.
        # Delegate HTML first.
        logger.info(f"{self.agent_id}: Delegating HTML for page '{page_name}' to {self.html_agent_id}")
        html_msg_data = {'component_name': f"{page_name}_structure", 'details': component_details}
        await self.send_dependency_to_specialist("HTML Specialist", html_msg_data)
        page_components_info['delegated_components']['html_structure'] = {'status': 'pending', 'agent_id': self.html_agent_id}

        # CSS and JS depend on HTML, mark them as pending_html.
        logger.info(f"{self.agent_id}: Delegating CSS styles for page '{page_name}' to {self.css_agent_id}")
        css_msg_data = {'component_name': f"{page_name}_styles", 'details': component_details}
        await self.send_dependency_to_specialist("CSS Specialist", css_msg_data)
        page_components_info['delegated_components']['css_styles'] = {'status': 'pending_html', 'agent_id': self.css_agent_id}

        logger.info(f"{self.agent_id}: Delegating JS logic for page '{page_name}' to {self.js_agent_id}")
        js_msg_data = {'component_name': f"{page_name}_script", 'details': component_details}
        await self.send_dependency_to_specialist("JavaScript Specialist", js_msg_data)
        page_components_info['delegated_components']['js_logic'] = {'status': 'pending_html', 'agent_id': self.js_agent_id}

        page_components_info['delegated'] = True
        page_components_info['delegation_time'] = time.time()
        context['step'] = f'waiting_for_components_{page_name}' # Update state
        self.task_context[task_id] = context
        self.update_state({'current_action': f'coordinating_{page_name}'})

    async def _assemble_final_code(self, page_name: str):
        """Assembles components into final files for a specific page."""
        if not self.current_task or not self.current_task.get('task_id'): return
        task_id = self.current_task['task_id']; context = self.task_context.get(task_id)
        if not context: return

        page_components_info = context.get('page_components', {}).get(page_name)
        if not page_components_info:
            logger.error(f"{self.agent_id}: Cannot assemble code for page '{page_name}', component info missing.")
            return

        components = page_components_info.get('received_components', {})
        details = context.get('details', {}) # Use context details

        html_code = components.get('html_structure', f"")
        # Assume shared CSS/JS, get from the first page's context if available
        first_page_name = context.get('ordered_page_names', [page_name])[0]
        css_code = context.get('page_components', {}).get(first_page_name, {}).get('received_components', {}).get('css_styles', '/* CSS styles missing */')
        js_code = context.get('page_components', {}).get(first_page_name, {}).get('received_components', {}).get('js_logic', '// JavaScript logic missing')

        project_name = context.get('project_name', 'default_project')
        sanitized_project = self._sanitize_filename(project_name)
        sanitized_page = self._sanitize_filename(page_name)

        # Define filenames relative to project root/output
        coder_output_dir = f"{sanitized_project}/Coder"
        html_filename_rel = f"{coder_output_dir}/{sanitized_page}.html"
        # Generate unique-ish names for shared CSS/JS based on first page info
        css_filename_rel = f"{coder_output_dir}/css/style_{task_id[:8]}.css"
        js_filename_rel = f"{coder_output_dir}/js/script_{task_id[:8]}.js"

        # Relative paths for linking within THIS specific HTML file
        css_link_path = f"css/{os.path.basename(css_filename_rel)}"
        js_link_path = f"js/{os.path.basename(js_filename_rel)}"

        assembled_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name.replace('_', ' ').title()} - {page_name.replace('_', ' ').title()}</title>
    <link rel="stylesheet" href="{css_link_path}">
</head>
<body>
{html_code}

<script src="{js_link_path}" defer></script>
</body>
</html>
"""
        # Store files to save *for this page*
        page_components_info['files_to_save_map'] = {
            html_filename_rel: assembled_html,
            # Only include CSS/JS if this is the *first* page being assembled
            **( {css_filename_rel: css_code} if context.get('current_page_index', 0) == 0 else {} ),
            **( {js_filename_rel: js_code} if context.get('current_page_index', 0) == 0 else {} ),
        }
        page_components_info['html_filename_rel'] = html_filename_rel # Store for QA notification
        page_components_info['assembled'] = True
        page_components_info['saved_files_map'] = {} # Reset save tracking for this page
        page_components_info['save_attempts'] = {}

        logger.info(f"{self.agent_id}: Prepared files for page '{page_name}' (Task: {task_id}): {list(page_components_info['files_to_save_map'].keys())}")
        self.task_context[task_id] = context


    async def _notify_qa(self, task_id: str, page_name: str, final_html_filename: str):
        """Sends notification to QA agent that a page is ready for review."""
        context = self.task_context.get(task_id)
        if not context: return
        page_specs_info = context.get('page_specs', {}).get(page_name, {})
        specs_filename = page_specs_info.get('filename')

        if not self.qa_agent_id:
            logger.warning(f"{self.agent_id}: Cannot notify QA for task {task_id}, QA agent ID not configured.")
            context['notification_sent'] = True # Mark anyway to complete task
            self.task_context[task_id] = context
            self.update_state({'current_action': f'qa_notification_skipped_{page_name}'})
            return

        logger.info(f"{self.agent_id}: Notifying QA agent ({self.qa_agent_id}) for project (using page '{page_name}' as context - File: {final_html_filename}, Task: {task_id}).")
        qa_message_data = {
            'type': 'code_ready_for_qa',
            'source_task_id': task_id,
            'project_name': context.get('project_name', 'Unknown Project'),
            'saved_filename': final_html_filename, # Main HTML file
            'specifications_filename': specs_filename
        }
        await self._send_message_to_agent(self.qa_agent_id, {'type': 'agent_message', 'message_data': qa_message_data})
        context['notification_sent'] = True # Mark notification sent
        self.task_context[task_id] = context
        self.update_state({'current_action': f'notified_qa_{page_name}'})