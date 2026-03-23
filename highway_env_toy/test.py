import torch
import numpy as np
import pandas as pd
from train import LaneChangeModel

# 加载模型
checkpoint = torch.load("lane_change_model.pth")
model = LaneChangeModel()
model.load_state_dict(checkpoint["model_state_dict"])
model.eval()

scaler = checkpoint["scaler"]
features = checkpoint["features"]

# 构造一个“出口拥堵、需要变道”的状态
sample_state = np.array([[
    0,      # lane_id 左车道
    80,     # speed
    12,     # front_gap
    0,      # not exit lane
    50,     # step
    0.5,    # reward
    0       # no collision
]])

sample_state = scaler.transform(sample_state)
sample_tensor = torch.tensor(sample_state, dtype=torch.float32)

with torch.no_grad():
    pred = model(sample_tensor).argmax(1).item()

action_map = {0:"减速", 1:"直行", 2:"向右变道"}
print(f"\n模型预测动作：{action_map[pred]}")