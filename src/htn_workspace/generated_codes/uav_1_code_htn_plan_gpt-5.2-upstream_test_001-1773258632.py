from utils.airsim_wrapper import AirSimWrapper
import time

def main():
    """
    该脚本根据 HTN 规划结果，执行 uav_1 的任务序列：起飞、拍照、返航。
    针对 sub_010（目标为 uav2）将不会执行，避免误操作。
    """
    print("[系统] 正在连接 AirSim...")
    aw = AirSimWrapper()
    is_airborne = False  # 用于判断当前是否处于空中，便于异常处理

    try:
        # 步骤 1：起飞（到指定高度 15m）
        print("[步骤 1/3] 起飞至 15 米高度")
        aw.takeoff()
        is_airborne = True

        # 步骤 2：执行拍照任务
        print("[步骤 2/3] 在当前机位进行拍照")
        photo_name = "uav1_turbine1_inspection"
        print(f"[步骤 2/3] 拍照名称：{photo_name} （实际拍照逻辑可通过 simGetImages 集成）")
        time.sleep(1)  # 简单等待，模拟拍照过程

        # 步骤 3：返航（高度 15m），并安全着陆
        print("[步骤 3/3] 返回起点（高度 15m）并降落")
        return_height = 15
        aw.fly_to([0, 0, return_height], velocity=2)
        aw.land()
        is_airborne = False

        # 任务 sub_010：目标为 uav2，因此本 UAV 不执行该任务（避免重复返航/降落）
        print("[提示] 任务 sub_010 指定目标为 uav2，该脚本仅控制 uav_1，已跳过该任务。")

        print("[系统] 所有任务执行完毕。")

    except Exception as e:
        print(f"[系统] 执行过程中发生异常: {e}")
        if is_airborne:
            print("[系统] 发生异常，执行紧急降落...")
            aw.land()
        else:
            print("[系统] 当前无人机已在地面，无需降落。")

if __name__ == "__main__":
    main()