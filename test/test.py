import airsim
import math
import time
import numpy as np

# ================== AirSimWrapper 类定义 (保持不变) ==================
objects_dict = {
    "turbine1": "BP_Wind_Turbines_C_1",
    "turbine2": "StaticMeshActor_2",
    "solarpanels": "StaticMeshActor_146",
    "crowd": "StaticMeshActor_6",
    "car": "StaticMeshActor_10",
    "tower1": "SM_Electric_trellis_179",
    "tower2": "SM_Electric_trellis_7",
    "tower3": "SM_Electric_trellis_8",
}


class AirSimWrapper:
    def __init__(self):
        self.client = airsim.MultirotorClient()
        self.client.confirmConnection()
        self.client.enableApiControl(True)
        self.client.armDisarm(True)

    def _to_airsim_z(self, z_human):
        return -z_human

    def get_drone_position(self):
        pose = self.client.simGetVehiclePose()
        return [
            pose.position.x_val,
            pose.position.y_val,
            -pose.position.z_val
        ]

    def takeoff(self):
        print("[aw] 起飞中...")
        self.client.takeoffAsync().join()
        time.sleep(2)
        print("[aw] 起飞完成")

    def land(self):
        print("[aw] 开始执行软着陆程序...")
        try:
            curr_pos = self.get_drone_position()
            current_z = curr_pos[2]
            if current_z > 5:
                print(f"[aw] 从 {current_z:.1f}米 快速降至 5米")
                self.fly_to([curr_pos[0], curr_pos[1], 5], velocity=1.5)
            print(f"[aw] 从 5米 缓慢降至 1.5米")
            self.fly_to([curr_pos[0], curr_pos[1], 1.5], velocity=0.8)
            print(f"[aw] 从 1.5米 极慢降至 0.3米")
            self.fly_to([curr_pos[0], curr_pos[1], 0.3], velocity=0.3)
            print(f"[aw] 悬停稳定中...")
            self.client.hoverAsync().join()
            time.sleep(1)
        except Exception as e:
            print(f"[aw] 软着陆流程中断: {e}")
        print(f"[aw] 执行最终降落...")
        self.client.landAsync().join()
        self.client.armDisarm(False)
        self.client.enableApiControl(False)
        print("[aw] ✅ 安全降落完成")

    def fly_to(self, point, velocity=2, tolerance=1.5, timeout=60):  # 稍微增加超时时间以防万一
        x, y, z = point[0], point[1], point[2]
        airsim_z = self._to_airsim_z(z)
        curr_pos = self.get_drone_position()
        dist_to_target = ((curr_pos[0] - x) ** 2 + (curr_pos[1] - y) ** 2 + (curr_pos[2] - z) ** 2) ** 0.5

        if dist_to_target < 0.5:
            print(f"[aw] 距离极短 ({dist_to_target:.1f}m)，直接稳定悬停")
            self.client.hoverAsync().join()
            return

        is_short = dist_to_target <= 8.0
        final_tolerance = 0.5 if is_short else tolerance
        final_velocity = min(velocity, 1.2) if is_short else velocity
        print(f"[aw] 飞往 ({x:.1f}, {y:.1f}, {z:.1f}) | 距离: {dist_to_target:.1f}m | 速度: {final_velocity}")

        start_time = time.time()
        stable_start_time = None
        required_stable_time = 0.3

        try:
            if is_short:
                self.client.moveToPositionAsync(x, y, airsim_z, final_velocity, timeout_sec=timeout)
            else:
                curr_pose = self.client.simGetVehiclePose()
                path = [airsim.Vector3r(curr_pose.position.x_val, curr_pose.position.y_val, curr_pose.position.z_val),
                        airsim.Vector3r(x, y, airsim_z)]
                flight_task = self.client.moveOnPathAsync(path, final_velocity, timeout,
                                                          airsim.DrivetrainType.MaxDegreeOfFreedom,
                                                          airsim.YawMode(False, 0), lookahead=10, adaptive_lookahead=1)
                flight_task.join()

            while True:
                curr_pos_final = self.get_drone_position()
                kinematics = self.client.getMultirotorState().kinematics_estimated
                dist_3d = ((curr_pos_final[0] - x) ** 2 + (curr_pos_final[1] - y) ** 2 + (
                            curr_pos_final[2] - z) ** 2) ** 0.5
                speed = (
                                    kinematics.linear_velocity.x_val ** 2 + kinematics.linear_velocity.y_val ** 2 + kinematics.linear_velocity.z_val ** 2) ** 0.5

                if dist_3d < final_tolerance and speed < 0.5:
                    if stable_start_time is None:
                        stable_start_time = time.time()
                    elif time.time() - stable_start_time > required_stable_time:
                        print(f"[aw] ✅ 稳定到达 (误差: {dist_3d:.2f}m)")
                        break
                else:
                    stable_start_time = None

                if time.time() - start_time > timeout:
                    print(f"[aw] ⚠️ 超时强制悬停")
                    break
                time.sleep(0.05)
            self.client.hoverAsync().join()
        except Exception as e:
            print(f"[aw] ❌ 飞行出错: {e}")
            self.client.hoverAsync().join()

    def fly_path(self, points, velocity=3, is_circle=False):
        print(f"[aw] 路径飞行，共 {len(points)} 个点")
        airsim_points = [airsim.Vector3r(p[0], p[1], self._to_airsim_z(p[2])) for p in points]

        lookahead_val = 2.0 if (is_circle or len(points) > 20) else 10.0
        adaptive_lookahead_val = 0 if (is_circle or len(points) > 20) else 1

        try:
            flight_task = self.client.moveOnPathAsync(
                airsim_points, velocity, 120,
                airsim.DrivetrainType.MaxDegreeOfFreedom,
                airsim.YawMode(False, 0),
                lookahead=lookahead_val, adaptive_lookahead=adaptive_lookahead_val
            )
            flight_task.join()
            print(f"[aw] ✅ 路径飞行完成")
            self.client.hoverAsync().join()
        except Exception as e:
            print(f"[aw] ❌ 路径飞行出错: {e}")
            self.client.hoverAsync().join()

    def set_yaw(self, yaw):
        print(f"[aw] 旋转朝向至 {yaw} 度")
        self.client.rotateToYawAsync(yaw, timeout_sec=5).join()

    def get_yaw(self):
        orientation_quat = self.client.simGetVehiclePose().orientation
        yaw = airsim.to_eularian_angles(orientation_quat)[2]
        return math.degrees(yaw)

    def get_position(self, object_name):
        if object_name not in objects_dict:
            raise ValueError(f"未知物体: {object_name}")
        query_string = objects_dict[object_name] + ".*"
        object_names_ue = []
        while len(object_names_ue) == 0:
            object_names_ue = self.client.simListSceneObjects(query_string)
        pose = self.client.simGetObjectPose(object_names_ue[0])
        return [pose.position.x_val, pose.position.y_val, -pose.position.z_val]


# ================== 修改后的测试主程序 ==================

def run_enhanced_test():
    print("=" * 60)
    print("开始 AirSimWrapper 增强测试 (20m 正方形)")
    print("=" * 60)

    try:
        # 1. 初始化 & 起飞
        print("\n[步骤 1] 初始化并起飞...")
        drone = AirSimWrapper()
        drone.takeoff()

        # 先飞到一个安全的起始高度和位置
        start_pos = drone.get_drone_position()
        flight_height = 10  # 飞行高度设定为10米，防止撞地
        print(f"\n[步骤 2] 爬升至安全高度 {flight_height}m...")
        drone.fly_to([start_pos[0], start_pos[1], flight_height], velocity=2)

        # 定义正方形参数
        center = drone.get_drone_position()
        side_length = 20.0  # 边长改为20单位

        # 定义正方形的4个顶点 (相对于当前位置)
        # 逻辑：右 -> 前 -> 左 -> 后 (回到起点)
        p0 = [center[0], center[1], flight_height]  # 起点
        p1 = [center[0] + side_length, center[1], flight_height]  # 右
        p2 = [center[0] + side_length, center[1] + side_length, flight_height]  # 前
        p3 = [center[0], center[1] + side_length, flight_height]  # 左

        square_path = [p0, p1, p2, p3, p0]
        vertex_names = ["起点", "顶点1 (右)", "顶点2 (前)", "顶点3 (左)", "终点/起点"]

        # 3. 开始正方形路径飞行
        print("\n" + "=" * 60)
        print(f"[步骤 3] 开始绘制 20m 正方形路径")
        print("=" * 60)

        for i, (target, name) in enumerate(zip(square_path, vertex_names)):
            print(f"\n🚀 正在前往第 {i + 1} 个点: {name}")
            print(f"   目标坐标: ({target[0]:.1f}, {target[1]:.1f}, {target[2]:.1f})")

            drone.fly_to(target, velocity=4)  # 速度稍微快一点

            print(f"✅ 到达 {name}!")
            print(f"   当前实际位置: {drone.get_drone_position()}")

            # 在顶点悬停2秒，方便观察
            if i < len(square_path) - 1:  # 最后一个点不停留太久，准备降落
                print("   顶点停留 2 秒...")
                time.sleep(2)

        print("\n" + "=" * 60)
        print("正方形路径绘制完成！")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n⚠️ 用户中断测试，尝试紧急降落...")
    except Exception as e:
        print(f"\n❌ 测试过程中发生严重错误: {e}")
    finally:
        # 无论如何，最后尝试降落
        try:
            print("\n[步骤 4] 开始降落...")
            drone.land()
        except Exception as e:
            print(f"无法执行自动降落: {e}，请手动接管。")


if __name__ == "__main__":
    input("请确保 AirSim 已启动，按任意键开始增强测试...")
    run_enhanced_test()