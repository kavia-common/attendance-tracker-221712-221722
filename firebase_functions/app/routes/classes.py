import logging
from datetime import datetime, date

from flask import g
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from marshmallow import Schema, fields, validates, ValidationError, validate

from ..auth import jwt_required, roles_required
from ..db import get_db_session


blp = Blueprint(
    "Classes",
    __name__,
    url_prefix="/classes",
)

# ---------------------------
# Marshmallow Schemas
# ---------------------------


class ClassSchema(Schema):
    id = fields.Int(dump_only=True, metadata={"description": "Class ID"})
    name = fields.Str(required=True, validate=validate.Length(min=1, max=255), metadata={"description": "Class name"})
    description = fields.Str(required=False, allow_none=True, metadata={"description": "Optional description"})
    teacher_email = fields.Email(dump_only=True, metadata={"description": "Owner/teacher email for the class"})
    created_at = fields.DateTime(dump_only=True, metadata={"description": "Creation timestamp"})


class CreateClassSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=255), metadata={"description": "Class name"})
    description = fields.Str(required=False, allow_none=True, metadata={"description": "Optional description"})


class EnrollmentSchema(Schema):
    message = fields.Str(dump_only=True)
    class_id = fields.Int(dump_only=True)
    student_email = fields.Email(dump_only=True)


class SessionSchema(Schema):
    id = fields.Int(dump_only=True, metadata={"description": "Session ID"})
    class_id = fields.Int(required=True, metadata={"description": "Associated class ID"})
    start_time = fields.DateTime(required=True, metadata={"description": "Session start time (ISO8601)"})
    end_time = fields.DateTime(required=True, metadata={"description": "Session end time (ISO8601)"})
    notes = fields.Str(required=False, allow_none=True, metadata={"description": "Optional session notes"})

    @validates("end_time")
    def validate_time_order(self, value, **kwargs):
        # end_time must be after start_time in the request payload
        data = self.context.get("data") if hasattr(self, "context") else None
        # Best-effort; also validated server-side in handler.
        if data and "start_time" in data:
            try:
                start = data["start_time"]
                if isinstance(start, str):
                    start = datetime.fromisoformat(start.replace("Z", "+00:00"))
                end = value
                if isinstance(end, str):
                    end = datetime.fromisoformat(end.replace("Z", "+00:00"))
                if end <= start:
                    raise ValidationError("end_time must be after start_time")
            except Exception:
                # let handler validate
                pass


class CreateSessionSchema(Schema):
    start_time = fields.DateTime(required=True, metadata={"description": "Session start time (ISO8601)"})
    end_time = fields.DateTime(required=True, metadata={"description": "Session end time (ISO8601)"})
    notes = fields.Str(required=False, allow_none=True, metadata={"description": "Optional session notes"})


class QueryDateSchema(Schema):
    date = fields.Date(required=True, metadata={"description": "Filter date in format YYYY-MM-DD"})

    @validates("date")
    def validate_date(self, value: date, **kwargs):
        # Accept any valid date; additional constraints can be added later.
        if not isinstance(value, date):
            raise ValidationError("Invalid date")


# ---------------------------
# Helper functions
# ---------------------------


def _ensure_db():
    """Get a DB session or return 503."""
    session = get_db_session()
    if session is None:
        abort(503, message="Database is not configured")
    return session


def _row_to_class_dict(row) -> dict:
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "description": row.get("description"),
        "teacher_email": row.get("teacher_email"),
        "created_at": row.get("created_at"),
    }


def _row_to_session_dict(row) -> dict:
    return {
        "id": row.get("id"),
        "class_id": row.get("class_id"),
        "start_time": row.get("start_time"),
        "end_time": row.get("end_time"),
        "notes": row.get("notes"),
    }


# ---------------------------
# API Routes
# ---------------------------


@blp.route("")
class ClassesListResource(MethodView):
    @blp.response(200, ClassSchema(many=True))
    @jwt_required
    def get(self):
        """
        List classes.
        - Teachers/Admin: list classes they own or all if admin
        - Students: list all classes (in this simple example)
        """
        session = _ensure_db()
        role = getattr(g, "user_role", None)
        email = getattr(g, "user_email", None)
        try:
            # Ensure tables exist (idempotent, for demo). In production, use migrations.
            session.execute(
                """
                CREATE TABLE IF NOT EXISTS classes (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    teacher_email TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )
            session.commit()

            if role == "teacher":
                result = session.execute(
                    "SELECT id, name, description, teacher_email, created_at FROM classes WHERE teacher_email = :email ORDER BY id DESC",
                    {"email": email},
                )
            elif role == "admin":
                result = session.execute(
                    "SELECT id, name, description, teacher_email, created_at FROM classes ORDER BY id DESC"
                )
            else:  # student
                result = session.execute(
                    "SELECT id, name, description, teacher_email, created_at FROM classes ORDER BY id DESC"
                )

            rows = [dict(r) for r in result.mappings().all()]
            return [_row_to_class_dict(r) for r in rows], 200
        except Exception as exc:
            session.rollback()
            logging.exception("Failed to list classes: %s", exc)
            abort(500, message="Internal server error")
        finally:
            session.close()

    @blp.arguments(CreateClassSchema)
    @blp.response(201, ClassSchema)
    @roles_required("teacher", "admin")
    def post(self, payload: dict):
        """
        Create a class. Only teacher/admin allowed.
        """
        session = _ensure_db()
        email = getattr(g, "user_email", None)
        try:
            session.execute(
                """
                CREATE TABLE IF NOT EXISTS classes (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    teacher_email TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )
            session.commit()

            result = session.execute(
                """
                INSERT INTO classes (name, description, teacher_email)
                VALUES (:name, :description, :teacher_email)
                RETURNING id, name, description, teacher_email, created_at
                """,
                {
                    "name": payload.get("name"),
                    "description": payload.get("description"),
                    "teacher_email": email,
                },
            )
            session.commit()
            row = dict(result.mappings().first())
            return _row_to_class_dict(row), 201
        except Exception as exc:
            session.rollback()
            logging.exception("Failed to create class: %s", exc)
            abort(500, message="Internal server error")
        finally:
            session.close()


@blp.route("/<int:class_id>/enroll")
class ClassEnrollmentResource(MethodView):
    @blp.response(200, EnrollmentSchema)
    @roles_required("student")
    def post(self, class_id: int):
        """
        Enroll current student into a class.
        """
        session = _ensure_db()
        student_email = getattr(g, "user_email", None)
        try:
            # Ensure tables
            session.execute(
                """
                CREATE TABLE IF NOT EXISTS classes (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    teacher_email TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )
            session.execute(
                """
                CREATE TABLE IF NOT EXISTS enrollments (
                    id SERIAL PRIMARY KEY,
                    class_id INT NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
                    student_email TEXT NOT NULL,
                    enrolled_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE (class_id, student_email)
                );
                """
            )
            session.commit()

            # Check class exists
            exists = session.execute(
                "SELECT 1 FROM classes WHERE id = :cid",
                {"cid": class_id},
            ).first()
            if not exists:
                abort(404, message="Class not found")

            # Upsert-like unique insert
            session.execute(
                """
                INSERT INTO enrollments (class_id, student_email)
                VALUES (:cid, :email)
                ON CONFLICT (class_id, student_email) DO NOTHING
                """,
                {"cid": class_id, "email": student_email},
            )
            session.commit()

            return {
                "message": "Enrolled",
                "class_id": class_id,
                "student_email": student_email,
            }, 200
        except Exception as exc:
            session.rollback()
            logging.exception("Failed to enroll: %s", exc)
            abort(500, message="Internal server error")
        finally:
            session.close()


# Sessions endpoints

@blp.route("/<int:class_id>/sessions")
class ClassSessionsResource(MethodView):
    @blp.arguments(CreateSessionSchema)
    @blp.response(201, SessionSchema)
    @roles_required("teacher", "admin")
    def post(self, payload: dict, class_id: int):
        """
        Create a session for a class.
        Teacher can only create for their own class; admin can create for any.
        """
        session = _ensure_db()
        role = getattr(g, "user_role", None)
        email = getattr(g, "user_email", None)
        try:
            # Ensure tables
            session.execute(
                """
                CREATE TABLE IF NOT EXISTS classes (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    teacher_email TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )
            session.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id SERIAL PRIMARY KEY,
                    class_id INT NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
                    start_time TIMESTAMPTZ NOT NULL,
                    end_time TIMESTAMPTZ NOT NULL,
                    notes TEXT
                );
                """
            )
            session.commit()

            # Verify class and ownership
            class_row = session.execute(
                "SELECT id, teacher_email FROM classes WHERE id = :cid",
                {"cid": class_id},
            ).mappings().first()
            if not class_row:
                abort(404, message="Class not found")

            if role == "teacher" and class_row["teacher_email"] != email:
                abort(403, message="Forbidden: not your class")

            # Validate times order
            start_time = payload["start_time"]
            end_time = payload["end_time"]
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            if end_time <= start_time:
                abort(400, message="end_time must be after start_time")

            result = session.execute(
                """
                INSERT INTO sessions (class_id, start_time, end_time, notes)
                VALUES (:cid, :start, :end, :notes)
                RETURNING id, class_id, start_time, end_time, notes
                """,
                {"cid": class_id, "start": start_time, "end": end_time, "notes": payload.get("notes")},
            )
            session.commit()
            row = dict(result.mappings().first())
            return _row_to_session_dict(row), 201
        except ValidationError as ve:
            session.rollback()
            abort(400, message=str(ve))
        except Exception as exc:
            session.rollback()
            logging.exception("Failed to create session: %s", exc)
            abort(500, message="Internal server error")
        finally:
            session.close()

    @blp.arguments(QueryDateSchema, location="query")
    @blp.response(200, SessionSchema(many=True))
    @jwt_required
    def get(self, args: dict, class_id: int):
        """
        Get sessions for a class on a particular date (YYYY-MM-DD).
        - Students: can view any class's sessions (demo scope)
        - Teachers: can view their own classes (admin can view any)
        """
        session = _ensure_db()
        role = getattr(g, "user_role", None)
        email = getattr(g, "user_email", None)
        try:
            session.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id SERIAL PRIMARY KEY,
                    class_id INT NOT NULL,
                    start_time TIMESTAMPTZ NOT NULL,
                    end_time TIMESTAMPTZ NOT NULL,
                    notes TEXT
                );
                """
            )
            session.commit()

            # Ownership check for teachers
            if role == "teacher":
                owner = session.execute(
                    "SELECT teacher_email FROM classes WHERE id = :cid",
                    {"cid": class_id},
                ).mappings().first()
                if not owner:
                    abort(404, message="Class not found")
                if owner["teacher_email"] != email:
                    abort(403, message="Forbidden: not your class")

            qdate: date = args["date"]
            # Filter by date: sessions whose start_time falls on that date in DB's timezone.
            result = session.execute(
                """
                SELECT id, class_id, start_time, end_time, notes
                FROM sessions
                WHERE class_id = :cid
                  AND DATE(start_time) = :qdate
                ORDER BY start_time ASC
                """,
                {"cid": class_id, "qdate": qdate},
            )
            rows = [dict(r) for r in result.mappings().all()]
            return [_row_to_session_dict(r) for r in rows], 200
        except Exception as exc:
            session.rollback()
            logging.exception("Failed to get sessions: %s", exc)
            abort(500, message="Internal server error")
        finally:
            session.close()
