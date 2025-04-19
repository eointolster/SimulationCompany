# main.py

import asyncio
import logging
import os
import sys
import threading
from typing import Dict, Any, Optional

# *** ADD FLASK request IMPORT ***
from flask import Flask, render_template, send_from_directory, request
from flask_socketio import SocketIO, emit

# --- Add src directory to Python path ---
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)
# --- ---

# Import core components
from src.llm_integration.api_clients import LLMService
from src.simulation.workflow_manager import WorkflowManager

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)
# --- ---

# --- Flask & SocketIO Setup ---
app = Flask(__name__, template_folder='frontend', static_folder='frontend/static')
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your_very_secret_key!') # Change in production!
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*") # Allow all origins for local dev
# --- ---

# --- Global Variables ---
llm_service: LLMService | None = None
workflow_manager: WorkflowManager | None = None
simulation_loop_thread: threading.Thread | None = None
simulation_event_loop: asyncio.AbstractEventLoop | None = None
# --- ---


# --- Simulation Control Functions (called via WebSocket) ---
def start_simulation_thread(user_request: str, llm_agent_configs: Optional[Dict[str, Dict[str, str]]] = None):
    """Runs the simulation in a separate thread with its own event loop."""
    global workflow_manager, simulation_event_loop, llm_service # Ensure llm_service is accessible
    logger.info(f"Starting simulation thread with request: '{user_request}'")
    if llm_agent_configs:
         logger.info(f"Using provided LLM agent configs: {llm_agent_configs}")
    else:
         logger.warning("No LLM agent configs provided, using defaults in WorkflowManager.")

    simulation_event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(simulation_event_loop)

    try:
        workflow_manager = WorkflowManager(
            llm_service=llm_service, # [cite: uploaded:SoftwareSim3d/src/llm_integration/api_clients.py]
            loop=simulation_event_loop,
            llm_agent_configs=llm_agent_configs
        ) # [cite: uploaded:SoftwareSim3d/src/simulation/workflow_manager.py]

        workflow_manager.register_websocket_callbacks(
            emit_agent_update=emit_agent_update_callback,
            emit_task_update=emit_task_update_callback,
            request_user_input=request_user_input_callback,
            emit_final_output=emit_final_output_callback
        )

        if workflow_manager and workflow_manager.agents:
            logger.info("Sending initial agent states to frontend...")
            for agent_id, agent in workflow_manager.agents.items(): # [cite: uploaded:SoftwareSim3d/src/agent_base.py]
                 initial_state = agent.internal_state.copy() # [cite: uploaded:SoftwareSim3d/src/agent_base.py]
                 initial_state['position'] = agent.initial_position # [cite: uploaded:SoftwareSim3d/src/agent_base.py]
                 initial_state['role'] = agent.role
                 emit_agent_update_callback(agent_id, initial_state)

        simulation_event_loop.run_until_complete(workflow_manager.start_simulation(user_request))
        logger.info("Simulation thread finished.")

    except Exception as e:
         logger.error(f"Error in simulation thread: {e}", exc_info=True)
         socketio.emit('simulation_error', {'error': str(e)})
    finally:
         if simulation_event_loop and simulation_event_loop.is_running():
             simulation_event_loop.close()
         logger.info("Simulation event loop closed.")

# --- WebSocket Callback Functions ---
def emit_agent_update_callback(agent_id: str, state: Dict[str, Any]):
    data_to_send = {'agent_id': agent_id,'state': state }
    socketio.emit('update_agent', data_to_send)
    socketio.sleep(0.01)

def emit_task_update_callback(task_id: str, task_data: Dict[str, Any]):
    logger.debug(f"[WebSocket Emit] Update Task: {task_id} - Status: {task_data.get('status', 'N/A')}")
    socketio.emit('update_task', {'task_id': task_id, 'data': task_data})
    socketio.sleep(0.01)

def request_user_input_callback(task_id: str, question: str):
    logger.info(f"[WebSocket Emit] Requesting User Input (Task {task_id}): {question}")
    socketio.emit('request_user_input', {'task_id': task_id, 'question': question})

def emit_final_output_callback(output: str, success: bool):
    logger.info(f"[WebSocket Emit] Simulation Complete. Success: {success}")
    socketio.emit('simulation_complete', {'output': output, 'success': success})
# --- ---

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html') # [cite: uploaded:SoftwareSim3d/frontend/index.html]

@app.route('/static/<path:path>')
def send_static(path):
     return send_from_directory('frontend/static', path)
# --- ---

# --- SocketIO Event Handlers ---

# Corrected connect handler
@socketio.on('connect')
def handle_connect():
    # Use the request context provided by Flask-SocketIO
    if request: # Check if request context is available
        logger.info(f'Client connected: {request.sid}')
    else:
        logger.info('Client connected (no request context available)')

# Corrected disconnect handler
@socketio.on('disconnect')
def handle_disconnect():
    # Use the request context provided by Flask-SocketIO
    if request: # Check if request context is available
        logger.info(f'Client disconnected: {request.sid}')
    else:
        logger.info('Client disconnected (no request context available)')
    # Optional disconnect logic...

# Corrected start_simulation handler
@socketio.on('start_simulation')
def handle_start_simulation(data: Dict):
    global simulation_loop_thread, workflow_manager
    if not isinstance(data, dict):
         logger.error(f"Invalid data received for start_simulation: {data}")
         emit('simulation_status', {'status': 'error', 'message': 'Invalid start data received.'})
         return

    user_request = data.get('request', 'Default request: Make a simple webpage.')
    llm_configs = data.get('llm_configs')

    logger.info(f"Received start_simulation request: '{user_request}'")
    if llm_configs: logger.info(f"Received LLM Configs: {llm_configs}")
    else: logger.warning("No LLM configs received from frontend.")

    if simulation_loop_thread and simulation_loop_thread.is_alive():
         logger.warning("Simulation is already running. Ignoring request.")
         emit('simulation_status', {'status': 'already_running'})
         return

    if workflow_manager and simulation_event_loop and workflow_manager.agents:
         logger.warning("Attempting to clean up previous simulation instance...")
         try:
              future = asyncio.run_coroutine_threadsafe(workflow_manager.stop_simulation(), simulation_event_loop)
              future.result(timeout=10)
              logger.info("Previous simulation stopped.")
         except Exception as e:
              logger.error(f"Error stopping previous simulation: {e}")
         workflow_manager = None
    if simulation_loop_thread:
         simulation_loop_thread.join(timeout=5)
         if simulation_loop_thread.is_alive():
              logger.error("Previous simulation thread did not exit cleanly.")
         simulation_loop_thread = None

    simulation_loop_thread = threading.Thread(
        target=start_simulation_thread,
        args=(user_request, llm_configs),
        daemon=True
    )
    simulation_loop_thread.start()
    emit('simulation_status', {'status': 'started'})

# Corrected user_response handler
@socketio.on('user_response')
def handle_user_response(data: Dict):
    if not isinstance(data, dict):
         logger.error(f"Invalid data received for user_response: {data}"); return

    task_id = data.get('task_id')
    response = data.get('response')
    if not task_id or response is None:
         logger.error(f"Invalid user_response data: missing task_id or response. Data: {data}"); return

    logger.info(f"Received user response for task {task_id}: '{response}'")

    if workflow_manager and simulation_event_loop and simulation_event_loop.is_running():
        asyncio.run_coroutine_threadsafe(
            workflow_manager.handle_user_response(task_id, response),
            simulation_event_loop
        )
    else:
        logger.error("Cannot handle user response: WorkflowManager or simulation loop not available/running.")
        emit('simulation_status', {'status': 'error', 'message': 'Simulation not active to handle response.'})
# --- ---

# --- Main Execution ---
if __name__ == "__main__":
    logger.info("Starting Application Server...")
    try:
        llm_service = LLMService() # [cite: uploaded:SoftwareSim3d/src/llm_integration/api_clients.py]
        if not llm_service.google_client and not llm_service.openai_client and not llm_service.anthropic_client: # [cite: uploaded:SoftwareSim3d/src/llm_integration/api_clients.py]
            logger.error("FATAL: No LLM clients could be configured. Check API keys in .env file.")
            print("\nERROR: Could not configure any LLM clients. Check .env file or API service status. Exiting.")
            sys.exit(1)
        else:
            logger.info("LLM Service initialized.")
    except Exception as e:
        logger.critical(f"Failed to initialize LLM Service: {e}", exc_info=True)
        print(f"\nFATAL ERROR initializing LLM Service: {e}. Exiting.")
        sys.exit(1)

    host = '127.0.0.1'; port = 5000
    logger.info(f"Flask-SocketIO server starting on http://{host}:{port}")
    socketio.run(app, host=host, port=port, debug=False, use_reloader=False)

    logger.info("Application server stopped.")
    if simulation_loop_thread and simulation_loop_thread.is_alive():
         logger.info("Attempting final cleanup of simulation thread...")
         if workflow_manager and simulation_event_loop:
             try:
                future = asyncio.run_coroutine_threadsafe(workflow_manager.stop_simulation(), simulation_event_loop)
                future.result(timeout=10) # Wait for stop completion
             except Exception as e:
                 logger.error(f"Error during final simulation stop: {e}")
         simulation_loop_thread.join(timeout=5) # Wait for thread exit