import sys
import os
import re
import time
import json
import argparse
from openai import OpenAI
import math

try:
    from utils.airsim_wrapper import AirSimWrapper

    print("✅ AirSimWrapper 加载成功")
except ImportError:
    print("⚠️  未找到 utils.airsim_wrapper，仅测试 API 连接")
    AirSimWrapper = None

aw = None
if AirSimWrapper:
    try:
        print("正在连接 AirSim...")
        aw = AirSimWrapper()
    except ImportError:
        print("⚠️  未找到 utils.airsim_wrapper，仅测试 API 连接")
        AirSimWrapper = None

aw.takeoff()

import math
import numpy as np


import math

# Step 1: Takeoff (safety: ensure drone is airborne)
print("\n" + "=" * 60)
print("Step 1: Takeoff to ensure the drone is airborne")
aw.takeoff()

# Step 2: Read current state
print("\n" + "=" * 60)
print("Step 2: Get current drone position and yaw")
pos = aw.get_drone_position()  # [x, y, z]
yaw = aw.get_yaw()
print(f"Current position: {pos}")
print(f"Current yaw: {yaw} deg")

# Step 3: Define a vertical-circle (in X-Z plane, Y fixed) with radius 10
print("\n" + "=" * 60)
print("Step 3: Plan a vertical circle (X-Z plane) with radius = 10")

r = 10.0
cx, cy, cz = pos[0], pos[1], pos[2]

# Raise the circle center upward to keep the lowest point reasonably above the current altitude
# (per your coordinate rule: Z axis positive is upward)
center_z_offset = 15.0
cz = cz + center_z_offset

center = [cx, cy, cz]
print(f"Circle center: {center}, radius: {r}")

# Generate circle points
num_points = 72  # smooth enough, safe reasonable choice
points = []
for i in range(num_points + 1):  # +1 to close the circle
    theta = 2.0 * math.pi * (i / num_points)
    x = cx + r * math.cos(theta)
    y = cy
    z = cz + r * math.sin(theta)
    points.append([x, y, z])

start_point = points[0]
print(f"Start point: {start_point}")
print(f"Total path points: {len(points)}")

# Step 4: Fly to the start point first (avoid sudden curved motion)
print("\n" + "=" * 60)
print("Step 4: Fly to the circle start point")
aw.fly_to(start_point)

# Step 5: Fly the vertical circular path
print("\n" + "=" * 60)
print("Step 5: Fly the vertical circle path (X-Z plane, Y constant)")
aw.fly_path(points)

# Step 6: End (stay at final point; no land unless requested)
print("\n" + "=" * 60)
print("Step 6: Finished drawing the vertical circle (holding position at the end point)")