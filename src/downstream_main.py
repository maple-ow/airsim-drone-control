import sys
import os
import re
import json
import glob
import argparse
import time
from openai import OpenAI

# ========== 【核心修改】路径导入逻辑 ==========
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
import paths
from paths import (
    CONFIG_PATH,
    SYSTEM_PROMPTS_DIR,
    HTN_PLANS_DIR,
    GENERATED_CODES_DIR
)


# ===========================================

class Colors:
    YELLOW = "\033[33m"
    ENDC = "\033[0m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    BLUE = "\033[34m"


# ================== 复用的基础设施函数（已适配 paths） ==================
def load_config():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"找不到配置文件: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
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
        print(f"  [{idx + 1}] {cfg.get('name', f'配置{idx + 1}')}")
    print("=" * 60)
    choice = input("请输入序号 [默认 1]: ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(configs):
            return configs[idx]
        else:
            return configs[0]
    except:
        return configs[0]


def get_model_list(selected_api):
    print(f"🔍 正在获取模型列表...")
    try:
        client = OpenAI(api_key=selected_api["api_key"], base_url=selected_api["base_url"])
        models = client.models.list()
        model_ids = [m.id for m in models.data if "gpt" in m.id or "qwen" in m.id or "codex" in m.id]
        return sorted(model_ids)
    except Exception as e:
        print(f"❌ 获取模型列表失败: {e}")
        return ["gpt-4o", "gpt-5.2-codex"]


def select_model(selected_api):
    model_ids = get_model_list(selected_api)
    if not model_ids:
        return None
    print("\n" + "=" * 60)
    print("✅ 找到以下模型：")
    print("=" * 60)
    for i, mid in enumerate(model_ids[:10]):
        print(f"  [{i + 1}] {mid}")
    print("=" * 60)
    choice = input(f"请选择模型序号 [默认 1]: ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(model_ids):
            return model_ids[idx]
        else:
            return model_ids[0]
    except:
        return model_ids[0]


def read_prompt(filepath):
    full_path = os.path.join(SYSTEM_PROMPTS_DIR, os.path.basename(filepath))
    if not os.path.exists(full_path):
        print(f"⚠️  找不到提示词文件: {full_path}")
        return ""
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


def extract_python_code(content):
    code_block_regex = re.compile(r"```(?:python)?\s*([\s\S]*?)\s*```")
    match = code_block_regex.search(content)
    if match:
        return match.group(1).strip()
    return content.strip()


# ================== 主程序 ==================
def main():
    parser = argparse.ArgumentParser(description="【下游模块】HTN规划结果→AirSim代码生成器")
    parser.add_argument("--sysprompt", type=str, default="downstream_code_gen.txt", help="下游系统提示词文件名")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🚁 【下游】AirSim代码生成控制台")
    print("=" * 60)

    # 1. 加载配置
    try:
        config = load_config()
    except Exception as e:
        print(f"{Colors.RED}❌ 配置加载失败: {e}{Colors.ENDC}")
        return

    # 2. 选择 API 和模型
    selected_api = select_api_config(config)
    client = OpenAI(api_key=selected_api["api_key"], base_url=selected_api["base_url"])

    selected_model = select_model(selected_api)
    if not selected_model:
        print(f"{Colors.RED}❌ 未选择模型{Colors.ENDC}")
        return
    print(f"\n🎯 当前模型: {selected_model}")

    # 3. 加载提示词
    print(f"\n[步骤1] 加载提示词: {args.sysprompt}")
    system_prompt = read_prompt(args.sysprompt)
    if not system_prompt:
        print(f"{Colors.RED}❌ 提示词加载失败{Colors.ENDC}")
        return

    # 4. 选择 HTN 规划结果
    print("\n[步骤2] 选择HTN规划结果文件...")
    htn_plans_dir = HTN_PLANS_DIR
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

    # 5. 读取 HTN 规划
    print("\n[步骤3] 解析HTN规划结果...")
    with open(selected_htn_file, "r", encoding="utf-8") as f:
        htn_plan = json.load(f)

    uav_ids = list(htn_plan.keys())
    print(f"  涉及无人机: {', '.join(uav_ids)}")

    # 6. 为每架无人机生成代码
    print("\n" + "-" * 60)
    print(f"{Colors.BLUE}[开始生成代码]{Colors.ENDC}")
    print("-" * 60)

    codes_dir = GENERATED_CODES_DIR
    if not os.path.exists(codes_dir):
        os.makedirs(codes_dir)

    generated_files = []

    for uav_id in uav_ids:
        print(f"\n🤖 正在为 {uav_id} 生成代码...")

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

            code = extract_python_code(reply)
            if code:
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

    # 7. 询问是否执行
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