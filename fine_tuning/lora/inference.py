import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

# 配置
BASE_MODEL = "Qwen/Qwen3.5-0.8B-Instruct"
LORA_MODEL = "./qwen35_driver_agent_lora"  # 微调后的LoRA路径
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# 加载基座模型和Tokenizer
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL, device_map="auto", trust_remote_code=True, torch_dtype=torch.bfloat16
)

# 加载LoRA权重
model = PeftModel.from_pretrained(model, LORA_MODEL)
model.eval()  # 推理模式

# 测试Prompt（仅场景，无规则）
prompt = """<|im_start|>user
场景：4车道左数第3车道，你的位置356.83m、车速25m/s，同车道前车32号位置421.83m、车速23.27m/s，左车道984号位置431.02m、车速21.62m/s，右车道792号位置450.83m、车速21.17m/s。请输出Action_id，格式为#### X。
<|im_end|>
<|im_start|>assistant"""

# 推理
with torch.no_grad():
    inputs = tokenizer(prompt, return_tensors="pt").to(DEVICE)
    outputs = model.generate(
        **inputs,
        max_new_tokens=10,  # 仅输出Action_id，足够
        temperature=0.01,  # 0.01=确定性输出，无随机性
        top_p=0.1,
        do_sample=False,
        eos_token_id=tokenizer.eos_token_id,
    )
    response = tokenizer.decode(outputs[0], skip_special_tokens=False)
    # 提取Action_id
    action_id = response.split("####")[-1].strip().split("\n")[0]
    print(f"📌 Driver Agent决策：Action_id = {action_id}")

# 预期输出：📌 Driver Agent决策：Action_id = 4
