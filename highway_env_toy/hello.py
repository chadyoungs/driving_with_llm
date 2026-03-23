import numpy as np
import gymnasium as gym

from highway_env.road.road import RoadNetwork
from highway_env.road.lane import StraightLane, CircularLane, LineType
from highway_env.road.road import Road
from highway_env.vehicle.controller import ControlledVehicle
from highway_env.envs.common.abstract import AbstractEnv

from gymnasium.wrappers import RecordVideo, FrameStackObservation


import matplotlib.pyplot as plt


env_default_config = {
    "highway-v0":
    {
        "observation": {
            "type": "Kinematics",
            "features": ["presence", "x", "y", "vx", "vy"],
            "observation_shape": (30, 50, 5)
        },
        "action": {
            "type": "DiscreteMetaAction",
        },
        "lanes_count": 4,
        "vehicles_count": 50,
        "duration": 40,  # [s]
        "initial_spacing": 2,
        "collision_reward": -1,  # The reward received when colliding with a vehicle.
        "reward_speed_range": [105, 125],  # [m/s] The reward for high speed is mapped linearly from this range to [0, HighwayEnv.HIGH_SPEED_REWARD].
        "simulation_frequency": 15,  # [Hz]
        "policy_frequency": 1,  # [Hz]
        "other_vehicles_type": "highway_env.vehicle.behavior.IDMVehicle",
        "screen_width": 600,  # [px]
        "screen_height": 150,  # [px]
        "centering_position": [0.3, 0.5],
        "scaling": 5.5,
        "show_trajectories": False,
        "render_agent": True,
        "offscreen_rendering": False
    }
}

def plot_road_network(road_obj: Road):
    """
    Plots the road network by iterating through the nested dictionary and list structure.
    """
    fig, ax = plt.subplots(figsize=(10, 10))
    
    # Correct iteration over the new nested dictionary and LIST structure
    for from_node, to_nodes in road_obj.network.graph.items():
        for to_node, lanes_at_edge in to_nodes.items():
            
            # ** FIX IS HERE: Iterate over the list using enumerate **
            for lane_index, lane in enumerate(lanes_at_edge):
                # --- Drawing Logic (remains the same) ---
                # 1. Create a range of longitudinal distances (s) along the lane's length
                s = np.linspace(0, lane.length, 100) 
                
                # 2. Reshape s to (100, 1) to enable broadcasting with the (2,) direction vector
                s_reshaped = s[:, np.newaxis] 
                
                # 3. Get the centerline coordinates (t=0 lateral offset)
                # Pass the reshaped array
                xy_center = lane.position(s_reshaped, 0) 
                
                # Note: The output structure is typically (N, 2) where N=100
                xs, ys = xy_center[:, 0], xy_center[:, 1]
                
                ax.plot(xs, ys, color='gray', linestyle='--', linewidth=1)
                
                # Draw lane boundaries (Apply the same reshaping here!)
                s_lateral = s_reshaped
                left_boundary_xy = lane.position(s_lateral, -lane.width/2)
                right_boundary_xy = lane.position(s_lateral, lane.width/2)
                
                ax.plot(left_boundary_xy[:, 0], left_boundary_xy[:, 1], color='black', linewidth=0.5)
                ax.plot(right_boundary_xy[:, 0], right_boundary_xy[:, 1], color='black', linewidth=0.5)
                """
                # Draw arrows for direction
                if len(xs) > 1:
                    # Use the first segment to define the direction vector
                    dx = xs[1] - xs[0]
                    dy = ys[1] - ys[0]
                    
                    # Place the arrow slightly into the lane to avoid overlap with nodes
                    arrow_position_index = min(5, len(xs) - 2) 
                    
                    # We must ensure dx and dy are single float values
                    print(dx, dy)
                    # --- FIX: Pass clear scalar values to ax.arrow ---
                    ax.arrow(
                        x=xs[arrow_position_index].item(), # Extract scalar from array element
                        y=ys[arrow_position_index].item(), # Extract scalar from array element
                        dx=dx.item(), # Extract scalar from the difference result
                        dy=dy.item(), # Extract scalar from the difference result
                        color='blue', 
                        head_width=1.5, 
                        head_length=1.5, 
                        length_includes_head=True
                    )
                """
    # ... rest of the function ...
    ax.set_aspect('equal', adjustable='box')
    ax.set_xlabel("X-coordinate")
    ax.set_ylabel("Y-coordinate")
    ax.set_title("Custom Intersection Road Network")
    ax.grid(True)

    # Replace plt.show() with this:
    plt.savefig("custom_road_network.png") 
    plt.close()
    
class HighwayExitEnv(AbstractEnv): 
    def _create_road(self) -> None:
        self.net = RoadNetwork()
        # 1. Define the Main Highway (Nodes 0 -> 1 -> 2)
        # We use LineType to define markings (CONTINUOUS on outside, STRIPED between lanes)
        line_types = [LineType.CONTINUOUS_LINE, LineType.STRIPED]
        
        # Lane 0 (Left)
        self.net.add_lane("0", "1", StraightLane([0, 0], [200, 0], line_types=line_types))
        self.net.add_lane("1", "2", StraightLane([200, 0], [600, 0], line_types=line_types))
        
        # Lane 1 (Right - where the exit starts)
        self.net.add_lane("0", "1", StraightLane([0, 4], [200, 4], line_types=[LineType.STRIPED, LineType.STRIPED]))
        # After node 1, the highway continues straight
        self.net.add_lane("1", "2", StraightLane([200, 4], [600, 4], line_types=[LineType.STRIPED, LineType.CONTINUOUS_LINE]))

        # 2. Define the Exit Ramp (Branching off from Node 1 to "exit")
        # CircularLane args: center, radius, start_angle, end_angle
        # We place the center so the curve starts tangentially at (100, 4)
        center = [200, 24] 
        radius = 20
        exit_lane = CircularLane(center, radius, np.deg2rad(-90), np.deg2rad(0), 
                                 clockwise=True, line_types=[LineType.STRIPED, LineType.CONTINUOUS_LINE])
        self.net.add_lane("1", "exit", exit_lane)

        self.road = Road(network=self.net, np_random=self.np_random, record_history=False)

    def _create_vehicles(self) -> None:
        # Add the Ego Vehicle
        self.vehicle = self.action_type.vehicle_class(self.road, self.road.network.get_lane(("0", "1", 1)).position(0, 0), speed=5)
        self.road.vehicles.append(self.vehicle)

    def _reset(self) -> None:
        self._create_road()
        self._create_vehicles()

    def _reward(self, action: int) -> float:
        # Reward for staying on the exit ramp
        on_exit = self.vehicle.lane_index[1] == "exit"
        return 1.0 if on_exit else 0.0

# --- Execution ---
if __name__ == "__main__":
    env = gym.make("highway-v0", render_mode="rgb_array")
    
    env = FrameStackObservation(env, stack_size=30)
    
    env = RecordVideo(
            env, 
            video_folder="./highway_recordings",
            episode_trigger=lambda episode_id: True  # Record every episode
        )
    
    # Overwrite the internal methods with our custom logic
    env.unwrapped._reset = lambda: HighwayExitEnv._reset(env.unwrapped)
    env.unwrapped._create_road = lambda: HighwayExitEnv._create_road(env.unwrapped)
    env.unwrapped._create_vehicles = lambda: HighwayExitEnv._create_vehicles(env.unwrapped)
    
    obs, _ = env.reset()
    done = False
    done = truncated = False

    while not (done or truncated):
        action = env.action_space.sample()
        obs, reward, done, truncated, info = env.step(action)
        env.render()
    
    env.close()
    
