import os
import sys
import math
import time

# ========== 路径配置 ==========
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from utils.airsim_wrapper import AirSimWrapper


def draw_pentagram():
    print("\n" + "=" * 60)
    print("⭐ 五角星任务测试 - 验证 AirSimWrapper 封装函数")
    print("=" * 60)

    # ========== 1. 初始化连接（验证 __init__） ==========
    print("\n[步骤1] 初始化 AirSim 连接...")
    try:
        aw = AirSimWrapper()
        print("✅ 连接成功！")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return

    # ========== 2. 五角星参数配置 ==========
    center_x, center_y = 0, 0  # 圆心坐标
    radius = 10  # 五角星外接圆半径（米）
    height = 20  # 飞行高度（米）
    velocity = 2  # 飞行速度（m/s）

    # 五角星的5个顶点角度（0°, 144°, 288°, 72°, 216°）
    pentagram_angles = [0, 144, 288, 72, 216]

    try:
        # ========== 3. 起飞（验证 takeoff） ==========
        print("\n[步骤2] 执行起飞...")
        aw.takeoff()

        # 验证 get_drone_position
        curr_pos = aw.get_drone_position()
        print(f"✅ 起飞完成，当前位置: {[round(p, 2) for p in curr_pos]}")

        # ========== 4. 计算并飞往第一个顶点（验证 fly_to） ==========
        print("\n[步骤3] 飞往五角星第一个顶点...")
        first_angle_rad = math.radians(pentagram_angles[0])
        first_x = center_x + radius * math.cos(first_angle_rad)
        first_y = center_y + radius * math.sin(first_angle_rad)

        aw.fly_to([first_x, first_y, height], velocity=velocity)
        curr_pos = aw.get_drone_position()
        print(f"✅ 到达第一个顶点，当前位置: {[round(p, 2) for p in curr_pos]}")

        # ========== 5. 依次飞往剩余4个顶点（验证 fly_to 长短距离适配） ==========
        print("\n[步骤4] 开始绘制五角星（共5个顶点）...")
        for i, angle_deg in enumerate(pentagram_angles[1:], start=2):
            angle_rad = math.radians(angle_deg)
            x = center_x + radius * math.cos(angle_rad)
            y = center_y + radius * math.sin(angle_rad)

            print(f"  正在飞往第 {i} 个顶点...")
            aw.fly_to([x, y, height], velocity=velocity)

            curr_pos = aw.get_drone_position()
            print(f"  ✅ 到达第 {i} 个顶点，当前位置: {[round(p, 2) for p in curr_pos]}")

        # ========== 6. 闭合五角星（验证短距离 fly_to） ==========
        print("\n[步骤5] 闭合五角星...")
        aw.fly_to([first_x, first_y, height], velocity=velocity)
        print("✅ 五角星闭合完成！")

        # ========== 7. 悬停观察（验证 hover 逻辑） ==========
        print("\n[步骤6] 悬停观察 3 秒...")
        time.sleep(3)

        # ========== 8. 返回起点（验证长距离 fly_to） ==========
        print("\n[步骤7] 返回起点...")
        aw.fly_to([0, 0, height], velocity=velocity)
        print("✅ 已返回起点上方")

        # ========== 9. 安全软着陆（验证 land） ==========
        print("\n[步骤8] 执行安全软着陆...")
        aw.land()

        print("\n" + "=" * 60)
        print("🎉 五角星任务测试完成！所有封装函数运行正常")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 任务执行出错: {e}")
        print("⚠️  执行紧急降落...")
        try:
            aw.land()
        except:
            pass


if __name__ == "__main__":
    draw_pentagram()