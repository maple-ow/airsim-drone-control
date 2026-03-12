from utils.airsim_wrapper import AirSimWrapper

# ================== 连接初始化 ==================
print("[系统] 正在连接 AirSim...")
aw = AirSimWrapper()  # 自动处理连接、解锁、坐标系

try:
    # ================== 任务执行序列 ==================
    print("[系统] 当前任务列表为空，无需执行飞行任务。")

except Exception as e:
    print(f"[系统] 执行出错: {e}")
    print("[系统] 紧急降落...")
    aw.land()

finally:
    print("[系统] 任务结束")