from flask import Response, request
from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import Schema, fields, validate

from ..db import ensure_schema, sse_broker
from ..models import get_attendance_for_class, get_attendance_summary_for_user, mark_attendance


class MarkSchema(Schema):
    class_id = fields.Integer(required=True)
    user_id = fields.Integer(required=True)
    status = fields.String(required=True, validate=validate.OneOf(["present", "absent", "late"]))


blp = Blueprint(
    "Attendance",
    "attendance",
    url_prefix="/attendance",
    description="Attendance endpoints and realtime updates",
)


@blp.route("")
class AttendanceCreateAndList(MethodView):
    # PUBLIC_INTERFACE
    def get(self):
        """
        List recent attendance for a class.
        Query: class_id (int), limit (int, optional)
        """
        class_id = request.args.get("class_id", type=int)
        limit = request.args.get("limit", default=100, type=int)
        if not class_id:
            return {"message": "class_id is required"}, 400
        events = get_attendance_for_class(class_id, limit=limit)
        return {"events": events}, 200

    # PUBLIC_INTERFACE
    def post(self):
        """
        Mark attendance for a user in a class.
        Body: { class_id, user_id, status }
        """
        payload = request.get_json(force=True, silent=True) or {}
        errors = MarkSchema().validate(payload)
        if errors:
            return {"errors": errors}, 400
        # Ensure schema exists once prior to first write
        ensure_schema()
        event = mark_attendance(payload["class_id"], payload["user_id"], payload["status"])
        return {"event": event}, 201


@blp.route("/summary")
class AttendanceSummary(MethodView):
    # PUBLIC_INTERFACE
    def get(self):
        """
        Get attendance summary for a user.
        Query: user_id
        """
        user_id = request.args.get("user_id", type=int)
        if not user_id:
            return {"message": "user_id is required"}, 400
        data = get_attendance_summary_for_user(user_id)
        return data, 200


@blp.route("/stream")
class AttendanceSSE(MethodView):
    # PUBLIC_INTERFACE
    def get(self):
        """
        Server-Sent Events stream for real-time updates.
        Clients can connect and receive events: class_created, class_member_added, attendance_marked.
        """
        # Instantiate directly to avoid circular import
        from ..db import SseClient  # local import

        sc = SseClient()
        client_id = sse_broker.register(sc)

        def generator():
            try:
                for chunk in sc.stream():
                    yield chunk
            finally:
                sse_broker.unregister(client_id)

        return Response(generator(), mimetype="text/event-stream")
