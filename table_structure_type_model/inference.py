import torch
from transformers import BertTokenizer, BertForSequenceClassification
import pickle

from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

# 设置设备为 CPU
device = torch.device("cpu")

# 加载 BERT 模型和 Tokenizer
model = BertForSequenceClassification.from_pretrained("bert-column-type-classifier-augment")
tokenizer = BertTokenizer.from_pretrained("bert-column-type-classifier-augment")
model.eval()

# 加载标签编码器
with open("./bert-column-type-classifier-augment/label_encoder.pkl", "rb") as f:
    label_encoder = pickle.load(f)

# 推理函数（单列名）
def predict_column_type(header: str) -> str:
    inputs = tokenizer(header, return_tensors="pt", truncation=True, padding=True, max_length=16)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        outputs = model(**inputs)
        pred_id = torch.argmax(outputs.logits, dim=1).item()
        result = label_encoder.inverse_transform([pred_id])[0]
        return str(result)  # 确保返回Python字符串

# 表结构推理函数（多列名）
def infer_table_structure(table_header: list[str]) -> list[str]:
    return [predict_column_type(h) for h in table_header]

# 示例输入
table_header = [
        "Series #(""2"")",
        "Season #(""1"")",
        "Title(""\"The Practical Joke War\""")",
        "Notes(""Alfie and Goo unleash harsh practical jokes on Dee Dee and his friends. Dee Dee, Harry and Donnel retaliate by pulling a practical joke on Alfie with the trick gum. After Alfie and Goo get even with Dee Dee and his friends, Melanie and Deonne help them get even. Soon, Alfie and Goo declare a practical joke war on Melanie, Dee Dee and their friends. This eventually stops when Roger and Jennifer end up on the wrong end of the practical joke war after being announced as the winner of a magazine contest for Best Family Of The Year. They set their children straight for their behavior and will have a talk with their friends' parents as well."")",
        "Original air date(""October 22, 1994"")"
      ]

# FastAPI 部分
app = FastAPI()

class TableHeaderRequest(BaseModel):
    table_header: list[str]

@app.post("/infer_table_structure")
async def infer_table_structure_api(request: TableHeaderRequest):
    result = infer_table_structure(request.table_header)
    return {"table_structure": result}

def main():
    # 启动 FastAPI 服务，指定端口
    uvicorn.run("inference:app", host="127.0.0.1", port=8080, reload=False)

if __name__ == "__main__":
    main()

