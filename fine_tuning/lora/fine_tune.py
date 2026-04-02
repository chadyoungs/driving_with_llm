import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

# ====================== 1. 基础配置（根据你的路径修改） ======================
MODEL_NAME = "Qwen/Qwen3.5-0.8B-Instruct"  # 本地模型路径或HF仓库名
DATASET_PATH = "./driver_agent_dataset.jsonl"  # 数据集路径
LORA_SAVE_PATH = "./qwen35_driver_agent_lora"  # LoRA权重保存路径
OUTPUT_DIR = "./train_output"  # 训练日志/临时文件路径

# ====================== 2. 量化配置（8GB显存也能跑） ======================
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,  # 4-bit量化，显存占用仅0.8GB左右
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
)

# ====================== 3. 加载模型和Tokenizer ======================
# 加载Tokenizer（Qwen专属配置）
tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME, trust_remote_code=True, padding_side="right", use_fast=False
)
tokenizer.pad_token = tokenizer.eos_token  # 设置pad token

# 加载模型
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    quantization_config=bnb_config,
    device_map="auto",  # 自动分配到GPU/CPU
    trust_remote_code=True,
    torch_dtype=torch.bfloat16,
)
# 准备模型用于LoRA训练
model = prepare_model_for_kbit_training(model)

# ====================== 4. LoRA configuration（Qwen3.5-0.8B） ======================
lora_config = LoraConfig(
    r=8,  # rank，0.8B model -> 8
    lora_alpha=16,  # alpha=2*r，classical configuration
    target_modules=["q_proj", "v_proj"],  # Qwen kernel module
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)
# 绑定LoRA到模型
model = get_peft_model(model, lora_config)
# 打印可训练参数（仅LoRA参数，极少量）
model.print_trainable_parameters()  # 输出：trainable params: ~1M (总参0.8B，仅0.125%可训练)

# ====================== 5. 加载并处理数据集 ======================
# 加载JSONL数据集
dataset = load_dataset("json", data_files=DATASET_PATH, split="train")


# 数据格式化函数（适配Qwen指令格式）
def format_example(example):
    # Qwen Instruct格式：<|im_start|>system\n你是Driver Agent，严格遵守驾驶规则<|im_end|>\n<|im_start|>user\n{instruction}\n{input}<|im_end|>\n<|im_start|>assistant\n{output}<|im_end|>
    system_prompt = "你是Driver Agent，核心规则：1. 安全第一，与前车保持≥25米安全距离；2. 前车速度更低且距离不足时优先减速；3. 变道需满足目标车道前车距离≥25米；4. 输出格式为#### + Action_id。"
    user_prompt = (
        example["instruction"] + "\n" + (example["input"] if example["input"] else "")
    )
    assistant_prompt = example["output"]

    prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{user_prompt}<|im_end|>\n<|im_start|>assistant\n{assistant_prompt}<|im_end|>"
    return {"text": prompt}


# 应用格式化
dataset = dataset.map(format_example)


# 数据编码函数
def tokenize_function(examples):
    return tokenizer(
        examples["text"],
        truncation=True,
        max_length=2048,  # 足够覆盖驾驶场景
        padding="max_length",
        return_overflowing_tokens=False,
    )


# 编码数据集
tokenized_dataset = dataset.map(
    tokenize_function, batched=True, remove_columns=dataset.column_names
)

# 数据整理器
data_collator = DataCollatorForLanguageModeling(
    tokenizer=tokenizer,
    mlm=False,  # 因果语言模型，非掩码
)

# ====================== 6. 训练参数配置（核心！） ======================
training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    per_device_train_batch_size=4,  # 8GB GPU -> 4，12GB GPU -> 8
    gradient_accumulation_steps=1,
    learning_rate=2e-4,  # 0.8B模型最优学习率
    num_train_epochs=3,  # 3轮足够，避免过拟合
    logging_steps=10,
    save_steps=-1,  # 仅训练结束保存一次
    fp16=True,  # 混合精度训练，加速+省显存
    optim="paged_adamw_8bit",  # 8bit优化器，省显存
    report_to="none",  # 不报告到wandb
    seed=42,
    disable_tqdm=False,
)

# ====================== 7. 开始训练 ======================
trainer = Trainer(
    model=model,
    args=training_args,
    data_collator=data_collator,
    train_dataset=tokenized_dataset,
)

# 启动训练
trainer.train()

# 保存LoRA权重
model.save_pretrained(LORA_SAVE_PATH)
tokenizer.save_pretrained(LORA_SAVE_PATH)

print(f"✅ LoRA微调完成！权重保存至：{LORA_SAVE_PATH}")
