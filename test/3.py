import sys
import os
import re
import time
from openai import OpenAI

# ==========================================
# 🚀 配置区
# ==========================================

#火山引擎

# PRESET_API_KEY = "f3f001f5-97fd-454c-870e-d85d2535d3fe"
# BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

#GPT公益站点

PRESET_API_KEY = "sk-BOIfaNR9CVuERB57c"
BASE_URL = "https://api.wataruu.me/v1"
# ==========================================

# --- 路径处理 (确保能找到你的 utils 库) ---
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
try:
    from airsim_utils_single import AirSimController
except ImportError:
    print("⚠️  警告：未找到 utils/airsim_utils.py，代码生成后可能无法执行")


def get_model_list():
    """自动获取可用模型列表"""
    print(f"🔍 正在获取模型列表...")
    try:
        client = OpenAI(api_key=PRESET_API_KEY, base_url=BASE_URL)
        models = client.models.list()
        # 按创建时间排序，最新的在前面
        sorted_models = sorted(models.data, key=lambda x: x.created, reverse=True)
        return [m.id for m in sorted_models]
    except Exception as e:
        print(f"❌ 获取模型失败，请检查 API Key 和网络: {e}")
        return None


def select_model():
    model_ids = get_model_list()
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


# --- 提示词 ---
SYSTEM_PROMPT = """
你是专业的 AirSim 无人机操作助手。
必须使用我提供的自定义库，不要用原始 airsim API。

库的使用方法：
1. 导入与初始化：
   from airsim_utils_single import AirSimController
   drone = AirSimController()

2. 可用函数：
   - drone.takeoff()  # 起飞
   - drone.land()     # 降落
   - drone.fly_to_relative(dx, dy, dz, velocity=5) 
     # 功能：相对坐标飞行，（注意z轴垂直水平面向下）。

输出要求：
- 只输出一个 ```python ... ``` 代码块。
- 代码里必须包含必要的 time.sleep()。
- 不要解释代码。
"""


# --- 主循环 ---
def main():
    print("\n" + "=" * 60)
    print("🚁 无人机自然语言控制台")
    print("=" * 60)

    if PRESET_API_KEY == "在这里粘贴你的火山引擎API-Key":
        print("❌ 请先在代码顶部填入你的 API Key！")
        return

    selected_model = select_model()
    if not selected_model:
        return

    print(f"\n🎯 当前模型: {selected_model}")
    print("💡 提示：请先启动虚幻引擎 AirSim 并点击播放按钮")
    print("-" * 60)

    client = OpenAI(api_key=PRESET_API_KEY, base_url=BASE_URL)

    while True:
        user_input = input("\n👤 请输入指令 (q退出 / s换模型): ").strip()
        if user_input.lower() == 'q':
            print("👋 再见")
            break
        if user_input.lower() == 's':
            selected_model = select_model()
            continue

        print("🤖 正在生成代码...")
        try:
            response = client.chat.completions.create(
                model=selected_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.2
            )
            content = response.choices[0].message.content

            # 提取代码
            code_match = re.search(r"```python(.*?)```", content, re.DOTALL)
            if code_match:
                code = code_match.group(1).strip()
                print("\n" + "-" * 60)
                print("📝 生成的代码：")
                print(code)
                print("-" * 60)

                confirm = input("✅ 确认执行? (y/n): ").lower()
                if confirm == 'y':
                    try:
                        print("🚀 执行中...")
                        # 执行代码
                        exec_globals = globals().copy()
                        exec(code, exec_globals)
                        print("🎉 执行完毕")
                    except Exception as e:
                        print(f"❌ 执行报错: {e}")
            else:
                print(f"\n🤖 模型回复: {content}")

        except Exception as e:
            print(f"❌ 出错: {e}")


if __name__ == "__main__":
    main()