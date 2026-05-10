from flask import jsonify, request

from memory.memory import delete_session, get_memory, load_memory, rename_session


def register_sessions(app):
    @app.route("/v1/sessions", methods=["GET"])
    def get_sessions():
        memory = load_memory()

        sessions = [
            {"id": sid, "title": data.get("title", "Chat")}
            for sid, data in memory.items()
        ]

        sessions.sort(key=lambda item: item["title"].lower())
        return jsonify({"sessions": sessions})

    @app.route("/v1/session/<session_id>", methods=["GET"])
    def get_session(session_id):
        session_data = get_memory(session_id)
        return jsonify({"messages": session_data["messages"]})

    @app.route("/v1/session/<session_id>/rename", methods=["POST"])
    def rename(session_id):
        data = request.json or {}
        rename_session(session_id, data.get("title", "Chat"))
        return jsonify({"status": "ok"})

    @app.route("/v1/session/<session_id>", methods=["DELETE"])
    def delete(session_id):
        delete_session(session_id)
        return jsonify({"status": "deleted"})