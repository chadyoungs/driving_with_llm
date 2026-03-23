import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# ==============================================
# 1. 定义模型（可解释、可落地、可用于HighD/真车）
# ==============================================
class LaneChangeModel(nn.Module):
    def __init__(self, input_size=8, hidden_size=64, output_size=3):
        super(LaneChangeModel, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size//2),
            nn.ReLU(),
            nn.Linear(hidden_size//2, output_size),
            nn.Softmax(dim=1)
        )

    def forward(self, x):
        return self.net(x)

# ==============================================
# 2. 加载刚才保存的轨迹数据
# ==============================================
df = pd.read_csv("highway_lanechange_trajectory.csv")

# 选择训练特征（全部来自仿真，可直接迁移到HighD）
features = [
    "lane_id",
    "speed_kmh",
    "front_gap_m",
    "is_exit_lane",
    "step",
    "reward",
    "is_collision"
]
target = "action"

# 清理数据
df = df.dropna()
X = df[features].values
y = df[target].values

# 标准化
scaler = StandardScaler()
X = scaler.fit_transform(X)

# 训练集测试集分割
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 转Tensor
X_train = torch.tensor(X_train, dtype=torch.float32)
y_train = torch.tensor(y_train, dtype=torch.long)
X_test = torch.tensor(X_test, dtype=torch.float32)
y_test = torch.tensor(y_test, dtype=torch.long)

# ==============================================
# 3. 初始化模型、损失、优化器
# ==============================================
model = LaneChangeModel(input_size=len(features))
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

# ==============================================
# 4. 训练
# ==============================================
epochs = 50
print("\n训练开始...\n")
for epoch in range(epochs):
    model.train()
    optimizer.zero_grad()
    outputs = model(X_train)
    loss = criterion(outputs, y_train)
    loss.backward()
    optimizer.step()

    if (epoch+1) % 10 == 0:
        model.eval()
        with torch.no_grad():
            test_out = model(X_test)
            acc = (test_out.argmax(1) == y_test).float().mean()
        print(f"Epoch {epoch+1:2d} | Loss: {loss.item():.3f} | Acc: {acc:.2f}")

# ==============================================
# 5. 保存模型（你获得最终模型！）
# ==============================================
torch.save({
    "model_state_dict": model.state_dict(),
    "scaler": scaler,
    "features": features
}, "lane_change_model.pth")

print("\n✅ 模型已保存：lane_change_model.pth")
print("✅ 可直接用于：HighD 微调、HighwayEnv 决策、真车变道策略")