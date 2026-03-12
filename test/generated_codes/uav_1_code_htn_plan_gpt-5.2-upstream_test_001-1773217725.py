from utils.airsim_wrapper import AirSimWrapper
import time

# ================== 配置 ==================
SAFE_VELOCITY = 2  # m/s

# ================== 连接初始化 ==================
print("[系统] 正在连接 AirSim...")
aw = AirSimWrapper()  # 自动处理连接、解锁、坐标系

try:
    # ================== 任务执行序列 ==================

    # 1. [sub_001] 起飞
    print("[任务1] 执行起飞")
    aw.takeoff()
    print("[任务1] 起飞完成")

    # 2. [sub_002] 悬停 5 秒
    print("[任务2] 悬停 5 秒")
    time.sleep(5)
    print("[任务2] 悬停完成")

    # 3. [sub_003] 飞往 (95.89, 12.86, 15)
    print("[任务3] 飞往水平圆起点")
    aw.fly_to([95.89, 12.86, 15], velocity=SAFE_VELOCITY)

    # 4. [sub_004] 飞往 (94.55, 17.86, 15)
    print("[任务4] 飞往水平圆路径点")
    aw.fly_to([94.55, 17.86, 15], velocity=SAFE_VELOCITY)

    # 5. [sub_005] 飞往 (90.89, 21.52, 15)
    print("[任务5] 飞往水平圆路径点")
    aw.fly_to([90.89, 21.52, 15], velocity=SAFE_VELOCITY)

    # 6. [sub_006] 飞往 (85.89, 22.86, 15)
    print("[任务6] 飞往水平圆路径点")
    aw.fly_to([85.89, 22.86, 15], velocity=SAFE_VELOCITY)

    # 7. [sub_007] 飞往 (80.89, 21.52, 15)
    print("[任务7] 飞往水平圆路径点")
    aw.fly_to([80.89, 21.52, 15], velocity=SAFE_VELOCITY)

    # 8. [sub_008] 飞往 (77.23, 17.86, 15)
    print("[任务8] 飞往水平圆路径点")
    aw.fly_to([77.23, 17.86, 15], velocity=SAFE_VELOCITY)

    # 9. [sub_009] 飞往 (75.89, 12.86, 15)
    print("[任务9] 飞往水平圆路径点")
    aw.fly_to([75.89, 12.86, 15], velocity=SAFE_VELOCITY)

    # 10. [sub_010] 飞往 (77.23, 7.86, 15)
    print("[任务10] 飞往水平圆路径点")
    aw.fly_to([77.23, 7.86, 15], velocity=SAFE_VELOCITY)

    # 11. [sub_011] 飞往 (80.89, 4.20, 15)
    print("[任务11] 飞往水平圆路径点")
    aw.fly_to([80.89, 4.20, 15], velocity=SAFE_VELOCITY)

    # 12. [sub_012] 飞往 (85.89, 2.86, 15)
    print("[任务12] 飞往水平圆路径点")
    aw.fly_to([85.89, 2.86, 15], velocity=SAFE_VELOCITY)

    # 13. [sub_013] 飞往 (90.89, 4.20, 15)
    print("[任务13] 飞往水平圆路径点")
    aw.fly_to([90.89, 4.20, 15], velocity=SAFE_VELOCITY)

    # 14. [sub_014] 飞往 (94.55, 7.86, 15)
    print("[任务14] 飞往水平圆路径点")
    aw.fly_to([94.55, 7.86, 15], velocity=SAFE_VELOCITY)

    # 15. [sub_015] 飞回起点 (95.89, 12.86, 15)
    print("[任务15] 水平圆闭合回到起点")
    aw.fly_to([95.89, 12.86, 15], velocity=SAFE_VELOCITY)

    # 16. [sub_016] 悬停 3 秒
    print("[任务16] 悬停 3 秒")
    time.sleep(3)
    print("[任务16] 悬停完成")

    # 17. [sub_017] 竖直圆点 (94.55, 12.86, 20)
    print("[任务17] 飞往竖直圆路径点")
    aw.fly_to([94.55, 12.86, 20], velocity=SAFE_VELOCITY)

    # 18. [sub_018] 竖直圆点 (90.89, 12.86, 23.66)
    print("[任务18] 飞往竖直圆路径点")
    aw.fly_to([90.89, 12.86, 23.66], velocity=SAFE_VELOCITY)

    # 19. [sub_019] 竖直圆点 (85.89, 12.86, 25)
    print("[任务19] 飞往竖直圆路径点")
    aw.fly_to([85.89, 12.86, 25], velocity=SAFE_VELOCITY)

    # 20. [sub_020] 竖直圆点 (80.89, 12.86, 23.66)
    print("[任务20] 飞往竖直圆路径点")
    aw.fly_to([80.89, 12.86, 23.66], velocity=SAFE_VELOCITY)

    # 21. [sub_021] 竖直圆点 (77.23, 12.86, 20)
    print("[任务21] 飞往竖直圆路径点")
    aw.fly_to([77.23, 12.86, 20], velocity=SAFE_VELOCITY)

    # 22. [sub_022] 竖直圆点 (75.89, 12.86, 15)
    print("[任务22] 飞往竖直圆路径点")
    aw.fly_to([75.89, 12.86, 15], velocity=SAFE_VELOCITY)

    # 23. [sub_023] 竖直圆点 (77.23, 12.86, 10)
    print("[任务23] 飞往竖直圆路径点")
    aw.fly_to([77.23, 12.86, 10], velocity=SAFE_VELOCITY)

    # 24. [sub_024] 竖直圆点 (80.89, 12.86, 6.34)
    print("[任务24] 飞往竖直圆路径点")
    aw.fly_to([80.89, 12.86, 6.34], velocity=SAFE_VELOCITY)

    # 25. [sub_025] 竖直圆点 (85.89, 12.86, 5)
    print("[任务25] 飞往竖直圆路径点")
    aw.fly_to([85.89, 12.86, 5], velocity=SAFE_VELOCITY)

    # 26. [sub_026] 竖直圆点 (90.89, 12.86, 6.34)
    print("[任务26] 飞往竖直圆路径点")
    aw.fly_to([90.89, 12.86, 6.34], velocity=SAFE_VELOCITY)

    # 27. [sub_027] 竖直圆点 (94.55, 12.86, 10)
    print("[任务27] 飞往竖直圆路径点")
    aw.fly_to([94.55, 12.86, 10], velocity=SAFE_VELOCITY)

    # 28. [sub_028] 竖直圆闭合回到起点 (95.89, 12.86, 15)
    print("[任务28] 竖直圆闭合回到起点")
    aw.fly_to([95.89, 12.86, 15], velocity=SAFE_VELOCITY)

    # 29. [sub_029] 返回起点并降落
    print("[任务29] 返回起点")
    aw.fly_to([0, 0, 10], velocity=SAFE_VELOCITY)
    aw.land()
    print("[任务29] 已返回起点并降落")

    # 30. [sub_030] 再次降落确认
    print("[任务30] 执行降落确认")
    aw.land()
    print("[任务30] 降落完成")

    # ================== 任务结束 ==================
    print("[系统] 所有任务执行完成")

except Exception as e:
    print(f"[系统] 执行出错: {e}")
    print("[系统] 紧急降落...")
    aw.land()

finally:
    print("[系统] 任务结束")