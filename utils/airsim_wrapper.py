import airsim
import math
import time
import numpy as np

# ================== 场景物体名称映射 ==================
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
        """
        初始化 AirSim 连接

        """
        self.client = airsim.MultirotorClient()
        self.client.confirmConnection()
        self.client.enableApiControl(True)
        self.client.armDisarm(True)



    # ================== 核心坐标系转换函数 ==================
    def _to_airsim_z(self, z_human):
        """内部辅助：人类友好 Z（向上为正） -> AirSim Z（向下为正）"""
        return -z_human

    def get_drone_position(self):
        """
        获取无人机当前位置
        :return: [X, Y, Z]，Z轴向上为正
        """
        pose = self.client.simGetVehiclePose()
        return [
            pose.position.x_val,
            pose.position.y_val,
            -pose.position.z_val  # 取反，统一 Z 轴向上
        ]

    # ================== 基础飞行动作 ==================
    def takeoff(self):
        """起飞（自动等待稳定）"""
        print("[aw] 起飞中...")
        self.client.takeoffAsync().join()
        time.sleep(2)  # 起飞后多等一会，确保稳定
        print("[aw] 起飞完成")

    def land(self):
        """
        安全软着陆（自动减速，避免砸机）
        流程：高空 -> 5米 -> 1.5米 -> 0.3米 -> 悬停 -> 原生降落
        """
        print("[aw] 开始执行软着陆程序...")
        try:
            curr_pos = self.get_drone_position()
            current_z = curr_pos[2]

            # 1. 如果飞得很高，先快速降到 5 米
            if current_z > 5:
                print(f"[aw] 从 {current_z:.1f}米 快速降至 5米")
                # 【核心修复】移除 auto_switch=False 参数
                self.fly_to([curr_pos[0], curr_pos[1], 5], velocity=1.5)

            # 2. 从 5m 缓慢降至 1.5m
            print(f"[aw] 从 5米 缓慢降至 1.5米")
            # 【核心修复】移除 auto_switch=False 参数
            self.fly_to([curr_pos[0], curr_pos[1], 1.5], velocity=0.8)

            # 3. 从 1.5m 极慢降至 0.3m
            print(f"[aw] 从 1.5米 极慢降至 0.3米")
            # 【核心修复】移除 auto_switch=False 参数
            self.fly_to([curr_pos[0], curr_pos[1], 0.3], velocity=0.3)

            # 4. 悬停稳定 1 秒
            print(f"[aw] 悬停稳定中...")
            self.client.hoverAsync().join()
            time.sleep(1)

        except Exception as e:
            print(f"[aw] 软着陆流程中断，启用紧急降落: {e}")

        # 5. 最后执行原生降落（此时已非常接近地面）
        print(f"[aw] 执行最终降落...")
        self.client.landAsync().join()
        self.client.armDisarm(False)
        self.client.enableApiControl(False)
        print("[aw] ✅ 安全降落完成")

    # ================== 核心飞行函数：自适应长/短距离 ==================
    def fly_to(self, point, velocity=2, tolerance=1.5, timeout=30):
        """
        【卡死修复版】彻底解决短距离不动/程序卡住问题
        """
        x, y, z = point[0], point[1], point[2]
        airsim_z = self._to_airsim_z(z)

        # ================== 1. 计算初始距离 ==================
        curr_pos = self.get_drone_position()
        dist_to_target = (
                                 (curr_pos[0] - x) ** 2 +
                                 (curr_pos[1] - y) ** 2 +
                                 (curr_pos[2] - z) ** 2
                         ) ** 0.5

        # ================== 2. 【核心修复】极短距离直接跳过 ==================
        if dist_to_target < 0.5:
            print(f"[aw] 距离极短 ({dist_to_target:.1f}m)，直接稳定悬停")
            self.client.hoverAsync().join()
            return

        # ================== 3. 长/短距离判断 ==================
        is_short = dist_to_target <= 8.0

        if is_short:
            final_tolerance = 0.5  # 稍微放大容忍度，避免死循环
            final_velocity = min(velocity, 1.2)  # 稍微提高一点速度，避免不动
            print(
                f"[aw] 检测到短距离 ({dist_to_target:.1f}m)，切换至精准模式 (容忍度: {final_tolerance}m, 速度: {final_velocity}m/s)")
        else:
            final_tolerance = tolerance
            final_velocity = velocity
            print(f"[aw] 检测到长距离 ({dist_to_target:.1f}m)，切换至平滑模式")

        print(f"[aw] 正在飞往 ({x:.1f}, {y:.1f}, {z:.1f})")

        import time
        start_time = time.time()
        stable_start_time = None
        required_stable_time = 0.3

        try:
            # ================== 4. 【核心修复】分情况启动任务 ==================
            if is_short:
                # 【短距离】启动任务，但不 join()！
                self.client.moveToPositionAsync(
                    x, y, airsim_z,
                    final_velocity,
                    timeout_sec=timeout
                )
                # 启动后立即进入监控循环
            else:
                # 【长距离】继续用 moveOnPathAsync + join()
                curr_pose = self.client.simGetVehiclePose()
                start_point = airsim.Vector3r(
                    curr_pose.position.x_val,
                    curr_pose.position.y_val,
                    curr_pose.position.z_val
                )
                end_point = airsim.Vector3r(x, y, airsim_z)
                path = [start_point, end_point]

                flight_task = self.client.moveOnPathAsync(
                    path,
                    final_velocity,
                    timeout,
                    airsim.DrivetrainType.MaxDegreeOfFreedom,
                    airsim.YawMode(False, 0),
                    lookahead=10,
                    adaptive_lookahead=1
                )
                flight_task.join()

            # ================== 5. 【核心修复】统一手动监控循环（长/短距离都用） ==================
            while True:
                # 获取当前状态
                curr_pos_final = self.get_drone_position()
                kinematics = self.client.getMultirotorState().kinematics_estimated

                # 计算误差
                dist_3d = (
                                  (curr_pos_final[0] - x) ** 2 +
                                  (curr_pos_final[1] - y) ** 2 +
                                  (curr_pos_final[2] - z) ** 2
                          ) ** 0.5

                speed = (
                                kinematics.linear_velocity.x_val ** 2 +
                                kinematics.linear_velocity.y_val ** 2 +
                                kinematics.linear_velocity.z_val ** 2
                        ) ** 0.5

                # 打印调试信息（可选，方便看状态）
                # print(f"[调试] 位置误差: {dist_3d:.2f}m, 速度: {speed:.2f}m/s")

                # 判断是否稳定到达
                if dist_3d < final_tolerance and speed < 0.5:
                    if stable_start_time is None:
                        stable_start_time = time.time()
                    elif time.time() - stable_start_time > required_stable_time:
                        print(f"[aw] ✅ 稳定到达目标 (位置误差: {dist_3d:.2f}m, 速度: {speed:.2f}m/s)")
                        break
                else:
                    stable_start_time = None

                # 超时保护（强制接管）
                if time.time() - start_time > timeout:
                    print(f"[aw] ⚠️  飞行超时 ({timeout}s)，强制悬停 (当前位置误差: {dist_3d:.2f}m)")
                    break

                time.sleep(0.05)

            # 最终强制悬停（无论是否到达，都接管控制权）
            self.client.hoverAsync().join()

        except Exception as e:
            print(f"[aw] ❌ 飞行出错: {e}，紧急悬停")
            self.client.hoverAsync().join()
    # ================== 核心飞行函数：路径飞行/画圆 ==================
    def fly_path(self, points, velocity=3, is_circle=False):
        """
        【优化版】沿路径飞行（专门适配画圆）
        :param points: 坐标点列表 [[x,y,z], ...]，Z轴向上为正
        :param velocity: 飞行速度
        :param is_circle: 是否是画圆任务（若是，自动优化参数）
        """
        print(f"[aw] 规划路径飞行，共 {len(points)} 个点")

        # 1. 转换坐标点
        airsim_points = []
        for point in points:
            x, y, z = point[0], point[1], point[2]
            airsim_points.append(airsim.Vector3r(x, y, self._to_airsim_z(z)))

        # 2. 根据任务类型动态设置参数
        if is_circle or len(points) > 20:
            lookahead_val = 2.0
            adaptive_lookahead_val = 0
            mode_str = "画圆/多航点模式"
        else:
            lookahead_val = 10.0
            adaptive_lookahead_val = 1
            mode_str = "普通长路径模式"

        print(f"[aw] 切换至 {mode_str}")

        try:
            # 3. 执行路径飞行
            flight_task = self.client.moveOnPathAsync(
                airsim_points,
                velocity,
                120,
                airsim.DrivetrainType.MaxDegreeOfFreedom,
                airsim.YawMode(False, 0),
                lookahead=lookahead_val,
                adaptive_lookahead=adaptive_lookahead_val
            )
            flight_task.join()

            print(f"[aw] ✅ 路径飞行完成")
            self.client.hoverAsync().join()

        except Exception as e:
            print(f"[aw] ❌ 路径飞行出错: {e}，紧急悬停")
            self.client.hoverAsync().join()

    # ================== 辅助功能：朝向控制 ==================
    def set_yaw(self, yaw):
        """旋转朝向至指定角度（度）"""
        print(f"[aw] 旋转朝向至 {yaw} 度")
        self.client.rotateToYawAsync(yaw, timeout_sec=5).join()

    def get_yaw(self):
        """获取当前朝向（度）"""
        orientation_quat = self.client.simGetVehiclePose().orientation
        yaw = airsim.to_eularian_angles(orientation_quat)[2]
        return math.degrees(yaw)

    # ================== 辅助功能：场景物体定位 ==================
    def get_position(self, object_name):
        """
        获取场景中物体的坐标
        :param object_name: 物体名（仅限 objects_dict 中定义的）
        :return: [X, Y, Z]，Z轴向上为正
        """
        if object_name not in objects_dict:
            raise ValueError(f"未知物体名: {object_name}，可选: {list(objects_dict.keys())}")

        query_string = objects_dict[object_name] + ".*"
        object_names_ue = []
        while len(object_names_ue) == 0:
            object_names_ue = self.client.simListSceneObjects(query_string)

        pose = self.client.simGetObjectPose(object_names_ue[0])
        return [
            pose.position.x_val,
            pose.position.y_val,
            -pose.position.z_val  # 统一 Z 轴向上
        ]