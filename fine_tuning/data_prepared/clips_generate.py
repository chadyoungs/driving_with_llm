import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")


def detect_lane_change_scenarios(
    tracks_path: str,
    tracks_meta_path: str,
    output_path: str = "/mnt/lane_change_scenarios_sample.csv",
):
    """
    Detect lane change scenarios in highD data and generate labeled CSV sample.
    """
    # Load & preprocess data
    tracks_df = pd.read_csv(tracks_path)
    tracks_meta_df = pd.read_csv(tracks_meta_path)

    # Sort by vehicle ID and frame (critical for change detection)
    tracks_df = tracks_df.sort_values(["id", "frame"]).reset_index(drop=True)
    tracks_df["vehicle_length"] = tracks_df["id"].map(
        tracks_meta_df.set_index("id")["length"]
    )
    tracks_df["is_truck"] = tracks_df["vehicle_length"] > 6  # Truck = length >6m

    # Initialize scenario results
    lc_scenarios = []

    # Process each vehicle (limit to 5 vehicles for sample CSV)
    sample_vehicle_ids = tracks_df["id"].unique()[:5]  # Sample 5 vehicles
    for vehicle_id in sample_vehicle_ids:
        veh_data = tracks_df[tracks_df["id"] == vehicle_id].reset_index(drop=True)
        if len(veh_data) < 20:  # Skip short trajectories
            continue

        # Get vehicle metadata
        veh_meta = tracks_meta_df[tracks_meta_df["id"] == vehicle_id].iloc[0]
        avg_speed = veh_meta["averageSpeed"]  # km/h

        # Detect lane changes (laneId difference)
        veh_data["prev_lane"] = veh_data["laneId"].shift(1)
        veh_data["lane_change"] = veh_data["laneId"] != veh_data["prev_lane"]
        veh_data["change_direction"] = np.where(
            veh_data["laneId"] < veh_data["prev_lane"], "left", "right"
        )

        # Iterate over detected lane changes
        change_frames = veh_data[
            veh_data["lane_change"] & ~veh_data["prev_lane"].isna()
        ].index
        for frame_idx in change_frames:
            change_row = veh_data.iloc[frame_idx]
            prev_row = veh_data.iloc[frame_idx - 1]

            # Extract core metrics for scenario detection
            change_dir = change_row["change_direction"]
            front_sight = change_row["frontSightDistance"]
            prev_front_sight = prev_row["frontSightDistance"]
            ttc = change_row["ttc"] if change_row["ttc"] > 0 else np.inf
            dhw = change_row["dhw"] if change_row["dhw"] > 0 else np.inf
            prev_speed = prev_row["xVelocity"] * 3.6  # m/s → km/h
            curr_speed = change_row["xVelocity"] * 3.6
            is_truck_prev = prev_row["is_truck"]

            # --------------------------
            # Scenario Detection Logic
            # --------------------------
            scenario = "Unclassified"

            # 1. Mandatory Scenarios
            if (
                change_dir == "right"
                and change_row["laneId"] == tracks_df["laneId"].max()
            ):
                scenario = "Exit"  # Rightmost lane = exit lane
            elif change_dir == "left" and prev_row["x"] < 100:
                scenario = "Merge"  # Low x = on-ramp merge
            elif (
                np.isnan(veh_data.iloc[frame_idx + 5]["laneId"])
                if frame_idx + 5 < len(veh_data)
                else False
            ):
                scenario = "Lane Drop/Closure"

            # 2. Voluntary Scenarios
            elif (
                change_dir == "left"
                and prev_speed < avg_speed * 0.8
                and curr_speed > prev_speed
            ):
                scenario = "Overtake"
            elif front_sight > prev_front_sight + 20:
                scenario = "Space Optimization"
            elif is_truck_prev and change_dir == "left":
                scenario = "Avoid Large Vehicles"

            # 3. Safety Scenarios
            elif ttc < 2 or dhw < 10:
                scenario = "Avoid Obstacles/Congestion"

            # 4. Unnecessary Scenarios
            elif abs(curr_speed - prev_speed) < 2:  # No speed gain
                scenario = "Frequent Lane Hopping"
            elif dhw < 10 and change_dir == "right":
                scenario = "Forced Cut-In"

            # Add to results
            lc_scenarios.append(
                {
                    "vehicle_id": int(vehicle_id),
                    "frame": int(change_row["frame"]),
                    "time_seconds": round(change_row["frame"] * 0.1, 1),
                    "start_lane": int(prev_row["laneId"]),
                    "end_lane": int(change_row["laneId"]),
                    "change_direction": change_dir,
                    "scenario": scenario,
                    "ttc_seconds": round(ttc, 1) if ttc != np.inf else "N/A",
                    "distance_headway_m": round(dhw, 1) if dhw != np.inf else "N/A",
                    "speed_before_kmh": round(prev_speed, 1),
                    "speed_after_kmh": round(curr_speed, 1),
                    "is_truck": bool(veh_meta["vehicleType"] == 2),
                }
            )

    # Generate sample CSV (limit to 20 rows for readability)
    sample_df = pd.DataFrame(lc_scenarios)[:20]
    sample_df.to_csv(output_path, index=False)

    # Print summary
    print(f"✅ Sample CSV saved to: {output_path}")
    print("\n📋 Sample CSV Preview:")
    print(
        sample_df[
            ["vehicle_id", "scenario", "start_lane", "end_lane", "speed_before_kmh"]
        ].to_string(index=False)
    )

    return sample_df


# Run for your uploaded highD data
if __name__ == "__main__":
    detect_lane_change_scenarios(
        tracks_path="/mnt/01_tracks.csv", tracks_meta_path="/mnt/01_tracksMeta.csv"
    )
