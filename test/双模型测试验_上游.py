import sys
import os
import re
import time
import json
import argparse
from openai import OpenAI

# ================== 保留原有基础设施 ==================
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


class Colors:
    YELLOW = "\033[33m"
    ENDC = "\033[0m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    BLUE = "\033[34m"


try:
    from utils.airsim_wrapper import AirSimWrapper

    print("✅ AirSimWrapper 加载成功 (仅用于获取环境状态，不执行代码)")
except ImportError:
    print("⚠️  未找到 utils.airsim_wrapper，仅运行在纯文本模式")
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


def save_chat_history(model_name, test_name, history):
    chats_dir = os.path.join(PROJECT_ROOT, "chats_upstream")
    if not os.path.exists(chats_dir):
        os.makedirs(chats_dir)
    filename = f"{model_name.replace('/', '-')}-{test_name}.txt"
    filepath = os.path.join(chats_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        for msg in history:
            f.write(f"[{msg['role'].upper()}]\n{msg['content']}\n")
            f.write("\n" + "-" * 30 + "\n")
    print(f"{Colors.GREEN}📝 对话记录已保存至: {filename}{Colors.ENDC}")


def save_structured_task(model_name, test_name, task_data):
    """保存结构化JSON任务，供下游HTN使用"""
    tasks_dir = os.path.join(PROJECT_ROOT, "structured_tasks")
    if not os.path.exists(tasks_dir):
        os.makedirs(tasks_dir)
    filename = f"{model_name.replace('/', '-')}-{test_name}-{int(time.time())}.json"
    filepath = os.path.join(tasks_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(task_data, f, indent=2, ensure_ascii=False)
    print(f"{Colors.BLUE}📦 结构化任务已保存至: {filename}{Colors.ENDC}")
    return filepath


def extract_json(content):
    """优化：先判断是否是纯文本沟通，再尝试解析JSON"""
    # 若包含澄清/风险提示关键词，直接返回None（表示仅沟通，无任务）
    clarify_keywords = ["需要你补充", "存在安全风险", "请修改", "确认后我会"]
    if any(keyword in content for keyword in clarify_keywords):

        return None

    # 尝试直接解析JSON
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 尝试从代码块中提取JSON
    code_block_regex = re.compile(r"```(.*?)```", re.DOTALL)
    code_blocks = code_block_regex.findall(content)
    if code_blocks:
        for block in code_blocks:
            if block.startswith("json"):
                block = block[4:]
            try:
                return json.loads(block.strip())
            except json.JSONDecodeError:
                continue
    return None


def get_drone_status_text(aw):
    if not aw:
        return ""
    try:
        pos = aw.get_drone_position()
        yaw = aw.get_yaw()
        status_text = f"""
【当前环境/无人机状态】
- 当前位置 (X, Y, Z): ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})
- 当前朝向 (Yaw): {yaw:.1f} 度
"""
        return status_text
    except Exception as e:
        print(f"⚠️  获取状态失败: {e}")
        return ""


# ================== 上游主程序 ==================
def main():
    parser = argparse.ArgumentParser(description="【上游模块】无人机自然语言任务拆解器")
    # 保留和基线代码一致的提示词参数，默认指向独立的上游提示词文件
    parser.add_argument("--sysprompt", type=str, default="system_prompts/upstream_task_parser.txt",help="上游系统提示词文件路径")
    parser.add_argument("--testname", type=str, default="upstream_test_001", help="测试名称，用于保存文件")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🚁 【上游】无人机任务拆解控制台")
    print("=" * 60)

    # 加载配置
    try:
        config = load_config()
    except Exception as e:
        print(f"{Colors.RED}❌ 配置加载失败: {e}{Colors.ENDC}")
        return

    selected_api = select_api_config(config)

    # 初始化API客户端
    print("正在初始化 API 客户端...")
    client = OpenAI(
        api_key=selected_api["api_key"],
        base_url=selected_api["base_url"]
    )

    # 连接AirSim（仅获取状态）
    aw = None
    if AirSimWrapper:
        try:
            print("正在连接 AirSim (仅获取状态)...")
            aw = AirSimWrapper()
        except Exception as e:
            print(f"{Colors.RED}⚠️  AirSim 连接失败: {e}{Colors.ENDC}")
            print("   将仅运行在纯文本模式\n")

    # 加载独立的系统提示词文件
    print(f"正在加载上游系统提示词: {args.sysprompt}")
    system_prompt_content = read_prompt(args.sysprompt)
    if not system_prompt_content:
        print(f"{Colors.RED}❌ 系统提示词加载失败，程序退出{Colors.ENDC}")
        return
    messages = [{"role": "system", "content": system_prompt_content}]

    # 选择模型
    selected_model = select_model(selected_api)
    if not selected_model:
        return

    print(f"\n🎯 当前模型: {selected_model}")
    print("-" * 60)
    print("提示：输入指令进行拆解，输入 !quit 退出，输入 !clear 清屏")

    # 主交互循环
    try:
        while True:
            user_input = input(f"\n{Colors.YELLOW}[上游] 请输入指令> {Colors.ENDC}").strip()
            if not user_input:
                continue

            if user_input.lower() == 's':
                selected_model = select_model(selected_api)
                if selected_model:
                    print(f"\n🎯 已切换至模型: {selected_model}")
                continue

            # 退出指令
            if user_input.lower() in ["!quit", "!exit", "q"]:
                save_chat_history(selected_model, args.testname, messages)
                print("👋 再见！下游见！")
                break

            # 清屏指令
            if user_input.lower() == "!clear":
                os.system('cls' if os.name == 'nt' else 'clear')
                continue

            # 拼接环境状态（如果有）
            status_text = get_drone_status_text(aw)
            augmented_input = user_input + ("\n\n" + status_text if status_text else "")
            messages.append({"role": "user", "content": augmented_input})

            # 调用大模型生成任务拆解
            try:
                print("🤖 正在拆解任务...")
                response = client.chat.completions.create(
                    model=selected_model,
                    messages=messages,
                    temperature=0  # 固定温度，保证JSON格式稳定
                )
                reply = response.choices[0].message.content
                messages.append({"role": "assistant", "content": reply})

                # 打印模型回复
                print(f"\n{Colors.GREEN}{reply}{Colors.ENDC}")

                # 提取并验证JSON
                task_data = extract_json(reply)
                if task_data:
                    print(f"\n{Colors.BLUE}✅ 成功解析出结构化任务！{Colors.ENDC}")

                    # 提示澄清需求
                    if "ambiguity_check" in task_data and task_data["ambiguity_check"] != "无歧义":
                        print(f"{Colors.YELLOW}⚠️  模型需要澄清: {task_data['ambiguity_check']}{Colors.ENDC}")

                    # 保存JSON文件，供HTN规划器使用
                    save_structured_task(selected_model, args.testname, task_data)
                else:
                    print(f"\n{Colors.RED}❌ 未能解析出有效的JSON格式，请重试或修正提示词{Colors.ENDC}")

            except Exception as e:
                print(f"{Colors.RED}❌ API 调用错误: {e}{Colors.ENDC}")
    except KeyboardInterrupt:
        print("\n\n检测到中断，正在保存记录...")
        save_chat_history(selected_model, args.testname + "_interrupted", messages)


if __name__ == "__main__":
    main()