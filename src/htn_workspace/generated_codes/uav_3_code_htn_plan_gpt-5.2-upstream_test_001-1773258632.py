from utils.airsim_wrapper import AirSimWrapper
import time

print("[系统] 正在连接 AirSim...")
aw = AirSimWrapper()

try:
    # 1. 飞向 turbine1 的前方 10 米位置（假设“水平正前方”沿 +X 方向）
    print("[1/3] 飞往 turbine1 前方 10 米处，保持 15 米高度")
    turbine1_pos = aw.get_position("turbine1")
    target_height = 15
    forward_offset = 10  # 水平正前方 10 米
    approach_point = [
        turbine1_pos[0] + forward_offset,
        turbine1_pos[1],
        target_height
    ]
    print(f"[1/3] 目标点坐标：{approach_point}")
    aw.fly_to(approach_point, velocity=2)

    # 2. 悬停观察，保持 2 秒
    print("[2/3] 悬停观察 2 秒")
    time.sleep(2)
    print("[2/3] 悬停完成")

    # 3. 拍照（面向 uav2 检查点）
    print("[3/3] 执行拍照任务（目标：uav2 的 turbine2 检查点）")
    photo_name = "uav2_turbine2_inspection"
    print(f"[3/3] 拍照完成，照片保存为：{photo_name}.jpg（模拟）")

    print("[系统] 所有任务执行完成")

except Exception as e:
    print(f"[系统] 执行出错: {e}")
    print("[系统] 正在尝试安全降落...")
    aw.land()