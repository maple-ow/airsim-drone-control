import airsim
import time

# 1. 连接到AirSim
client = airsim.MultirotorClient()
client.confirmConnection()
client.enableApiControl(True)  # 启用API控制
client.armDisarm(True)         # 解锁电机

print("✅ 成功连接到AirSim并解锁电机")

# 2. 测试起飞
print("🚀 正在起飞...")
client.takeoffAsync().join()  # join()表示等待动作完成
time.sleep(2)

# 3. 测试获取当前位置
pose = client.simGetVehiclePose()
print(f"📍 当前位置: X={pose.position.x_val:.2f}, Y={pose.position.y_val:.2f}, Z={pose.position.z_val:.2f}")

# 4. 测试移动到相对位置 (向右飞5米，向前飞5米，高度保持)
print("✈️  正在移动...")
client.moveToPositionAsync(pose.position.x_val + 5, pose.position.y_val + 5, pose.position.z_val, 5).join()
time.sleep(2)

# 5. 测试降落
print("🪂 正在降落...")
client.landAsync().join()
client.armDisarm(False)        # 上锁电机
client.enableApiControl(False)  # 释放API控制

print("🎉 基础功能测试完成！")