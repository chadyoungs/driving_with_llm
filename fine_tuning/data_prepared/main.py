import argparse
import os
from glob import glob

from fine_tuning.data_prepared.utils.skill_assess import SkillAssessment

"""
   This script is for generating fine-tuning data for lane change and 
   lane keeping tasks based on the highD dataset.
   The process includes three main steps:
   1.   Driving Skill Assessment: Evaluating driver skill levels using the 
        skill_assess.py script, which analyzes various driving metrics to 
        categorize drivers into different skill levels.
   2.   Skilled Data Generation: Using the clips_generate.py script to extract
        lane change and lane keeping clips from the highD dataset, specifically 
        focusing on clips from skilled drivers identified in the previous step.
   3.   Fine-tuning Data Generation: Processing the extracted clips to create a 
        structured dataset suitable for fine-tuning LLM models for lane change and 
        lane keeping tasks. This involve labeling the data, balancing the dataset, 
        and ensuring it is in the correct format for training. 
   3.1  Data Labeling: Annotating the extracted clips with relevant labels such as
        lane change type (left lane change, right lane change), lane keeping status
        (accelerate, decelerate).
   3.2  Data Balancing: Ensuring that the dataset has a balanced representation of
        different classes (e.g., lane change vs. lane keeping, skilled vs. unskilled drivers) to prevent bias during model training.
   3.3  Data Formatting: Converting the processed data into a format suitable for input into LLM models, such as JSON or CSV, with appropriate feature engineering to enhance model performance.
"""


def argument_parser():
    args = argparse.ArgumentParser(
        description="Generate fine-tuning data for lane change and lane keeping tasks based on the highD dataset."
    )
    args.add_argument(
        "--data_split",
        type=str,
        choices=["train", "test"],
        default="train",
        help="Specify whether to generate training or testing data.",
    )

    return args


def driving_skill_assessment(
    tracks_data_path, tracks_metadata_path, recording_metadata_path
):
    """
    call skill_assess.py to evaluate driver skill levels based on highD data.
    Outputs: driver_skill_assessment.csv with skill scores and categories.
    """
    skill_assessment = SkillAssessment(
        tracks_data_path, tracks_metadata_path, recording_metadata_path
    )
    skill_assessment.check_input_data()
    # speed_std, acc_std, jerk_mean_for_largest_values
    skill_assessment.kinematic_stability()
    # lane_deviation_mean
    skill_assessment.lane_center_deviation()
    # follow_dist_mean
    skill_assessment.following_stability()
    # harsh_maneuver_frequency
    skill_assessment.harsh_maneuver_frequency()
    # lane_change_frequency
    skill_assessment.lane_change_frequency()
    # crtical ttc and thw counts
    skill_assessment.safety_criteria()
    # overall skill assessment and classification
    skill_assessment.assess(expert_threshold=5)


def skilled_data_generation(
    tarcks_data_path, tracks_metadata_path, recording_metadata_path
):
    """
    call clips_generate.py to generate lane change and lane keeping clips by skilled drivers.
    process the generated clips and create a structured dataset for fine-tuning LLM models.
    Outputs: structured dataset suitable for fine-tuning LLM models.
    """
    pass


def get_raw_files():
    raw_files = glob("/mnt/sdb/datasets/highd-dataset-v1.0/data/*_tracks.csv")
    raw_files = sorted(raw_files, key=lambda x: int(os.path.basename(x).split("_")[0]))

    return raw_files


if __name__ == "__main__":
    args = argument_parser().parse_args()
    data_split = args.data_split

    raw_tracks_files = get_raw_files()
    if data_split == "train":
        raw_tracks_files_train = raw_tracks_files[: int(0.8 * len(raw_tracks_files))]
    elif data_split == "test":
        raw_tracks_files_test = raw_tracks_files[int(0.8 * len(raw_tracks_files)) :]
    else:
        raise ValueError("Invalid data split. Choose 'train' or 'test'.")

    for tracks_data_path in raw_tracks_files_train:
        tracks_metadata_path = tracks_data_path.replace(
            "_tracks.csv", "_tracksMeta.csv"
        )
        recording_metadata_path = tracks_data_path.replace(
            "_tracks.csv", "_recordingMeta.csv"
        )

        # 1st step, get skill level results
        driving_skill_assessment(
            tracks_data_path, tracks_metadata_path, recording_metadata_path
        )

        # 2nd step, get fine tuning data
        skilled_data_generation(
            tracks_data_path, tracks_metadata_path, recording_metadata_path
        )
