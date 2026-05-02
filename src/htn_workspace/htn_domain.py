# src/htn_workspace/htn_domain.py
from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable


# ==================== 基础数据结构 ====================
@dataclass
class Task:
    task_id: str
    task_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)


@dataclass
class UAV:
    uav_id: str
    capabilities: List[str] = field(default_factory=lambda: ["fly", "camera"])


# ==================== HTN 核心域定义 ====================

# 1. 原子任务 (Primitive Tasks)
# 这些任务不会被 HTN 拆解，将直接透传给下游大模型用于生成 AirSim 代码。
PRIMITIVE_TASKS = {
    # 基础飞控微操
    "takeoff",
    "land",
    "fly_to",
    "fly_path",
    "set_yaw",
    "take_photo",
    # 高阶灵活扩展 (HTN 不拆解，由下游大模型手写复杂代码)
    "generate_trajectory",
    "custom_skill"
}


# 2. 复合任务拆解方法 (Methods)
# 方法签名：def method_name(state: dict, params: dict) -> List[Dict]

def method_inspect_target(state: dict, params: dict) -> List[Dict]:
    """
    拆解规则：标准目标检查流程
    流程：起飞 -> 飞向目标 -> 绕圈/对准拍照 -> 返航 -> 降落
    """
    target = params.get("target", "unknown_target")
    home_pos = params.get("home_pos", [0, 0, 10])  # 默认返航点

    return [
        {"type": "takeoff", "params": {"height": 10}},
        {"type": "fly_to", "params": {"target_name": target, "velocity": 2}},
        {"type": "take_photo", "params": {"camera_name": "0"}},
        {"type": "fly_to", "params": {"target_pos": home_pos, "velocity": 3}},
        {"type": "land", "params": {}}
    ]


def method_patrol_area(state: dict, params: dict) -> List[Dict]:
    """
    拆解规则：区域巡逻流程
    流程：起飞 -> 沿航点平滑飞行 -> 返航 -> 降落
    """
    points = params.get("points", [])
    home_pos = params.get("home_pos", [0, 0, 15])

    return [
        {"type": "takeoff", "params": {"height": 15}},
        # is_circle=True 会在下游调用 moveOnPathAsync 时启用平滑转角
        {"type": "fly_path", "params": {"points": points, "velocity": 3, "is_circle": True}},
        {"type": "fly_to", "params": {"target_pos": home_pos, "velocity": 3}},
        {"type": "land", "params": {}}
    ]


# 3. 注册复合任务库 (HTN Methods Dictionary)
HTN_METHODS = {
    "inspect_target": [method_inspect_target],
    "patrol_area": [method_patrol_area]
}