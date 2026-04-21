import os
from collections import defaultdict

import numpy as np
import pandas as pd

from fine_tuning.data_prepared.utils.dataloader import HighDataLoder

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


class SkillAssessment(HighDataLoder):
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
        super().__init__(
            tracks_data_path,
            tracks_metadata_path,
            recording_metadata_path,
            build_lookups,
            filtering,
        )
        self.assess_results = defaultdict(dict)
        self.skilled_drivers = defaultdict(list)

    def assess(self, expert_threshold=6):
        # --------------------------
        # Classify Driver Skill (Expert/Novice)
        # --------------------------
        assessment_results = defaultdict(list)

        for vehicle_id, metrics in self.assess_results.items():
            speed_std = metrics.get("speed_std", np.inf)
            acc_std = metrics.get("acc_std", np.inf)
            jerk_mean = metrics.get("jerk_mean", np.inf)
            lane_deviation = metrics.get("lane_deviation_mean", np.inf)
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
            assessment_results["speed_std"].append(speed_std)
            assessment_results["acc_std"].append(acc_std)
            assessment_results["jerk_mean"].append(jerk_mean)
            assessment_results["lane_deviation_mean"].append(lane_deviation)
            assessment_results["follow_dist_mean"].append(follow_dist_mean)
            assessment_results["harsh_freq"].append(harsh_freq)
            assessment_results["lane_change_freq"].append(lane_change_freq)
            assessment_results["critical_ttc_count"].append(critical_ttc_count)
            assessment_results["critical_thw_count"].append(critical_thw_count)

        file_name = (
            os.path.basename(self.tracks_data_path).split(".csv")[0]
            + "_skill_level.csv"
        )
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        skill_level_csv_file_loc = os.path.join(
            cur_dir, "generation_results", f"{file_name}"
        )
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
                self.assess_results[vehicle_id]["acc_std"] = self.acc_std
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
                    "lane_deviation_mean"
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
                    (driver_trajectory["acceleration"] > HARD_ACCEL).sum()
                ) + ((driver_trajectory["acceleration"] < HARD_BRAKE).sum())

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
        """
        Lane Change Quality
        Feature: Lane Change Quality (Smooth = Expert)

        lateral acceleration during lane change should be moderate and not too high (comfortable)
        longitudinal acceleration during lane change should not be harsh braking or acceleration (comfortable)
        enough gap with front and rear vehicles in the target lane (safety)
        avoid lane weaving (safety)
        avoid lane changes in dense traffic (safety)
        less redundant lane changes (efficiency)
        """
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
        """
        Speed Compliance
        Feature: Speed Compliance (Compliant = Expert)

        Consistently adhering to speed limits and avoiding excessive speeding can indicate a more responsible and experienced driver
        , while frequent speeding may suggest a less skilled or more aggressive driver.
        """
        pass

    def sight_clarity(self):
        """
        Sight Clarity
        Feature: Sight Clarity (Clear = Expert)

        Maintaining clear sightlines (e.g., not following too closely, avoiding blind spots) can indicate safer
        and more skilled driving, while poor sightlines may suggest inexperience or riskier behavior.
        """
        pass


if __name__ == "__main__":
    root_dir = "/mnt/sdb/datasets/highd-dataset-v1.0/data"
    root_dir = "~/Documents/data/highd-dataset-v1.0/data"

    # Example usage
    tracks_data_path = os.path.join(root_dir, "01_tracks.csv")
    tracks_metadata_path = os.path.join(root_dir, "01_tracksMeta.csv")
    recording_metadata_path = os.path.join(root_dir, "01_recordingMeta.csv")

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
    skill_assessment.assess(expert_threshold=5)
