import os
import sys
import glob
import json
from htn_domain import UAV, Task, HTNDomain
from htn_planner import HTNPlanner

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


class Colors:
    GREEN = "\033[32m"
    ENDC = "\033[0m"
    BLUE = "\033[34m"
    YELLOW = "\033[33m"


def main():
    print("\n" + "=" * 60)
    print("🚁 HTN规划器测试控制台")
    print("=" * 60)

    # ================== 1. 初始化无人机（对应开题中的 U 集合） ==================
    print("\n[步骤1] 初始化无人机编队...")
    # 你可以根据需要修改这里的无人机配置
    uavs = [
        UAV(uav_id="uav_1", capabilities=["recon", "photo", "fly"], current_state={"battery": 100}),
        UAV(uav_id="uav_2", capabilities=["recon", "relay", "fly"], current_state={"battery": 100}),
        UAV(uav_id="uav_3", capabilities=["photo", "fly"], current_state={"battery": 100})
    ]
    for uav in uavs:
        print(f"  - {uav.uav_id}: 能力={uav.capabilities}, 电量={uav.current_state.get('battery', 100)}%")

    # ================== 2. 选择上游生成的JSON任务 ==================
    print("\n[步骤2] 选择上游任务文件...")
    tasks_dir = os.path.join(PROJECT_ROOT, "structured_tasks")
    if not os.path.exists(tasks_dir):
        print(f"⚠️  未找到上游任务文件夹: {tasks_dir}，请先运行 upstream_main.py 生成任务")
        return

    # 列出所有JSON文件，按时间从新到旧排序
    json_files = sorted(glob.glob(os.path.join(tasks_dir, "*.json")), key=os.path.getmtime, reverse=True)
    if not json_files:
        print(f"⚠️  上游任务文件夹为空，请先运行 upstream_main.py 生成任务")
        return

    print("  找到以下上游任务文件（最新的在最前）：")
    for i, f in enumerate(json_files[:5]):  # 只显示最新的5个
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

    # ================== 3. 运行HTN规划 ==================
    print("\n[步骤3] 运行HTN规划器...")
    domain = HTNDomain()
    planner = HTNPlanner(domain)

    # 转换上游JSON为HTN任务
    initial_tasks = domain.convert_upstream_json_to_tasks(selected_file)

    # 执行规划
    try:
        plans = planner.plan(initial_tasks, uavs)
    except Exception as e:
        print(f"❌ 规划失败: {e}")
        return

    # ================== 4. 可视化规划结果 ==================
    print("\n" + "-" * 60)
    print(f"{Colors.BLUE}[规划结果可视化]{Colors.ENDC}")
    print("-" * 60)
    for uav_id, tasks in plans.items():
        print(f"\n{Colors.GREEN}🎯 无人机 {uav_id} 的执行计划:{Colors.ENDC}")
        for i, task in enumerate(tasks):
            print(
                f"  {i + 1}. [{task.task_id}] {task.params.get('_upstream_type', task.task_type)} -> 参数: {task.params}")

    # ================== 5. 保存规划结果（供下游使用） ==================
    print("\n[步骤4] 保存规划结果...")
    output_dir = os.path.join(PROJECT_ROOT, "htn_plans")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_filename = f"htn_plan_{os.path.basename(selected_file)}"
    output_path = os.path.join(output_dir, output_filename)
    planner.save_plans_to_json(plans, output_path)

    print(f"\n{Colors.GREEN}✅ HTN规划完成！下游可以读取: {output_filename}{Colors.ENDC}")


if __name__ == "__main__":
    main()