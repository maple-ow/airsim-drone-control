import airsim
import numpy as np

class AirSimController:
    def __init__(self, vehicle_name="Drone1"):
        self.client = airsim.MultirotorClient()
        #self.vehicle_name = vehicle_name
        self.client.confirmConnection()
        self.client.enableApiControl(True, )
        self.client.armDisarm(True, )

    def get_position(self):
        """获取当前坐标 (X, Y, Z)"""
        pose = self.client.simGetVehiclePose()
        return (pose.position.x_val, pose.position.y_val, pose.position.z_val)

    def fly_to_relative(self, dx=0, dy=0, dz=0, velocity=5):
        """相对当前位置飞行 (dx, dy, dz)"""
        x, y, z = self.get_position()
        self.client.moveToPositionAsync(x + dx, y + dy, z + dz, velocity, ).join()

    def fly_to_absolute(self, x, y, z, velocity=5):
        """绝对坐标飞行"""
        self.client.moveToPositionAsync(x, y, z, velocity, ).join()

    def takeoff(self):
        self.client.takeoffAsync().join()

    def land(self):
        self.client.landAsync().join()
        self.client.armDisarm(False, )
        self.client.enableApiControl(False, )

    # 后续可以添加：拍照、画圆、获取图像等函数