from __future__ import annotations

from uuid import uuid4

from flask import Flask, Response, jsonify, request
from flask_cors import CORS

from .chat import ask_question

app = Flask(__name__, static_folder="../frontend/build", static_url_path="/")
CORS(app)


@app.route("/")
def api_index():
    return app.send_static_file("index.html")


@app.route("/health")
def health() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200


@app.route("/api/chat", methods=["POST"])
def api_chat():
    request_json = request.get_json(silent=True) or {}
    question = request_json.get("question")
    if not isinstance(question, str) or not question.strip():
        return jsonify({"msg": "Missing question from request JSON"}), 400

    session_id = request.args.get("session_id") or str(uuid4())
    stream = ask_question(question.strip(), session_id)
    return Response(stream, mimetype="text/event-stream")


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    app.run(host="0.0.0.0", port=4000, debug=False)
