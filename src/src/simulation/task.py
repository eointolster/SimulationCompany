import uuid
import logging
from typing import Dict, Optional, Any

# Define standardized task statuses
STATUS_PENDING = 'pending'
STATUS_IN_PROGRESS = 'in_progress'
STATUS_COMPLETED = 'completed'
STATUS_FAILED = 'failed'
STATUS_WAITING_RESPONSE = 'waiting_user_input'
STATUS_WAITING_DEPENDENCY = 'waiting_dependency'

logger = logging.getLogger(__name__)

class Task:
    def __init__(self,
                 task_type: str,
                 description: str,
                 details: Optional[Dict[str, Any]] = None,
                 assigned_to_role: Optional[str] = None,
                 originating_task_id: Optional[str] = None,
                 task_id: Optional[str] = None):
        """
        A task object used to track work assigned to agents.
        """
        self.task_id = task_id or f"task_{uuid.uuid4().hex[:8]}"
        self.task_type = task_type
        self.description = description
        self.details = details or {}
        self.assigned_to_role = assigned_to_role
        self.originating_task_id = originating_task_id
        self.status = STATUS_PENDING
        self.result: Optional[str] = None
        self.child_tasks: Dict[str, str] = {}  # Mapping of subtask_id -> status
        self.dependencies: Dict[str, Dict[str, Any]] = {}  # Track inputs needed (e.g., {"marketing_strategy": {...}})
        self.last_update_time: Optional[float] = None  # Could be set externally to throttle task rechecks

        logger.debug(f"Task created: {self.task_id} [{self.task_type}] - Assigned to: {assigned_to_role}")

    def to_dict(self) -> Dict[str, Any]:
        """Return a serializable dict for messaging or logging."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "description": self.description,
            "details": self.details,
            "assigned_to_role": self.assigned_to_role,
            "originating_task_id": self.originating_task_id,
            "status": self.status,
            "result": self.result,
            "child_tasks": self.child_tasks,
            "dependencies": self.dependencies
        }

    def update_status(self, new_status: str):
        """Update task status with optional logging."""
        logger.info(f"Task {self.task_id} status changed: {self.status} -> {new_status}")
        self.status = new_status

    def is_waiting_for_dependencies(self) -> bool:
        """Returns True if the task is still waiting for required inputs from other agents."""
        for dep, value in self.dependencies.items():
            if not value.get("ready"):
                logger.debug(f"Task {self.task_id} still waiting for dependency: {dep}")
                return True
        return False

    def mark_dependency_ready(self, dep_name: str, content: Any, metadata: Optional[Dict[str, Any]] = None):
        """Mark a dependency as satisfied."""
        self.dependencies[dep_name] = {
            "ready": True,
            "content": content,
            "metadata": metadata or {}
        }
        logger.info(f"Task {self.task_id}: Dependency '{dep_name}' marked as ready.")

    def get_dependency(self, dep_name: str) -> Optional[Dict[str, Any]]:
        """Return the full dependency dict if available."""
        return self.dependencies.get(dep_name)

    def add_dependency(self, dep_name: str, required: bool = True):
        """Register a new dependency required for task execution."""
        if dep_name not in self.dependencies:
            self.dependencies[dep_name] = {"ready": not required, "content": None}
            logger.debug(f"Task {self.task_id}: Added dependency '{dep_name}' (Required: {required})")
