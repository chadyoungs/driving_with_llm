"""
To visualize the highD dataset on its highway image,
create a script that loads the dataset, processes the vehicle trajectories,
and overlays them onto the background image.
The visualization will include lane boundaries, vehicle positions,
and relevant metrics like speed and time-to-collision (TTC).
"""

import math
import warnings

import cv2
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


def scale(x):

    return x / 0.4024


# --------------------------
# Step 1: Load Data & Prepare Image
# --------------------------
def load_data_and_image(
    tracks_path, tracks_meta_path, recording_meta_path, bg_image_path
):
    """Load highD data and background image"""
    # Load core data
    tracks_df = pd.read_csv(tracks_path)
    tracks_meta_df = pd.read_csv(tracks_meta_path)
    recording_meta_df = pd.read_csv(recording_meta_path)

    tracks_df = tracks_df.merge(
        tracks_meta_df[["id", "class"]], on="id", how="left"
    )  # Add vehicle dimensions and class
    # Load your background image
    bg_image = cv2.imread(bg_image_path)
    if bg_image is None:
        raise ValueError(f"Could not load background image from {bg_image_path}")

    # Get image dimensions
    img_height, img_width = bg_image.shape[:2]
    print(f"✅ Loaded background image: {img_width}x{img_height}")

    upper_lane_markings = recording_meta_df["upperLaneMarkings"].iloc[0]
    lower_lane_markings = recording_meta_df["lowerLaneMarkings"].iloc[0]

    lane_y_positions = []
    for i in [upper_lane_markings, lower_lane_markings]:
        lane_y_positions.extend([float(pos) for pos in i.split(";")])

    frame_rate = recording_meta_df["frameRate"].iloc[0]
    print(f"✅ Recording frame rate: {frame_rate} fps")

    return tracks_df, tracks_meta_df, bg_image, lane_y_positions, frame_rate


# --------------------------
# Step 2: Visualization on Image
# --------------------------
def visualize_on_your_image(
    tracks_path, tracks_meta_path, recording_meta_path, bg_image_path
):
    # Load data and image
    tracks_df, tracks_meta_df, bg_image, lane_y_positions, frame_rate = (
        load_data_and_image(
            tracks_path, tracks_meta_path, recording_meta_path, bg_image_path
        )
    )

    # Get image dimensions
    img_height, img_width = bg_image.shape[:2]

    # Get all frames
    all_frames = sorted(tracks_df["frame"].unique())
    frame_delay = int(1000 / frame_rate)  # Convert frame rate to delay in ms

    # Create window
    cv2.namedWindow("HighD Visualization on Highway Image", cv2.WINDOW_NORMAL)

    # --------------------------
    # Animate frame by frame
    # --------------------------
    for frame_num in all_frames:
        # Copy background image (reset for each frame)
        frame_image = bg_image.copy()

        # Get all vehicles in current frame
        frame_vehicles = tracks_df[tracks_df["frame"] == frame_num]

        # --------------------------
        # Draw lane boundaries (white lines)
        # --------------------------
        for lane_y in lane_y_positions:
            cv2.line(
                frame_image,
                (0, int(scale(lane_y))),
                (img_width, int(scale(lane_y))),
                (255, 255, 255),
                1,
            )

        # --------------------------
        # Draw each vehicle
        # --------------------------
        for _, vehicle in frame_vehicles.iterrows():
            # Get vehicle data
            veh_id = int(vehicle["id"])
            x = vehicle["x"]
            y = vehicle["y"]

            length = vehicle["width"]
            width = vehicle["height"]

            vehicle_type = vehicle["class"]
            speed = math.sqrt(
                vehicle["xVelocity"] ** 2 + vehicle["yVelocity"] ** 2
            )  # m/s → km/h
            ttc = vehicle["ttc"] if vehicle["ttc"] > 0 else "N/A"

            # Define vehicle color
            color = (0, 255, 0)  # Green = Expert, Red = Novice
            outline_color = (
                (0, 255, 255) if vehicle_type == "Truck" else color
            )  # Yellow for trucks

            # Draw vehicle as a rectangle (scaled to image)
            top_left = (int(scale(x)), int(scale(y)))
            bottom_right = (int(scale(x + length)), int(scale(y + width)))

            # Draw filled vehicle
            cv2.rectangle(frame_image, top_left, bottom_right, color, -1)
            # Draw outline
            cv2.rectangle(frame_image, top_left, bottom_right, outline_color, 2)

            # Draw speed/TTC
            metric_text = f"Speed: {speed:.0f}km/h | TTC: {ttc}s"
            cv2.putText(
                frame_image,
                metric_text,
                (int(scale(x)), int(scale(y + width / 2)) + 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.25,
                (255, 255, 255),
                1,
            )

        # --------------------------
        # Draw frame info
        # --------------------------
        frame_info = f"Frame: {frame_num} | Time: {frame_num * 0.1:.1f}s | Vehicles: {len(frame_vehicles)}"
        cv2.putText(
            frame_image,
            frame_info,
            (20, 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.3,
            (0, 255, 255),
            1,
        )

        # --------------------------
        # Display frame
        # --------------------------
        cv2.imshow("HighD Visualization on Highway Image", frame_image)

        # Controls: 'q' to quit, 'space' to pause
        key = cv2.waitKey(frame_delay) & 0xFF
        if key == ord("q"):
            break
        elif key == ord(" "):
            while True:
                pause_key = cv2.waitKey(0) & 0xFF
                if pause_key == ord(" "):
                    break
                elif pause_key == ord("q"):
                    cv2.destroyAllWindows()
                    return

    # Cleanup
    cv2.destroyAllWindows()
    print("✅ Animation completed!")


if __name__ == "__main__":
    TRACKS_PATH = "/mnt/sdb/datasets/highd-dataset-v1.0/data/01_tracks.csv"
    TRACKS_META_PATH = "/mnt/sdb/datasets/highd-dataset-v1.0/data/01_tracksMeta.csv"
    RECORDING_META_PATH = (
        "/mnt/sdb/datasets/highd-dataset-v1.0/data/01_recordingMeta.csv"
    )

    BACKGROUND_IMAGE_PATH = "/mnt/sdb/datasets/highd-dataset-v1.0/data/01_highway.png"  # Path to your provided image

    try:
        visualize_on_your_image(
            tracks_path=TRACKS_PATH,
            tracks_meta_path=TRACKS_META_PATH,
            recording_meta_path=RECORDING_META_PATH,
            bg_image_path=BACKGROUND_IMAGE_PATH,
        )
    except Exception as e:
        print(f"❌ Error: {str(e)}")
