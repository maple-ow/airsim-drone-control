# src/htn_workspace/htn_planner.py
from typing import List, Dict, Any
import json
import os
import sys

# 适配路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, PROJECT_ROOT)
import paths

# 导入 HTN 域定义
from htn_domain import UAV, Task, PRIMITIVE_TASKS, HTN_METHODS


class HTNPlanner:
    def __init__(self):
        pass

    def parse_upstream_json(self, upstream_json_path: str) -> List[Task]:
        """解析上游生成的JSON任务文件，转换为Task对象列表"""
        if not os.path.exists(upstream_json_path):
            raise FileNotFoundError(f"上游任务文件不存在: {upstream_json_path}")

        with open(upstream_json_path, "r", encoding="utf-8") as f:
            upstream_json = json.load(f)

        task_list = []
        for subtask in upstream_json.get("subtasks", []):
            task = Task(
                task_id=subtask.get("subtask_id", "T_unknown"),
                task_type=subtask.get("type", "unknown"),
                params=subtask.get("params", {}),
                dependencies=subtask.get("dependencies", [])
            )
            task_list.append(task)
        return task_list

    def collect_required_uav_ids(self, upstream_json_path: str) -> List[str]:
        """从上游JSON中收集所有任务指定的无人机ID"""
        if not os.path.exists(upstream_json_path):
            raise FileNotFoundError(f"上游任务文件不存在: {upstream_json_path}")

        with open(upstream_json_path, "r", encoding="utf-8") as f:
            upstream_json = json.load(f)

        required_uav_ids = set()
        for subtask in upstream_json.get("subtasks", []):
            target_uavs = subtask.get("params", {}).get("_target_uavs", [])
            required_uav_ids.update(target_uavs)

        if not required_uav_ids:
            required_uav_ids.add("uav_1")

        return sorted(list(required_uav_ids))

    def decompose_task(self, task_dict: dict, current_state: dict) -> List[Dict[str, Any]]:
        """
        【HTN 核心引擎】递归拆解任务
        将高级复合任务一步步拆解为原子任务列表。
        """
        task_type = task_dict["type"]
        params = task_dict.get("params", {})

        # 1. 递归基：如果是原子任务 (含 generate_trajectory / custom_skill)，直接返回
        if task_type in PRIMITIVE_TASKS:
            return [task_dict]

        # 2. 如果是复合任务，查找对应的拆解方法
        if task_type in HTN_METHODS:
            methods = HTN_METHODS[task_type]
            for method in methods:
                sub_tasks_raw = method(current_state, params)
                if sub_tasks_raw is not None:
                    final_plan = []
                    for i, sub_raw in enumerate(sub_tasks_raw):
                        # 【核心修复】：复合任务拆解时，只有第一个子任务继承父任务的依赖等待锁
                        inherited_deps = task_dict.get("dependencies", []) if i == 0 else []

                        sub_task = {
                            "task_id": f"{task_dict.get('task_id', 'T')}_sub{i + 1}",
                            "type": sub_raw["type"],
                            "params": sub_raw.get("params", {}),
                            "dependencies": inherited_deps,
                            "assigned_uav": task_dict.get("assigned_uav")
                        }
                        # 递归处理
                        final_plan.extend(self.decompose_task(sub_task, current_state))
                    return final_plan

        # 3. 动态容错：既不是已知原子任务，也没定义拆解方法
        print(f"  [HTN 提示] 遇到未定义任务类型 '{task_type}'，将其作为动态原子任务透传。")
        return [task_dict]

    def plan(self, initial_tasks: List[Task], uavs: List[UAV]) -> Dict[str, List[Dict[str, Any]]]:
        """执行完整规划：阶段一 (初级分配) -> 阶段二 (深度拆解)"""
        uav_id_map = {uav.uav_id: uav for uav in uavs}

        # === 阶段一：初级任务分配 ===
        initial_plan = {uav.uav_id: [] for uav in uavs}
        for task in initial_tasks:
            target_uavs = task.params.get("_target_uavs", [])
            if target_uavs:
                for uav_id in target_uavs:
                    if uav_id in uav_id_map:
                        initial_plan[uav_id].append({
                            "task_id": task.task_id,
                            "type": task.task_type,
                            "params": task.params,
                            "dependencies": task.dependencies,
                            "assigned_uav": uav_id
                        })
            else:
                if uavs:
                    default_uav = uavs[0]
                    initial_plan[default_uav.uav_id].append({
                        "task_id": task.task_id,
                        "type": task.task_type,
                        "params": task.params,
                        "dependencies": task.dependencies,
                        "assigned_uav": default_uav.uav_id
                    })

        # === 阶段二：HTN 深度拆解 ===
        final_plan = {}
        for uav_id, tasks in initial_plan.items():
            if not tasks:
                continue

            decomposed_tasks = []
            current_state = {"uav_id": uav_id, "battery": 100}

            for task in tasks:
                expanded_sequence = self.decompose_task(task, current_state)
                decomposed_tasks.extend(expanded_sequence)

            final_plan[uav_id] = decomposed_tasks

        return final_plan

    def save_plans_to_json(self, plans: Dict[str, List[Dict]], output_filename: str):
        """保存规划结果到JSON文件"""
        save_dir = paths.HTN_PLANS_DIR
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        output_path = os.path.join(save_dir, output_filename)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(plans, f, indent=2, ensure_ascii=False)
        print(f"  [HTN] 深度规划结果已保存至: {output_path}")
        return output_path