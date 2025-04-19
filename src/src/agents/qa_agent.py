# SoftwareSim3d/src/agents/qa_agent.py

import asyncio
import logging
import json
import re
from typing import Optional, Dict, Any, Callable, Awaitable, Tuple, Set
import os

# Import base class and constants/types
from ..agent_base import Agent  # Base Agent class
from ..simulation.task import Task  # Task class if used

logger = logging.getLogger(__name__)

# Define zone constants
SAVE_ZONE_NAME = "SAVE_ZONE"
QA_DESK_ZONE_NAME = "QA_DESK"  # Assuming QA has its own desk

class QAAgent(Agent):
    """
    The QA agent reviews code produced by the Coder agent,
    checking for correctness, completeness, and alignment with specifications.
    """
    def __init__(self,
                 agent_id: str,
                 role: str,  # Accept role as required by WorkflowManager
                 message_queue: asyncio.Queue,
                 broadcast_callback: Callable[[Dict[str, Any]], Awaitable[None]],
                 loop: asyncio.AbstractEventLoop,
                 initial_position: Tuple[float, float, float],
                 target_desk_position: Tuple[float, float, float],
                 **kwargs):  # Accept any additional args via kwargs

        # Call base class __init__ with all required args
        super().__init__(
            agent_id=agent_id,
            role=role,
            message_queue=message_queue,
            broadcast_callback=broadcast_callback,
            loop=loop,
            initial_position=initial_position,
            target_desk_position=target_desk_position,
            llm_service=kwargs.get('llm_service'),
            llm_type=kwargs.get('llm_type'),
            llm_model_name=kwargs.get('llm_model_name'),
            available_tools=kwargs.get('available_tools'),
            required_tool_zones=kwargs.get('required_tool_zones'),
            zone_coordinates_map=kwargs.get('zone_coordinates_map')
        )
        
        # Store any QA-specific attributes
        self.coder_lead_id = kwargs.get('coder_lead_id', "coder-01")  # Default if not provided
        self.ceo_agent_id = kwargs.get('ceo_agent_id', "ceo-01")  # Default if not provided
        
        # Ensure needed zones exist
        if not hasattr(self, 'zone_coordinates'): 
            self.zone_coordinates = {}
            logger.warning(f"{self.agent_id}: Initializing empty zone_coordinates.")
        
        if QA_DESK_ZONE_NAME not in self.zone_coordinates: 
            self.zone_coordinates[QA_DESK_ZONE_NAME] = target_desk_position
            logger.warning(f"Added {QA_DESK_ZONE_NAME} position.")
        
        if SAVE_ZONE_NAME not in self.zone_coordinates: 
            save_zone = (35, 0.1, -25)
            logger.warning(f"Using default {SAVE_ZONE_NAME} position: {save_zone}")
            self.zone_coordinates[SAVE_ZONE_NAME] = save_zone
        
        if not self.coder_lead_id:
            logger.error(f"{self.agent_id}: Initialized without coder_lead_id!")
        if not self.ceo_agent_id:
            logger.warning(f"{self.agent_id}: Initialized without ceo_agent_id! Approval notification will fail.")
            
        logger.info(f"QAAgent {self.agent_id} initialized. Reporting to Coder: {self.coder_lead_id}, Notifying CEO: {self.ceo_agent_id}")
    
    # --- Implement abstract method from base Agent class ---
    def get_prompt(self, task_details: Dict[str, Any], context: Dict[str, Any]) -> Optional[str]:
        """Generates the LLM prompt for the QA task."""
        task_type = task_details.get('task_type')
        details = task_details.get('details', {})
        description = task_details.get('description', '')
        project_name = details.get('project_name', '[Unknown Project]')
        code_to_review = context.get('code_to_review', 'No code content available.')
        specifications = context.get('specifications_content', None)

        # Check if this is a code review task
        if task_type == 'review_code' or "review code" in description.lower() or "qa check" in description.lower():
            spec_section = f"\n\n--- SPECIFICATIONS ---\n{specifications}\n--- END SPECIFICATIONS ---" if specifications else "\n\n--- NOTE: Specs not provided or read yet. ---"

            # Enhanced prompt for more thorough review
            prompt = f"""You are a QA Engineer reviewing code for project '{project_name}'. Your job is to thoroughly analyze the following code against the provided specifications.

{spec_section}

--- CODE TO REVIEW ---
Filename: {details.get('code_filename_to_review', 'N/A')}
{code_to_review}
--- END CODE ---

Please conduct a comprehensive review checking for:

1. **Structural Completeness:**
   - Verify all required HTML tags are present and properly closed
   - Check if the document has proper structure (DOCTYPE, html, head, body)
   - Identify any abrupt endings or truncated sections

2. **Specification Compliance:**
   - Compare the code against ALL requirements in the specifications
   - Check that all specified sections, components, and features are implemented
   - Verify colors, layouts, and styles match the specification requirements
   - Ensure all required JavaScript functionality is included

3. **Functionality:**
   - Assess if the JavaScript code would function as expected
   - Check for proper event handling and DOM manipulation
   - Identify logic errors or bugs in the implementation

4. **Best Practices:**
   - Check for semantic HTML usage
   - Verify responsive design implementation
   - Assess accessibility features

**Your response MUST be in this exact JSON format:**
{{
  "requires_fix": boolean,
  "feedback": "Detailed explanation of issues found or confirmation that the code meets all requirements"
}}

Set "requires_fix" to true if ANY of these conditions are met:
- The code is incomplete (missing closing tags, abrupt endings)
- Required features from specifications are missing or incorrectly implemented
- There are logic errors or bugs that would prevent functionality
- Critical best practices are violated

Be extremely thorough and detail-oriented in your assessment. Your feedback will determine if the code needs revision."""
            return prompt.strip()

        logger.warning(f"{self.agent_id}: Cannot generate prompt for unknown task type '{task_type}' or description: '{description}'")
        return None

    # --- Added _handle_arrival method ---
    async def _handle_arrival(self, zone: str):
        """Handles actions upon arriving at a zone."""
        # First, call the base class handler
        await super()._handle_arrival(zone)
        
        task_id = self.current_task.get('task_id') if self.current_task else None
        if not task_id or task_id not in self.task_context:
            logger.warning(f"{self.agent_id}: Arrived at {zone}, but no active task or task context.")
            return
            
        context = self.task_context[task_id]
        details = self.current_task.get('details', {})
        
        # Handle arrival at SAVE_ZONE
        if zone == SAVE_ZONE_NAME:
            logger.info(f"{self.agent_id}: Arrived at {SAVE_ZONE_NAME}, checking if files need to be read.")
            
            # Check what files need to be read
            file_to_read = None
            code_filename_rel = details.get('code_filename_to_review')
            specs_filename_rel = details.get('specifications_filename')
            
            # Prioritize reading code file first, then specs
            if code_filename_rel and 'code_to_review' not in context:
                file_to_read = code_filename_rel
                logger.info(f"{self.agent_id}: Need to read code file: {file_to_read}")
            elif specs_filename_rel and 'specifications_content' not in context:
                file_to_read = specs_filename_rel
                logger.info(f"{self.agent_id}: Need to read specs file: {file_to_read}")
            
            # Trigger file read if needed
            if file_to_read:
                logger.info(f"{self.agent_id}: Arrived at {SAVE_ZONE_NAME}, initiating read for {file_to_read}.")
                # Use execute_action to trigger tool use
                await self.execute_action({
                    'action': 'use_tool',
                    'tool_name': 'file_read',
                    'params': {'filename': file_to_read}
                })
            else:
                logger.debug(f"{self.agent_id}: Arrived at {SAVE_ZONE_NAME}, but no immediate file read needed.")
                # Check if we should return to desk
                has_code = 'code_to_review' in context
                has_specs = 'specifications_content' in context or not specs_filename_rel
                
                if has_code and has_specs:
                    logger.info(f"{self.agent_id}: All files read. Moving back to desk to process.")
                    # Move back to desk to process files
                    await self.execute_action({
                        'action': 'move_to_zone',
                        'zone_name': QA_DESK_ZONE_NAME
                    })
        
        # Handle arrival at QA_DESK
        elif zone == QA_DESK_ZONE_NAME:
            # Check if we need to call LLM for review
            has_code = 'code_to_review' in context
            has_specs = 'specifications_content' in context or not details.get('specifications_filename')
            llm_review_complete = 'qa_feedback' in context
            
            if has_code and has_specs and not llm_review_complete:
                logger.info(f"{self.agent_id}: At desk with all files read. Initiating LLM review.")
                prompt = self.get_prompt(self.current_task, context)
                if prompt:
                    context['step'] = 'calling_llm'
                    self.task_context[task_id] = context
                    await self.execute_action({
                        'action': 'use_llm', 
                        'prompt': prompt
                    })
            elif llm_review_complete and not context.get('notification_sent'):
                logger.info(f"{self.agent_id}: At desk with review complete. Ready to send notification.")
                # _decide_next_action will handle sending the notification
            
    # --- Core Decision Logic ---
    async def _decide_next_action(self) -> Optional[Dict[str, Any]]:
        """Determines the next logical step for the QA agent."""
        if not self.current_task:
            return {'action': 'wait'}

        task_id = self.current_task.get('task_id')
        if not task_id:
            logger.error(f"{self.agent_id}: Current task has no ID. Cannot proceed.")
            self.current_task = None
            return {'action': 'wait'}

        if task_id not in self.task_context:
            self.task_context[task_id] = {'step': 'start'}
        context = self.task_context[task_id]

        task_type = self.current_task.get('task_type')
        details = self.current_task.get('details', {})
        step = context.get('step', 'start')
        
        # Debug logging to diagnose task completion issues
        current_action = self.get_state('current_action')
        logger.debug(f"{self.agent_id}: Deciding action for task {task_id} (Type: {task_type}) at step '{step}', current_action: '{current_action}'. Context Keys: {list(context.keys())}")

        # --- Handle Failures First ---
        if context.get('read_failed'):
            return {'action': 'fail_task', 'error': context.get('error_details', 'File read failed previously.')}
        if step == 'error':
            return {'action': 'fail_task', 'error': context.get('error_details', 'Task entered error state.')}

        # --- Get Current Zone ---
        current_zone = self.get_state('current_zone')

        # --- Inputs Required ---
        code_filename_rel = details.get('code_filename_to_review')
        specs_filename_rel = details.get('specifications_filename')  # Optional

        # --- State Checks ---
        has_code_content = 'code_to_review' in context
        has_specs_content = 'specifications_content' in context or not specs_filename_rel  # True if specs read or not needed
        read_files_complete = has_code_content and has_specs_content
        llm_review_complete = 'qa_feedback' in context
        notification_sent = context.get('notification_sent', False)  # Check if notification was sent

        # 1. Read Files if necessary
        if (step == 'start' or step == 'files_read_partially') and not read_files_complete:
            # Need to read files, make sure we're at SAVE_ZONE
            if current_zone != SAVE_ZONE_NAME:
                logger.info(f"{self.agent_id}: Need to read files, moving to {SAVE_ZONE_NAME}.")
                return {'action': 'move_to_zone', 'zone_name': SAVE_ZONE_NAME}
            else:
                # Already at SAVE_ZONE, file reads should be initiated by _handle_arrival
                # This is just a fallback in case _handle_arrival didn't trigger the read
                file_to_read = None
                if not has_code_content and code_filename_rel:
                    file_to_read = code_filename_rel
                elif not has_specs_content and specs_filename_rel:
                    file_to_read = specs_filename_rel
                
                if file_to_read:
                    context['step'] = 'reading_files'
                    self.task_context[task_id] = context
                    return {'action': 'use_tool', 'tool_name': 'file_read', 'params': {'filename': file_to_read}}
                
                return {'action': 'wait', 'reason': 'waiting_for_file_read_trigger'}

        # 2. Call LLM if files are ready and review not done
        if read_files_complete and not llm_review_complete:
            # Need to be at desk to do LLM review
            if current_zone != QA_DESK_ZONE_NAME:
                logger.info(f"{self.agent_id}: Files read complete, moving to {QA_DESK_ZONE_NAME} for review.")
                return {'action': 'move_to_zone', 'zone_name': QA_DESK_ZONE_NAME}
            else:
                # At desk, call LLM
                prompt = self.get_prompt(self.current_task, context)
                if prompt:
                    context['step'] = 'calling_llm'
                    self.task_context[task_id] = context
                    return {'action': 'use_llm', 'prompt': prompt}
                else:
                    return {'action': 'fail_task', 'error': 'Could not generate LLM prompt for QA review.'}

        # --- STEP 3: Send Notification if LLM review is done and notification not sent ---
        if llm_review_complete and not notification_sent:
            # Preferably send notifications from desk
            if current_zone != QA_DESK_ZONE_NAME:
                logger.info(f"{self.agent_id}: Review complete, moving to {QA_DESK_ZONE_NAME} to send notification.")
                return {'action': 'move_to_zone', 'zone_name': QA_DESK_ZONE_NAME}

            # At Desk, prepare notification
            requires_fix = context.get('requires_fix', True)  # Default true if key missing
            feedback = context.get('qa_feedback', 'Feedback unavailable.')
            reviewed_code_filename = details.get('code_filename_to_review')
            original_code_task_id = details.get('original_code_task_id')
            specs_filename = details.get('specifications_filename')

            context['step'] = 'sending_notification' # Mark intent to send
            # NOTE: DO NOT set context['notification_sent'] = True here anymore.

            # Determine where to send notification based on review result
            if requires_fix:
                # Send feedback to Coder
                target_agent_id = self.coder_lead_id
                message_data = {
                    'type': 'qa_feedback',
                    'source_task_id': task_id,
                    'original_code_task_id': original_code_task_id,
                    'requires_fix': True,
                    'feedback': feedback,
                    'failed_code_filename': reviewed_code_filename,
                    'specifications_filename': specs_filename,
                    'project_name': details.get('project_name', 'Unknown Project')
                }
                logger.info(f"{self.agent_id}: Preparing to send FIX feedback to Coder ({target_agent_id}).")
            else:
                # Send approval to CEO
                target_agent_id = self.ceo_agent_id
                message_data = {
                    'type': 'qa_approved',
                    'source_task_id': task_id,
                    'original_code_task_id': original_code_task_id,
                    'project_name': details.get('project_name'),
                    'filename': reviewed_code_filename
                }
                logger.info(f"{self.agent_id}: Preparing to send APPROVAL to CEO ({target_agent_id}).")

            if not target_agent_id:
                missing_id = "coder_lead_id" if requires_fix else "ceo_agent_id"
                return {'action': 'fail_task', 'error': f"Cannot send notification: {missing_id} is not configured."}

            # Wrap message data in agent_message format
            wrapped_message_data = {'type': 'agent_message', 'message_data': message_data}
            
            # Update task context *only* with the current step intent
            self.task_context[task_id] = context 
            
            # Return the action to send the message
            return {'action': 'send_message_to_agent', 'target_agent_id': target_agent_id, 'message_data': wrapped_message_data}

        # --- STEP 4: Complete Task if notification was successfully sent ---
        # Rely ONLY on the 'current_action' state updated by the base class after send succeeds
        if self.get_state('current_action') == 'message_sent':
            # Check context again to ensure we were indeed trying to send
            if context.get('step') == 'sending_notification':
                 logger.info(f"{self.agent_id}: Detected message was sent successfully. Completing task {task_id}.")
                 final_message = f"QA review complete. Requires Fix: {context.get('requires_fix', 'Unknown')}"
                 # Context will be cleared upon task completion by the base class or workflow manager
                 return {'action': 'complete_task', 'result': final_message}
            else:
                # This case shouldn't ideally happen if logic flows correctly
                logger.warning(f"{self.agent_id}: State is 'message_sent' but step was '{context.get('step')}'. Waiting.")
                return {'action': 'wait'}

        # Fallback: Wait if none of the above conditions met
        logger.debug(f"{self.agent_id}: No immediate action determined for task {task_id} at step '{step}'. Waiting.")
        return {'action': 'wait'}

    # --- Response Processing ---
    async def _process_llm_response(self, llm_response: str):
        """Parses the LLM response for QA feedback."""
        if not self.current_task:
            logger.error(f"{self.agent_id}: Cannot process LLM response, no active task.")
            return
            
        task_id = self.current_task.get('task_id')
        if task_id not in self.task_context:
            logger.error(f"{self.agent_id}: Cannot process LLM response, no context found for task {task_id}")
            return
            
        context = self.task_context[task_id]
        logger.info(f"{self.agent_id}: Processing LLM review response for task {task_id}.")

        try:
            # Enhanced regex to find JSON block, even with leading/trailing text
            json_match = re.search(r'\{[\s\S]*\}', llm_response)
            if not json_match:
                raise ValueError("No JSON object found in the response.")

            json_string = json_match.group(0)
            review_data = json.loads(json_string)
            feedback = review_data.get('feedback')
            requires_fix = review_data.get('requires_fix')

            if feedback is None or requires_fix is None:
                # Attempt to extract from malformed response as fallback
                logger.warning(f"{self.agent_id}: LLM response missing required JSON keys. Attempting fallback extraction.")
                feedback = feedback or llm_response  # Use raw response if feedback key missing
                # Infer requires_fix based on keywords if boolean missing
                if requires_fix is None:
                    requires_fix = any(word in feedback.lower() for word in ["fail", "bug", "error", "incomplete", "fix", "issue"])
                logger.warning(f"{self.agent_id}: Fallback extraction: requires_fix={requires_fix}")
                # Ensure requires_fix is boolean
                requires_fix = bool(requires_fix)

            # Explicitly check for incompleteness hints from LLM
            if isinstance(feedback, str) and ("incomplete" in feedback.lower() or "cut off" in feedback.lower() or "missing closing tag" in feedback.lower()):
                logger.warning(f"{self.agent_id}: LLM feedback explicitly mentions incompleteness for task {task_id}. Forcing requires_fix=True.")
                requires_fix = True

            context['qa_feedback'] = feedback
            context['requires_fix'] = bool(requires_fix)  # Ensure boolean
            context['step'] = 'llm_review_processed'  # Update step
            logger.info(f"{self.agent_id}: QA Review Parsed for task {task_id}: Requires Fix = {context['requires_fix']}")

        except (json.JSONDecodeError, ValueError) as e:
            error_msg = f"Failed to parse QA LLM JSON: {e}. Response: {llm_response[:300]}..."
            logger.error(f"{self.agent_id}: {error_msg}")
            context['qa_feedback'] = f"Error: LLM response parsing failed ({e}). Treating as failed review.\nRaw: {llm_response}"
            context['requires_fix'] = True  # Default fix on error
            context['step'] = 'llm_review_processed'  # Still processed, but with error state noted implicitly
            context['error_details'] = error_msg  # Store error detail

        self.task_context[task_id] = context
        self.update_state({'current_action': 'processed_llm_response', 'current_thoughts': 'LLM review processed.'})

    async def _process_tool_result(self, tool_name: str, result: Any):
        """Processes the result from a tool execution."""
        if not self.current_task:
            logger.error(f"{self.agent_id}: Cannot process tool result, no active task.")
            return
            
        task_id = self.current_task.get('task_id')
        if task_id not in self.task_context:
            logger.error(f"{self.agent_id}: Cannot process tool result, no context found for task {task_id}")
            return
            
        context = self.task_context[task_id]
        details = self.current_task.get('details', {})

        logger.info(f"{self.agent_id}: Processing result for tool '{tool_name}'. Task: {task_id}.")
        success = False
        error_details = None

        if tool_name == 'file_read':
            code_filename_rel = details.get('code_filename_to_review')
            specs_filename_rel = details.get('specifications_filename')

            if isinstance(result, dict) and result.get('status') == 'success':
                content = result.get('content', '')
                read_filename = result.get('filename', 'unknown file')

                if read_filename == code_filename_rel:
                    context['code_to_review'] = content
                    logger.debug(f"{self.agent_id}: Stored code content for {read_filename}.")
                elif read_filename == specs_filename_rel:
                    context['specifications_content'] = content
                    logger.debug(f"{self.agent_id}: Stored specs content for {read_filename}.")
                else:
                    logger.warning(f"{self.agent_id}: Read file '{read_filename}' but it didn't match expected code ('{code_filename_rel}') or specs ('{specs_filename_rel}') filenames.")

                # Check if all required files are now read
                has_code = 'code_to_review' in context
                has_specs = 'specifications_content' in context or not specs_filename_rel  # Specs are ready if read or not required

                if has_code and has_specs:
                    context['step'] = 'files_read_complete'
                    logger.info(f"{self.agent_id}: All required files read for task {task_id}.")
                    
                    # Trigger move back to desk now that files are read
                    current_zone = self.get_state('current_zone')
                    if current_zone == SAVE_ZONE_NAME:
                        logger.info(f"{self.agent_id}: All files read, scheduling move back to desk.")
                        # Schedule a move back to desk to continue processing
                        self.loop.create_task(self.execute_action({
                            'action': 'move_to_zone', 
                            'zone_name': QA_DESK_ZONE_NAME
                        }))
                else:
                    context['step'] = 'files_read_partially'  # Still need more files
                    logger.info(f"{self.agent_id}: Read {read_filename}, still waiting for other files for task {task_id}.")
                    
                    # Check if we need to read more files immediately
                    more_to_read = False
                    file_to_read = None
                    
                    if not has_code and code_filename_rel:
                        file_to_read = code_filename_rel
                        more_to_read = True
                    elif not has_specs and specs_filename_rel:
                        file_to_read = specs_filename_rel
                        more_to_read = True
                    
                    if more_to_read and file_to_read and self.get_state('current_zone') == SAVE_ZONE_NAME:
                        logger.info(f"{self.agent_id}: Immediately reading next required file: {file_to_read}")
                        # Schedule immediate read of next file
                        self.loop.create_task(self.execute_action({
                            'action': 'use_tool',
                            'tool_name': 'file_read',
                            'params': {'filename': file_to_read}
                        }))
                
                success = True
            else:
                error_details = f"File read failed for {result.get('filename', 'unknown file')}: {result.get('result') if isinstance(result,dict) else result}"
                logger.error(f"{self.agent_id}: {error_details}")
                context['read_failed'] = True  # Mark persistent failure
                context['error_details'] = error_details
                context['step'] = 'error'  # Move to error state
                success = False
        else:
            logger.warning(f"{self.agent_id}: Received result for unhandled tool: {tool_name}")
            success = False
            error_details = f"Unhandled tool result: {tool_name}"
            context['step'] = 'error'  # Treat unexpected tool result as error

        self.task_context[task_id] = context
        self.update_state({
            'current_action': f'processed_{tool_name}_result',
            'current_thoughts': f"Tool {tool_name} processed ({'Success' if success else 'Failure'})."
        })

    # --- Override the execute_action method to better handle message sending ---
    async def execute_action(self, action: Optional[Dict[str, Any]]):
        """Override base class execute_action to handle message sending completion better"""
        if not action or not action.get('action'):
            return
            
        action_type = action.get('action')
        
        # Special handling for sending messages
        if action_type == 'send_message_to_agent':
            target_id = action.get('target_agent_id')
            msg_data = action.get('message_data')
            
            if target_id and msg_data:
                try:
                    await self._send_message_to_agent(target_id, msg_data)
                    # Mark notification as sent in current task context AFTER successful send
                    if self.current_task and self.current_task.get('task_id') in self.task_context:
                        task_id = self.current_task.get('task_id')
                        context = self.task_context[task_id]
                        context['notification_sent'] = True
                        self.task_context[task_id] = context
                        logger.info(f"{self.agent_id}: Message sent to {target_id}, marked notification_sent=True")
                    
                    self.update_state({'current_action': 'message_sent'})
                    
                    # For QA messages that require fix, immediately complete the task
                    # after sending instead of waiting for another decision cycle
                    if isinstance(msg_data, dict) and msg_data.get('type') == 'agent_message':
                        message_content = msg_data.get('message_data', {})
                        if isinstance(message_content, dict) and message_content.get('type') == 'qa_feedback':
                            if message_content.get('requires_fix', False):
                                logger.info(f"{self.agent_id}: QA feedback with fix requirement sent. Immediately completing task.")
                                final_message = f"QA review complete. Fix required. Feedback sent to coder."
                                await self._complete_current_task(final_message)
                                return
                except Exception as e:
                    logger.error(f"{self.agent_id}: Failed to send message to {target_id}: {e}")
                    self.update_state({'last_error': f"Message sending failed: {e}"})
            else:
                logger.error(f"{self.agent_id}: Missing target agent ID or message data for sending.")
                
            # Return after handling the message send to avoid double-processing
            return
            
        # For all other actions, call the base class implementation
        await super().execute_action(action)

    # --- Message Handling ---
    async def _handle_agent_specific_message(self, sender_id: str, message_data: Any):
            """Handles messages specifically relevant to the QA agent's workflow."""
            if not isinstance(message_data, dict):
                logger.warning(f"{self.agent_id}: Received non-dict message data from {sender_id}")
                return

            data_type = message_data.get('type')
            
            # Handle notification from coder that code is ready for review
            if data_type == 'code_ready_for_qa':
                source_task_id = message_data.get('source_task_id')
                project_name = message_data.get('project_name', 'Unknown Project')
                saved_filename = message_data.get('saved_filename')
                specs_filename = message_data.get('specifications_filename')
                
                logger.info(f"{self.agent_id}: Received code ready notification from Coder. File: {saved_filename}")
                
                # If we already have an active task, check if we should replace it or ignore this message
                if self.current_task:
                    current_task_id = self.current_task.get('task_id')
                    logger.warning(f"{self.agent_id}: Received code ready notification but already has active task {current_task_id}.")
                    
                    # Check if the current task is far along in processing
                    context = self.task_context.get(current_task_id, {})
                    current_step = context.get('step', 'start')
                    
                    # If we're already processing QA feedback or late in the process, ignore this new notification
                    if current_step in ['llm_review_processed', 'sending_notification', 'notification_sent']:
                        logger.warning(f"{self.agent_id}: Ignoring new code ready notification as current task is at step {current_step}")
                        return
                    
                    # If we're early in the process, we could replace the task, but for now let's just log and continue
                    logger.warning(f"{self.agent_id}: Will continue with current task. New code notification will be handled after completion.")
                    return
                
                # Create a new task for ourselves if no active task
                logger.info(f"{self.agent_id}: Creating new QA task for code review based on coder notification.")
                task_details = {
                    'description': f"Review code for project '{project_name}'",
                    'task_type': 'review_code',
                    'details': {
                        'project_name': project_name,
                        'code_filename_to_review': saved_filename,
                        'specifications_filename': specs_filename,
                        'original_code_task_id': source_task_id
                    },
                    'task_id': f"qa_task_{source_task_id[-8:]}"
                }
                
                await self.assign_task(task_details)
                logger.info(f"{self.agent_id}: Created new QA task {task_details['task_id']} based on coder notification.")
                
                # Immediately schedule a move to SAVE_ZONE to start reading files
                # This helps reduce delay in starting the file read process
                self.loop.create_task(self.execute_action({
                    'action': 'move_to_zone', 
                    'zone_name': SAVE_ZONE_NAME
                }))
            elif data_type == 'response_to_qa_feedback':
                # Handle any responses from the coder about the QA feedback
                feedback_response = message_data.get('response')
                original_feedback_id = message_data.get('original_feedback_id')
                
                logger.info(f"{self.agent_id}: Received response from Coder about feedback {original_feedback_id}: {feedback_response}")
                # Currently just log this information, could be used in future to track fix status
            else:
                logger.debug(f"{self.agent_id}: Received unhandled message of type {data_type} from {sender_id}")

    async def _send_message_to_agent(self, target_agent_id: str, message_data: Any):
        """Helper to send message via broadcast callback, ensuring proper structure."""
        # Pass the actual message data directly to the base class sender
        await super()._send_message_to_agent(target_agent_id, message_data)
        # Base class's sender handles logging and exceptions
        # We can update state here if needed *after* the send is attempted
        self.update_state({'current_action': 'message_sent'})
