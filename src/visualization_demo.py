import streamlit as st
import os
import sys
import json
import matplotlib.pyplot as plt

# ========== 1. 路径配置（复用你的 paths.py） ==========
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
import paths

# ========== 2. 页面配置 ==========
st.set_page_config(
    page_title="无人机巡检三层架构演示系统",
    page_icon="🚁",
    layout="wide"
)

st.title("🚁 无人机巡检三层架构演示系统")
st.markdown("---")

# ========== 3. 侧边栏：模式选择 ==========
mode = st.sidebar.radio(
    "选择演示模式",
    ["1. 上游任务拆解", "2. HTN任务规划", "3. 仿真执行与结果"]
)

# ========== 4. 模块1：上游任务拆解可视化 ==========
if mode == "1. 上游任务拆解":
    st.header("📝 模块1：自然语言→结构化任务拆解")

    # 文本输入
    user_instruction = st.text_area(
        "输入自然语言飞行指令",
        value="双机协同：uav_1起飞到15米巡检turbine1，uav_2起飞到20米巡检turbine2，完成后一起返回降落",
        height=100
    )

    # 一键拆解按钮
    if st.button("🔧 一键拆解任务"):
        st.info("正在调用上游任务拆解逻辑...")

        # TODO: 这里接入你的 upstream_main.py 的核心拆解函数
        # 为了演示，先放一个模拟的JSON结果
        mock_upstream_result = {
            "task_id": "task_20260312_demo",
            "original_instruction": user_instruction,
            "subtasks": [
                {"subtask_id": "sub_001", "type": "takeoff", "params": {"height": 15, "_target_uavs": ["uav_1"]},
                 "dependencies": []},
                {"subtask_id": "sub_002", "type": "takeoff", "params": {"height": 20, "_target_uavs": ["uav_2"]},
                 "dependencies": []}
            ]
        }

        # 展示结果
        st.success("✅ 任务拆解完成！")
        st.subheader("📦 结构化任务JSON")
        st.json(mock_upstream_result)

        # 保存到 session_state，供下一个模块使用
        st.session_state['upstream_result'] = mock_upstream_result

# ========== 5. 模块2：HTN任务规划可视化 ==========
elif mode == "2. HTN任务规划":
    st.header("🎯 模块2：HTN任务规划与多机分配")

    # 检查是否有上游结果
    if 'upstream_result' not in st.session_state:
        st.warning("⚠️ 请先在模块1完成任务拆解")
    else:
        st.subheader("📥 上游任务输入")
        st.json(st.session_state['upstream_result'])

        if st.button("🤖 运行HTN规划器"):
            st.info("正在运行HTN任务规划与分配...")

            # TODO: 这里接入你的 htn_planner.py 的核心规划函数
            # 为了演示，先放一个模拟的分配结果
            mock_htn_result = {
                "uav_1": [
                    {"task_id": "sub_001", "type": "takeoff", "params": {"height": 15}},
                    {"task_id": "sub_003", "type": "goto", "params": {"target": "turbine1"}}
                ],
                "uav_2": [
                    {"task_id": "sub_002", "type": "takeoff", "params": {"height": 20}},
                    {"task_id": "sub_004", "type": "goto", "params": {"target": "turbine2"}}
                ]
            }

            st.success("✅ HTN规划完成！")

            # 展示多机分配看板
            st.subheader("📋 多机任务分配看板")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### 🚁 uav_1 任务列表")
                for task in mock_htn_result['uav_1']:
                    st.info(f"- [{task['task_id']}] {task['type']}")
            with col2:
                st.markdown("### 🚁 uav_2 任务列表")
                for task in mock_htn_result['uav_2']:
                    st.info(f"- [{task['task_id']}] {task['type']}")

            # 保存HTN结果
            st.session_state['htn_result'] = mock_htn_result

# ========== 6. 模块3：仿真执行与结果可视化 ==========
elif mode == "3. 仿真执行与结果":
    st.header("✈️ 模块3：仿真执行与结果展示")

    if 'htn_result' not in st.session_state:
        st.warning("⚠️ 请先在模块2完成HTN规划")
    else:
        if st.button("🚀 生成代码并启动仿真"):
            st.info("正在生成下游代码并启动AirSim仿真...")
            # TODO: 这里接入你的 downstream_main.py 逻辑
            st.success("✅ 仿真执行完成！")

            # ========== 画飞行轨迹图（毕设论文高分素材） ==========
            st.subheader("🗺️ 飞行轨迹图")

            # 模拟轨迹数据（实际应从AirSim读取）
            import numpy as np

            t = np.linspace(0, 2 * np.pi, 100)
            x1 = 10 * np.cos(t)
            y1 = 10 * np.sin(t)
            x2 = 15 * np.cos(t + np.pi)
            y2 = 15 * np.sin(t + np.pi)

            fig, ax = plt.subplots(figsize=(8, 6))
            ax.plot(x1, y1, label='uav_1 轨迹', linewidth=2)
            ax.plot(x2, y2, label='uav_2 轨迹', linewidth=2, linestyle='--')
            ax.scatter(0, 0, c='red', s=100, label='turbine1')
            ax.scatter(20, 0, c='blue', s=100, label='turbine2')
            ax.set_xlabel('X (m)')
            ax.set_ylabel('Y (m)')
            ax.set_title('双机协同巡检飞行轨迹')
            ax.legend()
            ax.grid(True)

            st.pyplot(fig)

            # ========== 展示巡检照片 ==========
            st.subheader("📸 巡检照片展示")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### uav_1 拍摄的 turbine1")
                # TODO: 这里放实际的AirSim照片路径
                st.image("https://via.placeholder.com/400x300?text=turbine1+Inspection+Photo",
                         caption="turbine1 巡检照片")
            with col2:
                st.markdown("#### uav_2 拍摄的 turbine2")
                st.image("https://via.placeholder.com/400x300?text=turbine2+Inspection+Photo",
                         caption="turbine2 巡检照片")