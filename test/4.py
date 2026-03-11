import math
import numpy as np

# 1) 确保无人机在空中
aw.takeoff()

# 2) 设定圆参数（半径=10；高度设为更安全的 Z=5）
R = 10.0
num_points = 36            # 圆周离散点数量，越大越圆滑
safe_z = 5.0               # 安全高度（Z轴正方向向上）
11111111111111111111111111111
# 3) 以当前水平位置为圆心，先爬升/移动到圆所在平面
cur_pos = aw.get_drone_position()
cx, cy = cur_pos[0], cur_pos[1]

# 先到达圆的起点（圆心右侧 R 处），并在安全高度
start_point = [cx + R, cy, safe_z]
aw.fly_to(start_point)

# 4) 生成圆周路径点（在水平面 Z=safe_z 绕一圈回到起点）
angles = np.linspace(0.0, 2.0 * math.pi, num_points + 1)  # +1 让最后一点回到起点
points = []
for a in angles:
    x = cx + R * math.cos(a)
    y = cy + R * math.sin(a)
    z = safe_z
    points.append([float(x), float(y), float(z)])

# 5) 沿路径飞行，完成“画圆”
aw.fly_path(points)

# 6) 任务完成后安全降落
aw.land()