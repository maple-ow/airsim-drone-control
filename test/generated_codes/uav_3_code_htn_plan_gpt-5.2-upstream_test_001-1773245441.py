from utils.airsim_wrapper import AirSimWrapper

# ================== 连接初始化 ==================
print("[系统] 正在连接 AirSim...")
aw = AirSimWrapper()  # 自动处理连接、解锁、坐标系（Z轴向上为正）

try:
    # ================== 任务执行序列 ==================
    # UAV: uav_3
    tasks = []  # 输入任务为空

    if not tasks:
        print("[系统] 当前任务列表为空，无需执行飞行任务。")
        # 不做任何动作，直接结束

except Exception as e:
    print(f"[系统] 执行出错: {e}")
    # 任务为空时通常不需要降落；若实际已起飞可按需启用：
    # print("[系统] 尝试安全降落...")
    # aw.land()

finally:
    print("[系统] 任务结束")