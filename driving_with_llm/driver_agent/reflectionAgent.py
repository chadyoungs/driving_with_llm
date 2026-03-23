import os
import textwrap
import time
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langchain_ollama import ChatOllama
from langchain.messages import HumanMessage, SystemMessage

from rich import print


class ReflectionAgent:
    def __init__(
        self, temperature: float = 0.0, verbose: bool = False
    ) -> None:
        self.llm = ChatOllama(
            model=os.getenv("OPENAI_CHAT_MODEL"),
            keep_alive="30m",
            temperature=temperature,
            max_tokens=2000,
            request_timeout=60,
        )

    def reflection(self, human_message: str, llm_response: str) -> str:
        delimiter = "####"
        system_message = textwrap.dedent(f"""\
        You are a multi-modal large language model, you can see and think. Now you act as a mature driving assistant, who can give accurate and correct advice for human driver in complex urban driving scenarios.
        You will be given a detailed description of the driving scenario of current frame along with the available actions allowed to take. 

        Your response should use the following format:
        <reasoning>
        <reasoning>
        <repeat until you have a decision>
        Response to user:{delimiter} <only output one `Action_id` as a int number of you decision, without any action name or explanation. The output decision must be unique and not ambiguous, for example if you decide to decelearate, then output `4`> 

        Make sure to include {delimiter} to separate every step.
        """)
        human_message = textwrap.dedent(f"""\
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
        """)

        print("Self-reflection is running, make take time...")
        start_time = time.time()
        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=human_message),
        ]
        response = self.llm.invoke(messages)
        target_phrase = f"{delimiter} What should LLM do to avoid such errors in the future:"
        substring = response.content[response.content.find(
            target_phrase)+len(target_phrase):].strip()
        corrected_memory = f"{delimiter} I have made a misake before and below is my self-reflection:\n{substring}"
        print("Reflection done. Time taken: {:.2f}s".format(
            time.time() - start_time))
        print("corrected_memory:", corrected_memory)

        return corrected_memory
