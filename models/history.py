import json
import os
from datetime import datetime

HISTORY_FILE = "data/history.json"


class HistoryManager:

    def __init__(self):
        os.makedirs("data", exist_ok=True)

        if not os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)

    def load_history(self):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_result(self, claim, result, confidence, evidence):

        history = self.load_history()

        history.append({
            "claim": claim,
            "result": result,
            "confidence": confidence,
            "evidence": evidence,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)

    def get_history(self):
        return self.load_history()