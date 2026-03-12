from utils.airsim_wrapper import AirSimWrapper
import time

print("[系统] 正在连接 AirSim...")
aw = AirSimWrapper()

try:
    # 1. 起飞
    print("[1/4] 起飞")
    aw.takeoff()
    
    # 1.1 确保达到目标高度（20米）
    current_pos = aw.get_drone_position()
    target_height = 20
    print(f"[1/4] 上升到 {target_height} 米高度以准备任务")
    aw.fly_to([current_pos[0], current_pos[1], target_height], velocity=2)
    
    # 2. 飞往 turbine2 的正前方 10 米（假设“正前方”是世界坐标的 +X 方向）
    print("[2/4] 飞往 turbine2 前方 10 米位置")
    turbine2_pos = aw.get_position("turbine2")
    offset_distance = 10  # 水平正前方 10 米
    target_point = [
        turbine2_pos[0] + offset_distance,
        turbine2_pos[1],
        target_height
    ]
    aw.fly_to(target_point, velocity=2)
    
    # 3. 悬停 2 秒
    print("[3/4] 悬停 2 秒以完成观察")
    time.sleep(2)
    
    # 4. 降落
    print("[4/4] 降落")
    aw.land()

except Exception as e:
    print(f"[系统] 执行出错: {e}")
    print("[系统] 紧急降落中...")
    aw.land()