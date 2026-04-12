import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent.parent.parent

sys.path.append(str(ROOT))
import warnings

from fine_tuning.data_prepared.utils.dataloader import HighDataLoder

warnings.filterwarnings("ignore")


class DataGenerator(HighDataLoder):
    def __init__(self, tracks_data_path, tracks_metadata_path, recording_metadata_path):
        super().__init__(
            tracks_data_path, tracks_metadata_path, recording_metadata_path
        )
        self._lane_change_vehicles = []
        self._lane_change_vehicles_info = defaultdict(dict)
        self._lane_keeping_vehicles = []
        self._clip_analysis_results = defaultdict(dict)
        self.generated_data = defaultdict(dict)

    @property
    def lane_change_vehicles_info(self):
        def detect_lane_changes(arr):
            diff = arr[:-1] != arr[1:]
            change_indices = np.where(diff)[0] + 1
            return change_indices

        for vehicle_id in self.lane_change_vehicles:
            lane_ids = self.tracks_df[self.tracks_df["id"] == vehicle_id][
                "laneId"
            ].values
            change_indices = detect_lane_changes(np.array(lane_ids))
            # Store the results
            self._lane_change_vehicles_info[vehicle_id]["change_indice"] = (
                change_indices[0]
            )

            if (
                self.tracks_meta_df[self.tracks_meta_df["id"] == vehicle_id][
                    "drivingDirection"
                ].values[0]
                == 2
            ):
                drive_direction = (
                    "left_lane_change"
                    if lane_ids[change_indices[0]] < lane_ids[change_indices[0] - 1]
                    else "right_lane_change"
                )
            else:
                drive_direction = (
                    "right_lane_change"
                    if lane_ids[change_indices[0]] < lane_ids[change_indices[0] - 1]
                    else "left_lane_change"
                )
            self._lane_change_vehicles_info[vehicle_id][
                "change_direction"
            ] = drive_direction

        return self._lane_change_vehicles_info

    @property
    def lane_change_vehicles(self):
        # lane change for once time in the track
        self._lane_change_vehicles = self.tracks_meta_df[
            (self.tracks_meta_df["id"].isin(self.valid_vehicles))
            & (self.tracks_meta_df["numLaneChanges"] == 1)
        ]["id"].unique()

        return self._lane_change_vehicles

    @property
    def lane_keeping_vehicles(self):
        self._lane_keeping_vehicles = self.tracks_meta_df[
            (self.tracks_meta_df["id"].isin(self.valid_vehicles))
            & (self.tracks_meta_df["numLaneChanges"] == 0)
        ]["id"].unique()

        return self._lane_keeping_vehicles

    def get_lane_change_clips(self):
        """
        Generate lane change clips based on highD data.
        Outputs: lane_change_clips.csv with clip start/end frames, lane change type, etc.
        """
        for vehicle_id in self.lane_change_vehicles_info.keys():
            try:
                # Get all trajectory data for the current driver (sorted by time)
                driver_trajectory = (
                    self.filtered_data[self.filtered_data["id"] == vehicle_id]
                    .sort_values("frame")
                    .reset_index(drop=True)
                )
                change_index = self.lane_change_vehicles_info[vehicle_id][
                    "change_indice"
                ]
                change_direction = self.lane_change_vehicles_info[vehicle_id][
                    "change_direction"
                ]

                # get the previous 3 seconds and the following 3 seconds data of the lane change
                driver_clip = driver_trajectory.iloc[
                    change_index
                    - 3 * self.frame_rate : change_index
                    + 3 * self.frame_rate
                ]
                analysis_res = self.clip_analysis(
                    driver_clip, vehicle_id, change_direction
                )
                res = self.save_clip(analysis_res)
                self.generated_data[vehicle_id] = res

            except Exception as e:
                print(f"Error processing lane change vehicle {vehicle_id}: {e}")

    def get_lane_keeping_clips(self):
        """
        Generate lane keeping clips based on highD data.
        Outputs: lane_keeping_clips.csv with clip start/end frames, lane deviation, etc.
        """
        for vehicle_id in self.lane_keeping_vehicles:
            try:
                # Get all trajectory data for the current driver (sorted by time)
                driver_trajectory = (
                    self.filtered_data[self.filtered_data["id"] == vehicle_id]
                    .sort_values("frame")
                    .reset_index(drop=True)
                )
                # get the middle 6 seconds data of the lane keeping
                duration = len(driver_trajectory)
                driver_clip = driver_trajectory.iloc[
                    duration // 2
                    - 3 * self.frame_rate : duration // 2
                    + 3 * self.frame_rate
                ]
                print(driver_clip)
                import pdb
                pdb.set_trace()
                analysis_res = self.clip_analysis(driver_clip, vehicle_id, None)
                res = self.save_clip(analysis_res)
                self.generated_data[vehicle_id] = res

            except Exception as e:
                print(f"Error processing lane keeping vehicle {vehicle_id}: {e}")

    def clip_analysis(self, driver_clip, vehicle_id, change_direction):
        """
        Analyze trajectory data to extract features for lane change and lane keeping clips,
        using 0.5 seconds window to simplify the trajectory data.
        Outputs: trajectory_analysis.csv with features like speed, acceleration, lane deviation, etc.
        """

        if change_direction == "left_lane_change":
            lane_change_type = "left"
        elif change_direction == "right_lane_change":
            lane_change_type = "right"
        else:
            lane_change_type = "lane_keeping"

    def save_clip(self, analysis_res):
        """
        Save generated clips and analysis results to CSV files.
        """
        pass


if __name__ == "__main__":
    """
    Main function to orchestrate the data generation process:
    1. Load highD dataset and perform driver skill assessment to classify drivers into skilled and unskilled categories.
    2. Generate lane change and lane keeping clips for skilled drivers based on the assessment results.
    3. Process the generated clips to extract relevant features and create a structured dataset suitable for fine-tuning LLM models.
    """
    root_dir = "/mnt/sdb/datasets/highd-dataset-v1.0/data"
    root_dir = "~/Documents/data/highd-dataset-v1.0/data"

    # Example usage
    tracks_data_path = os.path.join(root_dir, "01_tracks.csv")
    tracks_metadata_path = os.path.join(root_dir, "01_tracksMeta.csv")
    recording_metadata_path = os.path.join(root_dir, "01_recordingMeta.csv")

    data_generator = DataGenerator(
        tracks_data_path, tracks_metadata_path, recording_metadata_path
    )
    data_generator.get_lane_change_clips()
    data_generator.get_lane_keeping_clips()
