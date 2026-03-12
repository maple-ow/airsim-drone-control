
import os

# ================== 1. 定义根目录（基于 paths.py 的位置自动计算） ==================

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# ================== 2. 基于根目录，定义所有其他路径 ==================

CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")
SYSTEM_PROMPTS_DIR = os.path.join(PROJECT_ROOT, "system_prompts")
UTILS_DIR = os.path.join(PROJECT_ROOT, "utils")


STRUCTURED_TASKS_DIR = os.path.join(PROJECT_ROOT, "structured_tasks")
CHATS_UPSTREAM_DIR = os.path.join(PROJECT_ROOT,"chats", "chats_upstream")

HTN_WORKSPACE_DIR = os.path.join(PROJECT_ROOT, "src", "htn_workspace")
HTN_PLANS_DIR = os.path.join(HTN_WORKSPACE_DIR, "htn_plans")
GENERATED_CODES_DIR = os.path.join(HTN_WORKSPACE_DIR, "generated_codes")

# ================== 3. 辅助函数：自动创建不存在的文件夹 ==================
def ensure_dirs():
    """自动创建所有需要的文件夹，避免 FileNotFoundError"""
    dirs_to_create = [
        SYSTEM_PROMPTS_DIR,
        UTILS_DIR,
        STRUCTURED_TASKS_DIR,
        CHATS_UPSTREAM_DIR,
        HTN_WORKSPACE_DIR,
        HTN_PLANS_DIR,
        GENERATED_CODES_DIR
    ]
    for d in dirs_to_create:
        if not os.path.exists(d):
            os.makedirs(d)
            print(f"[paths] 自动创建文件夹: {d}")

# 运行时自动创建文件夹
ensure_dirs()