import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings("ignore")


class Behavior_Evaluator(object):
    def __init__(self):
        pass
    
    def lane_keeping_evaluation(self):
        """
        Evaluate lane keeping behavior based on highD data.
        Using metrics like 
                 lane deviation, speed stability, etc.
        """
        pass
    
    def lane_change_evaluation(self):
        """
        Evaluate lane change behavior based on highD data.
        
        intent mandatory, e.g. exit/merge
        intent voluntary, e.g. overtake, avoid obstacle
        intentunnecessary, e.g. no clear reason, low speed, short gap, lane hopping
        
        smooth, low lateral acceleration, >= 2s duration
        abrupt, high lateral acceleration, < 1.5s duration
        reversed, canceled mid-change or multiple lane changes in short time
           
        """
        """
        start_idx = max(0, change_start - 10)
        end_idx = min(len(veh_data) - 1, change_start + 10)
        change_window = veh_data.iloc[start_idx:end_idx]
        
        # Skip if no actual lane change in window
        if len(change_window["laneId"].unique()) < 2:
            continue
        
        # Calculate core metrics
        start_lane = change_window.iloc[0]["laneId"]
        end_lane = change_window.iloc[-1]["laneId"]
        direction = "left" if end_lane < start_lane else "right"
        duration = (change_window["frame"].max() - change_window["frame"].min()) * 0.1  # seconds
        lateral_accel = abs(change_window["yAcceleration"]).max()
        avg_speed = change_window["xVelocity"].mean() * 3.6  # km/h
        
        # Calculate safety context (gap to adjacent vehicles)
        left_gap = change_window["leftPrecedingId"].iloc[0]
        right_gap = change_window["rightPrecedingId"].iloc[0]
        ttc = change_window["ttc"].min() if "ttc" in change_window.columns else np.inf
        gap = change_window["precedingXDistance"].min() if "precedingXDistance" in change_window.columns else np.inf
        
        # --- Categorize Intent ---
        # Simplified intent: voluntary if speed > 60km/h and gap > 20m; mandatory if near exit (laneId > 3)
        if end_lane > 3 and avg_speed < 50:
            intent = "mandatory"
        elif avg_speed > 60 and gap > 20:
            intent = "voluntary"
        else:
            intent = "unnecessary"
        
        # --- Categorize Execution ---
        if duration >= 2 and lateral_accel < 0.5:
            execution = "smooth"
        elif duration < 1.5 and lateral_accel > 1.0:
            execution = "abrupt"
        else:
            execution = "reversed" if len(change_window["laneId"].unique()) > 2 else "moderate"
        
        # --- Categorize Context ---
        if gap >= 25 and ttc >= 3:
            context = "safe"
        elif gap < 15 or ttc < 2:
            context = "risky"
        else:
            context = "congested"
        
        # --- Calculate Lane Change Score (1-10; higher = better) ---
        score = 10
        if intent == "unnecessary":
            score -= 3
        if execution == "abrupt":
            score -= 3
        elif execution == "reversed":
            score -= 4
        if context == "risky":
            score -= 4
        score = max(1, score)  # Ensure score is at least 1
        """
    
    def acceleration_evaluation(self):
        """
        Evaluate acceleration behavior based on highD data.
        Outputs: acceleration_evaluation.csv with metrics like harsh acceleration frequency, speed variability, etc.
        """
        pass
    
    def deceleration_evaluation(self):
        """
        Evaluate deceleration behavior based on highD data.
        Outputs: deceleration_evaluation.csv with metrics like harsh braking frequency, speed variability, etc.
        """
        pass

def categorize_lane_changes(
    tracks_path: str,
    tracks_meta_path: str,
    output_path: str = "/mnt/lane_change_categories.csv",
):
    """
    Categorize lane change behavior from highD data and link to driver skill.
    Outputs: lane_change_categories.csv with detailed change categories and driver scores.
    """
    # Load data
    tracks_df = pd.read_csv(tracks_path)
    tracks_meta_df = pd.read_csv(tracks_meta_path)

    # Sort tracks by vehicle and frame
    tracks_df = tracks_df.sort_values(["id", "frame"]).reset_index(drop=True)

    # Initialize results list
    lane_change_data = []

    # Process each vehicle
    for vehicle_id in tracks_df["id"].unique():
        veh_data = tracks_df[tracks_df["id"] == vehicle_id].reset_index(drop=True)
        if len(veh_data) < 2:
            continue

        # Get vehicle metadata
        veh_meta = tracks_meta_df[tracks_meta_df["id"] == vehicle_id].iloc[0]
        total_distance = veh_data["x"].max() - veh_data["x"].min()
        if total_distance < 10:  # Skip vehicles that barely moved
            continue

        # Detect lane changes (laneId changes)
        veh_data["lane_change"] = veh_data["laneId"].diff().fillna(0) != 0
        change_frames = veh_data[veh_data["lane_change"]].index

        for i, change_start in enumerate(change_frames):
            # Define change window (±10 frames = ±1s)
            start_idx = max(0, change_start - 10)
            end_idx = min(len(veh_data) - 1, change_start + 10)
            change_window = veh_data.iloc[start_idx:end_idx]

            # Skip if no actual lane change in window
            if len(change_window["laneId"].unique()) < 2:
                continue

            # Calculate core metrics
            start_lane = change_window.iloc[0]["laneId"]
            end_lane = change_window.iloc[-1]["laneId"]
            direction = "left" if end_lane < start_lane else "right"
            duration = (
                change_window["frame"].max() - change_window["frame"].min()
            ) * 0.1  # seconds
            lateral_accel = abs(change_window["yAcceleration"]).max()
            avg_speed = change_window["xVelocity"].mean() * 3.6  # km/h

            # Calculate safety context (gap to adjacent vehicles)
            left_gap = change_window["leftPrecedingId"].iloc[0]
            right_gap = change_window["rightPrecedingId"].iloc[0]
            ttc = (
                change_window["ttc"].min() if "ttc" in change_window.columns else np.inf
            )
            gap = (
                change_window["precedingXDistance"].min()
                if "precedingXDistance" in change_window.columns
                else np.inf
            )

            # --- Categorize Intent ---
            # Simplified intent: voluntary if speed > 60km/h and gap > 20m; mandatory if near exit (laneId > 3)
            if end_lane > 3 and avg_speed < 50:
                intent = "mandatory"
            elif avg_speed > 60 and gap > 20:
                intent = "voluntary"
            else:
                intent = "unnecessary"

            # --- Categorize Execution ---
            if duration >= 2 and lateral_accel < 0.5:
                execution = "smooth"
            elif duration < 1.5 and lateral_accel > 1.0:
                execution = "abrupt"
            else:
                execution = (
                    "reversed"
                    if len(change_window["laneId"].unique()) > 2
                    else "moderate"
                )

            # --- Categorize Context ---
            if gap >= 25 and ttc >= 3:
                context = "safe"
            elif gap < 15 or ttc < 2:
                context = "risky"
            else:
                context = "congested"

            # --- Calculate Lane Change Score (1-10; higher = better) ---
            score = 10
            if intent == "unnecessary":
                score -= 3
            if execution == "abrupt":
                score -= 3
            elif execution == "reversed":
                score -= 4
            if context == "risky":
                score -= 4
            score = max(1, score)  # Ensure score is at least 1

            # Add to results
            lane_change_data.append(
                {
                    "vehicle_id": vehicle_id,
                    "change_id": f"{vehicle_id}_{i+1}",
                    "start_frame": change_window["frame"].min(),
                    "end_frame": change_window["frame"].max(),
                    "duration_s": round(duration, 2),
                    "start_lane": int(start_lane),
                    "end_lane": int(end_lane),
                    "direction": direction,
                    "intent": intent,
                    "execution": execution,
                    "context": context,
                    "lateral_accel_max": round(lateral_accel, 3),
                    "avg_speed_kmh": round(avg_speed, 1),
                    "min_gap_m": round(gap, 1) if gap != np.inf else "N/A",
                    "min_ttc_s": round(ttc, 1) if ttc != np.inf else "N/A",
                    "lane_change_score": score,
                }
            )

    # Convert to DataFrame and save
    lc_df = pd.DataFrame(lane_change_data)
    lc_df.to_csv(output_path, index=False)
    print(f"✅ Lane change categories saved to: {output_path}")

    # Print summary
    print("\n📊 Lane Change Summary:")
    print(f"Total changes detected: {len(lc_df)}")
    print("\nBy Intent:")
    print(lc_df["intent"].value_counts().to_string())
    print("\nBy Execution:")
    print(lc_df["execution"].value_counts().to_string())
    print("\nBy Context:")
    print(lc_df["context"].value_counts().to_string())
    print(f"\nAverage Lane Change Score: {lc_df['lane_change_score'].mean():.1f}/10")

    return lc_df


# Run for your uploaded data
if __name__ == "__main__":
    categorize_lane_changes(
        tracks_path="/mnt/01_tracks.csv", tracks_meta_path="/mnt/01_tracksMeta.csv"
    )
