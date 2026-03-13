from utils.airsim_wrapper import AirSimWrapper
import math
import time


def main():
    print("\n" + "=" * 60)
    print("🔵 独立画圆功能测试")
    print("=" * 60)

    try:
        # 1. 连接无人机
        print("\n[1/5] 连接 AirSim...")
        aw = AirSimWrapper()  # 单无人机测试，不传 vehicle_name
        print("✅ 连接成功！")

        # 2. 起飞
        print("\n[2/5] 起飞到 15 米...")
        aw.takeoff(height=15)
        print("✅ 起飞完成！")

        # 3. 飞到画圆起始点（圆心正前方）
        print("\n[3/5] 飞到画圆起始点...")
        circle_center = [0, 0, 15]  # 固定圆心，方便测试
        circle_radius = 5  # 半径 5 米
        start_point = [circle_center[0] + circle_radius, circle_center[1], circle_center[2]]

        print(f"   圆心: {circle_center}")
        print(f"   起始点: {start_point}")
        aw.fly_to(start_point, velocity=2)
        print("✅ 到达起始点！")

        # 4. 生成画圆航点并执行
        print("\n[4/5] 开始画圆...")
        num_points = 36  # 36个点，画一个圆
        waypoints = []

        print(f"   正在生成 {num_points} 个航点...")
        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            x = circle_center[0] + circle_radius * math.cos(angle)
            y = circle_center[1] + circle_radius * math.sin(angle)
            z = circle_center[2]
            waypoints.append([x, y, z])
            # 每生成10个点打印一次
            if (i + 1) % 10 == 0:
                print(f"   已生成 {i + 1}/{num_points} 个航点")

        print(f"   航点生成完成！")
        print(f"   第一个航点: {waypoints[0]}")
        print(f"   最后一个航点: {waypoints[-1]}")

        # 执行画圆
        print(f"\n   正在执行画圆路径 (is_circle=True)...")
        aw.fly_path(waypoints, velocity=2, is_circle=True)
        print("✅ 画圆完成！")

        # 5. 降落
        print("\n[5/5] 执行降落...")
        aw.land()
        print("✅ 降落完成！")

        print("\n" + "=" * 60)
        print("🎉 画圆测试全部完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        print("⚠️  执行紧急降落...")
        try:
            aw.land()
        except Exception as e2:
            print(f"❌ 紧急降落失败: {e2}")


if __name__ == "__main__":
    main()