
import sys
import os
import re
import json
import glob
import argparse
from openai import OpenAI

# 关键：路径统一
HTN_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


class Colors:
    YELLOW = "\033[33m"
    ENDC = "\033[0m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    BLUE = "\033[34m"


# ================== 复用上游的基础设施函数 ==================
def load_config(config_path="config.json"):
    path = os.path.join(PROJECT_ROOT, config_path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到配置文件: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def select_api_config(config):
    configs = config.get("api_configs", [])
    if not configs:
        return {
            "base_url": config.get("BASE_URL", "https://api.openai.com/v1"),
            "api_key": config.get("API_KEY", "")
        }
    print("\n" + "=" * 60)
    print("🌐 请选择 API 配置：")
    print("=" * 60)
    for idx, cfg in enumerate(configs):
        print(f"  [{idx + 1}] {cfg['name']}")
    print("=" * 60)
    choice = input("请输入序号 [默认 1]: ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(configs):
            selected = configs[idx]
        else:
            selected = configs[0]
    except:
        selected = configs[0]
    print(f"✅ 已选择: {selected['name']}")
    return selected


def get_model_list(selected_api):
    print(f"🔍 正在获取模型列表...")
    try:
        client = OpenAI(api_key=selected_api["api_key"], base_url=selected_api["base_url"])
        models = client.models.list()
        sorted_models = sorted(models.data, key=lambda x: x.created, reverse=True)
        return [m.id for m in sorted_models]
    except Exception as e:
        print(f"❌ 获取模型失败，请检查 API Key 和网络: {e}")
        return None


def select_model(selected_api):
    model_ids = get_model_list(selected_api)
    if not model_ids:
        return None
    print("\n" + "=" * 60)
    print("✅ 找到以下接入点：")
    print("=" * 60)
    for i, mid in enumerate(model_ids):
        print(f"  [{i + 1}] {mid}")
    print("=" * 60)
    choice = input(f"请选择模型 [默认 1]: ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(model_ids):
            return model_ids[idx]
    except:
        pass
    print("➡️  默认选择第1个")
    return model_ids[0]


def read_prompt(filepath):
    full_path = os.path.join(PROJECT_ROOT, filepath)
    if not os.path.exists(full_path):
        print(f"⚠️  找不到提示词文件: {full_path}")
        return ""
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


def extract_python_code(content):
    """从回复中提取Python代码（复用基线代码逻辑）"""
    code_block_regex = re.compile(r"```(.*?)```", re.DOTALL)
    code_blocks = code_block_regex.findall(content)
    if code_blocks:
        full_code = "\n".join(code_blocks)
        if full_code.startswith("python"):
            full_code = full_code[7:]
        return full_code.strip()
    return None


# ================== 下游核心逻辑 ==================

def main():
    parser = argparse.ArgumentParser(description="【下游模块】HTN规划结果转AirSim代码生成器")
    parser.add_argument("--sysprompt", type=str, default="system_prompts/downstream_code_gen.txt",
                        help="下游系统提示词文件路径")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🚁 【下游】AirSim代码生成控制台")
    print("=" * 60)

    # ================== 1. 加载配置和初始化 ==================
    try:
        config = load_config()
    except Exception as e:
        print(f"{Colors.RED}❌ 配置加载失败: {e}{Colors.ENDC}")
        return

    selected_api = select_api_config(config)
    print("正在初始化 API 客户端...")
    client = OpenAI(api_key=selected_api["api_key"], base_url=selected_api["base_url"])

    # ================== 2. 选择HTN规划结果文件 ==================
    print("\n[步骤1] 选择HTN规划结果文件...")
    htn_plans_dir = os.path.join(HTN_ROOT, "htn_plans")
    if not os.path.exists(htn_plans_dir):
        print(f"⚠️  未找到HTN规划文件夹: {htn_plans_dir}，请先运行 test_htn.py")
        return

    json_files = sorted(glob.glob(os.path.join(htn_plans_dir, "*.json")), key=os.path.getmtime, reverse=True)
    if not json_files:
        print(f"⚠️  HTN规划文件夹为空，请先运行 test_htn.py")
        return

    print("  找到以下HTN规划文件（最新的在最前）：")
    for i, f in enumerate(json_files[:5]):
        print(f"  [{i + 1}] {os.path.basename(f)}")

    choice = input("\n请选择文件序号 [默认 1]: ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(json_files):
            selected_htn_file = json_files[idx]
        else:
            selected_htn_file = json_files[0]
    except:
        selected_htn_file = json_files[0]
    print(f"✅ 已选择: {os.path.basename(selected_htn_file)}")

    # ================== 3. 加载下游提示词并选择模型 ==================
    print(f"\n[步骤3] 加载下游提示词: {args.sysprompt}")
    system_prompt = read_prompt(args.sysprompt)
    if not system_prompt:
        print(f"{Colors.RED}❌ 提示词加载失败{Colors.ENDC}")
        return

    selected_model = select_model(selected_api)
    if not selected_model:
        return
    print(f"\n🎯 当前模型: {selected_model}")

    # ================== 4. 读取并解析HTN规划结果 ==================
    print("\n[步骤2] 解析HTN规划结果...")
    with open(selected_htn_file, "r", encoding="utf-8") as f:
        htn_plan = json.load(f)

    uav_ids = list(htn_plan.keys())
    print(f"  涉及无人机: {', '.join(uav_ids)}")

    # ================== 5. 为每架无人机生成代码 ==================
    print("\n" + "-" * 60)
    print(f"{Colors.BLUE}[开始生成代码]{Colors.ENDC}")
    print("-" * 60)

    codes_dir = os.path.join(HTN_ROOT, "generated_codes")
    if not os.path.exists(codes_dir):
        os.makedirs(codes_dir)

    generated_files = []

    for uav_id in uav_ids:
        print(f"\n🤖 正在为 {uav_id} 生成代码...")

        # 构建输入
        input_data = {
            "uav_id": uav_id,
            "tasks": htn_plan[uav_id]
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(input_data, ensure_ascii=False, indent=2)}
        ]

        try:
            response = client.chat.completions.create(
                model=selected_model,
                messages=messages,
                temperature=0
            )
            reply = response.choices[0].message.content

            # 提取代码
            code = extract_python_code(reply)
            if code:
                # 保存代码
                code_filename = f"{uav_id}_code_{os.path.basename(selected_htn_file).replace('.json', '.py')}"
                code_path = os.path.join(codes_dir, code_filename)
                with open(code_path, "w", encoding="utf-8") as f:
                    f.write(code)
                print(f"{Colors.GREEN}✅ {uav_id} 代码已保存: {code_filename}{Colors.ENDC}")
                generated_files.append((uav_id, code_path))
            else:
                print(f"{Colors.RED}❌ {uav_id} 未能提取到有效代码{Colors.ENDC}")
                print(f"模型回复预览: {reply[:200]}...")

        except Exception as e:
            print(f"{Colors.RED}❌ {uav_id} 代码生成失败: {e}{Colors.ENDC}")

    # ================== 6. 询问是否执行 ==================
    if generated_files:
        print("\n" + "=" * 60)
        print(f"{Colors.GREEN}🎉 所有代码生成完成！{Colors.ENDC}")
        print("=" * 60)

        confirm = input(f"\n{Colors.YELLOW}是否现在执行生成的代码? (y/n，仅单无人机测试): {Colors.ENDC}").lower()
        if confirm == 'y':
            if len(generated_files) == 1:
                uav_id, code_path = generated_files[0]
                print(f"\n🚀 正在执行 {uav_id} 的代码...")
                try:
                    # 导入并执行代码
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("drone_code", code_path)
                    drone_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(drone_module)
                except Exception as e:
                    print(f"{Colors.RED}❌ 执行报错: {e}{Colors.ENDC}")
            else:
                print(
                    f"{Colors.YELLOW}⚠️  多无人机代码请手动分别运行，文件位于: htn_workspace/generated_codes/{Colors.ENDC}")


if __name__ == "__main__":
    main()