from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import json


# ================== 1. 核心数据类定义（匹配开题数学建模） ==================

@dataclass
class UAV:
    """无人机类：对应开题中的 U = {u_1, u_2, ..., u_n}"""
    uav_id: str
    capabilities: List[str] = field(default_factory=list)  # 能力集：["recon", "photo", "relay", "fly"]
    current_state: Dict[str, Any] = field(default_factory=dict)  # 状态：位置、电量、是否可用
    is_available: bool = True


@dataclass
class Task:
    """任务类：对应开题中的 T = (τ_1, τ_2, ..., τ_K)"""
    task_id: str
    task_type: str  # "compound"（复合）或 "primitive"（原子）
    params: Dict[str, Any] = field(default_factory=dict)
    subtasks: List["Task"] = field(default_factory=list)  # 复合任务的子任务
    dependencies: List[str] = field(default_factory=list)  # 依赖的前置任务ID
    required_capability: Optional[str] = None  # 执行该任务需要的能力
    assigned_uav: Optional[str] = None  # 规划后分配的无人机ID


# ================== 2. HTN领域知识：分解规则库 ==================

class HTNDomain:
    def __init__(self):
        # 预定义复合任务的分解规则（可扩展）
        self.decomposition_rules = {
            "multi_uav_area_recon": self._decompose_multi_area_recon,
            "single_uav_patrol": self._decompose_single_patrol
        }

        # 预定义原子任务 -> 能力需求的映射
        self.task_capability_map = {
            "takeoff": None,
            "goto": None,
            "hover": None,
            "take_photo": "photo",
            "land": None,
            "return_to_launch": None,
            "recon": "recon",
            "relay": "relay"
        }

    def get_required_capability(self, task_type: str) -> Optional[str]:
        """获取任务类型对应的能力需求"""
        return self.task_capability_map.get(task_type, None)

    # ------------------ 复合任务分解规则实现 ------------------

    def _decompose_multi_area_recon(self, compound_task: Task, available_uavs: List[UAV]) -> List[Task]:
        """
        分解规则：多机区域侦察
        输入：复合任务（包含区域、无人机数量）
        输出：原子任务列表（每架无人机分配一个子区域）
        """
        area = compound_task.params.get("area", "unknown_area")
        num_uavs = len([u for u in available_uavs if "recon" in u.capabilities])

        # 简单的区域分割逻辑（可根据需要替换为更复杂的算法）
        sub_areas = [f"{area}_part_{i + 1}" for i in range(num_uavs)]

        subtasks = []
        for i, sub_area in enumerate(sub_areas):
            # 为每个子区域生成一组原子任务
            base_id = f"{compound_task.task_id}_uav{i + 1}"
            subtasks.extend([
                Task(task_id=f"{base_id}_takeoff", task_type="primitive", params={"height": 10}, dependencies=[],
                     required_capability=None),
                Task(task_id=f"{base_id}_goto", task_type="primitive", params={"target": sub_area, "height": 10},
                     dependencies=[f"{base_id}_takeoff"], required_capability=None),
                Task(task_id=f"{base_id}_recon", task_type="primitive", params={"duration": 10},
                     dependencies=[f"{base_id}_goto"], required_capability="recon"),
                Task(task_id=f"{base_id}_photo", task_type="primitive", params={"photo_name": f"{sub_area}_photo"},
                     dependencies=[f"{base_id}_recon"], required_capability="photo"),
                Task(task_id=f"{base_id}_return", task_type="primitive", params={}, dependencies=[f"{base_id}_photo"],
                     required_capability=None)
            ])
        return subtasks

    def _decompose_single_patrol(self, compound_task: Task, available_uavs: List[UAV]) -> List[Task]:
        """分解规则：单机巡逻（示例）"""
        waypoints = compound_task.params.get("waypoints", [])
        base_id = compound_task.task_id

        subtasks = [Task(task_id=f"{base_id}_takeoff", task_type="primitive", params={"height": 15}, dependencies=[],
                         required_capability=None)]

        for i, wp in enumerate(waypoints):
            subtasks.append(
                Task(task_id=f"{base_id}_goto_{i}", task_type="primitive", params={"target": wp, "height": 15},
                     dependencies=[subtasks[-1].task_id], required_capability=None)
            )

        subtasks.append(
            Task(task_id=f"{base_id}_land", task_type="primitive", params={}, dependencies=[subtasks[-1].task_id],
                 required_capability=None))
        return subtasks

    # ------------------ 上游JSON转HTN任务的转换函数 ------------------

    def convert_upstream_json_to_tasks(self, upstream_json_path: str) -> List[Task]:
        """
        【核心对接函数】读取上游生成的JSON文件，转换为HTN的Task对象列表
        """
        with open(upstream_json_path, "r", encoding="utf-8") as f:
            upstream_data = json.load(f)

        tasks = []
        for sub_json in upstream_data.get("subtasks", []):
            task = Task(
                task_id=sub_json["subtask_id"],
                task_type="primitive",  # 上游输出的都是原子任务
                params=sub_json["params"],
                dependencies=sub_json.get("dependency", []),
                required_capability=self.get_required_capability(sub_json["type"])
            )
            # 把上游的type存到params里，方便下游使用
            task.params["_upstream_type"] = sub_json["type"]
            tasks.append(task)

        return tasks