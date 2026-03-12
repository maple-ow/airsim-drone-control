from htn_domain import UAV, Task, HTNDomain
from typing import List, Dict, Any
import json


class HTNPlanner:
    def __init__(self, domain: HTNDomain):
        self.domain = domain

    def plan(self, initial_tasks: List[Task], available_uavs: List[UAV]) -> Dict[str, List[Task]]:
        """
        核心规划入口（完全匹配开题伪代码）
        :param initial_tasks: 初始任务列表（来自上游JSON或复合任务）
        :param available_uavs: 可用无人机列表
        :return: 每架无人机的时序化任务计划 {uav_id: [Task, Task, ...]}
        """
        print(f"[HTN] 开始规划，初始任务数: {len(initial_tasks)}, 可用无人机数: {len(available_uavs)}")

        # 步骤1：分解所有复合任务为原子任务（如果初始任务是复合的）
        all_primitive_tasks = self._decompose_all_tasks(initial_tasks, available_uavs)
        print(f"[HTN] 分解完成，原子任务数: {len(all_primitive_tasks)}")

        # 步骤2：为原子任务分配无人机
        uav_task_assignments = self._assign_tasks_to_uavs(all_primitive_tasks, available_uavs)
        print(f"[HTN] 任务分配完成，涉及无人机: {list(uav_task_assignments.keys())}")

        # 步骤3：为每架无人机生成时序化执行计划（基于依赖关系排序）
        final_plans = self._generate_temporal_plans(uav_task_assignments)
        print(f"[HTN] 时序计划生成完成")

        return final_plans

    def _decompose_all_tasks(self, tasks: List[Task], available_uavs: List[UAV]) -> List[Task]:
        """递归分解所有复合任务"""
        all_primitives = []
        for task in tasks:
            if task.task_type == "compound":
                # 查找分解规则并分解
                if task.task_type in self.domain.decomposition_rules:
                    subtasks = self.domain.decomposition_rules[task.task_type](task, available_uavs)
                    # 递归分解子任务
                    all_primitives.extend(self._decompose_all_tasks(subtasks, available_uavs))
                else:
                    raise ValueError(f"未知的复合任务类型: {task.task_type}")
            else:
                all_primitives.append(task)
        return all_primitives

    def _assign_tasks_to_uavs(self, tasks: List[Task], uavs: List[UAV]) -> Dict[str, List[Task]]:
        """
        基于能力匹配的任务分配（开题中的“智能体任务分配”步骤）
        策略：
        1. 优先分配给有对应能力的无人机
        2. 若任务无能力需求，分配给当前任务数最少的无人机（负载均衡）
        """
        assignments = {u.uav_id: [] for u in uavs}
        task_id_to_task = {t.task_id: t for t in tasks}

        # 先处理有明确依赖的任务，确保依赖任务和被依赖任务在同一架无人机上
        assigned_task_ids = set()

        # 第一轮：分配无依赖的任务
        for task in tasks:
            if not task.dependencies:
                self._assign_single_task(task, uavs, assignments)
                assigned_task_ids.add(task.task_id)

        # 第二轮：分配有依赖的任务，确保和依赖任务在同一架无人机
        while len(assigned_task_ids) < len(tasks):
            for task in tasks:
                if task.task_id in assigned_task_ids:
                    continue
                # 检查所有依赖是否已分配
                if all(dep_id in assigned_task_ids for dep_id in task.dependencies):
                    # 找到依赖任务所在的无人机
                    dep_task = task_id_to_task[task.dependencies[0]]
                    target_uav_id = dep_task.assigned_uav
                    # 分配到同一架无人机
                    assignments[target_uav_id].append(task)
                    task.assigned_uav = target_uav_id
                    assigned_task_ids.add(task.task_id)

        return assignments

    def _assign_single_task(self, task: Task, uavs: List[UAV], assignments: Dict[str, List[Task]]):
        """为单个无依赖任务分配无人机"""
        # 筛选有能力的无人机
        if task.required_capability:
            candidates = [u for u in uavs if task.required_capability in u.capabilities and u.is_available]
        else:
            candidates = [u for u in uavs if u.is_available]

        if not candidates:
            raise ValueError(f"没有可用无人机执行任务: {task.task_id} (需要能力: {task.required_capability})")

        # 选择当前任务数最少的无人机（负载均衡）
        candidates.sort(key=lambda u: len(assignments[u.uav_id]))
        selected_uav = candidates[0]

        assignments[selected_uav.uav_id].append(task)
        task.assigned_uav = selected_uav.uav_id

    def _generate_temporal_plans(self, assignments: Dict[str, List[Task]]) -> Dict[str, List[Task]]:
        """
        为每架无人机的任务排序（基于依赖关系的拓扑排序）
        这里简化处理：按任务ID的数字顺序排序，更复杂的可以做拓扑排序
        """
        final_plans = {}
        for uav_id, tasks in assignments.items():
            # 简单排序：按task_id中的数字排序
            def get_task_number(task):
                import re
                match = re.search(r'(\d+)', task.task_id)
                return int(match.group(1)) if match else 0

            tasks_sorted = sorted(tasks, key=get_task_number)
            final_plans[uav_id] = tasks_sorted
        return final_plans

    def save_plans_to_json(self, plans: Dict[str, List[Task]], output_path: str):
        """将规划结果保存为JSON，供下游代码生成器使用"""
        result = {}
        for uav_id, tasks in plans.items():
            result[uav_id] = []
            for task in tasks:
                result[uav_id].append({
                    "task_id": task.task_id,
                    "type": task.params.get("_upstream_type", task.task_type),
                    "params": task.params,
                    "dependencies": task.dependencies,
                    "assigned_uav": task.assigned_uav
                })

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"[HTN] 规划结果已保存至: {output_path}")
        return output_path