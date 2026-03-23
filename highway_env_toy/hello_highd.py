import numpy as np
import pandas as pd

# ======================================================
# 【工业级】HighD 自动驾驶轨迹 → 结构化标签 全自动打标工具
# 功能：输入 HighD 轨迹CSV + 车道信息 → 输出全量标注数据
# ======================================================

class HighDAutoLabeler:
    def __init__(self):
        # 定义输出的所有结构化标签（Meta）
        self.label_columns = [
            "frame", "vehicle_id", "x", "y",
            "speed", "accel", "jerk", "heading",
            "lane_id", "lane_width", "lane_count",
            "front_vehicle", "front_gap", "front_v_diff",
            "rear_vehicle", "rear_gap",
            "left_vehicle", "left_gap",
            "right_vehicle", "right_gap",
            "dhw", "ttc", "thw",
            "is_congest", "is_following", "is_lane_change",
            "is_cutin", "is_hard_brake",
            "scene_type", "risk_level"
        ]

    # ------------------------------
    # 1. 基础运动学：速度、加速度、Jerk
    # ------------------------------
    def compute_kinematics(self, df):
        df = df.sort_values(["vehicle_id", "frame"])
        dt = 1/25  # HighD 帧率 25Hz

        # 速度
        df["speed"] = np.sqrt(df["xVelocity"]**2 + df["yVelocity"]**2) * 3.6  # 转 km/h
        # 加速度
        df["accel"] = df["speed"].diff() / dt
        # 加加速度 Jerk（舒适性）
        df["jerk"] = df["accel"].diff() / dt
        # 航向
        df["heading"] = np.arctan2(df["yVelocity"], df["xVelocity"])
        return df

    # ------------------------------
    # 2. 匹配前后左右车辆（核心）
    # ------------------------------
    def match_surrounding_vehicles(self, group):
        group = group.sort_values("x")
        group = group.reset_index(drop=True)

        for i, row in group.iterrows():
            cx, clane = row.x, row.lane_id
            candidates = group[group.index != i]

            # 前车
            front = candidates[(candidates.x > cx) & (candidates.lane_id == clane)]
            if not front.empty:
                f = front.iloc[0]
                group.at[i, "front_vehicle"] = f.vehicle_id
                group.at[i, "front_gap"] = f.x - cx
                group.at[i, "front_v_diff"] = row.speed - f.speed

            # 后车
            rear = candidates[(candidates.x < cx) & (candidates.lane_id == clane)]
            if not rear.empty:
                r = rear.iloc[-1]
                group.at[i, "rear_vehicle"] = r.vehicle_id
                group.at[i, "rear_gap"] = cx - r.x

            # 左侧车（假设左车道号更小）
            left = candidates[(candidates.lane_id == clane - 1)]
            if not left.empty:
                l = left.iloc[(left.x - cx).abs().argmin()]
                group.at[i, "left_vehicle"] = l.vehicle_id
                group.at[i, "left_gap"] = np.hypot(cx - l.x, 3.5)  # 车道宽 3.5m

            # 右侧车
            right = candidates[(candidates.lane_id == clane + 1)]
            if not right.empty:
                r = right.iloc[(right.x - cx).abs().argmin()]
                group.at[i, "right_vehicle"] = r.vehicle_id
                group.at[i, "right_gap"] = np.hypot(cx - r.x, 3.5)
        return group

    # ------------------------------
    # 3. 安全指标：TTC、DHW、THW
    # ------------------------------
    def compute_safety_metrics(self, df):
        df["dhw"] = df["front_gap"]
        df["ttc"] = df["front_gap"] / np.clip(df["front_v_diff"], 0.1, None)
        df["thw"] = df["front_gap"] / np.clip(df["speed"] / 3.6, 0.1, None)
        df["ttc"] = df["ttc"].replace([np.inf, -np.inf], 99)
        return df

    # ------------------------------
    # 4. 事件识别
    # ------------------------------
    def detect_events(self, df):
        df["is_hard_brake"] = (df["accel"] < -4.0).astype(int)
        df["is_congest"] = ((df["speed"] < 40) & (df["front_gap"] < 15)).astype(int)
        df["is_following"] = ((df["speed"] > 40) & (df["front_gap"] < 50)).astype(int)
        df["is_lane_change"] = df.groupby("vehicle_id")["lane_id"].diff().fillna(0).abs().astype(int)
        df["is_cutin"] = ((df["left_gap"] < 10) | (df["right_gap"] < 10)).astype(int)
        return df

    # ------------------------------
    # 5. 场景类型 & 危险等级
    # ------------------------------
    def label_scene_and_risk(self, df):
        # 场景类型
        def get_scene(row):
            if row["is_congest"]: return "congestion"
            if row["is_cutin"]: return "cutin"
            if row["is_lane_change"]: return "lane_change"
            if row["is_following"]: return "following"
            if row["is_hard_brake"]: return "hard_brake"
            return "cruise"

        df["scene_type"] = df.apply(get_scene, axis=1)

        # 风险等级
        def risk_level(row):
            if row["ttc"] < 2.0 or row["is_hard_brake"]:
                return "high"
            elif row["ttc"] < 3.5 or row["is_cutin"]:
                return "medium"
            else:
                return "low"

        df["risk_level"] = df.apply(risk_level, axis=1)
        return df

    # ------------------------------
    # 总入口：一键全自动打标
    # ------------------------------
    def run(self, highd_trajectory_csv, save_path="highd_labeled.csv"):
        print("🔹 读取 HighD 轨迹...")
        df = pd.read_csv(highd_trajectory_csv)

        print("🔹 计算运动学...")
        df = self.compute_kinematics(df)

        print("🔹 匹配周围车辆...")
        df = df.groupby("frame").apply(self.match_surrounding_vehicles).reset_index(drop=True)

        print("🔹 计算安全指标...")
        df = self.compute_safety_metrics(df)

        print("🔹 识别事件...")
        df = self.detect_events(df)

        print("🔹 场景标注 & 风险评估...")
        df = self.label_scene_and_risk(df)

        # 保存最终结构化标签
        df[self.label_columns].to_csv(save_path, index=False)
        print(f"✅ 全自动打标完成！输出：{save_path}")
        return df


# ======================================================
# 【使用方法】
# 1. 下载 HighD 数据集
# 2. 放入对应路径
# 3. 运行
# ======================================================
if __name__ == "__main__":
    labeler = HighDAutoLabeler()
    # 替换成你的 HighD 轨迹文件
    df_labeled = labeler.run("01_highway.csv")
    print(df_labeled[["speed", "front_gap", "ttc", "scene_type", "risk_level"]].head(10))