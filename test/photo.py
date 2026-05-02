import sys
import os
import time

# 确保能找到 utils 模块
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from utils.airsim_wrapper import AirSimWrapper


def main():
    print("=" * 50)
    print("📸 AirSim 拍照功能测试启动")
    print("=" * 50)

    try:
        # 初始化无人机 (默认使用 uav_1，如果你的环境里只有一架，可以传 vehicle_name="")
        aw = AirSimWrapper(vehicle_name="uav_1")

        # 1. 起飞到 5 米高度，以便获得更好的视野
        print("\n[步骤 1] 准备起飞...")
        aw.takeoff(height=5)
        time.sleep(2)  # 悬停稳定一下

        # 2. 测试自动命名拍照
        print("\n[步骤 2] 测试自动命名拍照...")
        saved_path_1 = aw.save_photo()
        if saved_path_1:
            print(f"✅ 第一张照片已保存到: {saved_path_1}")

        # 旋转一下角度，拍第二张
        print("\n[步骤 3] 旋转 45 度，测试自定义命名拍照...")
        aw.set_yaw(45)
        time.sleep(1)

        # 3. 测试自定义目录和自定义命名拍照
        saved_path_2 = aw.save_photo(save_dir="test_custom_dir", filename="my_test_photo.png")
        if saved_path_2:
            print(f"✅ 第二张照片已保存到: {saved_path_2}")

        # 4. 降落
        print("\n[步骤 4] 测试完毕，准备降落...")
        aw.land()

        print("\n🎉 测试圆满完成！请去对应文件夹检查生成的图片。")

    except Exception as e:
        print(f"\n❌ 发生错误: {e}")


if __name__ == "__main__":
    main()