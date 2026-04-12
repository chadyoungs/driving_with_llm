import gymnasium as gym
import matplotlib.pyplot as plt
import numpy as np
from gymnasium.wrappers import FrameStackObservation, RecordVideo
from highway_env.envs.common.abstract import AbstractEnv
from highway_env.road.lane import CircularLane, LineType, StraightLane
from highway_env.road.road import Road, RoadNetwork
from highway_env.vehicle.behavior import IDMVehicle
from highway_env.vehicle.controller import ControlledVehicle

"""_summary_
        "highway-v0": {
            "observation": {
                "type": "Kinematics",
                "features": [
                    "presence",
                    "x",
                    "y",
                    "vx",
                    "vy",
                ],
                "observation_shape": (
                    30,
                    50,
                    5,
                ),
            },
            "action": {
                "type": "DiscreteMetaAction",
            },
            "lanes_count": 4,
            "road_length": 800,
            "initial_lane_id": 0,
            "vehicles_count": 50,
            "controlled_vehicles": 1,
            "traffic_density": 0.6,
            "lane_vehicle_density": [
                0.2,
                0.3,
                0.6,
                1.0,
            ],  # 右侧=出口=拥堵
            "duration": 40,  # [s]
            "initial_spacing": 2,
            "simulation_frequency": 15,  # [Hz]
            "policy_frequency": 1,  # [Hz]
            "other_vehicles_type": "highway_env.vehicle.behavior.IDMVehicle",
            "collision_reward": -10,  # The reward received when colliding with a vehicle.
            "reward_speed_range": [
                105,
                125,
            ],  # [m/s] The reward for high speed is mapped linearly from this range to [0, HighwayEnv.HIGH_SPEED_REWARD].
            "right_lane_reward": 0.2,
            "lane_change_reward": 0.1,
            "speed_reward": 0.2,
            "high_speed_reward": 0.5,
            "screen_width": 600,  # [px]
            "screen_height": 150,  # [px]
            "centering_position": [
                0.3,
                0.5,
            ],
            "scaling": 5.5,
            "show_trajectories": False,
            "render_agent": True,
            "offscreen_rendering": False,
            "randomize": False,
        }
"""


def plot_road_network(road_obj: Road):
    """
    Plots the road network by iterating through the nested dictionary and list structure.
    兼容 highway-env 所有路网：直行、圆弧、左转、右转、路口
    """
    fig, ax = plt.subplots(figsize=(12, 12))

    # 遍历路网
    for from_node, to_nodes in road_obj.network.graph.items():
        for to_node, lanes_list in to_nodes.items():
            for lane in lanes_list:
                # 采样车道点
                s = np.linspace(0, lane.length, 150)

                # 中心线
                xy = np.array([lane.position(si, 0) for si in s])
                ax.plot(xy[:, 0], xy[:, 1], color="gray", linestyle="--", linewidth=1.5)

                # 左边界
                xy_left = np.array([lane.position(si, -lane.width / 2) for si in s])
                ax.plot(xy_left[:, 0], xy_left[:, 1], color="black", linewidth=1)

                # 右边界
                xy_right = np.array([lane.position(si, lane.width / 2) for si in s])
                ax.plot(xy_right[:, 0], xy_right[:, 1], color="black", linewidth=1)

    # 样式
    ax.set_aspect("equal")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_title("Road Network (Lanes + Boundaries)")
    ax.grid(True)

    plt.savefig("road_network.png", dpi=300)
    plt.close()
    print("✅ 路网图已保存为 road_network.png")


def make_real_cross_road() -> Road:
    road = Road(
        network=RoadNetwork(),
        vehicles=[],
        np_random=np.random.default_rng(),
    )
    L = 100
    W = 4.0
    C = np.array([0.0, 0.0])

    road.network.add_lane("S_R", "C", StraightLane(C + [W, -L], C + [W, 0], 20))
    road.network.add_lane("S_T", "C", StraightLane(C + [0, -L], C + [0, 0], 20))
    road.network.add_lane("S_L", "C", StraightLane(C + [-W, -L], C + [-W, 0], 20))

    road.network.add_lane("N_R", "C", StraightLane(C + [-W, L], C + [-W, 0], 20))
    road.network.add_lane("N_T", "C", StraightLane(C + [0, L], C + [0, 0], 20))
    road.network.add_lane("N_L", "C", StraightLane(C + [W, L], C + [W, 0], 20))

    road.network.add_lane("W_R", "C", StraightLane(C + [-L, -W], C + [0, -W], 20))
    road.network.add_lane("W_T", "C", StraightLane(C + [-L, 0], C + [0, 0], 20))
    road.network.add_lane("W_L", "C", StraightLane(C + [-L, W], C + [0, W], 20))

    road.network.add_lane("E_R", "C", StraightLane(C + [L, W], C + [0, W], 20))
    road.network.add_lane("E_T", "C", StraightLane(C + [L, 0], C + [0, 0], 20))
    road.network.add_lane("E_L", "C", StraightLane(C + [L, -W], C + [0, -W], 20))

    road.network.add_lane("C", "N", StraightLane(C, C + [0, L], 20))
    road.network.add_lane("C", "S", StraightLane(C, C + [0, -L], 20))
    road.network.add_lane("C", "E", StraightLane(C, C + [L, 0], 20))
    road.network.add_lane("C", "W", StraightLane(C, C + [-L, 0], 20))

    r = 8.0
    road.network.add_lane("S_L", "E", CircularLane(C, r, np.pi / 2, np.pi, True, 15))
    road.network.add_lane("N_L", "W", CircularLane(C, r, -np.pi / 2, 0, True, 15))
    road.network.add_lane("W_L", "S", CircularLane(C, r, np.pi, -np.pi / 2, True, 15))
    road.network.add_lane("E_L", "N", CircularLane(C, r, 0, np.pi / 2, True, 15))

    r = 3.5
    road.network.add_lane("S_R", "W", CircularLane(C, r, np.pi / 2, 0, False, 15))
    road.network.add_lane("N_R", "E", CircularLane(C, r, -np.pi / 2, -np.pi, False, 15))
    road.network.add_lane("W_R", "N", CircularLane(C, r, np.pi, np.pi / 2, False, 15))
    road.network.add_lane("E_R", "S", CircularLane(C, r, 0, -np.pi / 2, False, 15))

    return road


class RealSignalIntersectionEnv(AbstractEnv):
    @classmethod
    def default_config(cls) -> dict:
        config = super().default_config()
        config.update(
            {
                "observation": {"type": "Kinematics", "vehicles_count": 4},
                "action": {"type": "DiscreteMetaAction"},
                "simulation_frequency": 15,
                "policy_frequency": 10,
                "collision_reward": -50,
                "offroad_terminal": True,
            }
        )
        return config

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timer = 0
        self.phase = 0
        self.stop_line = 18.0

    def _reset(self):
        self._create_road()
        self._create_vehicles()
        self.timer = 0
        self.phase = 0

    def _create_road(self):
        self.road = make_real_cross_road()
        """
        self.net = RoadNetwork()
        # 1. Define the Main Highway (Nodes 0 -> 1 -> 2)
        # We use LineType to define markings (CONTINUOUS on outside, STRIPED between lanes)
        line_types = [
            LineType.CONTINUOUS_LINE,
            LineType.STRIPED,
        ]

        # Lane 0 (Left)
        self.net.add_lane(
            "0",
            "1",
            StraightLane(
                [0, 0],
                [200, 0],
                line_types=line_types,
            ),
        )
        self.net.add_lane(
            "1",
            "2",
            StraightLane(
                [200, 0],
                [600, 0],
                line_types=line_types,
            ),
        )

        # Lane 1 (Right - where the exit starts)
        self.net.add_lane(
            "0",
            "1",
            StraightLane(
                [0, 4],
                [200, 4],
                line_types=[
                    LineType.STRIPED,
                    LineType.STRIPED,
                ],
            ),
        )
        # After node 1, the highway continues straight
        self.net.add_lane(
            "1",
            "2",
            StraightLane(
                [200, 4],
                [600, 4],
                line_types=[
                    LineType.STRIPED,
                    LineType.CONTINUOUS_LINE,
                ],
            ),
        )

        # 2. Define the Exit Ramp (Branching off from Node 1 to "exit")
        # CircularLane args: center, radius, start_angle, end_angle
        # We place the center so the curve starts tangentially at (100, 4)
        center = [200, 24]
        radius = 20
        exit_lane = CircularLane(
            center,
            radius,
            np.deg2rad(-90),
            np.deg2rad(0),
            clockwise=True,
            line_types=[
                LineType.STRIPED,
                LineType.CONTINUOUS_LINE,
            ],
        )
        self.net.add_lane("1", "exit", exit_lane)

        self.road = Road(
            network=self.net,
            np_random=self.np_random,
            record_history=False,
        )
        """

    def _create_vehicles(self):
        # ===================== 修复：全部使用正确索引 (from, to, 0) =====================
        ego = ControlledVehicle.make_on_lane(
            self.road, ("0", "1", 0), speed=15, longitudinal=0
        )
        self.road.vehicles.append(ego)
        self.controlled_vehicles = [ego]

        car = IDMVehicle.make_on_lane(
            self.road, ("0", "1", 0), speed=15, longitudinal=30
        )
        self.road.vehicles.append(car)

    def _step(self, action):
        self.timer += 1
        if self.timer % 40 == 0:
            self.phase = (self.phase + 1) % 4

        ego = self.controlled_vehicles[0]
        dist = np.linalg.norm(ego.position)
        near_stop = self.stop_line - 6 < dist < self.stop_line + 6

        if near_stop:
            x, y = ego.position
            if not (
                (self.phase == 0 and y < 0)
                or (self.phase == 1 and y < 0)
                or (self.phase == 2 and x < 0)
                or (self.phase == 3 and x < 0)
            ):
                ego.act({"steering": 0, "acceleration": -1.0}, 1 / 15)

        return super()._step(action)

    def _reward(self, action):
        return -0.1 + 0.6 * self.controlled_vehicles[0].speed / 20

    def _is_terminated(self):
        return (
            self.controlled_vehicles[0].crashed
            or not self.controlled_vehicles[0].on_road
            or self.steps > 180
        )

    def _is_truncated(self):
        return False


gym.register(
    id="real-signal-intersection-v0",
    entry_point="__main__:RealSignalIntersectionEnv",
)

if __name__ == "__main__":
    env = gym.make("real-signal-intersection-v0", render_mode="rgb_array")
    env = FrameStackObservation(env, stack_size=30)
    env = RecordVideo(
        env,
        video_folder="./highway_recordings",
        episode_trigger=lambda episode_id: True,  # Record every episode
    )

    obs, info = env.reset()
    print("✅ 启动成功！")

    while True:
        obs, reward, done, truncated, info = env.step(env.action_space.sample())
        if done or truncated:
            break
    env.close()
