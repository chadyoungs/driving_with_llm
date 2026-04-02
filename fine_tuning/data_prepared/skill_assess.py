import os
from collections import defaultdict

import numpy as np
import pandas as pd

MAX_SPEED_STD = 5.0
MAX_ACCEL_STD = 1.5
MAX_JERK = 3.0
MAX_LANE_OFFSET = 0.5
MAX_DHW = 200.0
MIN_DHW = 30.0
HARD_ACCEL = 2.0
HARD_BRAKE = -3.0
MIN_TTC = 3.0
MIN_THW = 2.0


class SkillAssessment(object):
    """
    Driving Skill Assessment
    """

    def __init__(
        self,
        tracks_data_path,
        tracks_metadata_path,
        recording_metadata_path,
        build_lookups=True,
        filtering=True,
    ):
        self.assess_results = defaultdict(dict)
        self.skilled_drivers = defaultdict(list)

        self._failed_vehicles = []

        try:
            # Load tracks (vehicle trajectory data)
            self.tracks_df = pd.read_csv(tracks_data_path)
            # Load tracksMeta (vehicle metadata: type, duration, etc.)
            self.tracks_meta_df = pd.read_csv(tracks_metadata_path)
            # Load recording metadata
            self.recording_meta_df = pd.read_csv(recording_metadata_path)
            print(f"✅ Loaded your data:")
            print(
                f"   - Tracks: {len(self.tracks_df):,} frames, {self.tracks_df['id'].nunique()} unique vehicles"
            )
            print(f"   - TracksMeta: {len(self.tracks_meta_df)} vehicles")
            print(f"   - RecordingMeta: {len(self.recording_meta_df)} recordings")
        except FileNotFoundError as e:
            raise ValueError(f"❌ Missing file: {e} (ensure paths match data files)")
        except Exception as e:
            raise RuntimeError(f"❌ Failed to load data: {str(e)}")

    def check_input_data(self, required_tracks_cols=None, required_meta_cols=None):
        # Check critical columns exist (avoid KeyErrors with your data)
        if required_tracks_cols is None:
            required_tracks_cols = [
                "frame",
                "id",
                "x",
                "xAcceleration",
                "precedingId",
                "laneId",
            ]
        missing_tracks_cols = [
            col for col in required_tracks_cols if col not in self.tracks_df.columns
        ]
        if missing_tracks_cols:
            raise ValueError(
                f"❌ Tracks file missing critical columns: {missing_tracks_cols}"
            )

        if required_meta_cols is None:
            required_meta_cols = [
                "id",
                "height",
                "numFrames",
                "class",
                "numLaneChanges",
            ]
        missing_meta_cols = [
            col for col in required_meta_cols if col not in self.tracks_meta_df.columns
        ]
        if missing_meta_cols:
            raise ValueError(
                f"❌ TracksMeta file missing critical columns: {missing_meta_cols}"
            )

    @property
    def frame_rate(self):
        if not hasattr(self, "_frame_rate"):
            self._frame_rate = (
                self.recording_meta_df["frameRate"].iloc[0]
                if "frameRate" in self.recording_meta_df.columns
                else 25
            )  # Default to 25Hz
        return self._frame_rate

    @property
    def lane_centers(self):
        if not hasattr(self, "_lane_centers"):
            lane_id = 2
            self._lane_centers = defaultdict()

            for _, i in enumerate(
                [
                    self.recording_meta_df["upperLaneMarkings"].iloc[0],
                    self.recording_meta_df["lowerLaneMarkings"].iloc[0],
                ]
            ):
                lane_markings = [float(x) for x in i.split(";") if x.strip()]
                lane_centers = [
                    round(
                        (lane_markings[i + 1] - lane_markings[i]) / 2
                        + lane_markings[i],
                        2,
                    )
                    for i in range(len(lane_markings) - 1)
                ]

                for i in lane_centers:
                    self._lane_centers[lane_id] = i
                    lane_id += 1
                lane_id += 1

        return self._lane_centers

    @property
    def front_vehicle_x_lookup(self):
        # Build fast lookup for front vehicle's x-coordinate (frame + id → x)
        # Critical for following distance calculation (no precedingX column!)
        if not hasattr(self, "_front_vehicle_lookup"):
            self._front_vehicle_lookup = self.tracks_df.set_index(["id", "frame"])[
                "x"
            ].to_dict()
        return self._front_vehicle_lookup

    @property
    def valid_vehicles(self):
        # Filter valid vehicles (driving duration > 10s to remove noise)
        # Filter car class only (remove trucks for skill assessment)
        if not hasattr(self, "_valid_vehicles"):
            duration_threshold = 10  # seconds
            self._valid_vehicles = self.tracks_meta_df[
                (
                    self.tracks_meta_df["numFrames"]
                    > duration_threshold * self.frame_rate
                )
                & (self.tracks_meta_df["class"] == "Car")
            ]["id"].unique()
        return self._valid_vehicles

    @property
    def failed_vehicles(self):
        return self._failed_vehicles

    @property
    def filtered_data(self):
        if not hasattr(self, "_filtered_tracks_df"):
            # Keep only valid vehicle data
            self._filtered_tracks_df = self.tracks_df[
                self.tracks_df["id"].isin(self.valid_vehicles)
            ]
        return self._filtered_tracks_df

    def assess(self, tracks_data_path, expert_threshold=6):
        # --------------------------
        # Classify Driver Skill (Expert/Novice)
        # --------------------------
        assessment_results = defaultdict(list)

        for vehicle_id, metrics in self.assess_results.items():
            speed_std = metrics.get("speed_std", np.inf)
            acc_std = metrics.get("acc_std", np.inf)
            jerk_mean = metrics.get("jerk_mean", np.inf)
            lane_deviation = metrics.get("lane_deviation", np.inf)
            follow_dist_mean = metrics.get("follow_dist_mean", np.inf)
            harsh_freq = metrics.get("harsh_freq", np.inf)
            lane_change_freq = metrics.get("lane_change_freq", np.inf)
            critical_ttc_count = metrics.get("critical_ttc_count", np.inf)
            critical_thw_count = metrics.get("critical_thw_count", np.inf)

            expert_criteria = [
                speed_std < MAX_SPEED_STD,  # Smooth velocity
                acc_std < MAX_ACCEL_STD,  # Smooth acceleration
                jerk_mean < MAX_JERK,  # Comfortable
                lane_deviation < MAX_LANE_OFFSET,  # Safety
                (follow_dist_mean < MAX_DHW) & (follow_dist_mean > MIN_DHW),  # Safety
                harsh_freq < 1,  # Comfortable
                lane_change_freq < 0.5,  # Few lane changes per km
                critical_ttc_count < 5,  # Stable following distance
                critical_thw_count < 2 * self.frame_rate,  # Rare harsh maneuvers
            ]

            # ≥ expert_threshold = Expert
            is_expert = 1 if sum(expert_criteria) >= expert_threshold else 0
            skill_level = "Expert" if is_expert == 1 else "Novice"

            assessment_results["id"].append(vehicle_id)
            assessment_results["skill_level"].append(skill_level)

        file_name = (
            os.path.basename(tracks_data_path).split(".csv")[0] + "_skill_level.csv"
        )
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        skill_level_csv_file_loc = os.path.join(cur_dir, "skill_level_results", f"{file_name}")
        to_save_data = pd.DataFrame(assessment_results)

        to_save_data.to_csv(skill_level_csv_file_loc, index=False)

    def kinematic_stability(self):
        """
        velocity, acceleration and jerk stability
        Feature: Longitudinal and Lateral Stability

        speed std < 5 km/h,
        acc std < 1.5 m/s², acceleration < 2.0 m/s², deceleration > -3.0 m/s²,
        |jerk| < 3 m/s³
        = smooth driving (expert)
        """
        for vehicle_id in self.valid_vehicles:
            try:

                # Get all trajectory data for the current driver (sorted by time)
                driver_trajectory = (
                    self.filtered_data[self.filtered_data["id"] == vehicle_id]
                    .sort_values("frame")
                    .reset_index(drop=True)
                )

                # speed stability
                driver_trajectory = driver_trajectory.dropna(
                    subset=["xVelocity", "yVelocity", "xAcceleration", "yAcceleration"]
                )
                driver_trajectory["speed"] = (
                    np.sqrt(
                        driver_trajectory["xVelocity"] ** 2
                        + driver_trajectory["yVelocity"] ** 2
                    )
                    * 3.6
                )  # m/s → km/h
                self.speed_std = round(driver_trajectory["speed"].std(), 3)

                # acceleration stability
                acc = np.sqrt(
                    driver_trajectory["xAcceleration"] ** 2
                    + driver_trajectory["yAcceleration"] ** 2
                )
                driver_trajectory["acceleration"] = np.where(
                    driver_trajectory["xAcceleration"] < 0, -acc, acc
                )

                self.acc_std = round(driver_trajectory["acceleration"].std(), 3)

                # jerk stability
                driver_trajectory["jerk"] = driver_trajectory[
                    "acceleration"
                ].diff().dropna() / (
                    1 / self.frame_rate
                )  # m/s³

                self.largest_jerk_values_mean = round(
                    driver_trajectory["jerk"].nlargest(self.frame_rate).mean(), 3
                )

                self.assess_results[vehicle_id]["speed_std"] = self.speed_std
                self.assess_results[vehicle_id][
                    "acc_mean"
                ] = self.largest_acc_values_mean
                self.assess_results[vehicle_id][
                    "deacc_mean"
                ] = self.minimum_acc_values_mean
                self.assess_results[vehicle_id][
                    "jerk_mean"
                ] = self.largest_jerk_values_mean

            except Exception as e:
                self._failed_vehicles.append(
                    (int(vehicle_id), str(e)[:200])
                )  # Log errors briefly
                continue

    def lane_center_deviation(self):
        """
        lane center_deviation
        Feature: Lateral Stability

        deviation < 0.5m, deviation std < 0.3m = stable driving (expert)
        """
        for vehicle_id in self.valid_vehicles:
            try:
                # Get all trajectory data for the current driver (sorted by time)
                driver_trajectory = (
                    self.filtered_data[self.filtered_data["id"] == vehicle_id]
                    .sort_values("frame")
                    .reset_index(drop=True)
                )
                driver_trajectory["lane_deviation"] = driver_trajectory.apply(
                    lambda row: abs(
                        row["y"]
                        + 0.5 * row["height"]
                        - self.lane_centers[row["laneId"]]
                    ),
                    axis=1,
                )

                self.lane_offset_mean = round(
                    driver_trajectory["lane_deviation"].mean(), 3
                )
                self.assess_results[vehicle_id][
                    "lane_deviation"
                ] = self.lane_offset_mean

            except Exception as e:
                self._failed_vehicles.append(
                    (int(vehicle_id), str(e)[:200])
                )  # Log errors briefly
                continue

    def following_stability(self):
        """
        following distance
        Feature: Following Distance Stability (Stable = Expert)

        following distance > 30m && following distance < 50m = stable following (expert)
        ( dhw )
        """
        for vehicle_id in self.valid_vehicles:
            try:
                # Get all trajectory data for the current driver (sorted by time)
                driver_trajectory = (
                    self.filtered_data[self.filtered_data["id"] == vehicle_id]
                    .sort_values("frame")
                    .reset_index(drop=True)
                )

                dhw_values = driver_trajectory["dhw"].dropna()  # Distance Headway (m)
                self.follow_dist_mean = round(dhw_values.mean(), 3)

                self.assess_results[vehicle_id][
                    "follow_dist_mean"
                ] = self.follow_dist_mean

            except Exception as e:
                self._failed_vehicles.append(
                    (int(vehicle_id), str(e)[:200])
                )  # Log errors briefly
                continue

    def harsh_maneuver_frequency(self):
        """
        Harsh Maneuver, such as hard braking or rapid acceleration.
        Feature: Harsh Maneuver Frequency (Rare = Expert)

        harsh acceleration > 2 m/s² or harsh deceleration < -3 m/s²
        = harsh maneuver

        Counts how often a driver performs harsh maneuvers, A high frequency of harsh
        maneuvers can indicate aggressive or inexperienced driving, while a low frequency
        suggests smoother and more controlled driving.
        """
        for vehicle_id in self.valid_vehicles:
            try:
                driver_trajectory = (
                    self.filtered_data[self.filtered_data["id"] == vehicle_id]
                    .sort_values("frame")
                    .reset_index(drop=True)
                )
                acc = np.sqrt(
                    driver_trajectory["xAcceleration"] ** 2
                    + driver_trajectory["yAcceleration"] ** 2
                )  # m/s²
                driver_trajectory["acceleration"] = np.where(
                    driver_trajectory["xAcceleration"] < 0, -acc, acc
                )

                harsh_maneuvers = (
                    (driver_trajectory["acceleration"] > HARD_ACCEL)
                    | (driver_trajectory["acceleration"] < -HARD_BRAKE)
                ).sum()  # Threshold for harsh maneuver
                self.harsh_freq = round(
                    harsh_maneuvers / (len(driver_trajectory) / self.frame_rate), 3
                )  # Harsh maneuvers per second
                self.assess_results[vehicle_id]["harsh_freq"] = self.harsh_freq

            except Exception as e:
                self._failed_vehicles.append(
                    (int(vehicle_id), str(e)[:200])
                )  # Log errors briefly
                continue

    def lane_change_frequency(self):
        """
        Lane Change
        Feature: Lane Change Frequency (Few = Expert)

        Frequent lane changes can indicate aggressive or inexperienced driving, while fewer lane changes
        suggest a more stable and experienced driver.
        """
        for vehicle_id in self.valid_vehicles:
            try:
                lane_change_times = self.tracks_meta_df[
                    self.tracks_meta_df["id"] == vehicle_id
                ]["numLaneChanges"].iloc[0]
                frame_num = self.tracks_meta_df[
                    self.tracks_meta_df["id"] == vehicle_id
                ]["numFrames"].iloc[0]

                self.lane_change_freq = round(
                    lane_change_times / (frame_num / self.frame_rate), 3
                )  # Changes per second
                self.assess_results[vehicle_id][
                    "lane_change_freq"
                ] = self.lane_change_freq

            except Exception as e:
                self.failed_vehicles.append(
                    (int(vehicle_id), str(e)[:200])
                )  # Log errors briefly
                continue

    def lane_change_evaluate(self):
        pass

    def safety_criteria(self):
        """
        ttc and thw
        Feature: Safety Criteria (Safe = Expert)
        """
        for vehicle_id in self.valid_vehicles:
            try:
                driver_trajectory = (
                    self.filtered_data[self.filtered_data["id"] == vehicle_id]
                    .sort_values("frame")
                    .reset_index(drop=True)
                )

                # Calculate safety metrics
                self.critical_ttc_count = len(
                    driver_trajectory[
                        (driver_trajectory["ttc"] > 0)
                        & (driver_trajectory["ttc"] < MIN_TTC)
                    ]
                )  # TTC>0 = valid

                self.critical_thw_count = len(
                    driver_trajectory[
                        (driver_trajectory["thw"] > 0)
                        & (driver_trajectory["thw"] < MIN_THW)
                    ]
                )

                self.assess_results[vehicle_id][
                    "critical_ttc_count"
                ] = self.critical_ttc_count
                self.assess_results[vehicle_id][
                    "critical_thw_count"
                ] = self.critical_thw_count

            except Exception as e:
                self.failed_vehicles.append(
                    (int(vehicle_id), str(e)[:200])
                )  # Log errors briefly
                continue

    def speed_compliance(self):
        pass

    def sight_clarity(self):
        pass


if __name__ == "__main__":
    # Example usage
    tracks_data_path = "/mnt/sdb/datasets/highd-dataset-v1.0/data/01_tracks.csv"
    tracks_metadata_path = "/mnt/sdb/datasets/highd-dataset-v1.0/data/01_tracksMeta.csv"
    recording_metadata_path = (
        "/mnt/sdb/datasets/highd-dataset-v1.0/data/01_recordingMeta.csv"
    )

    skill_assessment = SkillAssessment(
        tracks_data_path, tracks_metadata_path, recording_metadata_path
    )
    skill_assessment.check_input_data()
    skill_assessment.kinematic_stability()
    skill_assessment.lane_center_deviation()
    skill_assessment.following_stability()
    skill_assessment.harsh_maneuver_frequency()
    skill_assessment.lane_change_frequency()
    skill_assessment.safety_criteria()
    skill_assessment.assess(tracks_data_path, expert_threshold=5)
