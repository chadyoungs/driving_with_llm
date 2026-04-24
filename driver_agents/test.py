import pytest
from agents import DriverAgent

def test_format_human_prompt_all_keys_present():
    vehicle_dict = {
        "preceding": [[1,2,3,4,5,6,7]]*6,
        "following": [[8,9,10,11,12,13,14]]*6,
        "left_preceding": [[15,16,17,18,19,20,21]]*6,
        "left_alongside": [[22,23,24,25,26,27,28]]*6,
        "left_following": [[29,30,31,32,33,34,35]]*6,
        "right_preceding": [[36,37,38,39,40,41,42]]*6,
        "right_alongside": [[43,44,45,46,47,48,49]]*6,
        "right_following": [[50,51,52,53,54,55,56]]*6,
        "left_allowed": True,
        "right_allowed": False,
    }
    agent = DriverAgent(llm=None, vehicle_dict=vehicle_dict)
    prompt = agent.format_human_prompt()
    assert "preceding: [1, 2, 3, 4, 5, 6, 7],[1, 2, 3, 4, 5, 6, 7],[1, 2, 3, 4, 5, 6, 7],[1, 2, 3, 4, 5, 6, 7],[1, 2, 3, 4, 5, 6, 7],[1, 2, 3, 4, 5, 6, 7]" in prompt
    assert "Left lane change is allowed: True" in prompt
    assert "Right lane change is allowed: False" in prompt

def test_format_human_prompt_missing_keys_and_bad_frames():
    vehicle_dict = {
        "preceding": [[1,2,3,4,5,6,7]]*6,
        # "following" missing
        "left_preceding": [[1,2,3,4,5,6]],  # bad frame (len 6, not 7)
        "left_alongside": [],  # empty
        "left_following": None,  # None
        "right_preceding": [[1,2,3,4,5,6,7]]*5,  # only 5 frames
        "right_alongside": [[1,2,3,4,5,6,7]]*6,
        "right_following": [[1,2,3,4,5,6,7]]*6,
        "left_allowed": False,
        "right_allowed": True,
    }
    agent = DriverAgent(llm=None, vehicle_dict=vehicle_dict)
    prompt = agent.format_human_prompt()
    # following, left_alongside, left_following, right_preceding should be filled with EMPTY
    EMPTY = "[999, 999, 0, 0, 0, 999, 999]"
    assert "following: " + ",".join([EMPTY]*6) in prompt
    assert "left_alongside: " + ",".join([EMPTY]*6) in prompt
    assert "left_following: " + ",".join([EMPTY]*6) in prompt
    assert "right_preceding: " + ",".join([EMPTY]*6) in prompt
    assert "Left lane change is allowed: False" in prompt
    assert "Right lane change is allowed: True" in prompt

def test_format_human_prompt_default_vehicle_dict():
    agent = DriverAgent(llm=None, vehicle_dict={})
    prompt = agent.format_human_prompt()
    EMPTY = "[999, 999, 0, 0, 0, 999, 999]"
    for key in [
        "preceding", "following", "left_preceding", "left_alongside", "left_following",
        "right_preceding", "right_alongside", "right_following"
    ]:
        assert f"{key}: " + ",".join([EMPTY]*6) in prompt
    assert "Left lane change is allowed: False" in prompt
    assert "Right lane change is allowed: False" in prompt

# To run the tests easily, just run:
# pytest driver_agents/test_agents.py