# htn_workspace/test_htn.py
import sys
import os
import json
import glob

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

import paths
from htn_planner import HTNPlanner, Task, UAV


def main():
    print("\n" + "=" * 60)
    print("🤖 HTN 任务规划器")
    print("=" * 60)

    # 1. 选择上游JSON文件
    print("\n[步骤1] 选择上游结构化任务文件...")
    tasks_dir = paths.STRUCTURED_TASKS_DIR
    if not os.path.exists(tasks_dir):
        print(f"⚠️  未找到上游任务文件夹: {tasks_dir}")
        return

    json_files = sorted(glob.glob(os.path.join(tasks_dir, "*.json")), key=os.path.getmtime, reverse=True)
    if not json_files:
        print(f"⚠️  上游任务文件夹为空")
        return

    print("  找到以下文件（最新的在最前）：")
    for i, f in enumerate(json_files[:5]):
        print(f"  [{i + 1}] {os.path.basename(f)}")

    choice = input("\n请选择文件序号 [默认 1]: ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(json_files):
            selected_file = json_files[idx]
        else:
            selected_file = json_files[0]
    except:
        selected_file = json_files[0]
    print(f"✅ 已选择: {os.path.basename(selected_file)}")

    # 2. 读取上游JSON
    with open(selected_file, "r", encoding="utf-8") as f:
        upstream_json = json.load(f)

    # 3. 动态收集需要的无人机 ID
    required_uav_ids = set()
    for subtask in upstream_json.get("subtasks", []):
        target_uavs = subtask.get("params", {}).get("_target_uavs", [])
        required_uav_ids.update(target_uavs)

    # 如果上游没有指定任何无人机，默认用 uav_1
    if not required_uav_ids:
        required_uav_ids = {"uav_1"}

    print(f"\n[步骤2] 检测到需要的无人机: {', '.join(required_uav_ids)}")

    # 4. 只初始化需要的无人机
    planner = HTNPlanner()
    initial_tasks = planner.parse_upstream_json(upstream_json)

    uavs = [UAV(uav_id=uav_id) for uav_id in required_uav_ids]

    # 5. 执行规划
    print("\n[步骤3] 正在执行HTN任务规划...")
    plans = planner.plan(initial_tasks, uavs)

    # 6. 打印规划结果
    print("\n" + "-" * 60)
    print("📋 规划结果：")
    print("-" * 60)
    for uav_id, tasks in plans.items():
        print(f"\n🚁 {uav_id} 任务列表 ({len(tasks)} 个任务):")
        for task in tasks:
            print(f"  - [{task['task_id']}] {task['type']}")

    # 7. 保存结果
    output_filename = f"htn_plan_{os.path.basename(selected_file)}"
    planner.save_plans_to_json(plans, output_filename)


if __name__ == "__main__":
    main()