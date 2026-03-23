import gymnasium as gym
from highway_env.envs import HighwayEnv
from highway_env.road.road import Road, RoadNetwork
from highway_env.road.lane import StraightLane, CircularLane
from highway_env.vehicle.controller import ControlledVehicle
import numpy as np
import matplotlib.pyplot as plt # For showing the road network
import matplotlib.patches as patches # For custom drawing


# --- Step 1: Define Our Custom Road Network (The "Private Map") ---
def create_cross_intersection_map() -> Road:
    """
    Creates a simple cross-intersection road network.
    """
    road = Road(network=RoadNetwork(), vehicles=[], np_random=np.random.default_rng())
    
    # Define Intersection Center and Lane Width
    intersection_center = np.array([0, 0])
    lane_width = StraightLane.DEFAULT_WIDTH
    
    # --- North-South Roads ---
    # North incoming
    ns_0_start = intersection_center + np.array([lane_width/2, 100])
    ns_0_end = intersection_center + np.array([lane_width/2, 0])
    road.network.add_lane("N_in_start", "N_in_end", StraightLane(ns_0_start, ns_0_end, speed_limit=20))
    
    # South outgoing
    ns_1_start = intersection_center + np.array([-lane_width/2, 0])
    ns_1_end = intersection_center + np.array([-lane_width/2, 100])
    road.network.add_lane("N_in_end", "S_out_end", StraightLane(ns_1_start, ns_1_end, speed_limit=20)) # From intersection to south
    
    # South incoming
    sn_0_start = intersection_center + np.array([-lane_width/2, -100])
    sn_0_end = intersection_center + np.array([-lane_width/2, 0])
    road.network.add_lane("S_in_start", "S_in_end", StraightLane(sn_0_start, sn_0_end, speed_limit=20))
    
    # North outgoing
    sn_1_start = intersection_center + np.array([lane_width/2, 0])
    sn_1_end = intersection_center + np.array([lane_width/2, -100])
    road.network.add_lane("S_in_end", "N_out_end", StraightLane(sn_1_start, sn_1_end, speed_limit=20)) # From intersection to north

    # --- East-West Roads ---
    # East incoming
    ew_0_start = intersection_center + np.array([100, -lane_width/2])
    ew_0_end = intersection_center + np.array([0, -lane_width/2])
    road.network.add_lane("E_in_start", "E_in_end", StraightLane(ew_0_start, ew_0_end, speed_limit=20))
    
    # West outgoing
    ew_1_start = intersection_center + np.array([0, lane_width/2])
    ew_1_end = intersection_center + np.array([100, lane_width/2])
    road.network.add_lane("E_in_end", "W_out_end", StraightLane(ew_1_start, ew_1_end, speed_limit=20)) # From intersection to west

    # West incoming
    we_0_start = intersection_center + np.array([-100, lane_width/2])
    we_0_end = intersection_center + np.array([0, lane_width/2])
    road.network.add_lane("W_in_start", "W_in_end", StraightLane(we_0_start, we_0_end, speed_limit=20))
    
    # East outgoing
    we_1_start = intersection_center + np.array([0, -lane_width/2])
    we_1_end = intersection_center + np.array([-100, -lane_width/2])
    road.network.add_lane("W_in_end", "E_out_end", StraightLane(we_1_start, we_1_end, speed_limit=20)) # From intersection to east

    # --- Add 'Dummy' Connections within the Intersection ---
    # These represent the traversable areas within the intersection itself.
    # For a simple cross, vehicles can theoretically move between any incoming/outgoing node.
    # In a real scenario, you'd add specific turn lanes.
    # Here we simplify by allowing any connection from an "end" node to an "out_end" node.
    # N_in_end connects to S_out_end (straight), W_out_end (left), E_out_end (right)
    road.network.add_lane("N_in_end", "S_out_end", StraightLane(ns_0_end, ns_1_start, speed_limit=20))
    
    radius = lane_width / 2
    center = intersection_center # [0, 0]
    start_phase = -np.pi / 2 # Start pointing North (90 degrees up)
    end_phase = np.pi # Total angle of 90 degrees

    # 1. Turn Lane (North to West): 90-degree left turn arc
    turn_lane_N_to_W = CircularLane(
        center=center, 
        radius=radius, 
        start_phase=start_phase, 
        end_phase=start_phase + np.pi/2, # End phase is 90 degrees from start
        clockwise=False, # Counter-clockwise turn
        speed_limit=20 
    )

    # Replace the SineLane call with the new CircularLane
    road.network.add_lane("N_in_end", "W_out_end", turn_lane_N_to_W)
    
    # For a full intersection, you would systematically add all possible connections/turns
    # This example focuses on demonstrating the structure.
    
    return road

from highway_env.road.road import LaneIndex
from highway_env.vehicle.behavior import IDMVehicle

# --- Step 2: Create a Custom Environment Class ---
# This class will load our specific road network
class CustomIntersectionEnv(HighwayEnv):
    """
    A custom environment that loads our pre-defined cross-intersection map.
    """
    
    @classmethod
    def default_config(cls) -> dict:
        config = super().default_config()
        config.update({
            "observation": {
                "type": "Kinematics",
                "vehicles_count": 2, # Observe 5 closest vehicles
                "features": ["presence", "x", "y", "vx", "vy", "heading"],
                "features_range": {  # Limit observation range to be reasonable for an intersection
                    "x": [-50, 50],
                    "y": [-50, 50],
                    "vx": [-20, 20],
                    "vy": [-20, 20]
                }
            },
            "action": {
                "type": "DiscreteMetaAction", # Recommended for simpler intersection control
                "lateral": True, # Allow lane changes (turns)
                "longitudinal": True # Allow speed control
            },
            "vehicles_density": 0.5, # More traffic
            "duration": 10, # Shorter episodes for quicker testing
            "ego_vehicle_speed_reward": 0.5, # Reward for maintaining speed
            "collision_reward": -20, # Harsh collision penalty
            "lane_centering_cost": 0.5, # Penalty for deviating from lane center
            "offroad_terminal": True # Episode ends if vehicle goes off-road
        })
        return config
    
    def _add_vehicles(self) -> None:
        """Add non-ego vehicles to specific entry lanes of the intersection."""
        
        # 1. Spawn a vehicle on the North incoming lane
        self.env_spawn_vehicle(
            lane_index=LaneIndex.from_ids("N_in_start", "N_in_end", 0),
            vehicle_type=IDMVehicle,
            speed=np.random.uniform(15, 20),
            position_longitudinal=35
        )
        
        # 2. Spawn a vehicle on the West incoming lane
        self.env_spawn_vehicle(
            lane_index=LaneIndex.from_ids("W_in_start", "W_in_end", 0),
            vehicle_type=IDMVehicle,
            speed=np.random.uniform(15, 20),
            position_longitudinal=20
        )

    def _road_randomization(self) -> None:
        """
        Loads our custom predefined road network.
        """
        self.road = create_cross_intersection_map()

        # Add initial ego vehicle
        ego_spawn_lane = self.road.network.get_lane(("N_in_start", "N_in_end", 0))
        print(ego_spawn_lane, "A")
        if ego_spawn_lane:
            self.road.vehicles.append(
                ControlledVehicle.make_on_lane(self.road, ego_spawn_lane, 
                                               speed=np.random.uniform(15, 20), 
                                               position=np.random.uniform(10, 30))
            )
            self.controlled_vehicles = [self.road.vehicles[0]]
        else:
            print("Warning: Could not spawn ego vehicle on 'N_in_start' lane.")



# --- Step 4: Visualize the Custom Map (Optional but helpful for debugging) ---
# --- CORRECTED CODE SNIPPET for plotting ---

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from highway_env.road.road import Road



# Visualize our created road network

# --- Step 5: Run the Simulation on the Custom Environment ---
if __name__ == "__main__":
    import highway_env # Make sure it's imported to register default environments too

    print("Creating custom environment 'custom-intersection-v0'...")
    # --- Step 3: Register the New Environment ---
    gym.register(
        id='custom-intersection-v0', 
        entry_point='__main__:CustomIntersectionEnv', # Assuming this script is run directly
    )
    env = gym.make('custom-intersection-v0', render_mode='human') # Use 'human' for GUI
    
    print("Resetting environment...")
    obs, info = env.reset()
    
    done = truncated = False
    total_reward = 0
    steps = 0

    print("Starting simulation...")
    while not (done or truncated):
        # Choose a random action
        # For 'DiscreteMetaAction', actions are: 0=LEFT, 1=IDLE, 2=RIGHT, 3=FASTER, 4=SLOWER
        action = env.action_space.sample() 
        
        obs, reward, done, truncated, info = env.step(action)
        env.render() # Renders the current state
        
        total_reward += reward
        steps += 1
        
        # Optional: Print some info
        if steps % 20 == 0:
            print(f"Step: {steps}, Reward: {reward:.2f}, Speed: {info['speed']:.2f}")

    print(f"\nSimulation Finished after {steps} steps.")
    print(f"Total Reward: {total_reward:.2f}")
    if done:
        print("Episode terminated (e.g., collision or goal).")
    if truncated:
        print("Episode truncated (e.g., reached max duration).")
        
    env.close()
    print("Environment closed.")
