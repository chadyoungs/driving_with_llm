# Fine Tuning a Model on HighD for Driver Agent on Highway

## 1 prepraed the training data
> extracted data from HighD Dataset, assess driver's skill level, get expert data to fine tune the LLM model

input data
past 3 seconds data


output data
## 2 fine tuning the LLM model
 data

 data balance


## 3 LLM
driver agent
relection agent
memory 
RAG
decision post process

## 4 Validation
Simulation Environment
highway-env
'highway-v0'

## 4 limitations

### 4.1 overview
* Current technology stack including E2E, VLA and WR models. E2E is widely-adopted technology with
sensors input (camera, radar, lidar, gnss, map, navigation) while the output is Accelerator pedal 
position (APP) and steering wheel angle(SWA). End-to-end models are characterized by a lack of inter-module information loss and the removal of tedious, conflicting rules typical of conventional methods.
Actually, we concentrated on prediction + decision + planning modules here. besides, we also give 
the chain of thoughts in our fined tuning model.

### 4.2 input
ignore the obstacles exists in the real scenario, car and trucks on highway, lane info, select postion, kpi as input.

### 4.3 output
the output is a discrete decision among in idle, accelerate, decelerate and left lane change, right lane change.

## 5 Todo
more scenario:
intersection

## 6 Reference


```bibtex
@article{wen2023dilu,
  title={Dilu: A knowledge-driven approach to autonomous driving with large language models},
  author={Wen, Licheng and Fu, Daocheng and Li, Xin and Cai, Xinyu and Ma, Tao and Cai, Pinlong and Dou, Min and Shi, Botian and He, Liang and Qiao, Yu},
  journal={arXiv preprint arXiv:2309.16292},
  year={2023}
}
```

## 7 Usage
## 7.1 Requirements

For an optimal experience, we recommend using conda to set up a new environment for DiLu.

```bash
conda create -n dilu python=3.8 
conda activate dilu
pip install -r requirements.txt
```
### 7.2 Configuration

All configurable parameters are located in `config.yaml`.

Before running DiLu, set up your OpenAI API keys. DiLu supports both OpenAI and Azure Openai APIs. 

Configure as below in `config.yaml`:
```yaml
OPENAI_API_TYPE: # 'openai' or 'azure'
# below are for Openai
OPENAI_KEY: # 'sk-xxxxxx' 
OPENAI_CHAT_MODEL: 'gpt-4-1106-preview' # Alternative models: 'gpt-3.5-turbo-16k-0613' (note: performance may vary)
# below are for Azure OAI service
AZURE_API_BASE: # https://xxxxxxx.openai.azure.com/
AZURE_API_VERSION: "2023-07-01-preview"
AZURE_API_KEY: #'xxxxxxx'
AZURE_CHAT_DEPLOY_NAME: # chat model deployment name
AZURE_EMBED_DEPLOY_NAME: # text embed model deployment name  
```

### 7.3 Run


### 7.4 Visualize
We provide a visualization scripts for the simulation result.
```bash
python ./visualize_results.py -r results/highway_0.db -m memories/20_mem
```
Open `http://127.0.0.1:7860` to view each frame's prompts and decisions!
