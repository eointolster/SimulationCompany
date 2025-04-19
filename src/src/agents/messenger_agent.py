# SoftwareSim3d/src/agents/messenger_agent.py

import asyncio
import logging
from typing import Optional, Dict, Any, Callable, Awaitable, Tuple, Set

# Import base class and constants
from ..agent_base import Agent, STATUS_IDLE, STATUS_WORKING, STATUS_FAILED #[cite: uploaded:SoftwareSim3d/src/agent_base.py]

# Type hinting imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..llm_integration.api_clients import LLMService #[cite: uploaded:SoftwareSim3d/src/llm_integration/api_clients.py]

logger = logging.getLogger(__name__)

class MessengerAgent(Agent):
    """
    Relays messages between the User Interface (via WorkflowManager) and the CEO.
    Does not use LLMs or complex tools. Includes basic defensive checks for message relay.
    """
    def __init__(self,
                 agent_id: str,
                 message_queue: asyncio.Queue,
                 broadcast_callback: Callable[[Dict[str, Any]], Awaitable[None]],
                 loop: asyncio.AbstractEventLoop,
                 initial_position: Tuple[float, float, float],
                 target_desk_position: Tuple[float, float, float],
                 ceo_agent_id: str,
                 **kwargs):

        super().__init__(
            agent_id=agent_id,
            role="Messenger",
            llm_service=None, llm_type=None, llm_model_name=None,
            message_queue=message_queue,
            broadcast_callback=broadcast_callback,
            loop=loop,
            initial_position=initial_position,
            target_desk_position=target_desk_position,
            available_tools=set(), required_tool_zones={},
            zone_coordinates_map=kwargs.get('zone_coordinates_map')
        ) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
        self.ceo_agent_id = ceo_agent_id
        if not self.ceo_agent_id:
             logger.error(f"MessengerAgent {self.agent_id} initialized without required ceo_agent_id!")
             # Consider setting a failed state? For now, just log error.
        logger.info(f"MessengerAgent {self.agent_id} initialized. Relaying to CEO: {self.ceo_agent_id}")

    # --- Minimal Abstract Method Implementations ---

    def get_prompt(self, task_details: Dict[str, Any], context: Dict[str, Any]) -> Optional[str]:
        return None # No LLM

    async def _decide_next_action(self) -> Optional[Dict[str, Any]]:
        # Defensive check: If somehow an error occurred previously, log it.
        last_error = self.get_state('last_error') #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
        if last_error:
            logger.error(f"Messenger {self.agent_id} found previous error state: {last_error}. Clearing and waiting.")
            self.update_state({'last_error': None}) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
            # Does not need to fail task as it's stateless relay

        # If assigned a task (shouldn't happen), complete it.
        if self.current_task:
             logger.warning(f"Messenger received unexpected task: {self.current_task}. Completing.")
             return {'action': 'complete_task', 'result': 'Relayed message.'} #[cite: uploaded:SoftwareSim3d/src/agent_base.py]

        # Default action is to wait for messages
        return {'action': 'wait'} #[cite: uploaded:SoftwareSim3d/src/agent_base.py]

    async def _process_llm_response(self, llm_response: str):
        pass # No LLM

    async def _process_tool_result(self, tool_name: str, result: Any):
        pass # No tools

    # --- Core Message Handling ---

    async def _handle_message(self, message: Dict[str, Any]):
        sender_id = message.get('sender_id', 'Unknown')
        content = message.get('content', {})
        message_type = content.get('type', 'unknown')

        logger.info(f"Messenger {self.agent_id} received message type '{message_type}' from {sender_id}")

        try:
            # Message from UI/WorkflowManager (relay to CEO)
            if sender_id == 'workflow_manager' or sender_id == 'user_interface':
                if message_type in ['user_request', 'user_clarification_response']:
                    if self.ceo_agent_id:
                        logger.info(f"Messenger relaying '{message_type}' to CEO ({self.ceo_agent_id})")
                        # Wrap content for CEO's specific handler
                        ceo_message_payload = {'type': 'agent_message', 'message_data': content}
                        await self._safe_send_to_agent(self.ceo_agent_id, ceo_message_payload) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
                    else:
                        logger.error(f"Messenger cannot relay '{message_type}': CEO ID unknown")
                        self.update_state({'last_error': "Cannot relay message: CEO ID unknown."}) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
                else:
                     logger.warning(f"Messenger received unhandled message type '{message_type}' from {sender_id}")

            # Message FROM the CEO (relay to UI via WorkflowManager)
            elif sender_id == self.ceo_agent_id and message_type == 'agent_message':
                 inner_content = content.get('message_data', {})
                 inner_type = inner_content.get('type')
                 if inner_type == 'request_user_input':
                      logger.info("Messenger relaying CEO 'request_user_input' to WorkflowManager.")
                      manager_message = {
                           'type': 'ui_request_user_input',
                           'question': inner_content.get('question'),
                           'originating_task_id': inner_content.get('originating_task_id')
                      }
                      await self._safe_send_to_manager(manager_message) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
                 elif inner_type == 'simulation_end':
                      logger.info("Messenger relaying CEO 'simulation_end' to WorkflowManager.")
                      manager_message = {
                           'type': 'ui_simulation_end',
                           'success': inner_content.get('success'),
                           'message': inner_content.get('message')
                      }
                      await self._safe_send_to_manager(manager_message) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
                 else:
                      logger.warning(f"Messenger received unhandled inner message type '{inner_type}' from CEO.")

            # Other messages (e.g., stop_agent) handled by base class
            else:
                logger.debug(f"Messenger passing message to base handler. Sender: {sender_id}, Type: {message_type}")
                await super()._handle_message(message) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]

        except Exception as e:
            logger.error(f"Messenger {self.agent_id} encountered error handling message: {e}", exc_info=True)
            # Set error state for potential check in next cycle, although Messenger has little state to recover
            self.update_state({'last_error': f'Error handling message: {e}'}) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]


    # --- Safe Message Sending Wrappers ---

    async def _safe_send_to_agent(self, target_agent_id: str, message_data: Any):
        """Wrapper for sending to agent with error handling."""
        try:
            # Using super() to call the base class's send method directly
            await super()._send_message_to_agent(target_agent_id, message_data) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
            self.update_state({'current_action': 'message_relayed'}) # Update action after successful send #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
        except Exception as e:
            logger.error(f"Messenger {self.agent_id} failed to send message to agent {target_agent_id}: {e}", exc_info=True)
            # Set error state for defensive checks
            self.update_state({'last_error': f'Failed to send message to agent {target_agent_id}: {e}'}) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]

    async def _safe_send_to_manager(self, message_content: Dict[str, Any]):
        """Wrapper for sending to manager with error handling."""
        try:
            # Using super() to call the base class's send method directly
            await super()._send_message_to_manager(message_content) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
            self.update_state({'current_action': 'message_relayed'}) # Update action after successful send #[cite: uploaded:SoftwareSim3d/src/agent_base.py]
        except Exception as e:
            logger.error(f"Messenger {self.agent_id} failed to send message to manager: {e}", exc_info=True)
            # Set error state for defensive checks
            self.update_state({'last_error': f'Failed to send message to manager: {e}'}) #[cite: uploaded:SoftwareSim3d/src/agent_base.py]


    # Override _send_message_to_agent etc. only if needing different base behavior
    # Using the safe wrappers above is preferred for handling relay logic