from utils.airsim_wrapper import AirSimWrapper
import time

# ================== 连接初始化 ==================
print("[系统] 正在连接 AirSim...")
aw = AirSimWrapper()  # 自动处理连接、解锁、坐标系

try:
    # ================== 任务执行序列 ==================
    print("[系统] 当前任务列表为空，无需执行飞行任务。")

    # 可选：保持短暂悬停或直接结束
    time.sleep(1)

    # ================== 任务结束 ==================
    print("[系统] 任务结束，无需降落操作。")

except Exception as e:
    print(f"[系统] 执行出错: {e}")
    print("[系统] 若已起飞将尝试降落...")
    try:
        aw.land()
    except Exception:
        pass

finally:
    print("[系统] 程序结束")