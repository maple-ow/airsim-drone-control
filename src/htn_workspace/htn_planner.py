# htn_workspace/htn_planner.py
from typing import List, Dict, Any
from dataclasses import dataclass, field
import json
import os
import sys

# 适配路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, PROJECT_ROOT)
import paths

# 从domain导入数据结构
from htn_domain import UAV, Task


class HTNPlanner:
    def __init__(self):
        pass

    def parse_upstream_json(self, upstream_json_path: str) -> List[Task]:
        """
        解析上游生成的JSON任务文件，转换为Task对象列表
        """
        if not os.path.exists(upstream_json_path):
            raise FileNotFoundError(f"上游任务文件不存在: {upstream_json_path}")

        with open(upstream_json_path, "r", encoding="utf-8") as f:
            upstream_json = json.load(f)

        task_list = []
        for subtask in upstream_json.get("subtasks", []):
            task = Task(
                task_id=subtask["subtask_id"],
                task_type=subtask["type"],
                params=subtask.get("params", {}),
                dependencies=subtask.get("dependencies", [])
            )
            task_list.append(task)
        return task_list

    def collect_required_uav_ids(self, upstream_json_path: str) -> List[str]:
        """
        【核心修复】从上游JSON中收集所有任务指定的无人机ID，避免硬编码
        """
        if not os.path.exists(upstream_json_path):
            raise FileNotFoundError(f"上游任务文件不存在: {upstream_json_path}")

        with open(upstream_json_path, "r", encoding="utf-8") as f:
            upstream_json = json.load(f)

        required_uav_ids = set()
        for subtask in upstream_json.get("subtasks", []):
            target_uavs = subtask.get("params", {}).get("_target_uavs", [])
            required_uav_ids.update(target_uavs)

        # 兜底：如果上游没有指定任何无人机，默认使用uav_1
        if not required_uav_ids:
            required_uav_ids.add("uav_1")

        return sorted(list(required_uav_ids))

    def plan(self, initial_tasks: List[Task], uavs: List[UAV]) -> Dict[str, List[Dict[str, Any]]]:
        """
        执行任务规划，严格遵守_target_uavs 约束
        """
        # 建立无人机 ID 到对象的映射
        uav_id_map = {uav.uav_id: uav for uav in uavs}
        # 初始化结果字典
        plan_result = {uav.uav_id: [] for uav in uavs}

        # 逐个分配任务
        for task in initial_tasks:
            # 优先读取任务指定的目标无人机
            target_uavs = task.params.get("_target_uavs", [])

            if target_uavs:
                # 只分配给指定的无人机，不在列表里的绝对不分配
                for uav_id in target_uavs:
                    if uav_id in uav_id_map:
                        # 转换为可序列化的字典，方便下游代码生成
                        serializable_task = {
                            "task_id": task.task_id,
                            "type": task.task_type,
                            "params": task.params,
                            "dependencies": task.dependencies,
                            "assigned_uav": uav_id
                        }
                        plan_result[uav_id].append(serializable_task)
            else:
                # 未指定无人机，默认分配给第一架无人机
                if uavs:
                    default_uav = uavs[0]
                    serializable_task = {
                        "task_id": task.task_id,
                        "type": task.task_type,
                        "params": task.params,
                        "dependencies": task.dependencies,
                        "assigned_uav": default_uav.uav_id
                    }
                    plan_result[default_uav.uav_id].append(serializable_task)

        # 只保留有任务的无人机，删除空任务列表
        plan_result = {uav_id: tasks for uav_id, tasks in plan_result.items() if tasks}
        return plan_result

    def save_plans_to_json(self, plans: Dict[str, List[Dict]], output_filename: str):
        """
        保存规划结果到JSON文件
        """
        save_dir = paths.HTN_PLANS_DIR
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        output_path = os.path.join(save_dir, output_filename)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(plans, f, indent=2, ensure_ascii=False)
        print(f"[HTN] 规划结果已保存至: {output_path}")
        return output_path