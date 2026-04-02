import os

from skill_assess import SkillAssessment

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
def driving_skill_assessment():
    """
    call skill_assess.py to evaluate driver skill levels based on highD data.
    Outputs: driver_skill_assessment.csv with skill scores and categories.
    """
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
    skill_assessment.assess(tracks_data_path)


def skilled_data_generation():
    """
    call clips_generate.py to generate lane change and lane keeping clips by skilled drivers.
    Outputs: clips for data extraction.
    """
    pass


def fine_tuning_data_generation():
    pass


def get_file_number_list():
    number_list = []
    return number_list


if __name__ == "__main__":
    number_list = get_file_number_list()
    for number in number_list:
        tracks_data_path = "/mnt/sdb/datasets/highd-dataset-v1.0/data/01_tracks.csv"
        tracks_metadata_path = (
            "/mnt/sdb/datasets/highd-dataset-v1.0/data/01_tracksMeta.csv"
        )
        recording_metadata_path = (
            "/mnt/sdb/datasets/highd-dataset-v1.0/data/01_recordingMeta.csv"
        )

        # 1st step, get skill level results
        

        # 2nd step, get skilled data

        # 3rd step, get fine tuning data
