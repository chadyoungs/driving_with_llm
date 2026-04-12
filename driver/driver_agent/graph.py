# This module merges driveragent.py, outputagent.py, and reflectionagent.py into a LangGraph workflow.
# driver_agent: makes driving decisions
# output_agent: checks the output of driver_agent
# reflection_agent: reflects on the output of output_agent

# coding: utf-8
from typing import TypedDict
from langgraph.graph import StateGraph, END
import sys
import os
from driveragent import driver_agent
from outputagent import output_agent
from reflectionagent import reflection_agent

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# ==========================
# 1. 定义全局状态（你必须统一）
# ==========================
class AgentState(TypedDict):
    user_query: str
    observation: str       # 观测（感知信息）
    decision: str           # Driver 输出
    thought: str            # 思考
    feedback: str           # Reflection 反馈
    is_safe: bool           # 是否安全
    revised_decision: str   # 修正后决策
    final_output: str       # Output 最终输出

# ==========================
# 2. 你自己的三个 Agent（你把你的函数贴这里）
# ==========================
def driver_agent(state: AgentState):
    # 你的 Driver 逻辑
    decision = "车辆保持车道，速度60km/h"
    thought = "前方无障碍物，正常行驶"
    return {"decision": decision, "thought": thought}

def reflection_agent(state: AgentState):
    # 你的反思检查
    feedback = "决策安全"
    is_safe = True
    revised_decision = state["decision"]
    return {"feedback": feedback, "is_safe": is_safe, "revised_decision": revised_decision}

def output_agent(state: AgentState):
    # 你的格式化输出
    final_output = {
        "action": state["revised_decision"],
        "status": "safe" if state["is_safe"] else "unsafe"
    }
    return {"final_output": str(final_output)}

# ==========================
# 3. 路由条件（是否回到 Driver）
# ==========================
def should_redirect_to_driver(state: AgentState):
    if not state["is_safe"]:
        return "driver"  # 不安全，回去重决策
    return "output"      # 安全，去输出

# ==========================
# 4. 构建 LangGraph 流程
# ==========================
workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("driver", driver_agent)
workflow.add_node("reflect", reflection_agent)
workflow.add_node("output", output_agent)

# 入口
workflow.set_entry_point("driver")

# 连接边
workflow.add_edge("driver", "reflect")

# 条件边（核心！）
workflow.add_conditional_edges(
    "reflect",
    should_redirect_to_driver,
    {
        "driver": "driver",
        "output": "output"
    }
)

workflow.add_edge("output", END)

# 编译
agent = workflow.compile()

# ==========================
# 运行
# ==========================
if __name__ == "__main__":
    res = agent.invoke({
        "user_query": "在城市道路行驶",
        "observation": "前方无车，车道线清晰",
        "decision": "",
        "feedback": "",
        "is_safe": False,
        "final_output": ""
    })
    print(res["final_output"])