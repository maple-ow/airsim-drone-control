import os
import sys
import json
import re
from htn_domain import UAV, Task, HTNDomain
from typing import List, Dict, Any

# ========== 【优化】直接导入 paths.py，统一路径管理 ==========
HTN_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(HTN_ROOT))  # 退两级到根目录 F:\air\
sys.path.insert(0, PROJECT_ROOT)
try:
    import paths
    from paths import HTN_PLANS_DIR
except ImportError:
    print("⚠️  未找到 paths.py，将使用默认路径")
    HTN_PLANS_DIR = os.path.join(HTN_ROOT, "htn_plans")


# ============================================================

class HTNPlanner:
    def __init__(self, domain: HTNDomain):
        self.domain = domain

    def plan(self, initial_tasks: List[Task], available_uavs: List[UAV]) -> Dict[str, List[Task]]:
        """
        核心规划入口（完全匹配开题伪代码 + 空任务过滤）
        :param initial_tasks: 初始任务列表（来自上游JSON或复合任务）
        :param available_uavs: 可用无人机列表
        :return: 每架无人机的时序化任务计划 {uav_id: [Task, Task, ...]}，仅包含有任务的无人机
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

        # ================== 【核心修改1】双保险：过滤掉任务列表为空的无人机 ==================
        filtered_final_plans = {}
        for uav_id, tasks in final_plans.items():
            if tasks:  # 只保留有任务的无人机
                filtered_final_plans[uav_id] = tasks

        print(f"[HTN] 时序计划生成完成，共 {len(filtered_final_plans)} 台无人机有任务")
        return filtered_final_plans
        # ====================================================================================

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

        # ================== 【核心修改2】提前过滤：分配完成后立即去掉空任务列表 ==================
        filtered_assignments = {}
        for uav_id, assigned_tasks in assignments.items():
            if assigned_tasks:
                filtered_assignments[uav_id] = assigned_tasks

        return filtered_assignments
        # ====================================================================================

    def _assign_single_task(self, task: Task, uavs: List[UAV], assignments: Dict[str, List[Task]]):
        """为单个无依赖任务分配无人机"""
        # 筛选有能力的无人机
        if hasattr(task, 'required_capability') and task.required_capability:
            candidates = [u for u in uavs if task.required_capability in u.capabilities]
        else:
            candidates = uavs

        if not candidates:
            raise ValueError(
                f"没有可用无人机执行任务: {task.task_id} (需要能力: {getattr(task, 'required_capability', '无')})")

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
                match = re.search(r'(\d+)', task.task_id)
                return int(match.group(1)) if match else 0

            tasks_sorted = sorted(tasks, key=get_task_number)
            final_plans[uav_id] = tasks_sorted
        return final_plans

    def save_plans_to_json(self, plans: Dict[str, List[Task]], output_path: str = None):
        """
        将规划结果保存为JSON，供下游代码生成器使用
        【优化】如果未指定 output_path，自动使用 paths.py 中的 HTN_PLANS_DIR
        """
        # ================== 【优化】自动路径处理 ==================
        if output_path is None:
            # 如果只传了文件名，自动拼接到 HTN_PLANS_DIR
            if os.path.basename(output_path) == output_path:
                output_path = os.path.join(HTN_PLANS_DIR, output_path)

        # ================== 【核心修改3】保存前再次过滤 ==================
        result = {}
        for uav_id, tasks in plans.items():
            if tasks:  # 只保存有任务的无人机
                result[uav_id] = []
                for task in tasks:
                    result[uav_id].append({
                        "task_id": task.task_id,
                        "type": task.params.get("_upstream_type", task.task_type),
                        "params": task.params,
                        "dependencies": task.dependencies,
                        "assigned_uav": task.assigned_uav
                    })

        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"[HTN] 规划结果已保存至: {output_path}")
        return output_path