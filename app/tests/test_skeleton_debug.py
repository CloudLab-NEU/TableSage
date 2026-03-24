import sys
import os

# Add app to path
app_path = r"d:\TableSage\app"
if app_path not in sys.path:
    sys.path.append(app_path)

from utils.question_skeleton_extract import extract_question_skeleton
from dotenv import load_dotenv

load_dotenv()

def test_skeleton():
    questions = [
        "what was the last year where tijuana was a venue?",
        "who was the opponent in the first game of the season?",
        "what is the average age of the grasshoppers?"
    ]
    
    for q in questions:
        print(f"Q: {q}")
        sk = extract_question_skeleton(q)
        print(f"SK: {sk}")
        print("-" * 40)

if __name__ == "__main__":
    test_skeleton()
