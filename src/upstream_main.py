import sys
import os
import re
import json
import argparse
import time
from openai import OpenAI

# ========== 【核心修改】路径导入逻辑 ==========
# 因为在 src/ 子目录下，先把根目录加到 sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
# 导入全局路径配置
import paths
from paths import (
    CONFIG_PATH,
    SYSTEM_PROMPTS_DIR,
    STRUCTURED_TASKS_DIR,
    CHATS_UPSTREAM_DIR
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
        # 简单过滤，只保留常用模型
        model_ids = [m.id for m in models.data if
                     "gpt" in m.id or "qwen" in m.id or "claude" in m.id or "llama" in m.id]
        return sorted(model_ids)
    except Exception as e:
        print(f"❌ 获取模型列表失败: {e}，将使用默认模型")
        return ["gpt-4o", "gpt-5.2"]


def select_model(selected_api):
    model_ids = get_model_list(selected_api)
    if not model_ids:
        return None
    print("\n" + "=" * 60)
    print("✅ 找到以下模型：")
    print("=" * 60)
    for i, mid in enumerate(model_ids[:10]):  # 只显示前10个
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
    """读取提示词文件（已适配 paths）"""
    full_path = os.path.join(SYSTEM_PROMPTS_DIR, os.path.basename(filepath))
    if not os.path.exists(full_path):
        print(f"⚠️  找不到提示词文件: {full_path}")
        return ""
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


def extract_json(content):
    """从回复中提取JSON"""
    # 先尝试直接解析
    try:
        return json.loads(content)
    except:
        pass
    # 尝试从代码块中提取
    code_block_regex = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```")
    match = code_block_regex.search(content)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass
    return None


def save_structured_task(model_name, test_name, task_data):
    """保存结构化任务（已适配 paths）"""
    tasks_dir = STRUCTURED_TASKS_DIR
    if not os.path.exists(tasks_dir):
        os.makedirs(tasks_dir)
    filename = f"{model_name.replace('/', '-')}-{test_name}-{int(time.time())}.json"
    filepath = os.path.join(tasks_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(task_data, f, indent=2, ensure_ascii=False)
    print(f"{Colors.BLUE}📦 结构化任务已保存至: {filename}{Colors.ENDC}")
    return filepath


def save_chat_history(model_name, test_name, history):
    """保存对话历史（已适配 paths）"""
    chats_dir = CHATS_UPSTREAM_DIR
    if not os.path.exists(chats_dir):
        os.makedirs(chats_dir)
    filename = f"{model_name.replace('/', '-')}-{test_name}.txt"
    filepath = os.path.join(chats_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        for msg in history:
            f.write(f"[{msg['role'].upper()}]\n{msg['content']}\n\n")
    print(f"{Colors.GREEN}📝 对话历史已保存{Colors.ENDC}")


# ================== 流式传输核心函数 ==================
def stream_chat_completion(client, model, messages):
    print(f"\n{Colors.GREEN}🤖 正在生成回复（流式）...{Colors.ENDC}")
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        stream=True,
        stream_options={"include_usage": True}
    )

    full_reply = ""
    print(f"\n{Colors.GREEN}", end="", flush=True)

    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content is not None:
            content = chunk.choices[0].delta.content
            full_reply += content
            print(content, end="", flush=True)

    print(f"{Colors.ENDC}\n")
    return full_reply


# ================== 主程序 ==================
def main():
    import time
    parser = argparse.ArgumentParser(description="【上游模块】自然语言→JSON任务拆解器（支持流式）")
    parser.add_argument("--sysprompt", type=str, default="upstream_task_parser.txt", help="上游系统提示词文件名")
    parser.add_argument("--testname", type=str, default="upstream_test_001", help="测试名称")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🚁 【上游】无人机任务拆解控制台（流式传输版）")
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

    # 4. 多轮交互
    messages = [{"role": "system", "content": system_prompt}]

    print("\n" + "-" * 60)
    print(f"{Colors.BLUE}[开始交互]{Colors.ENDC}")
    print("-" * 60)
    print("提示：输入 'quit' 或 'exit' 退出，输入 'clear' 清空对话历史")

    while True:
        user_input = input(f"\n{Colors.YELLOW}[上游] 请输入指令> {Colors.ENDC}").strip()

        if not user_input:
            continue
        if user_input.lower() in ["quit", "exit"]:
            break
        if user_input.lower() == "clear":
            messages = [{"role": "system", "content": system_prompt}]
            print("✅ 对话历史已清空")
            continue

        messages.append({"role": "user", "content": user_input})

        try:
            # 流式获取回复
            full_reply = stream_chat_completion(client, selected_model, messages)
            messages.append({"role": "assistant", "content": full_reply})

            # 尝试提取 JSON
            task_data = extract_json(full_reply)
            if task_data:
                save_structured_task(selected_model, args.testname, task_data)
                save_chat_history(selected_model, args.testname, messages)
            else:
                print(f"{Colors.YELLOW}💡 模型未输出JSON任务，可能是在沟通澄清{Colors.ENDC}")

        except Exception as e:
            print(f"{Colors.RED}❌ 调用失败: {e}{Colors.ENDC}")

    print("\n👋 再见！")


if __name__ == "__main__":
    main()