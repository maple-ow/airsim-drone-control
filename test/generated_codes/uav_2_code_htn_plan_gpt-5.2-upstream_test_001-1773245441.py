from utils.airsim_wrapper import AirSimWrapper
import time

"""
任务输入:
{
  "uav_id": "uav_2",
  "tasks": []
}

说明：
- 当前无任何原子任务需要执行。
- 代码将完成 AirSimWrapper 初始化并直接结束。
"""

# ================== 连接初始化 ==================
print("[系统] 正在连接 AirSim...")
aw = AirSimWrapper()  # 自动处理连接、解锁、坐标系（Z轴向上为正）

try:
    # ================== 任务执行序列 ==================
    print("[系统] 当前任务列表为空（tasks=[]），无需执行飞行任务。")
    # 如需保持程序短暂停留，便于观察日志，可取消注释：
    # time.sleep(2)

except Exception as e:
    print(f"[系统] 执行出错: {e}")
    # 没有飞行任务，这里不强制降落；如需要也可调用 aw.land()

finally:
    print("[系统] 任务结束")