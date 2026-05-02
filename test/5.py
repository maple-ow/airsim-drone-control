import os
import sys
import time
import math
import shutil
import threading
from datetime import datetime
from pathlib import Path

from utils.airsim_wrapper import AirSimWrapper

MISSION = {
    "uav_id": "uav_2",
    "tasks": [
        {
            "task_id": "T_06",
            "type": "takeoff",
            "params": {"height": 8, "_target_uavs": ["uav_2"]},
            "dependencies": [],
            "assigned_uav": "uav_2",
        },
        {
            "task_id": "T_07",
            "type": "fly_to",
            "params": {"target_pos": [129.86, 69.31, -8.0], "_target_uavs": ["uav_2"]},
            "dependencies": ["T_06"],
            "assigned_uav": "uav_2",
        },
        {
            "task_id": "T_08",
            "type": "custom_skill",
            "params": {
                "instruction": "到达 tower1 上空当前位置后，稳定悬停 0.5 秒，然后拍摄 1 张照片，并使用 save_photo 保存到本地（文件名包含 uav_2 与 tower1 与时间戳信息）。拍照期间保持当前位置与高度不变。",
                "_target_uavs": ["uav_2"],
            },
            "dependencies": ["T_07"],
            "assigned_uav": "uav_2",
        },
        {
            "task_id": "T_09",
            "type": "fly_to",
            "params": {"target_pos": [47.07, 106.08, -8.0], "_target_uavs": ["uav_2"]},
            "dependencies": ["T_08"],
            "assigned_uav": "uav_2",
        },
        {
            "task_id": "T_10",
            "type": "custom_skill",
            "params": {
                "instruction": "到达 solarpanels 正上方当前位置后，执行悬停 2.0 秒（保持位置与高度），然后拍摄 1 张照片，并使用 save_photo 保存到本地（文件名包含 uav_2 与 solarpanels 与时间戳信息）。",
                "_target_uavs": ["uav_2"],
            },
            "dependencies": ["T_09"],
            "assigned_uav": "uav_2",
        },
        {
            "task_id": "T_11",
            "type": "custom_skill",
            "params": {
                "instruction": "执行安全软着陆：在当前位置保持水平位置不变，逐步降低下降率（例如 0.5 m/s 左右）直至触地；触地后停桨/解锁前确认垂直速度接近 0，并完成落地。",
                "_target_uavs": ["uav_2"],
            },
            "dependencies": ["T_10"],
            "assigned_uav": "uav_2",
        },
    ],
}

# 1) 初始化全局事件锁
events = {t["task_id"]: threading.Event() for t in MISSION["tasks"]}
errors_lock = threading.Lock()
errors = []


def _now_ts():
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def save_photo(photo_obj, out_path: Path):
    """
    尽最大可能将 take_photo() 返回值保存到本地。
    支持常见情况：
    - 返回已存在的文件路径(str)
    - 返回 bytes / bytearray
    - 返回具有 image_data_uint8/width/height 属性的对象（类似 AirSim ImageResponse）
    - 返回 numpy.ndarray（若 numpy/PIL 可用）
    """
    _ensure_dir(out_path.parent)

    # Case A: already a filepath
    if isinstance(photo_obj, str):
        src = Path(photo_obj)
        if src.exists() and src.is_file():
            shutil.copyfile(src, out_path)
            return

    # Case B: raw bytes
    if isinstance(photo_obj, (bytes, bytearray)):
        with open(out_path, "wb") as f:
            f.write(photo_obj)
        return

    # Case C: AirSim-like response object
    if hasattr(photo_obj, "image_data_uint8"):
        raw = getattr(photo_obj, "image_data_uint8")
        w = getattr(photo_obj, "width", None)
        h = getattr(photo_obj, "height", None)
        # Try to decode as image if possible
        try:
            from PIL import Image  # type: ignore

            if isinstance(raw, (bytes, bytearray)) and w and h:
                img = Image.frombytes("RGB", (int(w), int(h)), bytes(raw))
                img.save(out_path)
                return
        except Exception:
            # fallback to raw dump
            pass

        if isinstance(raw, (bytes, bytearray)):
            with open(out_path, "wb") as f:
                f.write(raw)
            return

    # Case D: numpy array
    try:
        import numpy as np  # type: ignore

        if isinstance(photo_obj, np.ndarray):
            try:
                from PIL import Image  # type: ignore

                arr = photo_obj
                if arr.dtype != np.uint8:
                    arr = np.clip(arr, 0, 255).astype(np.uint8)
                if arr.ndim == 2:
                    img = Image.fromarray(arr, mode="L")
                elif arr.ndim == 3 and arr.shape[2] in (3, 4):
                    img = Image.fromarray(arr[:, :, :3], mode="RGB")
                else:
                    # unknown layout; dump raw bytes
                    with open(out_path, "wb") as f:
                        f.write(arr.tobytes())
                    return
                img.save(out_path)
                return
            except Exception:
                with open(out_path, "wb") as f:
                    f.write(photo_obj.tobytes())
                return
    except Exception:
        pass

    raise RuntimeError(f"save_photo: Unsupported photo type: {type(photo_obj)}")


def _dist(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _hover_and_photo(aw: AirSimWrapper, uav_name: str, label: str, hover_s: float):
    # 保持当前位置与高度不变：记录当前位置，仅 sleep + 拍照；若有微小漂移，拍照后轻微纠偏回原点
    pos0 = aw.get_drone_position()
    time.sleep(float(hover_s))

    photo = aw.take_photo(camera_name="0")
    out_dir = Path(os.getcwd()) / "photos"
    filename = f"{uav_name}_{label}_{_now_ts()}.png"
    out_path = out_dir / filename
    save_photo(photo, out_path)

    pos1 = aw.get_drone_position()
    if _dist(pos0, pos1) > 0.5:
        aw.fly_to(target_pos=pos0, velocity=1)


def _soft_landing(aw: AirSimWrapper, descent_rate_mps: float = 0.5, step_time_s: float = 0.5, ground_z: float = 0.0):
    """
    安全软着陆（近似实现）：
    - 保持水平位置不变
    - 分步改变 z 向 ground_z 靠近，模拟 ~descent_rate_mps 的下降率
    - 最后调用 aw.land() 完成落地
    注：不同坐标系下，ground_z=0 仍通常代表地面（NED 或 ENU），该实现自动按当前 z 与 ground_z 的差值方向移动。
    """
    pos = aw.get_drone_position()
    x, y, z = pos[0], pos[1], pos[2]
    eps = 0.25  # close enough to consider touchdown

    while abs(z - ground_z) > eps:
        pos = aw.get_drone_position()
        x, y, z = pos[0], pos[1], pos[2]
        diff = ground_z - z
        step = min(abs(descent_rate_mps * step_time_s), abs(diff))
        z_next = z + (step if diff > 0 else -step)
        aw.fly_to(target_pos=[x, y, z_next], velocity=max(0.2, float(descent_rate_mps)))
        time.sleep(float(step_time_s))

        # 若已非常接近 ground_z，退出循环交给 land()
        if abs(z_next - ground_z) <= eps:
            break

    # 触地前后做一次短暂稳定等待（无法直接读取垂直速度，这里用时间近似）
    time.sleep(0.5)
    aw.land()
    time.sleep(0.5)


def run_uav_2():
    uav_name = "uav_2"
    print(f"[{uav_name}] 初始化...")
    aw = AirSimWrapper(vehicle_name=uav_name)

    for task in MISSION["tasks"]:
        task_id = task["task_id"]
        task_type = task["type"]
        params = task.get("params", {})
        deps = task.get("dependencies", [])

        try:
            # 等待依赖
            for dep in deps:
                events[dep].wait()

            print(f"[{uav_name}] 执行 {task_id}: {task_type}")

            if task_type == "takeoff":
                height = float(params.get("height", 10))
                aw.takeoff(height=height)

            elif task_type == "fly_to":
                if "target_name" in params and params["target_name"] is not None:
                    # 按规则：飞向命名目标必须做 10m 安全截断
                    target_name = str(params["target_name"])
                    curr_pos = aw.get_drone_position()
                    real_pos = aw.get_position(target_name)

                    dx = real_pos[0] - curr_pos[0]
                    dy = real_pos[1] - curr_pos[1]
                    dz = real_pos[2] - curr_pos[2]
                    distance = math.sqrt(dx * dx + dy * dy + dz * dz)

                    safe_distance = 10.0
                    if distance > safe_distance and distance > 1e-6:
                        ratio = (distance - safe_distance) / distance
                        safe_pos = [
                            curr_pos[0] + dx * ratio,
                            curr_pos[1] + dy * ratio,
                            curr_pos[2] + dz * ratio,
                        ]
                    else:
                        safe_pos = curr_pos

                    aw.fly_to(target_pos=safe_pos, velocity=2)
                else:
                    target_pos = params.get("target_pos", None)
                    if not (isinstance(target_pos, list) and len(target_pos) == 3):
                        raise ValueError(f"{task_id}: fly_to missing valid target_pos")
                    aw.fly_to(target_pos=target_pos, velocity=2)

            elif task_type == "generate_trajectory":
                points = params.get("points", [])
                if not isinstance(points, list) or len(points) == 0:
                    raise ValueError(f"{task_id}: generate_trajectory missing points")
                aw.fly_path(points=points, velocity=3, is_circle=False)

            elif task_type == "custom_skill":
                instruction = str(params.get("instruction", ""))

                if "tower1" in instruction and "悬停 0.5" in instruction and "拍摄 1 张照片" in instruction:
                    _hover_and_photo(aw=aw, uav_name=uav_name, label="tower1", hover_s=0.5)

                elif "solarpanels" in instruction and "悬停 2.0" in instruction and "拍摄 1 张照片" in instruction:
                    _hover_and_photo(aw=aw, uav_name=uav_name, label="solarpanels", hover_s=2.0)

                elif "软着陆" in instruction or "安全软着陆" in instruction:
                    _soft_landing(aw=aw, descent_rate_mps=0.5, step_time_s=0.5, ground_z=0.0)

                else:
                    # 通用兜底：尽量不做危险动作，执行短暂悬停
                    pos = aw.get_drone_position()
                    time.sleep(1.0)
                    # 若有漂移则回到原位
                    pos1 = aw.get_drone_position()
                    if _dist(pos, pos1) > 0.5:
                        aw.fly_to(target_pos=pos, velocity=1)

            else:
                raise ValueError(f"Unsupported task type: {task_type}")

        except Exception as e:
            with errors_lock:
                errors.append((uav_name, task_id, repr(e)))
            print(f"[{uav_name}] ❌ 任务失败 {task_id}: {e}")
        finally:
            # 无论成功失败都释放事件，避免死锁
            events[task_id].set()

    print(f"[{uav_name}] 任务队列执行完毕。")


if __name__ == "__main__":
    print("🚀 启动集群中枢控制器...")

    t = threading.Thread(target=run_uav_2, name="thread_uav_2", daemon=False)
    t.start()
    t.join()

    if errors:
        print("❌ 集群任务存在错误：")
        for uav_name, task_id, err in errors:
            print(f" - [{uav_name}] {task_id}: {err}")
        sys.exit(1)

    print("✅ 所有集群任务执行完毕。")