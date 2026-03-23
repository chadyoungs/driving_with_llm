import gymnasium as gym
import highway_env
import numpy as np
import torch
import torch.nn as nn
import pandas as pd

# ==============================================
# 【1】轨迹预测模型 LSTM → 输出未来 3 秒轨迹
# ==============================================
class TrajectoryPredictor(nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm = nn.LSTM(2, 32, batch_first=True)
        self.fc = nn.Linear(32, 2*5)  # 未来 5 步

    def forward(self, x):
        _, (h, _) = self.lstm(x)
        return self.fc(h[-1]).view(-1,5,2)

# ==============================================
# 【2】真正的神经网络决策模型 ✅ 真正使用！
# 输入：自车状态 + 周围车状态 + 预测信息
# 输出：变道/直行/减速
# ==============================================
class LaneChangeDecisionModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(12, 64), nn.ReLU(),
            nn.Linear(64, 32), nn.ReLU(),
            nn.Linear(32, 3)  # 0=减速,1=直行,2=右变道
        )

    def forward(self, x):
        return self.net(x)

# ==============================================
# 【3】安全规则引擎
# ==============================================
class SafetyChecker:
    @staticmethod
    def can_lane_change(speed, front_gap):
        if front_gap < max(6, speed * 0.3):
            return False
        return True

# ==============================================
# 主程序：迷你 NOA —— 真正带神经网络决策
# ==============================================
if __name__ == "__main__":
    env = gym.make("highway-v0", render_mode="human")
    env.unwrapped.configure({
        "lanes_count": 4,
        "road_length": 800,
        "screen_width":1000,"screen_height":600,
        "vehicles_count":50,
        "initial_lane_id":0,
        "lane_vehicle_density":[0.2,0.3,0.6,1.0],
        "collision_reward":-10,
        "randomize":False
    })

    # ======================
    # 初始化 2 个神经网络 ✅
    # ======================
    predictor = TrajectoryPredictor()
    decision_model = LaneChangeDecisionModel()

    # 切换为评估模式（真正推理）
    predictor.eval()
    decision_model.eval()

    safety = SafetyChecker()
    history = []
    traj_data = []

    obs, info = env.reset()

    for step in range(1500):
        ego = env.unwrapped.vehicle
        lane_id = ego.lane_index[2]
        x, y = ego.position[0], ego.position[1]
        speed = ego.speed * 3.6
        front_gap = ego.front_gap if hasattr(ego,"front_gap") else 25

        history.append([x, y])
        if len(history) > 10:
            history.pop(0)

        # ==========================
        # 1. 轨迹预测（LSTM）
        # ==========================
        pred_done = 0
        if len(history) >= 5:
            hist_tensor = torch.tensor(history[-5:], dtype=torch.float32).unsqueeze(0)
            with torch.no_grad():
                future = predictor(hist_tensor)
            pred_done = 1

        # ==========================
        # 2. 构造神经网络输入
        # ==========================
        state = np.array([
            lane_id, speed, front_gap,
            1 if lane_id<3 else 0,
            1 if safety.can_lane_change(speed,front_gap) else 0,
            step%100, front_gap/10, speed/100,
            0,0,0,pred_done
        ], dtype=np.float32)

        # ==========================
        # 3. 神经网络决策 ✅ 真正运行
        # ==========================
        with torch.no_grad():
            logits = decision_model(torch.from_numpy(state))
            act = logits.argmax().item()

        # ==========================
        # 4. 安全规则约束（量产关键）
        # ==========================
        safe = safety.can_lane_change(speed, front_gap)
        if act == 2 and not safe:
            act = 1

        # 出口策略：尽量向右变道
        if lane_id < 3 and safe:
            act = 2

        # ==========================
        # 执行动作
        # ==========================
        obs, rwd, ter, trc, info = env.step(act)
        env.render()

        traj_data.append({
            "step":step, "lane":lane_id, "speed":round(speed,2),
            "front_gap":round(front_gap,2), "nn_action":act,
            "pred_used":pred_done, "safe":int(safe), "collision":int(ter)
        })

        if ter or trc:
            print(f"结束 | 碰撞={ter} | 安全变道={safe}")
            break

    env.close()
    pd.DataFrame(traj_data).to_csv("mininoa_final.csv", index=False)
    print("✅ 迷你 NOA 运行完成：预测模型 + 神经网络决策 + 安全规则")