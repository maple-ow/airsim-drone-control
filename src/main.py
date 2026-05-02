import sys
import os
import re
import json
import glob
import argparse
import time
import multiprocessing
import subprocess
import importlib.util
from typing import Dict, List, Any, Optional, Tuple
from openai import OpenAI

# ========== 路径导入逻辑 ==========
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

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

USER_PREFS_PATH = os.path.join(PROJECT_ROOT, "user_session_prefs.json")


# ========== 统一颜色输出类 ==========
class Colors:
    YELLOW = "\033[33m"
    ENDC = "\033[0m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    BLUE = "\033[34m"


# ================== CLI 交互工具 ==================
def safe_input(prompt_text: str) -> str:
    """普通单行输入，支持 /q 退出"""
    user_input = input(prompt_text).strip()
    if user_input.lower() == "/q":
        print("\n👋 再见！")
        sys.exit(0)
    return user_input


def multiline_input(prompt_text: str) -> str:
    """多行输入函数，专门用于任务指令"""
    print(f"\n{Colors.YELLOW}💡 多行输入模式：{Colors.ENDC}")
    print(f"  - 直接粘贴或输入多行任务指令")
    print(f"  - 输入 {Colors.GREEN}/send{Colors.ENDC} 结束并发送")
    print(f"  - 输入 {Colors.YELLOW}/clear{Colors.ENDC} 清空当前输入")
    print(f"  - 输入 {Colors.BLUE}/s{Colors.ENDC} 重新选择API/模型")
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
            lines.clear()
            print(f"\n{Colors.YELLOW}✅ 输入已清空，请重新输入：{Colors.ENDC}")
            continue
        elif line_stripped.lower() == "/s":
            # 捕获到 /s，立即作为系统命令返回，不再等待 /send
            return "/s"
        else:
            lines.append(line)

    print(f"\n{Colors.YELLOW}────────────────────────────────────────{Colors.ENDC}")
    return "\n".join(lines).strip()


def cleanup_generated_files():
    """清理历史生成文件"""
    print(f"\n{'=' * 60}\n{Colors.YELLOW}🧹 开始清理历史文件...{Colors.ENDC}\n{'=' * 60}")
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

    print(f"{'=' * 60}\n{Colors.GREEN}✅ 清理完成！共删除了 {total_deleted} 个文件{Colors.ENDC}\n{'=' * 60}")


# ================== 配置与模型管理 ==================
def load_user_prefs() -> Optional[Dict]:
    if not os.path.exists(USER_PREFS_PATH):
        return None
    try:
        with open(USER_PREFS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None


def save_user_prefs(api_idx: int, model_name: str):
    try:
        with open(USER_PREFS_PATH, "w", encoding="utf-8") as f:
            json.dump({"api_idx": api_idx, "model_name": model_name}, f, indent=2, ensure_ascii=False)
    except:
        pass


def load_config() -> Dict:
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"找不到配置文件: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def select_api_config(config: Dict, force_reselect: bool = False) -> Tuple[Dict, int]:
    configs = config.get("api_configs", [])
    if not configs:
        return {"base_url": config.get("BASE_URL"), "api_key": config.get("API_KEY")}, 0

    if not force_reselect:
        prefs = load_user_prefs()
        if prefs and "api_idx" in prefs:
            idx = prefs["api_idx"]
            if 0 <= idx < len(configs):
                print(f"\n{Colors.GREEN}✅ 复用上次的API配置: {configs[idx].get('name', f'配置{idx + 1}')}{Colors.ENDC}")
                return configs[idx], idx

    print(f"\n{'=' * 60}\n🌐 请选择 API 配置：\n{'=' * 60}")
    for idx, cfg in enumerate(configs):
        print(f"  [{idx + 1}] {cfg.get('name', f'配置{idx + 1}')}")
    print("=" * 60)

    choice = safe_input("请输入序号 [默认 1]: ")
    try:
        idx = int(choice) - 1
        return configs[idx], idx if 0 <= idx < len(configs) else (configs[0], 0)
    except:
        return configs[0], 0


def get_model_list(selected_api: Dict, mode: str = "upstream") -> List[str]:
    """
    极速获取模型列表：不测试权限，直接返回全部，毫秒级速度
    完全不过滤，原样返回接口给的所有模型名
    """
    try:
        client = OpenAI(api_key=selected_api["api_key"], base_url=selected_api["base_url"])
        models = client.models.list()

        # 直接提取所有模型 ID，不做任何检查、不测试、不过滤
        model_ids = [m.id for m in models.data]

        return sorted(model_ids)

    except Exception as e:
        print(f"⚠️ 获取模型列表失败: {e}")
        return []


def select_model(selected_api: Dict, mode: str = "upstream", force_reselect: bool = False) -> Optional[str]:
    model_ids = get_model_list(selected_api, mode)

    # 尝试复用：如果不强制重选，且有历史记录，则尝试复用
    if not force_reselect:
        prefs = load_user_prefs()
        if prefs and "model_name" in prefs:
            old_model = prefs["model_name"]
            # 当API获取列表失败，或者旧模型在获取的列表中时，直接复用
            if (not model_ids) or (old_model in model_ids):
                print(f"{Colors.GREEN}✅ 复用上次的模型: {old_model}{Colors.ENDC}")
                return old_model

    # 若无法复用且列表为空，启用手动回退模式
    if not model_ids:
        print(f"\n{Colors.YELLOW}⚠️ 无法自动获取可用模型列表，已切换为手动输入模式{Colors.ENDC}")
        fallback_model = safe_input("请输入目标模型名称 (如 gpt-4o, qwen-max 等，或 /q 退出): ")
        if not fallback_model:
            print(f"{Colors.YELLOW}⚠️ 未输入，默认使用 gpt-4o{Colors.ENDC}")
            return "gpt-4o"
        return fallback_model

    # 正常菜单选择
    print(f"\n{'=' * 60}\n✅ 找到以下模型 (最多显示 20 个)：\n{'=' * 60}")
    for i, mid in enumerate(model_ids[:20]):
        print(f"  [{i + 1}] {mid}")
    print("=" * 60)

    choice = safe_input(f"请选择模型序号 (或直接输入自定义模型名称) [默认 1]: ")

    if not choice:
        return model_ids[0]

    try:
        idx = int(choice) - 1
        return model_ids[idx] if 0 <= idx < len(model_ids) else model_ids[0]
    except ValueError:
        # 用户直接输入了字符串形式的模型名
        return choice


def setup_api_and_model(mode: str, force_reselect: bool = False):
    try:
        config = load_config()
    except Exception as e:
        print(f"{Colors.RED}❌ 配置加载失败: {e}{Colors.ENDC}")
        return None, None, None, None

    api_cfg, api_idx = select_api_config(config, force_reselect)
    client = OpenAI(api_key=api_cfg["api_key"], base_url=api_cfg["base_url"])
    model = select_model(api_cfg, mode, force_reselect)

    if not model:
        print(f"{Colors.RED}❌ 用户取消了模型选择，操作终止。{Colors.ENDC}")
        return None, None, None, None

    save_user_prefs(api_idx, model)
    print(f"\n🎯 当前选中模型: {model}")
    return client, model, config, api_idx


def read_prompt(filepath: str) -> str:
    full_path = os.path.join(SYSTEM_PROMPTS_DIR, os.path.basename(filepath))
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"找不到提示词文件: {full_path}")
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


# ================== 状态感知模块 (解耦优化) ==================
def _fetch_uavs_status(AirSimWrapper) -> List[Dict]:
    """尝试获取常用无人机状态"""
    detected_uavs = []
    for uav_id in ["uav_1", "uav_2", "uav_3"]:
        try:
            aw = AirSimWrapper(vehicle_name=uav_id)
            uav_status = {
                "uav_id": uav_id if uav_id else "default_uav",
                "position": [round(p, 2) for p in aw.get_drone_position()],
                "yaw": round(aw.get_yaw(), 1)
            }
            detected_uavs.append(uav_status)
            print(f"  ✅ 发现无人机: {uav_status['uav_id']}")
            print(f"     位置: {uav_status['position']}, 朝向: {uav_status['yaw']}°")

            # 释放控制
            aw.client.enableApiControl(False, vehicle_name=uav_id)
            aw.client.armDisarm(False, vehicle_name=uav_id)
        except Exception:
            continue
    return detected_uavs


def _fetch_scene_objects(AirSimWrapper, anchor_uav_id: str) -> List[Dict]:
    """尝试获取场景核心物体位置"""
    objects = ["turbine1", "turbine2", "tower1", "tower2", "solarpanels"]
    detected_objects = []

    try:
        temp_aw = AirSimWrapper(vehicle_name=anchor_uav_id)
        for obj_name in objects:
            try:
                pos = temp_aw.get_position(obj_name)
                detected_objects.append({
                    "object_name": obj_name,
                    "position": [round(p, 2) for p in pos]
                })
                print(f"  ✅ 发现物体: {obj_name}, 位置: {[round(p, 2) for p in pos]}")
            except:
                continue
    except:
        pass
    finally:
        if 'temp_aw' in locals() and temp_aw:
            temp_aw.client.enableApiControl(False, vehicle_name=temp_aw.vehicle_name)
            temp_aw.client.armDisarm(False, vehicle_name=temp_aw.vehicle_name)

    return detected_objects


def get_scene_and_uav_status() -> Dict:
    print(f"\n{'=' * 60}\n🔍 正在获取场景与无人机状态...\n{'=' * 60}")

    status_info = {"uavs": [], "scene_objects": []}
    try:
        from utils.airsim_wrapper import AirSimWrapper

        # 1. 获取无人机状态
        uavs = _fetch_uavs_status(AirSimWrapper)
        if not uavs:
            print("  ⚠️  未连接到 AirSim，使用默认无人机状态")
            uavs = [{"uav_id": "uav_1", "position": [0, 0, 0], "yaw": 0, "battery": 100}]
        status_info["uavs"] = uavs

        # 2. 获取场景物体状态
        anchor_id = uavs[0]["uav_id"] if uavs else ""
        scene_objs = _fetch_scene_objects(AirSimWrapper, anchor_id)
        if not scene_objs:
            print("  ⚠️  未检测到场景物体，使用默认位置")
            scene_objs = [
                {"object_name": "turbine1", "position": [20, 0, 0]},
                {"object_name": "turbine2", "position": [0, 20, 0]}
            ]
        status_info["scene_objects"] = scene_objs

    except Exception as e:
        print(f"  ⚠️  获取状态模块异常: {e}\n  ℹ️  将使用默认状态数据")
        status_info = {
            "uavs": [{"uav_id": "uav_1", "position": [0, 0, 0], "yaw": 0, "battery": 100}],
            "scene_objects": [{"object_name": "turbine1", "position": [20, 0, 0]}]
        }

    print("=" * 60)
    return status_info


def format_status_for_prompt(status_info: Dict) -> str:
    prompt_text = "\n【当前场景与无人机状态（实时获取）】\n1. 可用无人机：\n"
    for uav in status_info["uavs"]:
        prompt_text += f"   - {uav['uav_id']}: 位置 {uav['position']}, 朝向 {uav['yaw']}°\n"

    prompt_text += "\n2. 场景物体位置：\n"
    for obj in status_info["scene_objects"]:
        prompt_text += f"   - {obj['object_name']}: 位置 {obj['position']}\n"

    prompt_text += "\n【任务要求】\n请根据上述实时状态，拆解用户的自然语言指令。\n"
    return prompt_text


# ================== LLM 交互处理 ==================
def stream_chat_completion(client, model, messages, prompt_prefix="🤖 正在生成回复（流式）..."):
    print(f"\n{Colors.GREEN}{prompt_prefix}{Colors.ENDC}")
    try:
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
    except Exception as e:
        print(f"\n{Colors.RED}❌ 大模型调用失败: {e}{Colors.ENDC}\n")
        return ""


def extract_json(content: str) -> Optional[Dict]:
    try:
        return json.loads(content)
    except:
        # 使用安全的 `{3}` 替代直接编写三个反引号
        code_block_regex = re.compile(r"`{3}(?:json)?\s*([\s\S]*?)\s*`{3}")
        match = code_block_regex.search(content)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
    return None


def extract_python_code(text: str) -> str:
    """提取生成的 Python 代码 (使用安全正则表示法)"""
    if not text:
        return ""

    # 使用安全的 `{3}`
    pattern_python = r"`{3}python\s*\n(.*?)\n`{3}"
    match = re.search(pattern_python, text, re.DOTALL)
    if match and match.group(1).strip():
        return match.group(1).strip()

    pattern_generic = r"`{3}\s*\n(.*?)\n`{3}"
    match = re.search(pattern_generic, text, re.DOTALL)
    if match and match.group(1).strip():
        return match.group(1).strip()

    # 回退机制：寻找 import / from 关键字
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip().startswith(("from ", "import ")):
            code_lines = lines[i:]
            cleaned = [l for l in code_lines if l.strip() != "```"]
            return "\n".join(cleaned).strip()

    return text.strip()


# ================== IO 保存逻辑 ==================
def save_structured_task(model_name: str, test_name: str, task_data: Dict) -> str:
    os.makedirs(STRUCTURED_TASKS_DIR, exist_ok=True)
    safe_model_name = str(model_name).replace('/', '-')
    filename = f"{safe_model_name}-{test_name}-{int(time.time())}.json"
    filepath = os.path.join(STRUCTURED_TASKS_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(task_data, f, indent=2, ensure_ascii=False)
    print(f"{Colors.BLUE}📦 结构化任务已保存至: {filename}{Colors.ENDC}")
    return filepath


def save_chat_history(model_name: str, test_name: str, history: List[Dict]):
    os.makedirs(CHATS_UPSTREAM_DIR, exist_ok=True)
    safe_model_name = str(model_name).replace('/', '-')
    filename = f"{safe_model_name}-{test_name}.txt"
    filepath = os.path.join(CHATS_UPSTREAM_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        for msg in history:
            f.write(f"[{msg['role'].upper()}]\n{msg['content']}\n\n")
    print(f"{Colors.GREEN}📝 对话历史已保存{Colors.ENDC}")


# ================== 核心控制流：上游模块 ==================
def run_upstream(args):
    print(f"\n{'=' * 60}\n🚁 【上游】无人机任务拆解控制台（流式传输版 + 状态感知）\n{'=' * 60}")

    client, model, _, _ = setup_api_and_model(mode="upstream")
    if not client or not model: return

    try:
        system_prompt = read_prompt(args.sysprompt)
    except Exception as e:
        print(f"{Colors.RED}❌ 提示词加载失败: {e}{Colors.ENDC}")
        return

    # 组合状态上下文
    status_info = get_scene_and_uav_status()
    enhanced_prompt = system_prompt + "\n" + format_status_for_prompt(status_info)
    messages = [{"role": "system", "content": enhanced_prompt}]

    print(f"\n{'-' * 60}\n{Colors.BLUE}[开始交互]{Colors.ENDC}\n{'-' * 60}")

    while True:
        user_input = multiline_input(f"\n{Colors.YELLOW}[上游] 请输入任务指令（输入 /send 发送）> {Colors.ENDC}")
        if not user_input: continue

        if user_input.lower() == "/s":
            new_client, new_model, _, _ = setup_api_and_model(mode="upstream", force_reselect=True)
            if new_client and new_model:
                client, model = new_client, new_model
            continue

        messages.append({"role": "user", "content": user_input})

        reply = stream_chat_completion(client, model, messages)
        if not reply:
            continue

        messages.append({"role": "assistant", "content": reply})

        task_data = extract_json(reply)
        if not task_data:
            print(f"{Colors.YELLOW}💡 模型未输出JSON任务，可能是在沟通澄清{Colors.ENDC}")
            continue

        save_structured_task(model, args.testname, task_data)
        save_chat_history(model, args.testname, messages)

        # 是否直接转入下游
        choice = safe_input(f"\n{Colors.YELLOW}任务已生成！输入回车继续对话，或输入 /e 切换到下游模型 > {Colors.ENDC}")
        if choice.lower() == "/e":
            class DownstreamArgs:
                sysprompt = "downstream_code_gen.txt"

            run_downstream(DownstreamArgs())
            break  # 下游结束后跳出循环


# ================== 核心控制流：下游模块 ==================
def run_downstream(args):
    print(f"\n{'=' * 60}\n🚁 【下游】AirSim全链路生成控制台（流式传输版+HTN整合）\n{'=' * 60}")

    client, model, _, _ = setup_api_and_model(mode="downstream")
    if not client or not model: return

    try:
        system_prompt = read_prompt(args.sysprompt)
    except Exception as e:
        print(f"{Colors.RED}❌ 提示词加载失败: {e}{Colors.ENDC}")
        return

    # 预交互切换
    while safe_input(f"\n{Colors.YELLOW}[下游] 按回车选择任务，或输入 /s 切换API/模型> {Colors.ENDC}").lower() == "/s":
        new_c, new_m, _, _ = setup_api_and_model(mode="downstream", force_reselect=True)
        if new_c and new_m: client, model = new_c, new_m

    # HTN 初始化与任务选择
    from htn_planner import HTNPlanner
    from htn_domain import UAV
    planner = HTNPlanner()

    os.makedirs(STRUCTURED_TASKS_DIR, exist_ok=True)
    json_files = sorted(glob.glob(os.path.join(STRUCTURED_TASKS_DIR, "*.json")), key=os.path.getmtime, reverse=True)
    if not json_files:
        print("⚠️ 未找到上游任务文件，请先运行上游模式。")
        return

    print("\n[步骤3] 找到以下上游任务文件（最新的在最前）：")
    for i, f in enumerate(json_files[:5]):
        print(f"  [{i + 1}] {os.path.basename(f)}")

    try:
        idx = int(safe_input("\n请选择文件序号 [默认 1]: ")) - 1
        selected_file = json_files[idx] if 0 <= idx < len(json_files) else json_files[0]
    except:
        selected_file = json_files[0]
    print(f"✅ 已选择: {os.path.basename(selected_file)}")

    # 规划执行
    try:
        uav_ids = planner.collect_required_uav_ids(selected_file)
        uavs = [UAV(uav_id=uid) for uid in uav_ids]
        initial_tasks = planner.parse_upstream_json(selected_file)
        plans = planner.plan(initial_tasks, uavs)
    except Exception as e:
        print(f"{Colors.RED}❌ 解析或规划失败: {e}{Colors.ENDC}")
        return

    # 结果展示与保存
    print(f"\n{'-' * 60}\n{Colors.BLUE}[HTN规划结果]{Colors.ENDC}\n{'-' * 60}")
    for uid, tasks in plans.items():
        print(f"\n{Colors.GREEN}🎯 无人机 {uid} 的执行计划 ({len(tasks)} 个任务):{Colors.ENDC}")
        for i, t in enumerate(tasks):
            print(f"  {i + 1}. [{t['task_id']}] {t['type']}")

    out_file = f"htn_plan_{os.path.basename(selected_file)}"
    planner.save_plans_to_json(plans, out_file)

    # 协同代码生成
    print(f"\n{'-' * 60}\n{Colors.BLUE}[开始生成多机协同代码]{Colors.ENDC}\n{'-' * 60}")
    os.makedirs(GENERATED_CODES_DIR, exist_ok=True)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps({"swarm_plan": plans}, ensure_ascii=False, indent=2)}
    ]

    reply = stream_chat_completion(client, model, messages, "🤖 正在生成全局多机协同代码（流式）...")
    if not reply:
        return

    code = extract_python_code(reply)

    if not code:
        print(f"{Colors.RED}❌ 未能提取到有效代码{Colors.ENDC}")
        return

    code_filename = f"swarm_control_{os.path.basename(selected_file).replace('.json', '.py')}"
    gen_path = os.path.join(GENERATED_CODES_DIR, code_filename)

    with open(gen_path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"{Colors.GREEN}✅ 全局协同代码已保存: {code_filename}{Colors.ENDC}")

    # 代码执行
    if safe_input(f"\n{Colors.YELLOW}是否现在执行生成的集群代码? (y/n): {Colors.ENDC}").lower() == 'y':
        print(f"\n{'=' * 60}\n🚀 启动集群中枢控制器...\n{'=' * 60}")
        try:
            subprocess.run([sys.executable, gen_path], check=True)
            print(f"\n{'=' * 60}\n{Colors.GREEN}✅ 集群任务执行完毕{Colors.ENDC}\n{'=' * 60}")
        except subprocess.CalledProcessError as e:
            print(f"\n{Colors.RED}❌ 集群代码执行异常中断，退出码: {e.returncode}{Colors.ENDC}")
        except Exception as e:
            print(f"\n{Colors.RED}❌ 启动进程失败: {e}{Colors.ENDC}")


# ================== 主程序入口 ==================
def main():
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description="无人机任务处理全链路控制台")
    subparsers = parser.add_subparsers(title="运行模式", dest="mode")

    p_up = subparsers.add_parser("upstream", help="自然语言→JSON任务拆解")
    p_up.add_argument("--sysprompt", default="upstream_task_parser.txt")
    p_up.add_argument("--testname", default="upstream_test_001")

    p_down = subparsers.add_parser("downstream", help="上游任务→HTN规划→代码执行")
    p_down.add_argument("--sysprompt", default="downstream_code_gen.txt")

    args = parser.parse_args()

    # 交互式菜单逻辑
    while not args.mode:
        print(f"\n{'=' * 60}\n📋 请选择操作：\n{'=' * 60}")
        print("  [1] 上游模式 - 自然语言→JSON任务拆解")
        print("  [2] 下游模式 - 上游任务→HTN规划→AirSim代码→并行执行")
        print("  [3] 清理历史文件 - 删除之前生成的JSON/代码/日志\n" + "=" * 60)

        choice = safe_input("请输入序号 [默认 1]: ")
        if choice == "3":
            cleanup_generated_files()
            time.sleep(1)
            continue

        if choice == "2":
            args.mode = "downstream"
            args.sysprompt = "downstream_code_gen.txt"
        else:
            args.mode = "upstream"
            args.sysprompt = "upstream_task_parser.txt"
            args.testname = "upstream_test_001"

        break

    run_upstream(args) if args.mode == "upstream" else run_downstream(args)


if __name__ == "__main__":
    main()