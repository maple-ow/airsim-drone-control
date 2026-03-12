from utils.airsim_wrapper import AirSimWrapper
import time
import math

# ================== 配置（按任务参数自拟） ==================
UAV_ID = "uav_1"

TAKEOFF_HEIGHT = 15.0   # 米，Z轴向上为正
GOTO_SPEED = 2.0        # m/s

CIRCLE_CENTER = [0.0, 0.0, 15.0]
CIRCLE_RADIUS = 6.0
CIRCLE_NUM_POINTS = 36

HOVER_DURATION_1 = 5.0  # 秒
HOVER_DURATION_2 = 5.0  # 秒

# sub_005 custom waypoints（按输入原样使用）
CUSTOM_WAYPOINTS = [
    [5.0, 0.0, 15.0],
    [4.92, 0.0, 15.87],
    [4.7, 0.0, 16.71],
    [4.33, 0.0, 17.5],
    [3.83, 0.0, 18.21],
    [3.21, 0.0, 18.83],
    [2.5, 0.0, 19.33],
    [1.71, 0.0, 19.7],
    [0.87, 0.0, 19.92],
    [0.0, 0.0, 20.0],
    [-0.87, 0.0, 19.92],
    [-1.71, 0.0, 19.7],
    [-2.5, 0.0, 19.33],
    [-3.21, 0.0, 18.83],
    [-3.83, 0.0, 18.21],
    [-4.33, 0.0, 17.5],
    [-4.7, 0.0, 16.71],
    [-4.92, 0.0, 15.87],
    [-5.0, 0.0, 15.0],
    [-4.92, 0.0, 14.13],
    [-4.7, 0.0, 13.29],
    [-4.33, 0.0, 12.5],
    [-3.83, 0.0, 11.79],
    [-3.21, 0.0, 11.17],
    [-2.5, 0.0, 10.67],
    [-1.71, 0.0, 10.3],
    [-0.87, 0.0, 10.08],
    [0.0, 0.0, 10.0],
    [0.87, 0.0, 10.08],
    [1.71, 0.0, 10.3],
    [2.5, 0.0, 10.67],
    [3.21, 0.0, 11.17],
    [3.83, 0.0, 11.79],
    [4.33, 0.0, 12.5],
    [4.7, 0.0, 13.29],
    [4.92, 0.0, 14.13],
    [5.0, 0.0, 15.0],
]


def generate_circle_waypoints(center, radius, num_points):
    """生成圆形航点（Z轴向上为正），用于 aw.fly_path(..., is_circle=True)"""
    cx, cy, cz = center
    waypoints = []
    for i in range(num_points):
        theta = 2.0 * math.pi * i / num_points
        x = cx + radius * math.cos(theta)
        y = cy + radius * math.sin(theta)
        z = cz
        waypoints.append([x, y, z])
    # 可选：闭合圆（不强制；is_circle=True 通常也可视为闭合）
    waypoints.append(waypoints[0])
    return waypoints


if __name__ == "__main__":
    print(f"[系统] UAV: {UAV_ID} 正在连接 AirSim...")
    aw = AirSimWrapper()  # 必须使用封装类，不直接调用 airsim.MultirotorClient

    try:
        # ================== 任务执行序列（按依赖顺序） ==================

        # [sub_001] takeoff
        print("[sub_001] 起飞")
        aw.takeoff()
        print("[sub_001] 起飞完成")

        # [sub_002] goto 起飞点正上方圆心(0,0,15)
        print("[sub_002] 飞往 起飞点正上方圆心(0,0,15)")
        aw.fly_to([0.0, 0.0, TAKEOFF_HEIGHT], velocity=GOTO_SPEED)
        print("[sub_002] 到达目标点")

        # [sub_003] fly_path circle
        print("[sub_003] 绕圆飞行（circle path）")
        circle_waypoints = generate_circle_waypoints(
            center=CIRCLE_CENTER,
            radius=CIRCLE_RADIUS,
            num_points=CIRCLE_NUM_POINTS
        )
        # 按规范：circle 需要 is_circle=True
        aw.fly_path(circle_waypoints, velocity=2, is_circle=True)
        print("[sub_003] 绕圆飞行完成")

        # [sub_004] hover 5s
        print(f"[sub_004] 悬停 {HOVER_DURATION_1} 秒")
        time.sleep(HOVER_DURATION_1)
        print("[sub_004] 悬停完成")

        # [sub_005] fly_path custom
        print("[sub_005] 按自定义路径飞行（custom path）")
        aw.fly_path(CUSTOM_WAYPOINTS, velocity=2)
        print("[sub_005] 自定义路径飞行完成")

        # [sub_006] hover 5s
        print(f"[sub_006] 悬停 {HOVER_DURATION_2} 秒")
        time.sleep(HOVER_DURATION_2)
        print("[sub_006] 悬停完成")

        # [sub_007] return_to_launch：飞往 [0,0,10] 后降落（按规则映射）
        print("[sub_007] 返回起点并降落（return_to_launch）")
        aw.fly_to([0.0, 0.0, 10.0], velocity=2)
        aw.land()
        print("[sub_007] 已返回并完成降落")

        # [sub_008] land（任务中仍要求执行）
        print("[sub_008] 执行降落（land）")
        aw.land()
        print("[sub_008] 降落完成")

        print("[系统] 所有任务执行完成")

    except Exception as e:
        print(f"[系统] 执行出错: {e}")
        print("[系统] 尝试安全降落...")
        try:
            aw.land()
        except Exception as e2:
            print(f"[系统] 降落失败: {e2}")
    finally:
        print("[系统] 任务结束")