import sys
import os
import re
import time
import json
import argparse
from openai import OpenAI

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

class Colors:
    YELLOW = "\033[33m"
    ENDC = "\033[0m"
    GREEN = "\033[32m"
    RED = "\033[31m"

try:
    from utils.airsim_wrapper import AirSimWrapper
    print("✅ AirSimWrapper 加载成功")
except ImportError:
    print("⚠️  未找到 utils.airsim_wrapper，仅测试 API 连接")
    AirSimWrapper = None

def load_config(config_path="config.json"):
    path = os.path.join(PROJECT_ROOT, config_path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到配置文件: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def select_api_config(config):
    configs = config.get("api_configs", [])
    if not configs:
        print("⚠️  检测到旧版配置格式")
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
    print("✅ 找到以下接入点 (Endpoint)：")
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
        print(f"⚠️  找不到提示词文件: {full_path}，将使用空内容")
        return ""
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()

def extract_python_code(content):
    code_block_regex = re.compile(r"```(.*?)```", re.DOTALL)
    code_blocks = code_block_regex.findall(content)
    if code_blocks:
        full_code = "\n".join(code_blocks)
        if full_code.startswith("python"):
            full_code = full_code[7:]
        return full_code.strip()
    return None

def save_chat_history(model_name, test_name, history):
    chats_dir = os.path.join(PROJECT_ROOT, "chats")
    if not os.path.exists(chats_dir):
        os.makedirs(chats_dir)
    filename = f"{model_name.replace('/', '-')}-{test_name}.txt"
    filepath = os.path.join(chats_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        for msg in history:
            f.write(f"[{msg['role'].upper()}]\n{msg['content']}\n")
            f.write("\n" + "-" * 30 + "\n")
    print(f"{Colors.GREEN}📝 记录已保存至: {filename}{Colors.ENDC}")

def get_drone_status_text(aw):
    if not aw:
        return ""
    try:
        pos = aw.get_drone_position()
        yaw = aw.get_yaw()
        status_text = f"""
【无人机当前实时状态】
- 当前位置 (X, Y, Z): ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})
- 当前朝向 (Yaw): {yaw:.1f} 度
"""
        return status_text
    except Exception as e:
        print(f"⚠️  获取状态失败: {e}")
        return ""

def main():
    parser = argparse.ArgumentParser(description="无人机自然语言控制台 (完整版)")
    parser.add_argument("--prompt", type=str, default="prompts/airsim_empty.txt", help="用户提示词文件")
    parser.add_argument("--sysprompt", type=str, default="system_prompts/airsim_chinese.txt", help="系统提示词文件")
    parser.add_argument("--testname", type=str, default="test_001", help="测试名称")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🚁 无人机自然语言控制台")
    print("=" * 60)

    try:
        config = load_config()
    except Exception as e:
        print(f"{Colors.RED}❌ 配置加载失败: {e}{Colors.ENDC}")
        return

    selected_api = select_api_config(config)

    print("正在初始化 API 客户端...")
    client = OpenAI(
        api_key=selected_api["api_key"],
        base_url=selected_api["base_url"]
    )

    aw = None
    if AirSimWrapper:
        try:
            print("正在连接 AirSim...")
            aw = AirSimWrapper()
        except Exception as e:
            print(f"{Colors.RED}⚠️  AirSim 连接失败: {e}{Colors.ENDC}")
            print("   将仅运行在 API 测试模式\n")

    print(f"正在加载提示词: {args.sysprompt}")
    system_prompt_content = read_prompt(args.sysprompt)
    initial_prompt_content = read_prompt(args.prompt)

    messages = []
    if system_prompt_content:
        messages.append({"role": "system", "content": system_prompt_content})
    if initial_prompt_content:
        messages.append({"role": "user", "content": initial_prompt_content})

    selected_model = select_model(selected_api)
    if not selected_model:
        return

    print(f"\n🎯 当前模型: {selected_model}")
    print("-" * 60)

    try:
        while True:
            user_input = input(f"\n{Colors.YELLOW}AirSim> {Colors.ENDC}").strip()
            if not user_input:
                continue

            if user_input.lower() in ["!quit", "!exit", "q"]:
                save_chat_history(selected_model, args.testname, messages)
                print("👋 再见！")
                break

            if user_input.lower() == "!clear":
                os.system('cls' if os.name == 'nt' else 'clear')
                continue

            if user_input.lower() == 's':
                selected_model = select_model(selected_api)
                if selected_model:
                    print(f"\n🎯 已切换至模型: {selected_model}")
                continue

            status_text = get_drone_status_text(aw)
            augmented_input = user_input + "\n\n" + status_text
            messages.append({"role": "user", "content": augmented_input})

            if status_text:
                print(f"{Colors.GREEN}{status_text}{Colors.ENDC}")

            try:
                print("🤖 正在生成...")
                response = client.chat.completions.create(
                    model=selected_model,
                    messages=messages,
                    temperature=0.3
                )
                reply = response.choices[0].message.content
                messages.append({"role": "assistant", "content": reply})

                print(f"\n{reply}")

                code = extract_python_code(reply)
                if code:
                    confirm = input(f"\n{Colors.YELLOW}是否执行代码? (y/n): {Colors.ENDC}").lower()
                    if confirm == 'y':
                        if not aw:
                            print(f"{Colors.RED}❌ AirSim 未连接，无法执行物理代码{Colors.ENDC}")
                            continue
                        try:
                            print("🚀 执行中...")
                            exec_globals = {
                                "aw": aw,
                                "math": __import__("math"),
                                "numpy": __import__("numpy")
                            }
                            exec(code, exec_globals)
                            print(f"{Colors.GREEN}✅ 执行完毕{Colors.ENDC}")
                        except Exception as e:
                            print(f"{Colors.RED}❌ 执行报错: {e}{Colors.ENDC}")
            except Exception as e:
                print(f"{Colors.RED}❌ API 调用错误: {e}{Colors.ENDC}")
    except KeyboardInterrupt:
        print("\n\n检测到中断，正在保存记录...")
        save_chat_history(selected_model, args.testname + "_interrupted", messages)

if __name__ == "__main__":
    main()