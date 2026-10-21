from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/active")
def active():
    return jsonify(service="alerts", endpoint="active", count=3, highest_severity="warning")

@app.route("/history")
def history():
    return jsonify(service="alerts", endpoint="history", total=47, last_date="2024-11-15")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5002)
