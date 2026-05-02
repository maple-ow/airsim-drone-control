import sys
import os
import re
import json
import glob
import argparse
import time
import multiprocessing
from openai import OpenAI

# ========== 路径导入逻辑（适配 HTN 模块） ==========
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
# 导入全局路径配置
import paths
from paths import (
    CONFIG_PATH,
    SYSTEM_PROMPTS_DIR,
    STRUCTURED_TASKS_DIR,
    CHATS_UPSTREAM_DIR,
    HTN_PLANS_DIR,
    GENERATED_CODES_DIR
)

HTN_WORKSPACE_DIR = os.path.join(PROJECT_ROOT, "src", "htn_workspace")
sys.path.insert(0, HTN_WORKSPACE_DIR)

# 会话偏好文件路径
USER_PREFS_PATH = os.path.join(PROJECT_ROOT, "user_session_prefs.json")


# ========== 统一颜色输出类 ==========
class Colors:
    YELLOW = "\033[33m"
    ENDC = "\033[0m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    BLUE = "\033[34m"


# ================== 全局输入校验工具函数（统一处理/q退出 + 多行输入） ==================
def safe_input(prompt_text):
    """普通单行输入，支持/q退出"""
    user_input = input(prompt_text).strip()
    if user_input.lower() == "/q":
        print("\n👋 再见！")
        sys.exit(0)
    return user_input


def multiline_input(prompt_text):
    """
    【新增】多行输入函数，专门用于任务指令：
    - 支持复制粘贴多行内容
    - 输入 /send 结束并发送
    - 输入 /q 退出
    - 输入 /clear 清空当前输入
    """
    print(f"\n{Colors.YELLOW}💡 多行输入模式：{Colors.ENDC}")
    print(f"  - 直接粘贴或输入多行任务指令")
    print(f"  - 输入 {Colors.GREEN}/send{Colors.ENDC} 结束并发送")
    print(f"  - 输入 {Colors.YELLOW}/clear{Colors.ENDC} 清空当前输入")
    print(f"  - 输入 {Colors.RED}/q{Colors.ENDC} 退出程序")
    print(f"{Colors.YELLOW}────────────────────────────────────────{Colors.ENDC}")
    print(prompt_text)

    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break

        line_stripped = line.strip()

        if line_stripped.lower() == "/send":
            break
        elif line_stripped.lower() == "/q":
            print("\n👋 再见！")
            sys.exit(0)
        elif line_stripped.lower() == "/clear":
            lines = []
            print(f"\n{Colors.YELLOW}✅ 输入已清空，请重新输入：{Colors.ENDC}")
            continue
        else:
            lines.append(line)

    full_input = "\n".join(lines).strip()
    print(f"\n{Colors.YELLOW}────────────────────────────────────────{Colors.ENDC}")
    return full_input


# ================== 清理历史文件功能 ==================
def cleanup_generated_files():
    """
    删除之前生成的文件，包括：
    1. 结构化任务 (STRUCTURED_TASKS_DIR)
    2. 对话历史 (CHATS_UPSTREAM_DIR)
    3. HTN规划文件 (HTN_PLANS_DIR)
    4. 生成的代码 (GENERATED_CODES_DIR)
    """
    print("\n" + "=" * 60)
    print(f"{Colors.YELLOW}🧹 开始清理历史文件...{Colors.ENDC}")
    print("=" * 60)

    # 定义需要清理的目录列表
    targets = [
        ("结构化任务", STRUCTURED_TASKS_DIR),
        ("对话历史", CHATS_UPSTREAM_DIR),
        ("HTN规划", HTN_PLANS_DIR),
        ("生成代码", GENERATED_CODES_DIR)
    ]

    total_deleted = 0

    for name, dir_path in targets:
        if not os.path.exists(dir_path):
            print(f"  ⏭️  [{name}] 目录不存在，跳过")
            continue

        files = glob.glob(os.path.join(dir_path, "*"))
        if not files:
            print(f"  ⏭️  [{name}] 目录为空，跳过")
            continue

        print(f"  🗑️  [{name}] 发现 {len(files)} 个文件，正在删除...")
        for f in files:
            try:
                if os.path.isfile(f):
                    os.remove(f)
                    total_deleted += 1
            except Exception as e:
                print(f"     ❌ 删除失败 {os.path.basename(f)}: {e}")

    print("=" * 60)
    print(f"{Colors.GREEN}✅ 清理完成！共删除了 {total_deleted} 个文件{Colors.ENDC}")
    print("=" * 60)


# ================== 会话偏好管理函数 ==================
def load_user_prefs():
    if not os.path.exists(USER_PREFS_PATH):
        return None
    try:
        with open(USER_PREFS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"{Colors.YELLOW}⚠️  读取会话偏好失败，将使用默认选择{Colors.ENDC}")
        return None


def save_user_prefs(api_idx, model_name):
    try:
        with open(USER_PREFS_PATH, "w", encoding="utf-8") as f:
            json.dump({"api_idx": api_idx, "model_name": model_name}, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"{Colors.YELLOW}⚠️  保存会话偏好失败{Colors.ENDC}")


# ================== 公共基础设施函数 ==================
def load_config():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"找不到配置文件: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def select_api_config(config, force_reselect=False):
    configs = config.get("api_configs", [])
    if not configs:
        return {
            "base_url": config.get("BASE_URL", "https://api.openai.com/v1"),
            "api_key": config.get("API_KEY", "")
        }, 0

    if not force_reselect:
        prefs = load_user_prefs()
        if prefs and "api_idx" in prefs:
            try:
                api_idx = prefs["api_idx"]
                if 0 <= api_idx < len(configs):
                    print(
                        f"\n{Colors.GREEN}✅ 复用上次的API配置: {configs[api_idx].get('name', f'配置{api_idx + 1}')}{Colors.ENDC}")
                    return configs[api_idx], api_idx
            except:
                pass

    print("\n" + "=" * 60)
    print("🌐 请选择 API 配置：")
    print("=" * 60)
    for idx, cfg in enumerate(configs):
        print(f"  [{idx + 1}] {cfg.get('name', f'配置{idx + 1}')}")
    print("=" * 60)
    choice = safe_input("请输入序号 [默认 1]: ")
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(configs):
            return configs[idx], idx
        else:
            return configs[0], 0
    except:
        return configs[0], 0


def get_model_list(selected_api, mode="upstream"):
    print(f"🔍 正在获取模型列表...")
    try:
        client = OpenAI(api_key=selected_api["api_key"], base_url=selected_api["base_url"])
        models = client.models.list()
        model_filter = ["gpt", "qwen", "claude", "llama"] if mode == "upstream" else ["gpt", "qwen", "codex"]
        model_ids = [m.id for m in models.data if 1 ]
        return sorted(model_ids)
    except Exception as e:
        print(f"❌ 获取模型列表失败，将使用默认模型")
        return ["gpt-4o", "gpt-5.2"] if mode == "upstream" else ["gpt-4o", "gpt-5.2-codex"]


def select_model(selected_api, mode="upstream", force_reselect=False):
    model_ids = get_model_list(selected_api, mode)
    if not model_ids:
        return None

    if not force_reselect:
        prefs = load_user_prefs()
        if prefs and "model_name" in prefs:
            model_name = prefs["model_name"]
            if model_name in model_ids:
                print(f"{Colors.GREEN}✅ 复用上次的模型: {model_name}{Colors.ENDC}")
                return model_name

    print("\n" + "=" * 60)
    print("✅ 找到以下模型：")
    print("=" * 60)
    for i, mid in enumerate(model_ids[:10]):
        print(f"  [{i + 1}] {mid}")
    print("=" * 60)
    choice = safe_input(f"请选择模型序号 [默认 1]: ")
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
        raise FileNotFoundError(f"找不到提示词文件: {full_path}")
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


def setup_api_and_model(mode, force_reselect=False):
    try:
        config = load_config()
    except Exception as e:
        print(f"{Colors.RED}❌ 配置加载失败: {e}{Colors.ENDC}")
        return None, None, None, None

    selected_api, api_idx = select_api_config(config, force_reselect=force_reselect)
    client = OpenAI(api_key=selected_api["api_key"], base_url=selected_api["base_url"])

    selected_model = select_model(selected_api, mode=mode, force_reselect=force_reselect)
    if not selected_model:
        print(f"{Colors.RED}❌ 未选择模型{Colors.ENDC}")
        return None, None, None, None

    save_user_prefs(api_idx, selected_model)

    print(f"\n🎯 当前模型: {selected_model}")
    return client, selected_model, config, api_idx


# ========== 场景与无人机状态感知模块 ==========
def get_scene_and_uav_status():
    """
    在模型决策前获取：
    1. 所有可用无人机的实时状态（位置、电量、朝向）
    2. 场景中关键物体的位置
    """
    print("\n" + "=" * 60)
    print("🔍 正在获取场景与无人机状态...")
    print("=" * 60)

    status_info = {
        "uavs": [],
        "scene_objects": []
    }

    try:
        # 尝试导入 AirSimWrapper 并连接
        from utils.airsim_wrapper import AirSimWrapper

        # 1. 尝试获取常见无人机的状态（uav_1, uav_2, uav_3）
        common_uav_ids = ["uav_1", "uav_2", "uav_3", ""]
        detected_uavs = []

        for uav_id in common_uav_ids:
            try:
                aw = AirSimWrapper(vehicle_name=uav_id)
                # 获取位置
                pos = aw.get_drone_position()
                # 获取朝向
                yaw = aw.get_yaw()
                # 模拟电量（AirSim原生API可能没有，这里用模拟值，你可以根据实际情况修改）
                battery = 100  # 可以替换为实际的电量获取API

                uav_status = {
                    "uav_id": uav_id if uav_id else "default_uav",
                    "position": [round(p, 2) for p in pos],
                    "yaw": round(yaw, 1),
                    "battery": battery
                }
                detected_uavs.append(uav_status)
                print(f"  ✅ 发现无人机: {uav_status['uav_id']}")
                print(
                    f"     位置: {uav_status['position']}, 朝向: {uav_status['yaw']}°, 电量: {uav_status['battery']}%")

                # 释放API控制，避免占用
                aw.client.enableApiControl(False, vehicle_name=uav_id)
                aw.client.armDisarm(False, vehicle_name=uav_id)

            except Exception as e:
                # 该无人机不存在，跳过
                continue

        if not detected_uavs:
            print(f"  ⚠️  未连接到 AirSim，使用默认无人机状态")
            detected_uavs = [
                {"uav_id": "uav_1", "position": [0, 0, 0], "yaw": 0, "battery": 100}
            ]

        status_info["uavs"] = detected_uavs

        # 2. 获取场景中关键物体的位置
        scene_object_names = ["turbine1", "turbine2", "tower1", "tower2", "solarpanels"]
        detected_objects = []

        # 临时连接一个无人机用于获取物体位置
        temp_aw = None
        try:
            temp_aw = AirSimWrapper(vehicle_name=detected_uavs[0]["uav_id"] if detected_uavs else "")
            for obj_name in scene_object_names:
                try:
                    obj_pos = temp_aw.get_position(obj_name)
                    detected_objects.append({
                        "object_name": obj_name,
                        "position": [round(p, 2) for p in obj_pos]
                    })
                    print(f"  ✅ 发现物体: {obj_name}, 位置: {[round(p, 2) for p in obj_pos]}")
                except:
                    # 物体不存在，跳过
                    continue
        except:
            pass
        finally:
            if temp_aw:
                temp_aw.client.enableApiControl(False, vehicle_name=temp_aw.vehicle_name)
                temp_aw.client.armDisarm(False, vehicle_name=temp_aw.vehicle_name)

        if not detected_objects:
            print(f"  ⚠️  未检测到场景物体，使用默认位置")
            detected_objects = [
                {"object_name": "turbine1", "position": [20, 0, 0]},
                {"object_name": "turbine2", "position": [0, 20, 0]}
            ]

        status_info["scene_objects"] = detected_objects

    except Exception as e:
        print(f"  ⚠️  获取状态失败: {e}")
        print(f"  ℹ️  将使用默认状态数据")
        # 默认状态数据
        status_info = {
            "uavs": [
                {"uav_id": "uav_1", "position": [0, 0, 0], "yaw": 0, "battery": 100}
            ],
            "scene_objects": [
                {"object_name": "turbine1", "position": [20, 0, 0]},
                {"object_name": "turbine2", "position": [0, 20, 0]}
            ]
        }

    print("=" * 60)
    return status_info


def format_status_for_prompt(status_info):
    """将状态信息格式化为自然语言，方便传给模型"""
    prompt_text = "\n【当前场景与无人机状态（实时获取）】\n"

    # 无人机状态
    prompt_text += "1. 可用无人机：\n"
    for uav in status_info["uavs"]:
        prompt_text += f"   - {uav['uav_id']}: 位置 {uav['position']}, 朝向 {uav['yaw']}°, 电量 {uav['battery']}%\n"

    # 场景物体
    prompt_text += "\n2. 场景物体位置：\n"
    for obj in status_info["scene_objects"]:
        prompt_text += f"   - {obj['object_name']}: 位置 {obj['position']}\n"

    prompt_text += "\n【任务要求】\n请根据上述实时状态，拆解用户的自然语言指令。\n"
    return prompt_text


# =====================================================

# ================== 通用流式生成函数 ==================
def stream_chat_completion(client, model, messages, prompt_prefix="🤖 正在生成回复（流式）..."):
    print(f"\n{Colors.GREEN}{prompt_prefix}{Colors.ENDC}")
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


# ================== 上游模块函数 ==================
def extract_json(content):
    try:
        return json.loads(content)
    except:
        code_block_regex = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```")
        match = code_block_regex.search(content)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
    return None


def save_structured_task(model_name, test_name, task_data):
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
    chats_dir = CHATS_UPSTREAM_DIR
    if not os.path.exists(chats_dir):
        os.makedirs(chats_dir)
    filename = f"{model_name.replace('/', '-')}-{test_name}.txt"
    filepath = os.path.join(chats_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        for msg in history:
            f.write(f"[{msg['role'].upper()}]\n{msg['content']}\n\n")
    print(f"{Colors.GREEN}📝 对话历史已保存{Colors.ENDC}")


def run_upstream(args):
    print("\n" + "=" * 60)
    print("🚁 【上游】无人机任务拆解控制台（流式传输版 + 状态感知）")
    print("=" * 60)

    client, selected_model, _, _ = setup_api_and_model(mode="upstream")
    if not client:
        return

    print(f"\n[步骤1] 加载提示词: {args.sysprompt}")
    try:
        system_prompt = read_prompt(args.sysprompt)
    except Exception as e:
        print(f"{Colors.RED}❌ 提示词加载失败: {e}{Colors.ENDC}")
        return

    # ========== 获取场景与无人机状态，并注入到提示词中 ==========
    status_info = get_scene_and_uav_status()
    status_prompt = format_status_for_prompt(status_info)
    # 把状态信息拼接到系统提示词后面
    enhanced_system_prompt = system_prompt + "\n" + status_prompt
    # ==========================================================================

    messages = [{"role": "system", "content": enhanced_system_prompt}]
    print("\n" + "-" * 60)
    print(f"{Colors.BLUE}[开始交互]{Colors.ENDC}")
    print("-" * 60)

    while True:
        user_input = multiline_input(f"\n{Colors.YELLOW}[上游] 请输入任务指令（输入 /send 发送）> {Colors.ENDC}")

        if not user_input:
            print(f"{Colors.YELLOW}⚠️  输入为空，请重新输入{Colors.ENDC}")
            continue

        if user_input.lower() == "/s":
            print("\n" + "=" * 60)
            print("🔄 重新选择API和模型...")
            print("=" * 60)
            new_client, new_model, _, _ = setup_api_and_model(mode="upstream", force_reselect=True)
            if new_client and new_model:
                client = new_client
                selected_model = new_model
            else:
                print(f"{Colors.RED}❌ 重新选择失败，将继续使用之前的配置{Colors.ENDC}")
            continue

        messages.append({"role": "user", "content": user_input})

        try:
            full_reply = stream_chat_completion(client, selected_model, messages)
            messages.append({"role": "assistant", "content": full_reply})

            task_data = extract_json(full_reply)
            if task_data:
                save_structured_task(selected_model, args.testname, task_data)
                save_chat_history(selected_model, args.testname, messages)

                # 【关键改动】任务生成后，询问用户继续对话或切换到下游
                while True:
                    user_choice = safe_input(
                        f"\n{Colors.YELLOW}任务已生成！输入回车继续对话，或输入 /e 切换到下游模型 > {Colors.ENDC}")
                    if user_choice.lower() == "/e":
                        # 切换到下游模式
                        print("\n" + "=" * 60)
                        print("🔄 切换到下游模式...")
                        print("=" * 60)

                        # 构造下游所需的参数对象
                        class DownstreamArgs:
                            sysprompt = "downstream_code_gen.txt"

                        downstream_args = DownstreamArgs()
                        run_downstream(downstream_args)
                        break  # 下游执行完后，回到上游循环
                    elif user_choice == "":
                        break  # 直接继续上游对话
                    else:
                        print(f"{Colors.YELLOW}⚠️  无效输入，请重新输入{Colors.ENDC}")
            else:
                print(f"{Colors.YELLOW}💡 模型未输出JSON任务，可能是在沟通澄清{Colors.ENDC}")

        except Exception as e:
            print(f"{Colors.RED}❌ 调用失败: {e}{Colors.ENDC}")


# ================== 下游模块函数（整合HTN规划器+修复JSON序列化） ==================
def extract_python_code(text: str) -> str:
    """
    【强化版】从模型回复中提取纯 Python 代码
    处理情况：
    1. 包含 ```python ... ``` 代码块
    2. 包含 ``` ... ``` 代码块
    3. 前面有说明文字，后面是代码
    4. 只保留从 "from" 或 "import" 开始的有效代码
    """
    import re

    if not text:
        return ""

    # 1. 优先尝试提取 ```python ... ``` 代码块
    pattern_python = r"```python\s*\n(.*?)\n```"
    match = re.search(pattern_python, text, re.DOTALL)
    if match:
        code = match.group(1).strip()
        if code:
            return code

    # 2. 尝试提取通用 ``` ... ``` 代码块
    pattern_generic = r"```\s*\n(.*?)\n```"
    match = re.search(pattern_generic, text, re.DOTALL)
    if match:
        code = match.group(1).strip()
        if code:
            return code

    # 3. 如果没有代码块，尝试找到代码开始的位置
    # 找到第一个 "from" 或 "import" 开头的行
    lines = text.split("\n")
    code_start_index = -1
    for i, line in enumerate(lines):
        stripped_line = line.strip()
        if stripped_line.startswith("from ") or stripped_line.startswith("import "):
            code_start_index = i
            break

    if code_start_index != -1:
        # 从找到的行开始，一直到最后
        code_lines = lines[code_start_index:]
        # 过滤掉末尾可能的 ``` 或其他 Markdown
        cleaned_code_lines = []
        for line in code_lines:
            if line.strip() == "```":
                break
            cleaned_code_lines.append(line)
        return "\n".join(cleaned_code_lines).strip()

    # 4. 兜底：如果以上都失败，返回原文本（但去掉首尾空白）
    return text.strip()


def execute_drone_code(uav_id, code_path):
    print(f"\n🚀 [{uav_id}] 进程启动，正在执行代码...")
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(f"drone_code_{uav_id}", code_path)
        drone_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(drone_module)
        print(f"\n{Colors.GREEN}✅ [{uav_id}] 代码执行完成{Colors.ENDC}")
    except Exception as e:
        print(f"\n{Colors.RED}❌ [{uav_id}] 代码执行报错: {e}{Colors.ENDC}")


def run_downstream(args):
    print("\n" + "=" * 60)
    print("🚁 【下游】AirSim全链路生成控制台（流式传输版+HTN整合）")
    print("=" * 60)

    # 1. 初始化API和模型
    client, selected_model, _, _ = setup_api_and_model(mode="downstream")
    if not client:
        return

    # 2. 加载提示词
    print(f"\n[步骤1] 加载提示词: {args.sysprompt}")
    try:
        system_prompt = read_prompt(args.sysprompt)
    except Exception as e:
        print(f"{Colors.RED}❌ 提示词加载失败: {e}{Colors.ENDC}")
        return

    # 3. 预交互环节（支持/s切换API和模型）
    print("\n" + "-" * 60)
    print(f"{Colors.BLUE}[准备选择上游任务]{Colors.ENDC}")
    print("-" * 60)
    while True:
        pre_choice = safe_input(f"{Colors.YELLOW}[下游] 按回车选择上游任务，或输入 /s 切换API/模型> {Colors.ENDC}")
        if pre_choice.lower() == "/s":
            print("\n" + "=" * 60)
            print("🔄 重新选择API和模型...")
            print("=" * 60)
            new_client, new_model, _, _ = setup_api_and_model(mode="downstream", force_reselect=True)
            if new_client and new_model:
                client = new_client
                selected_model = new_model
            else:
                print(f"{Colors.RED}❌ 重新选择失败，将继续使用之前的配置{Colors.ENDC}")
            continue
        break

    # ================== HTN 规划器流程 ==================
    # 4. 初始化HTN规划器
    print("\n[步骤2] 初始化HTN规划器...")
    from htn_planner import HTNPlanner
    from htn_domain import UAV
    planner = HTNPlanner()

    # 5. 选择上游生成的JSON任务
    print("\n[步骤3] 选择上游任务文件...")
    tasks_dir = STRUCTURED_TASKS_DIR
    if not os.path.exists(tasks_dir):
        print(f"⚠️  未找到上游任务文件夹: {tasks_dir}，请先运行上游模式生成任务")
        return

    json_files = sorted(glob.glob(os.path.join(tasks_dir, "*.json")), key=os.path.getmtime, reverse=True)
    if not json_files:
        print(f"⚠️  上游任务文件夹为空，请先运行上游模式生成任务")
        return

    print("  找到以下上游任务文件（最新的在最前）：")
    for i, f in enumerate(json_files[:5]):
        print(f"  [{i + 1}] {os.path.basename(f)}")

    choice = safe_input("\n请选择文件序号 [默认 1]: ")
    try:
        idx = int(choice) - 1
        selected_task_file = json_files[idx] if 0 <= idx < len(json_files) else json_files[0]
    except:
        selected_task_file = json_files[0]
    print(f"✅ 已选择: {os.path.basename(selected_task_file)}")

    # 6. 动态收集需要的无人机
    print("\n[步骤4] 解析任务，初始化无人机编队...")
    try:
        # 收集任务里指定的无人机ID
        required_uav_ids = planner.collect_required_uav_ids(selected_task_file)
        # 只初始化需要的无人机
        uavs = [UAV(uav_id=uav_id) for uav_id in required_uav_ids]
        print(f"  ✅ 检测到需要的无人机: {', '.join(required_uav_ids)}")
        for uav in uavs:
            print(f"  - 已初始化 {uav.uav_id}，能力集: {uav.capabilities}")

        # 解析上游任务为Task对象
        initial_tasks = planner.parse_upstream_json(selected_task_file)
    except Exception as e:
        print(f"{Colors.RED}❌ 任务解析/无人机初始化失败: {e}{Colors.ENDC}")
        return

    # 7. 执行HTN规划
    print("\n[步骤5] 执行HTN任务规划...")
    try:
        plans = planner.plan(initial_tasks, uavs)
    except Exception as e:
        print(f"{Colors.RED}❌ HTN规划失败: {e}{Colors.ENDC}")
        return

    # 8. 可视化规划结果
    print("\n" + "-" * 60)
    print(f"{Colors.BLUE}[HTN规划结果]{Colors.ENDC}")
    print("-" * 60)
    for uav_id, tasks in plans.items():
        print(f"\n{Colors.GREEN}🎯 无人机 {uav_id} 的执行计划 ({len(tasks)} 个任务):{Colors.ENDC}")
        for i, task in enumerate(tasks):
            print(f"  {i + 1}. [{task['task_id']}] {task['type']}")

    # 9. 保存规划结果
    print("\n[步骤6] 保存HTN规划结果...")
    htn_output_filename = f"htn_plan_{os.path.basename(selected_task_file)}"
    planner.save_plans_to_json(plans, htn_output_filename)
    # ================== HTN规划器流程结束 ==================

    # 9. 流式生成代码
    print("\n" + "-" * 60)
    print(f"{Colors.BLUE}[开始生成代码]{Colors.ENDC}")
    print("-" * 60)

    codes_dir = GENERATED_CODES_DIR
    if not os.path.exists(codes_dir):
        os.makedirs(codes_dir)
    generated_files = []

    uav_ids = list(plans.keys())
    for uav_id in uav_ids:
        input_data = {
            "uav_id": uav_id,
            "tasks": plans[uav_id]
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(input_data, ensure_ascii=False, indent=2)}
        ]

        try:
            full_reply = stream_chat_completion(
                client,
                selected_model,
                messages,
                prompt_prefix=f"🤖 正在为 {uav_id} 生成代码（流式）..."
            )

            code = extract_python_code(full_reply)
            if code:
                # ================== 修改文件后缀为 .py ==================
                base_task_name = os.path.basename(selected_task_file)
                # 使用 replace 将 .json 替换为 .py
                code_filename = f"{uav_id}_code_{base_task_name.replace('.json', '.py')}"
                # ==========================================================================

                code_path = os.path.join(codes_dir, code_filename)
                with open(code_path, "w", encoding="utf-8") as f:
                    f.write(code)
                print(f"{Colors.GREEN}✅ {uav_id} 代码已保存: {code_filename}{Colors.ENDC}")
                generated_files.append((uav_id, code_path))
            else:
                print(f"{Colors.RED}❌ {uav_id} 未能提取到有效代码{Colors.ENDC}")
                print(f"模型回复预览: {full_reply[:200]}...")

        except Exception as e:
            print(f"{Colors.RED}❌ {uav_id} 代码生成失败: {e}{Colors.ENDC}")

    # 10. 多无人机并行执行
    if generated_files:
        print("\n" + "=" * 60)
        print(f"{Colors.GREEN}🎉 所有代码生成完成！{Colors.ENDC}")
        print("=" * 60)

        confirm = safe_input(
            f"\n{Colors.YELLOW}是否现在执行生成的代码? (y/n，支持多无人机同时执行): {Colors.ENDC}").lower()
        if confirm == 'y':
            print("\n" + "=" * 60)
            print(f"🚀 启动多无人机并行执行...")
            print("=" * 60)

            processes = []
            for uav_id, code_path in generated_files:
                p = multiprocessing.Process(target=execute_drone_code, args=(uav_id, code_path))
                processes.append(p)
                p.start()

            for p in processes:
                p.join()

            print("\n" + "=" * 60)
            print(f"{Colors.GREEN}✅ 所有无人机代码执行完毕{Colors.ENDC}")
            print("=" * 60)


# ================== 主入口函数 ==================
def main():
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(description="无人机任务处理全链路控制台")
    subparsers = parser.add_subparsers(title="运行模式", dest="mode", help="选择运行模式")

    # 上游子命令
    parser_upstream = subparsers.add_parser("upstream", help="上游模式 - 自然语言→JSON任务拆解")
    parser_upstream.add_argument("--sysprompt", type=str, default="upstream_task_parser.txt",
                                 help="上游系统提示词文件名")
    parser_upstream.add_argument("--testname", type=str, default="upstream_test_001", help="测试名称")

    # 下游子命令
    parser_downstream = subparsers.add_parser("downstream", help="下游模式 - 上游任务→HTN规划→AirSim代码→并行执行")
    parser_downstream.add_argument("--sysprompt", type=str, default="downstream_code_gen.txt",
                                   help="下游系统提示词文件名")

    args = parser.parse_args()

    # 如果未通过命令行指定模式，则进入交互式菜单
    if not args.mode:
        while True:
            print("\n" + "=" * 60)
            print("📋 请选择操作：")
            print("=" * 60)
            print("  [1] 上游模式 - 自然语言→JSON任务拆解")
            print("  [2] 下游模式 - 上游任务→HTN规划→AirSim代码→并行执行")
            print("  [3] 清理历史文件 - 删除之前生成的JSON/代码/日志")
            print("=" * 60)
            mode_choice = safe_input("请输入序号 [默认 1]: ")

            if mode_choice == "3":
                # 用户选择了清理，执行清理后回到菜单
                cleanup_generated_files()
                print(f"\n{Colors.GREEN}💡 清理完成，即将返回主菜单...{Colors.ENDC}")
                time.sleep(1.5)  # 稍微暂停让用户看清结果
                continue

            # 处理模式选择
            if mode_choice == "2":
                args.mode = "downstream"
                args.sysprompt = "downstream_code_gen.txt"
            else:
                args.mode = "upstream"
                args.sysprompt = "upstream_task_parser.txt"
                args.testname = "upstream_test_001"
            break  # 退出循环进入模式

    # 执行对应模式
    run_upstream(args) if args.mode == "upstream" else run_downstream(args)


if __name__ == "__main__":
    main()