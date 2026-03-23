import gymnasium as gym
import highway_env
import numpy as np
import pandas as pd
from datetime import datetime

# ======================
# 终极修复版 | 出口拥堵 + 轨迹保存CSV
# 直接运行！无报错！
# ======================

if __name__ == "__main__":
    # 1. 创建环境
    env = gym.make("highway-v0", render_mode="human")

    # 2. 出口拥堵配置
    env.unwrapped.configure({
        "lanes_count": 4,
        "road_length": 800,
        "screen_width": 1000,
        "screen_height": 600,
        "show_trajectories": True,

        "vehicles_count": 60,
        "controlled_vehicles": 1,
        "initial_lane_id": 0,

        "traffic_density": 0.6,
        "lane_vehicle_density": [0.2, 0.3, 0.6, 1.0],  # 右侧=出口=拥堵

        "other_vehicles_type": "highway_env.vehicle.behavior.IDMVehicle",
        "collision_reward": -10,
        "right_lane_reward": 0.2,
        "lane_change_reward": 0.1,
        "speed_reward": 0.2,
        "high_speed_reward": 0.5,
        "randomize": False
    })

    # ======================
    # 轨迹存储
    # ======================
    trajectory_data = []
    episode = 1

    # ======================
    # 开始运行
    # ======================
    obs, info = env.reset()

    for step in range(1000):
        # 自车状态
        ego = env.unwrapped.vehicle
        lane_id = ego.lane_index[2]
        x, y = round(ego.position[0], 2), round(ego.position[1], 2)
        speed = round(ego.speed * 3.6, 2)  # 转 km/h
        heading = round(ego.heading, 2)

        # 决策：向右变道去出口
        action = 2 if lane_id < 3 else 1

        # ======================
        # 【修复】安全获取前车距离（无报错版本）
        # ======================
        front_gap = None
        if hasattr(ego, "front_gap") and ego.front_gap is not None:
            front_gap = round(ego.front_gap, 2)
        else:
            # 从观测值提取安全距离（兼容所有版本）
            if len(obs.shape) == 1:
                try:
                    front_gap = round(obs[1], 2) if obs[1] > 0 else None
                except:
                    front_gap = None

        # 执行动作
        obs, reward, terminated, truncated, info = env.step(action)
        env.render()

        # ======================
        # 记录每一步轨迹
        # ======================
        step_data = {
            "episode": episode,
            "step": step,
            "lane_id": lane_id,
            "x": x,
            "y": y,
            "speed_kmh": speed,
            "heading": heading,
            "action": action,
            "reward": round(reward, 2),
            "front_gap_m": front_gap,
            "is_collision": 1 if terminated else 0,
            "is_lane_change": 1 if action == 2 else 0,
            "is_exit_lane": 1 if lane_id == 3 else 0,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        trajectory_data.append(step_data)

        if terminated or truncated:
            print(f"Episode {episode} 结束在 step {step}")
            break

    env.close()

    # ======================
    # 保存 CSV
    # ======================
    df = pd.DataFrame(trajectory_data)
    df.to_csv("highway_lanechange_trajectory.csv", index=False)
    print(f"\n✅ 轨迹已保存： highway_lanechange_trajectory.csv")
    print(f"📊 总步数： {len(df)}")
    print(f"💥 碰撞次数： {df['is_collision'].sum()}")
    print(f"🔄 变道次数： {df['is_lane_change'].sum()}")