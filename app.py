import os, io, csv, json
from flask import Flask, render_template, request, jsonify, send_file
from race_parser import parse_pdf, compute_race

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("pdf")
    if not f:
        return jsonify({"error": "No file"}), 400
    path = os.path.join(app.config["UPLOAD_FOLDER"], "race.pdf")
    f.save(path)
    try:
        races = parse_pdf(path)
        result = []
        for race in races:
            rows = compute_race(race)
            if rows:
                result.append({"race_num": race["race_num"],
                                "race_name": race["race_name"],
                                "current_dist": race["current_dist"],
                                "rows": rows})
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download", methods=["POST"])
def download():
    data = request.json
    si = io.StringIO()
    cols = ["Sl.No","Name","Old Weight","New Weight","Old Distance",
            "Current Distance","Old Time(sec)","PNR Race","Standard PNR",
            "Adjusted Time","Speed Rating","ODDS","Final Rating",
            "Speed Rank","Odds Rank","Value Score"]
    writer = csv.writer(si)
    for race in data:
        writer.writerow([f"Race {race['race_num']} - {race['race_name']} ({race['current_dist']}m)"])
        writer.writerow(cols)
        for row in race["rows"]:
            writer.writerow([row.get(c, "") for c in cols])
        writer.writerow([])
    output = io.BytesIO()
    output.write(si.getvalue().encode("utf-8-sig"))
    output.seek(0)
    return send_file(output, mimetype="text/csv",
                     as_attachment=True, download_name="race_analysis.csv")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=False)
