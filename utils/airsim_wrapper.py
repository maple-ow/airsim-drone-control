# utils/airsim_wrapper.py (修复版)
import airsim
import math
import numpy as np

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
        print("✅ AirSim 连接成功 (坐标系已统一: Z轴向上为正)")

    def takeoff(self):
        print("[aw] 起飞中...")
        self.client.takeoffAsync().join()
        # 起飞后多等一会，确保稳定
        import time
        time.sleep(2)

    def land(self):
        print("[aw] 开始执行软着陆程序...")
        import time

        try:
            # 1. 获取当前位置
            curr_pos = self.get_drone_position()
            current_z = curr_pos[2]

            # 2. 如果飞得很高，先快速降到 5 米
            if current_z > 5:

                self.fly_to([curr_pos[0], curr_pos[1], 5], velocity=1.5)

            # 3. 从 5m 缓慢降至 1.5m (关键减速阶段)

            self.fly_to([curr_pos[0], curr_pos[1], 1.5], velocity=0.8)

            # 4. 从 1.5m 极慢降至 0.3m (几乎是飘下去)

            self.fly_to([curr_pos[0], curr_pos[1], 0.3], velocity=0.3)

            # 5. 悬停稳定 1 秒

            self.client.hoverAsync().join()
            time.sleep(1)

        except Exception as e:
            print(f"[aw] 软着陆流程中断，启用紧急降落: {e}")

        # 6. 最后执行原生降落 (此时已经非常接近地面，不会砸下来了)

        self.client.landAsync().join()

        self.client.armDisarm(False)
        self.client.enableApiControl(False)
        print("[aw] ✅ 安全降落完成")

    def get_drone_position(self):
        """
        获取无人机当前位置
        返回: [X, Y, Z]，其中 Z 轴向上为正
        """
        pose = self.client.simGetVehiclePose()
        # 【关键修复】在这里统一做转换：AirSim Z -> 人类友好 Z
        # AirSim 里 z_val 是负数（在空中），我们取反让它变成正数
        return [
            pose.position.x_val,
            pose.position.y_val,
            -pose.position.z_val  # 取反
        ]

    def _to_airsim_z(self, z_human):
        """内部辅助函数：把人类的 Z 转成 AirSim 的 Z"""
        return -z_human

    def fly_to(self, point, velocity=2, tolerance=1.5):
        """
        飞往指定坐标（修正版：兼容 AirSim 原生 API）
        point: [x, y, z]，Z轴向上为正
        velocity: 飞行速度 (建议 <= 2)
        tolerance: 到达容忍度（米）
        """
        x, y, z = point[0], point[1], point[2]
        airsim_z = self._to_airsim_z(z)

        print(f"[aw] 正在飞往 ({x:.1f}, {y:.1f}, {z:.1f})，速度: {velocity} m/s")

        # 【修正】只使用 AirSim 原生支持的参数
        # 先让飞机往目标点飞
        self.client.moveToPositionAsync(x, y, airsim_z, velocity)

        # 【核心逻辑保留】手动监控位置，提前接管
        import time
        timeout = 60
        start_time = time.time()

        while True:
            # 获取当前位置
            curr_pose = self.client.simGetVehiclePose()
            curr_x = curr_pose.position.x_val
            curr_y = curr_pose.position.y_val

            # 计算与目标点的直线距离
            dist = ((curr_x - x) ** 2 + (curr_y - y) ** 2) ** 0.5

            # 检查是否进入目标范围
            if dist < tolerance:
                print(f"[aw] ✅ 接近目标 (距离: {dist:.2f}m)，执行悬停")
                # 关键：立即停止当前移动，切换到悬停模式
                self.client.hoverAsync().join()
                break

            # 超时保护
            if time.time() - start_time > timeout:
                print(f"[aw] ⚠️  飞行超时")
                self.client.hoverAsync().join()
                break

            time.sleep(0.1)

    def fly_path(self, points, velocity=3):
        """
        沿路径飞行
        points: 坐标点列表 [[x,y,z], ...]，Z轴向上为正
        """
        print(f"[aw] 规划路径飞行，共 {len(points)} 个点")

        airsim_points = []
        for point in points:
            x, y, z = point[0], point[1], point[2]
            airsim_points.append(airsim.Vector3r(x, y, self._to_airsim_z(z)))

        # 【关键修复 2】优化飞控参数，解决漩涡问题
        # 1. 去掉 ForwardOnly，改用 MaxDegreeOfFreedom
        # 2. 增加 lookahead 距离
        # 3. 允许飞机自由调整朝向
        self.client.moveOnPathAsync(
            airsim_points,
            velocity,
            120,
            airsim.DrivetrainType.MaxDegreeOfFreedom,  # 允许自由移动，不强制机头朝前
            airsim.YawMode(False, 0),
            lookahead=-1,  # 设为 -1 让系统自动计算
            adaptive_lookahead=1
        ).join()

    def set_yaw(self, yaw):
        print(f"[aw] 旋转朝向至 {yaw} 度")
        self.client.rotateToYawAsync(yaw, timeout_sec=5).join()

    def get_yaw(self):
        orientation_quat = self.client.simGetVehiclePose().orientation
        yaw = airsim.to_eularian_angles(orientation_quat)[2]
        return math.degrees(yaw)

    def get_position(self, object_name):
        query_string = objects_dict[object_name] + ".*"
        object_names_ue = []
        while len(object_names_ue) == 0:
            object_names_ue = self.client.simListSceneObjects(query_string)
        pose = self.client.simGetObjectPose(object_names_ue[0])
        # 物体坐标也做同样的 Z 轴转换
        return [pose.position.x_val, pose.position.y_val, -pose.position.z_val]