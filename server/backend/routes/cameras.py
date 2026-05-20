from flask import Blueprint, jsonify

from providers.cameras.external_camera_provider import get_camera_status

cameras_bp = Blueprint("cameras", __name__)


@cameras_bp.get("/v1/cameras")
def cameras_status():
    return jsonify(get_camera_status())

