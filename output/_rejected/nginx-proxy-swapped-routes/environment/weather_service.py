from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/forecast")
def forecast():
    return jsonify(service="weather", endpoint="forecast", temp_c=22, condition="sunny")

@app.route("/conditions")
def conditions():
    return jsonify(service="weather", endpoint="conditions", humidity_pct=45, wind_kph=12)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001)
