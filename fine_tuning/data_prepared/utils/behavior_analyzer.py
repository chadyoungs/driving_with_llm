import numpy as np
from scipy.signal import savgol_filter


class TrendAnalyzer:
    def __init__(self, series_data, fps=25):
        """
        Input:
            series_data
            fps: default 25Hz
        """
        self.v = np.array(series_data)
        self.fps = fps
        self.window = fps
        self.smoothed = None
        self.trend = None
        self.slope = None
        self.oscillation = None
        self.desc = ""

    def smooth(self, window_length=11, polyorder=2):
        self.smoothed = savgol_filter(
            self.v, window_length=window_length, polyorder=polyorder
        )

    def compute_trend_slope(self):
        x = np.arange(len(self.smoothed))
        k, b = np.polyfit(x, self.smoothed, 1)
        self.slope = k * self.fps

    def compute_oscillation(self):
        raw_var = np.var(self.v)
        smooth_var = np.var(self.smoothed)
        self.oscillation = (raw_var - smooth_var) / (smooth_var + 1e-6)

    def classify(self):
        """
        categorizing into 5 types based on slope and oscillation:
        steady, slow_up, fast_up, slow_down, fast_down, oscillating
        """
        osc = self.oscillation
        slope = self.slope

        # 1. 先判断是否震荡
        if osc > 0.15:
            self.trend = "oscillating"
            self.desc = "oscillating time series"
            return

        # 2. 判断升降幅度
        if abs(slope) < 0.2:
            self.trend = "steady"
            self.desc = "steady time series"
        elif slope > 0:
            if slope >= 0.8:
                self.trend = "fast_up"
                self.desc = "fast upward trend"
            else:
                self.trend = "slow_up"
                self.desc = "slow upward trend"
        else:
            if slope <= -0.8:
                self.trend = "fast_down"
                self.desc = "fast downward trend"
            else:
                self.trend = "slow_down"
                self.desc = "slow downward trend"

    def run(self):
        self.smooth()
        self.compute_trend_slope()
        self.compute_oscillation()
        self.classify()
        return {
            "trend_type": self.trend,
            "slope": round(self.slope, 3),
            "oscillation": round(self.oscillation, 3),
            "description": self.desc,
        }


class HierarchicalLaneAnalyzer:
    def __init__(self, data):
        """
        输入 data 字典必须包含：
        - maneuver: 0=keep, 1=left_change, 2=right_change
        - lane_pre, lane_post: 变道前后车道
        - v_ego_pre, v_ego_post: 变道前后自车速度
        - v_flow: 车流平均速度
        - neighbors: 8个方向车辆信息，每个包含：
            exist, dist, v_rel, TTC, PET
        """
        self.data = data
        self.maneuver = data["maneuver"]
        self.neighbors = data["neighbors"]

        # 中间结果
        self.level1 = {}  # 每个邻近车安全评级
        self.level2 = ""  # 本车道状态
        self.level3 = {"left": False, "right": False}  # 左右是否可安全变道
        self.reason = ""
        self.quality = "good"  # good / bad
        self.final_summary = ""

    # =============================================
    # Level 1：逐个分析 8 个邻近车辆的安全关系
    # =============================================
    def analyze_level1_single(self, n_type, data):
        if not data["exist"]:
            return "free"
        dist = data["dist"]
        ttc = data["TTC"]
        pet = data["PET"]

        if "pre" in n_type:
            if ttc > 2.5 and dist > 20:
                return "safe"
            elif ttc > 1.5:
                return "warning"
            else:
                return "risky"
        elif "foll" in n_type:
            if pet > 1.5 and dist > 15:
                return "safe"
            elif pet > 1.0:
                return "warning"
            else:
                return "risky"
        elif "along" in n_type:
            if dist > 2.5:
                return "safe"
            else:
                return "risky"
        return "unknown"

    def run_level1(self):
        for n_type in self.neighbors:
            self.level1[n_type] = self.analyze_level1_single(
                n_type, self.neighbors[n_type]
            )

    # =============================================
    # Level 2：分析本车道状态（舒适/压抑/被迫减速）
    # =============================================
    def run_level2(self):
        ego_v = self.data["v_ego_pre"]
        flow_v = self.data["v_flow"]
        pre = self.neighbors["preceding"]
        pre_stat = self.level1["preceding"]

        if not pre["exist"]:
            self.level2 = "comfortable"
        elif pre["v_rel"] > 1.0:
            self.level2 = "uncomfortable (front slow)"
        elif ego_v < flow_v - 2:
            self.level2 = "suppressed speed"
        elif pre_stat == "risky":
            self.level2 = "forced to slow down"
        else:
            self.level2 = "stable following"

    # =============================================
    # Level 3：判断左右车道是否可安全变道
    # =============================================
    def run_level3(self):
        # 左变可行性
        left_ok = (
            self.level1["left_pre"] in ["safe", "free"]
            and self.level1["left_along"] in ["safe", "free"]
            and self.level1["left_foll"] in ["safe", "free"]
        )

        # 右变可行性
        right_ok = (
            self.level1["right_pre"] in ["safe", "free"]
            and self.level1["right_along"] in ["safe", "free"]
            and self.level1["right_foll"] in ["safe", "free"]
        )

        self.level3["left"] = left_ok
        self.level3["right"] = right_ok

    # =============================================
    # Level 4：生成原因 + 好坏 + 最终总结
    # =============================================
    def judge_quality(self):
        if self.maneuver in [1, 2]:
            target_safe = (
                self.level3["left"] if self.maneuver == 1 else self.level3["right"]
            )
            if not target_safe:
                self.quality = "bad"
            elif (
                self.neighbors["left_foll"]["PET"] < 1.0
                or self.neighbors["right_foll"]["PET"] < 1.0
            ):
                self.quality = "bad"
            else:
                self.quality = "good"
        else:
            left_risk = not self.level3["left"]
            right_risk = not self.level3["right"]
            if left_risk and right_risk:
                self.quality = "good"
            elif self.level2 in ["comfortable", "stable following"]:
                self.quality = "good"
            else:
                self.quality = "bad"

    def get_reason(self):
        if self.maneuver in [1, 2]:
            if self.level2 in ["uncomfortable (front slow)", "suppressed speed"]:
                return "overtake (front vehicle too slow)"
            else:
                return "better space in target lane"
        else:
            if not self.level3["left"] and not self.level3["right"]:
                return "no safe gap on both sides"
            elif self.level2 == "comfortable":
                return "current lane is smooth and comfortable"
            else:
                return "stable cruising, no need to change"

    def build_summary(self):
        mano_str = {0: "lane keeping", 1: "left lane change", 2: "right lane change"}[
            self.maneuver
        ]
        quality_str = "good and safe" if self.quality == "good" else "risky and bad"

        if self.maneuver != 0:
            self.final_summary = (
                f"Ego performs {mano_str}. Reason: {self.reason}. "
                f"Current lane: {self.level2}. "
                f"This behavior is {quality_str}."
            )
        else:
            self.final_summary = (
                f"Ego performs {mano_str}. Reason: {self.reason}. "
                f"Current lane: {self.level2}. "
                f"This behavior is {quality_str}."
            )

    # =============================================
    # 一键运行全流程
    # =============================================
    def run(self):
        self.run_level1()
        self.run_level2()
        self.run_level3()
        self.judge_quality()
        self.reason = self.get_reason()
        self.build_summary()
        return {
            "level1_neighbor_status": self.level1,
            "level2_current_lane": self.level2,
            "level3_safe_change": self.level3,
            "maneuver_type": self.maneuver,
            "reason": self.reason,
            "quality": self.quality,
            "final_summary": self.final_summary,
        }


# =============================================
# 示例：输入一条真实数据 → 输出微调结论
# =============================================
if __name__ == "__main__":
    sample_data = {
        "maneuver": 2,  # 0=keep,1=left,2=right
        "lane_pre": 1,
        "lane_post": 2,
        "v_ego_pre": 22.0,
        "v_ego_post": 26.0,
        "v_flow": 25.0,
        "neighbors": {
            "preceding": {"exist": 1, "dist": 18, "v_rel": 2.0, "TTC": 2.2, "PET": 99},
            "following": {"exist": 1, "dist": 25, "v_rel": -0.5, "TTC": 99, "PET": 2.0},
            "left_pre": {"exist": 1, "dist": 12, "v_rel": 1.0, "TTC": 1.2, "PET": 99},
            "left_along": {"exist": 1, "dist": 1.8, "v_rel": 0, "TTC": 99, "PET": 99},
            "left_foll": {"exist": 1, "dist": 10, "v_rel": 0.5, "TTC": 99, "PET": 0.8},
            "right_pre": {"exist": 0, "dist": 999, "v_rel": 0, "TTC": 99, "PET": 99},
            "right_along": {"exist": 0, "dist": 999, "v_rel": 0, "TTC": 99, "PET": 99},
            "right_foll": {"exist": 0, "dist": 999, "v_rel": 0, "TTC": 99, "PET": 99},
        },
    }

    # 分析
    analyzer = HierarchicalLaneAnalyzer(sample_data)
    result = analyzer.run()

    # 打印所有结果
    print("===== 层次化分析结果 =====")
    for k, v in result.items():
        print(f"{k}: {v}")

    print("\n===== 大模型微调用最终结论 =====")
    print(result["final_summary"])
