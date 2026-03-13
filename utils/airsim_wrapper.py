import airsim
import time
import math
from typing import List, Optional, Tuple


class AirSimWrapper:
    # 原项目的场景物体名称映射字典
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

    def __init__(self, vehicle_name: str = ""):
        """
        初始化 AirSim 连接
        :param vehicle_name: 无人机名称，如 "uav_1"、"uav_2"，默认为空（控制第一架无人机）
        """
        self.vehicle_name = vehicle_name
        self.client = airsim.MultirotorClient()
        self.client.confirmConnection()

        # 解锁飞控
        self.client.enableApiControl(True, vehicle_name=self.vehicle_name)
        self.client.armDisarm(True, vehicle_name=self.vehicle_name)

        # 打印连接日志
        self._log(f"已连接 AirSim，飞控已解锁")

    def _log(self, message: str):
        """内部日志函数，自动带上无人机ID"""
        if self.vehicle_name:
            print(f"[{self.vehicle_name}] {message}")
        else:
            print(f"[无人机] {message}")

    # ==================== 基础飞行动作 ====================
    def takeoff(self, height: float = 10, timeout: float = 15):
        """
        起飞到指定高度
        :param height: 起飞高度（米），Z轴向上
        :param timeout: 超时时间（秒）
        """
        self._log(f"正在起飞到 {height} 米...")
        # 先执行原生起飞
        self.client.takeoffAsync(timeout_sec=timeout, vehicle_name=self.vehicle_name).join()
        # 再飞到指定高度（AirSim原生Z轴向下，取反）
        self.client.moveToZAsync(-height, velocity=2, vehicle_name=self.vehicle_name).join()
        self._log("起飞完成")

    def land(self, timeout: float = 20):
        """
        安全软着陆（多级减速：高空→5m→1.5m→0.3m→悬停→降落）
        :param timeout: 超时时间（秒）
        """
        self._log("正在执行安全软着陆...")
        try:
            # 获取当前高度
            curr_pos = self.get_drone_position()
            curr_z = curr_pos[2]

            # 多级减速逻辑
            if curr_z > 5:
                self._log(f"当前高度 {curr_z:.1f}m，先减速到 5m")
                self.fly_to([curr_pos[0], curr_pos[1], 5], velocity=2)

            if curr_z > 1.5:
                self._log("减速到 1.5m")
                self.fly_to([curr_pos[0], curr_pos[1], 1.5], velocity=1)

            if curr_z > 0.3:
                self._log("减速到 0.3m")
                self.fly_to([curr_pos[0], curr_pos[1], 0.3], velocity=0.5)

            # 悬停稳定
            self._log("悬停稳定 1 秒")
            time.sleep(1)

            # 执行最终降落
            self.client.landAsync(timeout_sec=timeout, vehicle_name=self.vehicle_name).join()

        except Exception as e:
            self._log(f"软着陆逻辑异常，执行原生降落: {e}")
            self.client.landAsync(timeout_sec=timeout, vehicle_name=self.vehicle_name).join()

        # 上锁并释放API控制
        self.client.armDisarm(False, vehicle_name=self.vehicle_name)
        self.client.enableApiControl(False, vehicle_name=self.vehicle_name)
        self._log("着陆完成，飞控已上锁")

    # ==================== 核心飞行：自适应单点飞行 ====================
    def fly_to(self,
               target_pos: List[float],
               velocity: float = 2,
               tolerance: Optional[float] = None,
               timeout: float = 120):
        """
        自适应飞往目标位置（自动判断长/短距离）
        :param target_pos: 目标坐标 [x, y, z]，Z轴向上
        :param velocity: 飞行速度（m/s），默认2m/s
        :param tolerance: 到达容忍度（米），默认根据距离自动调整
        :param timeout: 超时时间（秒）
        """
        x, y, z = target_pos
        # 转换为 AirSim 原生坐标（Z轴向下）
        airsim_z = -z

        # 获取当前位置
        curr_pos = self.get_drone_position()
        dx = x - curr_pos[0]
        dy = y - curr_pos[1]
        dz = z - curr_pos[2]
        distance = math.sqrt(dx ** 2 + dy ** 2 + dz ** 2)

        # 自动调整参数
        if tolerance is None:
            tolerance = 1.5 if distance > 8 else 0.5

        # 极短距离：直接跳过
        if distance < 0.5:
            self._log(f"距离目标仅 {distance:.2f}m，无需移动")
            return

        # 调整速度：短距离自动限速
        actual_velocity = velocity
        if distance <= 8:
            actual_velocity = min(velocity, 1.2)

        self._log(f"正在飞往 [{x:.1f}, {y:.1f}, {z:.1f}]，距离 {distance:.1f}m，速度 {actual_velocity:.1f}m/s")

        # 执行飞行
        self.client.moveToPositionAsync(
            x, y, airsim_z,
            velocity=actual_velocity,
            timeout_sec=timeout,
            vehicle_name=self.vehicle_name
        ).join()

        self._log("到达目标位置")

    # ==================== 核心飞行：路径飞行/画圆 ====================
    def fly_path(self,
                 points: List[List[float]],
                 velocity: float = 3,
                 is_circle: bool = False):
        """
        沿指定路径飞行
        :param points: 路径点列表 [[x1,y1,z1], [x2,y2,z2], ...]，Z轴向上
        :param velocity: 飞行速度（m/s）
        :param is_circle: 是否是画圆/多边形/多航点任务，默认False（设为True会优化参数）
        """
        if not points:
            self._log("路径点为空，跳过")
            return

        # 转换为 AirSim 原生路径点（Z轴向下）
        airsim_waypoints = []
        for point in points:
            x, y, z = point
            airsim_waypoints.append(airsim.Vector3r(x, y, -z))

        self._log(f"开始执行路径飞行，共 {len(points)} 个航点，速度 {velocity}m/s")

        if is_circle:
            # 画圆/多边形优化：使用 lookahead 更平滑
            self._log("画圆模式：启用平滑参数优化")
            self.client.moveOnPathAsync(
                airsim_waypoints,
                velocity=velocity,
                timeout_sec=120,
                drivetrain=airsim.DrivetrainType.ForwardOnly,
                yaw_mode=airsim.YawMode(False, 0),
                lookahead=-1,
                adaptive_lookahead=1,
                vehicle_name=self.vehicle_name
            ).join()
        else:
            # 普通路径飞行
            self.client.moveOnPathAsync(
                airsim_waypoints,
                velocity=velocity,
                timeout_sec=120,
                vehicle_name=self.vehicle_name
            ).join()

        self._log("路径飞行完成")

    # ==================== 朝向控制 ====================
    def set_yaw(self, yaw: float, timeout: float = 5):
        """
        旋转无人机朝向到指定角度
        :param yaw: 目标朝向角度（度）
        :param timeout: 超时时间（秒）
        """
        self._log(f"旋转到 {yaw} 度")
        self.client.rotateToYawAsync(yaw, timeout_sec=timeout, vehicle_name=self.vehicle_name).join()

    def get_yaw(self) -> float:
        """
        获取当前朝向角度
        :return: 当前朝向（度）
        """
        kinematics = self.client.getMultirotorState(vehicle_name=self.vehicle_name).kinematics_estimated
        _, _, yaw = airsim.to_eularian_angles(kinematics.orientation)
        return math.degrees(yaw)

    # ==================== 位置获取 ====================
    def get_drone_position(self) -> List[float]:
        """
        获取无人机当前位置
        :return: [x, y, z]，Z轴向上为正
        """
        pose = self.client.simGetVehiclePose(vehicle_name=self.vehicle_name)
        # AirSim 原生 Z 轴向下，转换为 Z 轴向上
        return [pose.position.x_val, pose.position.y_val, -pose.position.z_val]

    def get_position(self, object_name: str) -> List[float]:
        """
        使用原项目逻辑获取场景中物体的坐标
        :param object_name: 物体名，如 "turbine1"、"tower1"
        :return: [x, y, z]，Z轴向上为正
        """
        # 1. 优先检查是否在映射字典里
        if object_name in self.objects_dict:
            try:
                # 使用原项目逻辑：通配符搜索 UE 实际物体名
                query_string = self.objects_dict[object_name] + ".*"
                object_names_ue = []

                # 循环直到找到（避免偶尔的搜索失败）
                while len(object_names_ue) == 0:
                    object_names_ue = self.client.simListSceneObjects(query_string)

                # 获取位置并统一 Z 轴向上
                pose = self.client.simGetObjectPose(object_names_ue[0])
                return [pose.position.x_val, pose.position.y_val, -pose.position.z_val]
            except:
                # 如果搜索失败，fallback 到直接获取
                pass

        # 2. 兼容逻辑：如果不在字典里或搜索失败，尝试直接用名字获取
        try:
            pose = self.client.simGetObjectPose(object_name)
            return [pose.position.x_val, pose.position.y_val, -pose.position.z_val]
        except Exception as e:
            raise ValueError(f"无法获取物体 {object_name} 的位置: {e}")

    # ==================== 拍照功能 ====================
    def take_photo(self, camera_name: str = "0", image_type: airsim.ImageType = airsim.ImageType.Scene):
        """
        拍照并返回图像数据
        :param camera_name: 相机名称，默认 "0"（前视相机）
        :param image_type: 图像类型，默认 Scene（可见光）
        :return: 图像数据
        """
        self._log(f"执行拍照（相机 {camera_name}）")
        responses = self.client.simGetImages(
            [airsim.ImageRequest(camera_name, image_type, pixels_as_float=False, compress=False)],
            vehicle_name=self.vehicle_name
        )
        if responses:
            return responses[0]
        return None