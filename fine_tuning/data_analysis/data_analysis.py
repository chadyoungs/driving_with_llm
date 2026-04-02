#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Traffic Data Analysis Script
Analyzing traffic tracking data
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime


def convert_to_serializable(value):
    """Convert any value to a JSON-serializable type (fixes float/dict issues)"""
    if isinstance(value, (int, float, str, bool, type(None))):
        # Directly return simple types (floats are allowed here!)
        return value
    elif isinstance(value, (list, tuple)):
        # Recursively process lists/tuples
        return [convert_to_serializable(item) for item in value]
    elif isinstance(value, dict):
        # Recursively process dictionaries (only if it's a dict)
        return {str(k): convert_to_serializable(v) for k, v in value.items()}
    else:
        # Convert unknown types to string (avoid errors)
        return str(value)


def load_and_prepare_data():
    """Load and prepare the traffic data"""
    print("Loading traffic data...")

    # Load data files
    tracks_df = pd.read_csv("/mnt/sdb/datasets/highd-dataset-v1.0/data/01_tracks.csv")
    tracks_meta_df = pd.read_csv(
        "/mnt/sdb/datasets/highd-dataset-v1.0/data/01_tracksMeta.csv"
    )

    print(
        f"Loaded {len(tracks_df)} tracking records for {len(tracks_meta_df)} vehicles"
    )

    # Convert speeds from km/h to m/s for physics calculations
    speed_columns = [
        "xVelocity",
        "yVelocity",
        "precedingXVelocity",
        "minXVelocity",
        "maxXVelocity",
        "meanXVelocity",
    ]
    for col in speed_columns:
        if col in tracks_df.columns:
            tracks_df[col] = tracks_df[col] / 3.6
        if col in tracks_meta_df.columns:
            tracks_meta_df[col] = tracks_meta_df[col] / 3.6

    # Filter out invalid safety metrics (negative values indicate no preceding vehicle)
    tracks_df["valid_dhw"] = tracks_df["dhw"] > 0
    tracks_df["valid_thw"] = tracks_df["thw"] > 0
    tracks_df["valid_ttc"] = tracks_df["ttc"] > 0

    return tracks_df, tracks_meta_df


def analyze_traffic_flow(tracks_df):
    """Analyze traffic flow patterns"""
    print("Analyzing traffic flow...")

    # Calculate vehicles per hour per lane
    total_time_hours = tracks_df["frame"].max() / 30 / 3600  # Assuming 30fps
    lane_counts = tracks_df.groupby(["laneId", "id"]).size().reset_index(name="count")
    vehicles_per_lane = lane_counts["laneId"].value_counts().sort_index()

    flow_rate = {}
    for lane_id, count in vehicles_per_lane.items():
        flow_rate[lane_id] = count / total_time_hours

    # Calculate density (vehicles per km)
    density = {}
    for lane_id in sorted(tracks_df["laneId"].unique()):
        lane_data = tracks_df[tracks_df["laneId"] == lane_id]
        if len(lane_data) > 0:
            max_x = lane_data["x"].max()
            min_x = lane_data["x"].min()
            length_km = (max_x - min_x) / 1000  # Convert meters to km
            if length_km > 0:
                density[lane_id] = vehicles_per_lane[lane_id] / length_km

    return {
        "vehicles_per_lane": {
            str(k): convert_to_serializable(v)
            for k, v in vehicles_per_lane.to_dict().items()
        },
        "flow_rate": {
            str(k): round(convert_to_serializable(v), 1) for k, v in flow_rate.items()
        },
        "density": {
            str(k): round(convert_to_serializable(v), 2) for k, v in density.items()
        },
        "total_time_hours": round(convert_to_serializable(total_time_hours), 2),
    }


def analyze_speed_patterns(tracks_meta_df):
    """Analyze speed distribution and patterns"""
    print("Analyzing speed patterns...")

    # Speed distribution by vehicle type
    speed_by_type = (
        tracks_meta_df.groupby("class")["meanXVelocity"]
        .agg(["mean", "std", "min", "max"])
        .round(2)
    )

    # Speed distribution by driving direction
    speed_by_direction = (
        tracks_meta_df.groupby("drivingDirection")["meanXVelocity"]
        .agg(["mean", "std", "min", "max"])
        .round(2)
    )

    # Create speed bins
    speed_bins = [0, 5, 10, 15, 20, 25, 30, 35, 40]
    speed_labels = ["0-5", "5-10", "10-15", "15-20", "20-25", "25-30", "30-35", "35-40"]
    tracks_meta_df["speed_bin"] = pd.cut(
        tracks_meta_df["meanXVelocity"],
        bins=speed_bins,
        labels=speed_labels,
        include_lowest=True,
    )
    speed_distribution = tracks_meta_df["speed_bin"].value_counts().sort_index()

    return {
        "speed_by_type": {
            str(k): {str(m): convert_to_serializable(n) for m, n in v.items()}
            for k, v in speed_by_type.to_dict().items()
        },
        "speed_by_direction": {
            str(k): {str(m): convert_to_serializable(n) for m, n in v.items()}
            for k, v in speed_by_direction.to_dict().items()
        },
        "speed_distribution": {
            str(k): convert_to_serializable(v)
            for k, v in speed_distribution.to_dict().items()
            if pd.notna(k)
        },
    }


def analyze_safety_metrics(tracks_df):
    """Analyze safety metrics (THW, TTC, DHW)"""
    print("Analyzing safety metrics...")

    # Calculate statistics for valid safety metrics
    safety_stats = {
        "dhw": {
            "mean": round(tracks_df[tracks_df["valid_dhw"]]["dhw"].mean(), 2),
            "std": round(tracks_df[tracks_df["valid_dhw"]]["dhw"].std(), 2),
            "min": round(tracks_df[tracks_df["valid_dhw"]]["dhw"].min(), 2),
            "max": round(tracks_df[tracks_df["valid_dhw"]]["dhw"].max(), 2),
            "count": convert_to_serializable(tracks_df["valid_dhw"].sum()),
        },
        "thw": {
            "mean": round(tracks_df[tracks_df["valid_thw"]]["thw"].mean(), 2),
            "std": round(tracks_df[tracks_df["valid_thw"]]["thw"].std(), 2),
            "min": round(tracks_df[tracks_df["valid_thw"]]["thw"].min(), 2),
            "max": round(tracks_df[tracks_df["valid_thw"]]["thw"].max(), 2),
            "count": convert_to_serializable(tracks_df["valid_thw"].sum()),
        },
        "ttc": {
            "mean": round(tracks_df[tracks_df["valid_ttc"]]["ttc"].mean(), 2),
            "std": round(tracks_df[tracks_df["valid_ttc"]]["ttc"].std(), 2),
            "min": round(tracks_df[tracks_df["valid_ttc"]]["ttc"].min(), 2),
            "max": round(tracks_df[tracks_df["valid_ttc"]]["ttc"].max(), 2),
            "count": convert_to_serializable(tracks_df["valid_ttc"].sum()),
        },
    }

    # Create bins for safety metrics
    dhw_bins = [0, 10, 20, 30, 40, 50, 100]
    dhw_labels = ["0-10", "10-20", "20-30", "30-40", "40-50", "50+"]
    tracks_df["dhw_bin"] = pd.cut(
        tracks_df[tracks_df["valid_dhw"]]["dhw"],
        bins=dhw_bins,
        labels=dhw_labels,
        include_lowest=True,
    )
    dhw_distribution = tracks_df["dhw_bin"].value_counts().sort_index()

    thw_bins = [0, 1, 2, 3, 4, 5, 10]
    thw_labels = ["0-1", "1-2", "2-3", "3-4", "4-5", "5+"]
    tracks_df["thw_bin"] = pd.cut(
        tracks_df[tracks_df["valid_thw"]]["thw"],
        bins=thw_bins,
        labels=thw_labels,
        include_lowest=True,
    )
    thw_distribution = tracks_df["thw_bin"].value_counts().sort_index()

    return {
        "safety_stats": safety_stats,
        "dhw_distribution": {
            str(k): convert_to_serializable(v)
            for k, v in dhw_distribution.to_dict().items()
            if pd.notna(k)
        },
        "thw_distribution": {
            str(k): convert_to_serializable(v)
            for k, v in thw_distribution.to_dict().items()
            if pd.notna(k)
        },
    }


def analyze_lane_usage(tracks_df):
    """Analyze lane usage patterns"""
    print("Analyzing lane usage...")

    # Lane usage distribution
    lane_usage = tracks_df["laneId"].value_counts().sort_index()

    # Lane changes analysis
    lane_changes = tracks_df.groupby("id")["laneId"].nunique()
    vehicles_with_changes = (lane_changes > 1).sum()
    total_changes = (lane_changes - 1).sum()

    # Average speed by lane
    speed_by_lane = (
        tracks_df.groupby("laneId")["xVelocity"].agg(["mean", "std", "count"]).round(2)
    )

    return {
        "lane_usage": {
            str(k): convert_to_serializable(v) for k, v in lane_usage.to_dict().items()
        },
        "vehicles_with_changes": convert_to_serializable(vehicles_with_changes),
        "total_changes": convert_to_serializable(total_changes),
        "speed_by_lane": {
            str(k): {str(m): convert_to_serializable(n) for m, n in v.items()}
            for k, v in speed_by_lane.to_dict().items()
        },
    }


def analyze_vehicle_types(tracks_meta_df):
    """Analyze vehicle type distribution and characteristics"""
    print("Analyzing vehicle types...")

    # Vehicle type distribution
    vehicle_types = tracks_meta_df["class"].value_counts()

    # Size distribution by vehicle type
    size_by_type = (
        tracks_meta_df.groupby("class")[["width", "height"]]
        .agg(["mean", "std"])
        .round(2)
    )

    # Speed comparison by vehicle type
    speed_comparison = (
        tracks_meta_df.groupby("class")["meanXVelocity"]
        .agg(["mean", "std", "min", "max"])
        .round(2)
    )

    # Lane change behavior by vehicle type
    lane_changes_by_type = (
        tracks_meta_df.groupby("class")["numLaneChanges"]
        .agg(["sum", "mean", "count"])
        .round(2)
    )

    return {
        "vehicle_types": {
            str(k): convert_to_serializable(v)
            for k, v in vehicle_types.to_dict().items()
        },
        "size_by_type": {
            str(k): {
                str(m): {str(n): convert_to_serializable(o) for n, o in p.items()}
                for m, p in v.items()
            }
            for k, v in size_by_type.to_dict().items()
        },
        "speed_comparison": {
            str(k): {str(m): convert_to_serializable(n) for m, n in v.items()}
            for k, v in speed_comparison.to_dict().items()
        },
        "lane_changes_by_type": {
            str(k): {str(m): convert_to_serializable(n) for m, n in v.items()}
            for k, v in lane_changes_by_type.to_dict().items()
        },
    }


def prepare_visualization_data(tracks_df, tracks_meta_df):
    """Prepare data for visualization"""
    print("Preparing visualization data...")

    # Sample data (first 10 vehicles' tracking data)
    sample_vehicle_ids = tracks_meta_df["id"].head(10).tolist()
    sample_data = tracks_df[tracks_df["id"].isin(sample_vehicle_ids)].head(100)

    # Convert to JSON format
    sample_tracks = []
    for _, row in sample_data.iterrows():
        sample_tracks.append(
            {
                "frame": convert_to_serializable(row["frame"]),
                "id": convert_to_serializable(row["id"]),
                "x": round(convert_to_serializable(row["x"]), 2),
                "y": round(convert_to_serializable(row["y"]), 2),
                "width": round(convert_to_serializable(row["width"]), 2),
                "height": round(convert_to_serializable(row["height"]), 2),
                "speed": round(
                    convert_to_serializable(row["xVelocity"]) * 3.6, 1
                ),  # Convert back to km/h
                "laneId": convert_to_serializable(row["laneId"]),
            }
        )

    # Vehicle metadata for sample
    sample_meta = []
    for _, row in tracks_meta_df[
        tracks_meta_df["id"].isin(sample_vehicle_ids)
    ].iterrows():
        sample_meta.append(
            {
                "id": convert_to_serializable(row["id"]),
                "class": convert_to_serializable(row["class"]),
                "width": round(convert_to_serializable(row["width"]), 2),
                "height": round(convert_to_serializable(row["height"]), 2),
                "avgSpeed": round(
                    convert_to_serializable(row["meanXVelocity"]) * 3.6, 1
                ),
                "maxSpeed": round(
                    convert_to_serializable(row["maxXVelocity"]) * 3.6, 1
                ),
                "laneChanges": convert_to_serializable(row["numLaneChanges"]),
                "distance": round(convert_to_serializable(row["traveledDistance"]), 1),
            }
        )

    return {"sample_tracks": sample_tracks, "sample_meta": sample_meta}


def main():
    """Main function to run the analysis"""
    print("=== Traffic Data Analysis ===")
    print(f"Analysis started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load and prepare data
    tracks_df, tracks_meta_df = load_and_prepare_data()

    # Run analyses
    traffic_flow_results = analyze_traffic_flow(tracks_df)
    speed_patterns_results = analyze_speed_patterns(tracks_meta_df)
    safety_metrics_results = analyze_safety_metrics(tracks_df)
    lane_usage_results = analyze_lane_usage(tracks_df)
    # vehicle_types_results = analyze_vehicle_types(tracks_meta_df)
    visualization_data = prepare_visualization_data(tracks_df, tracks_meta_df)

    # Combine results
    results = {
        "summary": {
            "totalVehicles": convert_to_serializable(len(tracks_meta_df)),
            "totalFrames": convert_to_serializable(tracks_df["frame"].max()),
            "totalRecords": convert_to_serializable(len(tracks_df)),
            "carCount": convert_to_serializable(
                tracks_meta_df[tracks_meta_df["class"] == "Car"].shape[0]
            ),
            "truckCount": convert_to_serializable(
                tracks_meta_df[tracks_meta_df["class"] == "Truck"].shape[0]
            ),
            "avgSpeed": round(
                convert_to_serializable(tracks_meta_df["meanXVelocity"].mean() * 3.6), 1
            ),  # Convert back to km/h
            "maxSpeed": round(
                convert_to_serializable(tracks_meta_df["maxXVelocity"].max() * 3.6), 1
            ),
            "totalLaneChanges": convert_to_serializable(
                tracks_meta_df["numLaneChanges"].sum()
            ),
        },
        "trafficFlow": traffic_flow_results,
        "speedPatterns": speed_patterns_results,
        "safetyMetrics": safety_metrics_results,
        "laneUsage": lane_usage_results,
        #'vehicleTypes': vehicle_types_results,
        "visualizationData": visualization_data,
    }

    # Save results to JSON
    with open("traffic_analysis_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Analysis completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Results saved to traffic_analysis_results.json")

    return results


if __name__ == "__main__":
    main()
