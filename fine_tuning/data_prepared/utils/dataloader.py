from collections import defaultdict

import pandas as pd


class HighDataLoder(object):
    def __init__(
        self,
        tracks_data_path,
        tracks_metadata_path,
        recording_metadata_path,
        build_lookups=True,
        filtering=True,
    ):
        self._failed_vehicles = []

        try:
            # Load tracks (vehicle trajectory data)
            self.tracks_data_path = tracks_data_path
            self.tracks_df = pd.read_csv(self.tracks_data_path)
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
