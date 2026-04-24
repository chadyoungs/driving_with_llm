import base64
import json
import os
import sqlite3
import textwrap
import time
from typing import List

from langchain.messages import AIMessage, HumanMessage, SystemMessage


from rich import print

#from scenario.envScenario import EnvScenario

ACTION_MAP = {
    "accelerate": 3,
    "decelerate": 4,
    "keep": 1,
    "left_lane_change": 0,
    "right_lane_change": 2,
}

example_answer = textwrap.dedent(
    f"""\
        Well, I have 5 actions to choose from. Now, I would like to know which action is possible. 
        I should first check if I can acceleration, then idle, finally decelerate.  I can also try to change lanes but with caution and not too frequently.

        - I want to know if I can accelerate, so I need to observe the car in front of me on the current lane, which is car `912`. The distance between me and car `912` is 382.33 - 363.14 = 19.19 m, and the difference in speed is 23.30 - 25.00 = -1.7 m/s. Car `912` is traveling 19.19 m ahead of me and its speed is 1.7 m/s slower than mine. This distance is too close and my speed is too high, so I should not accelerate.
        - Since I cannot accelerate, I want to know if I can maintain my current speed. I need to observe the car in front of me on the current lane, which is car `912`. The distance between me and car `912` is 382.33 - 363.14 = 19.19 m, and the difference in speed is 23.30 - 25.00 = -1.7 m/s. Car `912` is traveling 19.19 m ahead of me and its speed is 1.7 m/s slower than mine. This distance is too close and my speed is too high, so if I maintain my current speed, I may collide with it.
        - Maintain my current speed is not a good idea, so I can only decelearate to keep me safe on my current lane. Deceleraion is a feasible action.
        - Besides decelearation, I can also try to change lanes. I should carefully check the distance and speed of the cars in front of me on the left and right lanes. Noted that change-lane is not a frequent action, so I should not change lanes too frequently.
        - I first try to change lanes to the left. The car in front of me on the left lane is car `488`. The distance between me and car `488` is 368.75-363.14=5.61 m, and the difference in speed is 23.61 - 25.00=-1.39 m/s. Car `488` is traveling 5.61 m ahead of me and its speed is 1.39 m/s slower than mine. This distance is too close, the safety lane-change distance is 25m. Besides, my speed is higher than the front car on the left lane. If I change lane to the left, I may collide with it.                                           So I cannot change lanes to the left.
        - Now I want to see if I can change lanes to the right. The car in front of me on the right lane is car 864. The distance between me and car 864 is 373.74-363.14 = 10.6 m, and the difference in speed is 23.61-25.00=-3.7 m/s. Car 864 is traveling 10.6 m ahead of me and its speed is 3.7 m/s slower than mine. The distance is too close and my speed is higher than the front car on the right lane. the safety lane-change distance is 25m. if I change lanes to the right, I may collide with it. So I cannot change lanes to the right.
        - Now my only option is to slow down to keep me safe.
        Final Answer: Deceleration
                                         
        Response to user:#### 4
        """
)


class DriverAgent:
    def __init__(
        self,
        llm,
        vehicle_dict=None,
    ) -> None:
        self.vehicle_dict = vehicle_dict
        self.llm = llm

    def format_human_prompt(self) -> str:
        """
        Construct a Human Message that meets the requirements.
        vehicle_dict must contain these 8 keys, each corresponding to 6 timesteps, with each timestep having 7 values: [x, y, v, a, heading, TTC, PET].
        Keys:preceding, following, left_preceding, left_alongside, left_following,right_preceding, right_alongside, right_following
        If a vehicle is not present, pass None or an empty list, and the placeholder will be filled automatically.
        """
        EMPTY = [999, 999, 0, 0, 0, 999, 999]
        EMPTY_STR = str(EMPTY)

        keys = [
            "preceding",
            "following",
            "left_preceding",
            "left_alongside",
            "left_following",
            "right_preceding",
            "right_alongside",
            "right_following",
        ]

        lines = [
            "Surrounding vehicles 6-step sequential data (3s, 2Hz, origin = ego at 0s):",
            "Field order per step: [x_pos(m), y_pos(m), velocity(m/s), acceleration(m/s²), heading(rad), TTC(s), PET(s)]",
            "",
        ]

        for key in keys:
            frames = self.vehicle_dict.get(key, None)
            if not frames or len(frames) != 6:
                frame_strs = [EMPTY_STR] * 6
            else:
                frame_strs = [str(f) for f in frames]

            line = f"{key}: " + ",".join(frame_strs)
            lines.append(line)

        lines.append("")
        lines.append(
            "Left lane change is allowed: {left_allowed}".format(
                left_allowed=self.vehicle_dict.get("left_allowed", False)
            )
        )
        lines.append(
            "Right lane change is allowed: {right_allowed}".format(
                right_allowed=self.vehicle_dict.get("right_allowed", False)
            )
        )
        lines.append("Do NOT change lanes if the target lane does not exist.")
        lines.append(
            "Reason about safety and traffic flow, Only choose actions that are safe and allowed by road network, then output only: action x1 y1 x2 y2 x3 y3 x4 y4"
        )

        return "\n".join(lines)

    def few_shot_decision(
        self,
        scenario_description: str = "Not available",
        previous_decisions: str = "Not available",
        available_actions: str = "Not available",
        driving_intensions: str = "Not available",
        fewshot_messages: List[str] = None,
        fewshot_answers: List[str] = None,
    ):
        # for template usage refer to: https://python.langchain.com/docs/modules/model_io/prompts/prompt_templates/

        system_message = textwrap.dedent(
            f"""\
        You are a precise autonomous driving decision and trajectory planning agent on a highway.

        Driving objectives (in priority order):
        1. Safety   – avoid collisions; TTC < 3 s or PET < 2 s signals danger and must be resolved first.
        2. Efficiency – maintain smooth traffic flow; prefer higher safe speeds and minimise unnecessary slowdowns.
        3. Comfort  – avoid harsh acceleration or braking; keep inputs gradual and smooth.

        Input: 6-step sequential observations (3 s, 2 Hz) for 8 surrounding vehicles:
          preceding, following,
          left_preceding, left_alongside, left_following,
          right_preceding, right_alongside, right_following.

        Each step: [x_pos(m), y_pos(m), velocity(m/s), acceleration(m/s²), heading(rad), TTC(s), PET(s)]
        Coordinate origin is the ego vehicle position at t = 0 s.
        Missing vehicles are represented by the placeholder [999, 999, 0, 0, 0, 999, 999].

        Metric notes:
        - TTC (Time-To-Collision): longitudinal safety indicator; lower is more dangerous. 999 = no conflict.
        - PET (Post-Encroachment-Time): lateral safety indicator for alongside vehicles. 999 = no conflict.
        - For pure longitudinal pairs (preceding / following), PET = 999.

        Reason briefly about safety, efficiency, and comfort, then make a decision.
        Choose exactly ONE action from: accelerate, decelerate, keep, left_lane_change, right_lane_change.

        Predict the ego trajectory for the next 2 seconds at 2 Hz (4 points total).
        Output ONLY ONE line in the strict format below:
        action x1 y1 x2 y2 x3 y3 x4 y4

        where (x1,y1) to (x4,y4) are ego positions at 0.5 s, 1.0 s, 1.5 s and 2.0 s respectively.
        Do NOT output any extra text, explanation or comment.

        Example: keep 5.0 0.0 10.0 0.0 15.0 0.0 20.0 0.0
        """
        )

        human_message = self.format_human_prompt()

        if fewshot_messages is None:
            raise ValueError("fewshot_message is None")
        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=human_message),
            AIMessage(content=example_answer),
        ]
        for i in range(len(fewshot_messages)):
            messages.append(HumanMessage(content=fewshot_messages[i]))
            messages.append(AIMessage(content=fewshot_answers[i]))
        messages.append(HumanMessage(content=human_message))

        start_time = time.time()
        print("[cyan]Agent answer:[/cyan]")
        response_content = ""

        response = self.llm.invoke(messages)
        response_content = response.content

        print("\n")

        # Parse "action x1 y1 x2 y2 x3 y3 x4 y4" output format.
        response_line = response_content.strip().splitlines()[-1].strip()
        tokens = response_line.split()
        action_word = tokens[0].lower() if tokens else ""
        result = ACTION_MAP.get(action_word, -1)

        if result == -1:
            print("Output action not recognised, asking LLM to clarify...")
            check_message = (
                f"The autonomous driving agent returned: '{response_line}'\n"
                "Extract the intended action and reply with exactly one word from:\n"
                "  accelerate, decelerate, keep, left_lane_change, right_lane_change\n"
                "No other text."
            )
            messages = [HumanMessage(content=check_message)]
            check_response = self.llm.invoke(messages)
            print("Check response:", check_response.content)
            action_word = check_response.content.strip().lower()
            result = ACTION_MAP.get(action_word, 1)  # fall back to 'keep'

        few_shot_answers_store = ""
        for i in range(len(fewshot_messages)):
            few_shot_answers_store += fewshot_answers[i] + "\n---------------\n"
        print("Result:", result)
        return (
            result,
            response_content,
            human_message,
            few_shot_answers_store,
        )

'''
class OutputParser:
    def __init__(
        self,
        llm,
        sce: Scenario,
    ) -> None:
        self.sce = sce
        self.llm = llm

        self.response_schemas = [
            ResponseSchema(
                name="action_id",
                description=f"output the id(int) of the decision. The comparative table is:  {{ 0: 'change_lane_left', 1: 'keep_speed or idle', 2: 'change_lane_right', 3: 'accelerate or faster',4: 'decelerate or slower'}} . For example, if the ego car wants to keep speed, please output 1 as a int.",
            ),
            ResponseSchema(
                name="action_name",
                description=f"output the name(str) of the decision. MUST consist with previous \"action_id\". The comparative table is:  {{ 0: 'change_lane_left', 1: 'keep_speed', 2: 'change_lane_right', 3: 'accelerate',4: 'decelerate'}} . For example, if the action_id is 3, please output 'Accelerate' as a str.",
            ),
            ResponseSchema(
                name="explanation",
                description=f"Explain for the driver why you make such decision in 40 words.",
            ),
        ]
        self.output_parser = StructuredOutputParser.from_response_schemas(
            self.response_schemas
        )
        self.format_instructions = self.output_parser.get_format_instructions()

    def agentRun(self, final_results: dict) -> str:
        print("[green]Output parser is running...[/green]")
        prompt_template = ChatPromptTemplate(
            messages=[
                HumanMessagePromptTemplate.from_template(
                    "parse the problem response follow the format instruction.\nformat_instructions:{format_instructions}\n response: {answer}"
                )
            ],
            input_variables=["answer"],
            partial_variables={"format_instructions": self.format_instructions},
        )
        input = prompt_template.format_prompt(
            answer=final_results["answer"] + final_results["thoughts"]
        )

        output = self.llm.invoke(input.to_messages())

        self.parseredOutput = self.output_parser.parse(output.content)
        self.dataCommit()

        return self.parseredOutput

    def dataCommit(self):
        conn = sqlite3.connect(self.sce.database)
        cur = conn.cursor()
        parseredOutput = json.dumps(self.parseredOutput)
        base64Output = base64.b64encode(parseredOutput.encode("utf-8")).decode("utf-8")
        cur.execute(
            """UPDATE decisionINFO SET outputParser ='{}' WHERE frame ={};""".format(
                base64Output,
                self.sce.frame,
            )
        )
        conn.commit()
        conn.close()


class ReflectionAgent:
    def __init__(
        self,
        llm,
    ) -> None:
        self.llm = llm

    def reflection(
        self,
        human_message: str,
        llm_response: str,
    ) -> str:
        delimiter = "####"
        system_message = textwrap.dedent(
            f"""\
        You are a multi-modal large language model, you can see and think. Now you act as a mature driving assistant, who can give accurate and correct advice for human driver in complex urban driving scenarios.
        You will be given a detailed description of the driving scenario of current frame along with the available actions allowed to take. 

        Your response should use the following format:
        <reasoning>
        <reasoning>
        <repeat until you have a decision>
        Response to user:{delimiter} <only output one `Action_id` as a int number of you decision, without any action name or explanation. The output decision must be unique and not ambiguous, for example if you decide to decelearate, then output `4`> 

        Make sure to include {delimiter} to separate every step.
        """
        )
        human_message = textwrap.dedent(
            f"""\
            ``` Human Message ```
            {human_message}
            ``` LLM Response ```
            {llm_response}

            Now, you know this action LLM output cause a collison after taking this action, which means there are some mistake in LLM resoning and cause the wrong action.    
            Please carefully check every reasoning in LLM response and find out the mistake in the reasoning process of LLM, and also output your corrected version of LLM response.
            Your answer should use the following format:
            {delimiter} Analysis of the mistake:
            <Your analysis of the mistake in LLM reasoning process>
            {delimiter} What should LLM do to avoid such errors in the future:
            <Your answer>
            {delimiter} Corrected version of LLM response:
            <Your corrected version of LLM response>
        """
        )

        print("Self-reflection is running, make take time...")
        start_time = time.time()
        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=human_message),
        ]
        response = self.llm.invoke(messages)
        target_phrase = (
            f"{delimiter} What should LLM do to avoid such errors in the future:"
        )
        substring = response.content[
            response.content.find(target_phrase) + len(target_phrase) :
        ].strip()
        corrected_memory = f"{delimiter} I have made a misake before and below is my self-reflection:\n{substring}"
        print("Reflection done. Time taken: {:.2f}s".format(time.time() - start_time))
        print(
            "corrected_memory:",
            corrected_memory,
        )

        return corrected_memory
'''