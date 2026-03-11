from airsim_utils_single import AirSimController
import time

drone = AirSimController()
drone.takeoff()
time.sleep(1)
drone.fly_to_relative(dx=10, dy=0, dz=0)  # 向右飞10米
time.sleep(1)
drone.fly_to_relative(dx=0, dy=10, dz=0)  # 向前飞10米
time.sleep(1)
drone.land()