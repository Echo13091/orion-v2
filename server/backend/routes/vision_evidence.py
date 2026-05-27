from flask import Blueprint, jsonify, send_file

from tools.vision_evidence import get_vision_evidence, latest_snapshot_path


vision_evidence_bp = Blueprint("vision_evidence", __name__)


@vision_evidence_bp.get("/v1/vision/evidence")
def vision_evidence():
    return jsonify(get_vision_evidence(capture=True))


@vision_evidence_bp.get("/v1/vision/evidence/status")
def vision_evidence_status():
    return jsonify(get_vision_evidence(capture=False))


@vision_evidence_bp.get("/v1/vision/evidence/latest.jpg")
def latest_vision_evidence_snapshot():
    path = latest_snapshot_path()
    if not path:
        return jsonify({"ok": False, "error": "No snapshot evidence available"}), 404

    return send_file(path, mimetype="image/jpeg", max_age=0)
