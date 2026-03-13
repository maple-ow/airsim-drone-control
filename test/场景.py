import airsim
import math


def main():
    print("\n" + "=" * 60)
    print("🔍 场景物体检测测试")
    print("=" * 60)

    try:
        # 1. 连接 AirSim（只连，不碰飞控）
        print("\n[1/3] 正在连接 AirSim...")
        client = airsim.MultirotorClient()
        client.confirmConnection()
        print("✅ 连接成功！")

        # 2. 获取默认无人机状态
        print("\n[2/3] 获取无人机状态...")
        try:
            pose = client.simGetVehiclePose()
            x, y, z = pose.position.x_val, pose.position.y_val, -pose.position.z_val

            kinematics = client.getMultirotorState().kinematics_estimated
            _, _, yaw = airsim.to_eularian_angles(kinematics.orientation)
            yaw_deg = round(math.degrees(yaw), 1)

            print(f"✅ 无人机位置: [{x:.2f}, {y:.2f}, {z:.2f}]")
            print(f"✅ 无人机朝向: {yaw_deg}°")
        except Exception as e:
            print(f"⚠️  获取无人机状态失败: {e}")

        # 3. 获取场景物体列表
        print("\n[3/3] 扫描场景物体...")
        try:
            # 方法1：尝试列出所有物体（取决于 AirSim 版本）
            print("正在尝试列出所有场景物体...")

            # 注意：不同版本的 AirSim API 可能不同
            # 这里尝试几种常见的方法

            # 尝试 A: 直接获取所有物体名称（最常用）
            try:
                # 这个 API 在某些 AirSim 版本中是 simListSceneObjects
                # 我们先尝试访问 simGetObjectPose 来测试常见物体
                common_names = [
                    "turbine1", "turbine2", "turbine3",
                    "tower1", "tower2", "tower3",
                    "solarpanels", "car", "crowd",
                    "Cube", "Cylinder", "Sphere"  # UE 默认物体名
                ]

                found_objects = []
                print(f"正在测试 {len(common_names)} 个常见物体名...")

                for name in common_names:
                    try:
                        pose = client.simGetObjectPose(name)
                        # 简单判断：如果位置不是 (0,0,0) 或者物体存在
                        # 注意：这只是一个粗略判断
                        if pose.position.x_val != 0 or pose.position.y_val != 0 or pose.position.z_val != 0:
                            pos = [pose.position.x_val, pose.position.y_val, -pose.position.z_val]
                            found_objects.append({
                                "name": name,
                                "position": [round(p, 2) for p in pos]
                            })
                    except:
                        continue

                if found_objects:
                    print(f"\n✅ 找到 {len(found_objects)} 个物体：")
                    for obj in found_objects:
                        print(f"  - {obj['name']}: 位置 {obj['position']}")
                else:
                    print("\n❌ 未找到常见物体。")
                    print("💡 请在下方输入你在 UE 编辑器里看到的物体名称：")
                    user_input_name = input("请输入物体名（或直接回车跳过）: ").strip()
                    if user_input_name:
                        try:
                            pose = client.simGetObjectPose(user_input_name)
                            pos = [pose.position.x_val, pose.position.y_val, -pose.position.z_val]
                            print(f"✅ 找到物体 {user_input_name}: 位置 {[round(p, 2) for p in pos]}")
                        except Exception as e:
                            print(f"❌ 还是找不到: {e}")

            except Exception as e:
                print(f"方法 A 失败: {e}")

        except Exception as e:
            print(f"❌ 扫描场景失败: {e}")

    except Exception as e:
        print(f"\n❌ 连接 AirSim 失败: {e}")
        print("💡 请确保 AirSim 仿真环境正在运行！")

    print("\n" + "=" * 60)
    print("测试结束")
    print("=" * 60)


if __name__ == "__main__":
    main()