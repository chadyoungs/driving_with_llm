import pygame
import xml.etree.ElementTree as ET
import numpy as np
from dataclasses import dataclass
import math
import re


@dataclass
class Vehicle:
    name: str          # vehicle name
    x: float           # x coordinate
    y: float           # y coordinate
    heading: float     # heading angle (degrees)
    speed: float       # speed (m/s)
    color: tuple       # display color
    width: float = 1.8 # width (m)
    length: float = 4.5# length (m)

@dataclass
class Scenario:
    vehicles: dict     # vehicle dictionary {name: Vehicle}
    params: dict       # global parameter dictionary {param_name: value}
    sim_time: float = 0.0  # simulation time
    sim_step: float = 0.1  # simulation step (seconds)


def resolve_param_ref(value_str, params):
    """
    Parse parameter references (e.g., ${main_car_speed}), replace with actual values
    :param value_str: string containing parameter references
    :param params: global parameter dictionary
    :return: parsed numerical value
    """
    if not isinstance(value_str, str):
        return float(value_str)
    
    # Match ${xxx} format parameter references
    pattern = r"\$\{(\w+)\}"
    matches = re.findall(pattern, value_str)
    
    if not matches:
        # No parameter references, directly convert to float
        return float(value_str)
    
    resolved_str = value_str
    for expr in matches:
        # Evaluate the expression inside ${} (e.g., "crossing_size/2" → 20.0/2 = 10)
        try:
            # Use params as local variables for evaluation
            evaluated_expr = eval(expr, {}, params)
            resolved_str = resolved_str.replace(f"${{{expr}}}", str(evaluated_expr))
        except Exception as e:
            raise ValueError(f"Failed to evaluate expression '${{{expr}}}' : {e}")

    # Step 2: Evaluate remaining math expressions (e.g., "-10.0" or "8.33*2")
    try:
        # Safe evaluation (only math operations, no unsafe code)
        result = float(eval(resolved_str, {}, {}))
        return result
    except Exception as e:
        raise ValueError(f"Failed to evaluate math expression '{resolved_str}' : {e}")

def parse_openscenario(file_path):
    """Parse OpenSCENARIO file, extract core scenario information (fixed parameter reference parsing)"""
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    # Initialize scenario object
    scenario = Scenario(vehicles={}, params={})
    
    # 1. Parse global parameters (prioritize parsing for subsequent parameter reference replacement)
    param_nodes = root.findall(".//ParameterDeclaration")
    for param in param_nodes:
        name = param.get("name")
        value = float(param.get("value"))
        scenario.params[name] = value
    
    # 2. Parse vehicle information
    vehicle_nodes = root.findall(".//ScenarioObject")
    for obj in vehicle_nodes:
        # Get vehicle name
        obj_name = obj.get("name")
        if "Vehicle" not in obj_name:
            continue

        # ========== Parse initial position ==========
        pos_nodes = root.findall(".//Actions/PrivateAction")
        for pos_node in pos_nodes:
            if pos_node.get("object") == obj_name:
                position = pos_node.find(".//Position")
                x = resolve_param_ref(position.get("x", "0.0"), scenario.params)
                y = resolve_param_ref(position.get("y", "0.0"), scenario.params)
                heading = float(position.get("h", "0.0"))
        
        # ========== Parse target speed (fix parameter references) ==========
        speed = 0.0
        # Find TargetSpeed in SpeedAction
        speed_node = obj.find(".//TargetSpeed")
        if speed_node is not None and speed_node.get("value") is not None:
            speed_str = speed_node.get("value")
            # Parse parameter references (e.g., ${main_car_speed})
            speed = resolve_param_ref(speed_str, scenario.params)
        
        # ========== Create vehicle object ==========
        # Set vehicle color (main car red, obstacle car blue)
        color = (255, 0, 0) if "Main" in obj_name else (0, 0, 255)
        
        scenario.vehicles[obj_name] = Vehicle(
            name=obj_name,
            x=x,
            y=y,
            heading=heading,
            speed=speed,
            color=color
        )
    
    return scenario


class ScenarioPlayer:
    def __init__(self, scenario, window_size=(800, 800), meters_per_pixel=20, simulation_duration=10):
        """
        Initializes the scenario player.
        :param scenario: scenario object containing vehicles and parameters
        :param window_size: window size
        :param meters_per_pixel: pixels per meter for scaling the visualization
        """
        pygame.init()
        self.window = pygame.display.set_mode(window_size)
        pygame.display.set_caption("OpenSCENARIO Player (Fixed Param Ref)")
        self.clock = pygame.time.Clock()
        
        self.scenario = scenario
        self.window_size = window_size
        self.meters_per_pixel = meters_per_pixel
        self.center_x = window_size[0] // 2
        self.center_y = window_size[1] // 2
        
        # color definitions
        self.road_color = (50, 50, 50)
        self.line_color = (255, 255, 255)
        self.bg_color = (240, 240, 240)
        
        # lane
        self.lane_width = 3.5  # lane width in meters
        
        # get the crossing size from parameters (default to 20 meters if not defined)
        self.crossing_size = self.scenario.params.get("crossing_size", 2 * self.lane_width)
        
        self.simulation_duration = simulation_duration  # total simulation duration in seconds
        
    def world_to_screen(self, x, y):
        """world coordinates to screen coordinates"""
        screen_x = self.center_x + x * self.meters_per_pixel
        # pygame's y axis is inverted (down is positive), so we subtract
        screen_y = self.center_y - y * self.meters_per_pixel
        return int(screen_x), int(screen_y)
    
    def draw_road(self):
        """draw the intersection roads"""
        # draw main road (north-south)
        pygame.draw.rect(
            self.window,
            self.road_color,
            (self.center_x - self.lane_width * self.meters_per_pixel, 0, 2 * self.lane_width * self.meters_per_pixel, self.window_size[1])
        )
        # draw crossing road (east-west)
        pygame.draw.rect(
            self.window,
            self.road_color,
            (0, self.center_y - self.lane_width * self.meters_per_pixel, self.window_size[0], 2 * self.lane_width * self.meters_per_pixel)
        )
        # draw center lines
        pygame.draw.line(
            self.window,
            self.line_color,
            (self.center_x, 0),
            (self.center_x, self.window_size[1]),
            2
        )
        pygame.draw.line(
            self.window,
            self.line_color,
            (0, self.center_y),
            (self.window_size[0], self.center_y),
            2
        )
    
    def draw_vehicle(self, vehicle):
        """draw a vehicle on the screen"""
        # coordinates of the vehicle center in screen space
        screen_x, screen_y = self.world_to_screen(vehicle.x, vehicle.y)
        
        # calculate display size of the vehicle
        display_width = vehicle.width * self.meters_per_pixel
        display_length = vehicle.length * self.meters_per_pixel
        
        # create a surface for the vehicle and draw a rectangle on it
        car_surface = pygame.Surface((display_length, display_width), pygame.SRCALPHA)
        pygame.draw.rect(car_surface, vehicle.color, (0, 0, display_length, display_width))
        
        # rotate the vehicle surface according to its heading
        compensate_angle = 90
        rotated_surface = pygame.transform.rotate(car_surface, -vehicle.heading + compensate_angle)
        rotated_rect = rotated_surface.get_rect(center=(screen_x, screen_y))
        
        # blit the rotated vehicle onto the main window
        self.window.blit(rotated_surface, rotated_rect)
        
        # draw vehicle name and speed above the vehicle
        font = pygame.font.SysFont(None, 20)
        speed_kmh = vehicle.speed * 3.6
        text = font.render(f"{vehicle.name} ({speed_kmh:.0f}km/h)", True, (0,0,0))
        self.window.blit(text, (screen_x - 50, screen_y - 30))
    
    def update_vehicle_position(self):
        """update vehicle positions based on speed and heading"""
        dt = self.scenario.sim_step
        for vehicle in self.scenario.vehicles.values():
            # convert heading to radians
            heading_rad = math.radians(vehicle.heading)
            # calculate displacement
            dx = vehicle.speed * dt * math.sin(heading_rad)
            dy = vehicle.speed * dt * math.cos(heading_rad)
            # update vehicle position
            vehicle.x += dx
            vehicle.y += dy
    
    def run(self):
        """run the scenario playback"""
        running = True
        paused = False
        
        while running:
            # event handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        paused = not paused
                    elif event.key == pygame.K_ESCAPE:
                        running = False
            
            # clear the screen
            self.window.fill(self.bg_color)
            
            # draw the road
            self.draw_road()
            
            # update and draw vehicles
            if not paused:
                self.update_vehicle_position()
                self.scenario.sim_time += self.scenario.sim_step
            
            for vehicle in self.scenario.vehicles.values():
                self.draw_vehicle(vehicle)
            
            # draw simulation information
            font = pygame.font.SysFont(None, 24)
            info_text = font.render(f"Simulation Time: {self.scenario.sim_time:.1f}s | Press Space to Pause/Resume | ESC to Exit", True, (0,0,0))
            self.window.blit(info_text, (10, 10))
            
            # refresh the display
            pygame.display.flip()
            self.clock.tick(1/self.scenario.sim_step)  # control the simulation speed
            
            if self.scenario.sim_time >= self.simulation_duration:
                break
        
        pygame.quit()

def main():
    scenario_file = "crossing_no_traffic_light.xosc"
    
    try:
        # decode the scenario file and create the scenario object
        print(f"Decoding scenario file: {scenario_file}")
        scenario = parse_openscenario(scenario_file)
        
        print("\nParsed Scenario Information:")
        print(f"Whole parameters: {scenario.params}")
        for name, vehicle in scenario.vehicles.items():
            print(f"Vehicle {name}: Position({vehicle.x:.1f}, {vehicle.y:.1f}) Heading{vehicle.heading}° Speed{vehicle.speed:.2f}m/s ({vehicle.speed*3.6:.0f}km/h)")
        
        print("\nStarting scenario player...")
        player = ScenarioPlayer(scenario, window_size=(800, 800), meters_per_pixel=15, simulation_duration=5)
        player.run()
        
    except FileNotFoundError:
        print(f"Error: File not found {scenario_file}, please check the file path")
    except Exception as e:
        print(f"Error:{str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()