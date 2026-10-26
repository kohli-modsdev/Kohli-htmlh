import binascii
import hashlib
import json
import time
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import requests
from flask import Flask, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE_URL = "https://www.v3gameb.com"

HEADERS = {
    "Content-Type": "application/json;charset=UTF-8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Origin": "https://www.v3gameb.com",
    "Referer": "https://www.v3gameb.com/#/pages/games/wingo/wingo",
}

KEY = bytes([58, 108, 37, 38, 47, 31, 48, 52, 25, 27, 29, 61, 5, 77, 44, 44])
IV = b"ARONHAVELOTGIRLS"
SALT = "c45463907278405daf79993178ee3c3a"


def encrypt(data_str: str) -> str:
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    ct = cipher.encrypt(pad(data_str.encode("utf-8"), AES.block_size))
    return binascii.hexlify(ct).decode("utf-8").upper()


def decrypt(hex_str: str) -> str:
    raw = binascii.unhexlify(hex_str)
    return unpad(AES.new(KEY, AES.MODE_CBC, IV).decrypt(raw), AES.block_size).decode("utf-8")


def create_sign(timestamp: int, data_str: str) -> str:
    return hashlib.md5(
        f"{data_str}{SALT}{data_str}{timestamp}".encode("utf-8")
    ).hexdigest().lower()


def api_request(endpoint: str, data: dict):
    data_str = json.dumps(data, separators=(",", ":"))
    ts = int(time.time() * 1000)
    payload = {
        "data": encrypt(data_str),
        "sign": create_sign(ts, data_str),
        "dateTime": ts,
    }
    try:
        res = requests.post(f"{BASE_URL}{endpoint}", json=payload,
                            headers=HEADERS, timeout=10).json()
        if res.get("code") == 200 and "data" in res:
            return json.loads(decrypt(res["data"])).get("data")
        return res
    except Exception as e:
        return {"error": str(e)}


# ------------------- Prediction Logic -------------------
def predict_next(results):
    """
    Simple prediction based on last 10 results.
    Returns dict: predicted number, color, size + confidence
    """
    if not results:
        return {"number": "?", "color": "N/A", "size": "N/A", "confidence": 0}

    nums = []
    for r in results:
        try:
            nums.append(int(r.get("lotteryResults", 0)))
        except:
            nums.append(0)

    # Analyze patterns
    last5 = nums[:5]
    big_count = sum(1 for n in last5 if n >= 5)
    small_count = 5 - big_count

    # Simple alternating strategy
    if big_count > small_count:
        pred_size = "Small"
    elif small_count > big_count:
        pred_size = "Big"
    else:
        pred_size = "Big" if nums[0] < 5 else "Small"

    # Color analysis
    green = [1, 3, 7, 9]
    red = [2, 4, 6, 8]
    violet = [0, 5]

    violet_recent = sum(1 for n in nums[:10] if n in violet)
    if violet_recent < 2:
        pred_color = "Violet"
        pred_num = 5
    elif nums[0] in green:
        pred_color = "Red"
        pred_num = 2
    else:
        pred_color = "Green"
        pred_num = 1

    confidence = min(95, 50 + abs(big_count - small_count) * 8)

    return {
        "number": pred_num,
        "color": pred_color,
        "size": pred_size,
        "confidence": confidence,
    }


# ------------------- Routes -------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/live/<int:playtime>")
def live(playtime):
    """Get current period + timer"""
    data = {"gameId": 1, "playtime": playtime, "systemType": 2}
    period = api_request("/app/getIssueData", data)

    result_data = {
        "gameId": 1,
        "playtime": playtime,
        "pageSize": 10,
        "pageNum": 1,
        "systemType": 2,
    }
    results = api_request("/app/lotteryHistoricalRecords", result_data)
    result_list = results.get("list", []) if isinstance(results, dict) else []

    prediction = predict_next(result_list)

    return jsonify({
        "period": period.get("issueNo") if isinstance(period, dict) else None,
        "seconds": period.get("seconds") if isinstance(period, dict) else None,
        "startTime": period.get("startTime") if isinstance(period, dict) else None,
        "results": result_list[:10],
        "prediction": prediction,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
