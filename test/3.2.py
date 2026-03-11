import os
import sys
import json
from string import Template
from typing import Dict, List, Optional

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# 新增：提示词配置常量（统一管理路径）
PROMPT_DIRS = {
    "system": os.path.join(PROJECT_ROOT, "system_prompts"),
    "user": os.path.join(PROJECT_ROOT, "prompts"),
    "templates": os.path.join(PROJECT_ROOT, "prompt_templates")
}

# 新增：创建默认目录（避免文件不存在）
for dir_path in PROMPT_DIRS.values():
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)


class PromptManager:
    """提示词管理类：封装读取、模板渲染、验证、上下文增强"""

    def __init__(self, drone_wrapper=None):
        self.drone_wrapper = drone_wrapper  # 无人机实例，用于获取状态
        self.prompt_templates = {}  # 缓存加载的提示词模板

    def read_prompt(self, filepath: str, encoding: str = "utf-8") -> str:
        """
        读取提示词文件（增强版）
        :param filepath: 相对路径/绝对路径
        :param encoding: 文件编码
        :return: 提示词内容
        """
        # 处理相对路径（优先匹配预设目录）
        if not os.path.isabs(filepath):
            for dir_name, dir_path in PROMPT_DIRS.items():
                test_path = os.path.join(dir_path, filepath)
                if os.path.exists(test_path):
                    filepath = test_path
                    break

        # 读取文件
        try:
            with open(filepath, "r", encoding=encoding) as f:
                content = f.read().strip()
            print(f"✅ 成功加载提示词: {filepath}")
            return content
        except FileNotFoundError:
            print(f"⚠️  提示词文件不存在: {filepath}，返回空内容")
            return ""
        except Exception as e:
            print(f"❌ 读取提示词失败: {e}，返回空内容")
            return ""

    def load_template(self, template_name: str, template_content: Optional[str] = None) -> None:
        """
        加载提示词模板（支持变量替换，如${drone_id}、${task}）
        :param template_name: 模板名称（用于缓存）
        :param template_content: 模板内容（为空则从文件读取）
        """
        if not template_content:
            template_content = self.read_prompt(f"{template_name}.txt")
        if template_content:
            self.prompt_templates[template_name] = Template(template_content)
            print(f"✅ 已加载提示词模板: {template_name}")

    def render_template(self, template_name: str, variables: Dict) -> str:
        """
        渲染提示词模板（替换变量）
        :param template_name: 模板名称
        :param variables: 变量字典（如{"drone_id": "drone_001", "task": "悬停"}）
        :return: 渲染后的提示词
        """
        if template_name not in self.prompt_templates:
            self.load_template(template_name)  # 懒加载模板

        template = self.prompt_templates.get(template_name)
        if not template:
            print(f"⚠️  模板{template_name}不存在，返回空内容")
            return ""

        try:
            return template.substitute(variables)
        except KeyError as e:
            print(f"❌ 模板渲染失败：缺少变量{e}")
            return ""

    def get_drone_context(self) -> str:
        """获取无人机状态上下文（增强版）"""
        if not self.drone_wrapper:
            return "【无人机状态】未连接AirSim\n"

        try:
            pos = self.drone_wrapper.get_drone_position()
            yaw = self.drone_wrapper.get_yaw()
            battery = self.drone_wrapper.get_battery()  # 假设新增电池状态接口
            context = f"""
【无人机实时状态】
- 位置 (X, Y, Z): ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})
- 朝向 (Yaw): {yaw:.1f} 度
- 剩余电量: {battery:.1f}%
"""
            return context
        except Exception as e:
            return f"【无人机状态】获取失败: {e}\n"

    def augment_prompt(self, user_input: str, add_drone_context: bool = True) -> str:
        """
        增强用户输入（拼接无人机状态/其他上下文）
        :param user_input: 原始用户输入
        :param add_drone_context: 是否添加无人机状态
        :return: 增强后的提示词
        """
        augmented = user_input.strip()
        if add_drone_context:
            augmented += "\n\n" + self.get_drone_context()
        return augmented

    def validate_prompt(self, prompt_content: str, required_keywords: List[str] = None) -> bool:
        """
        验证提示词有效性（检查必填关键词）
        :param prompt_content: 提示词内容
        :param required_keywords: 必填关键词列表（如["无人机", "控制"]）
        :return: 是否有效
        """
        if not prompt_content:
            print("❌ 提示词为空，验证失败")
            return False

        if not required_keywords:
            return True

        missing = [kw for kw in required_keywords if kw not in prompt_content]
        if missing:
            print(f"❌ 提示词缺少必填关键词: {missing}")
            return False

        print("✅ 提示词验证通过")
        return True


# ====================== 模块使用示例 ======================
if __name__ == "__main__":
    # 模拟AirSimWrapper（仅测试）
    class MockAirSimWrapper:
        def get_drone_position(self): return (10.5, 20.3, -5.0)

        def get_yaw(self): return 90.0

        def get_battery(self): return 85.5


    # 初始化提示词管理器
    pm = PromptManager(drone_wrapper=MockAirSimWrapper())

    # 1. 读取基础提示词
    sys_prompt = pm.read_prompt("airsim_chinese.txt")

    # 2. 加载并渲染模板
    pm.load_template("drone_task")  # 加载prompt_templates/drone_task.txt
    rendered_prompt = pm.render_template(
        "drone_task",
        {"drone_id": "drone_001", "task": "飞到(50, 50, -10)位置并悬停"}
    )

    # 3. 增强用户输入
    user_input = "执行任务"
    augmented_input = pm.augment_prompt(user_input)

    # 4. 验证提示词
    is_valid = pm.validate_prompt(augmented_input, ["无人机", "位置"])

    print("\n=== 渲染后的模板 ===")
    print(rendered_prompt)
    print("\n=== 增强后的用户输入 ===")
    print(augmented_input)