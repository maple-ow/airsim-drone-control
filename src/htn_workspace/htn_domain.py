# htn_workspace/htn_domain.py
from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class Task:
    task_id: str
    task_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    required_capability: str = "basic"

@dataclass
class UAV:
    uav_id: str
    capabilities: List[str] = field(default_factory=lambda: ["basic", "fly", "photo", "recon"])
    current_state: Dict[str, Any] = field(default_factory=dict)
    current_task: Task = None