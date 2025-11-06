from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import Schema, fields

from ..models import add_student_to_class, create_class, get_class_members, list_classes_for_teacher


class CreateClassSchema(Schema):
    name = fields.String(required=True, description="Class name")
    teacher_id = fields.Integer(required=True, description="Teacher user id")


class AddStudentSchema(Schema):
    class_id = fields.Integer(required=True)
    user_id = fields.Integer(required=True)


blp = Blueprint(
    "Classes",
    "classes",
    url_prefix="/classes",
    description="Manage classes and membership",
)


@blp.route("")
class ClassesListCreate(MethodView):
    # PUBLIC_INTERFACE
    def get(self):
        """
        List classes for a teacher.
        Query params:
          - teacher_id: int
        """
        teacher_id = request.args.get("teacher_id", type=int)
        if not teacher_id:
            return {"message": "teacher_id is required"}, 400
        items = list_classes_for_teacher(teacher_id)
        return {"classes": items}, 200

    # PUBLIC_INTERFACE
    def post(self):
        """
        Create a class.
        Body: { name: str, teacher_id: int }
        """
        payload = request.get_json(force=True, silent=True) or {}
        errors = CreateClassSchema().validate(payload)
        if errors:
            return {"errors": errors}, 400
        data = create_class(payload["name"], payload["teacher_id"])
        return {"class": data}, 201


@blp.route("/members")
class ClassMembers(MethodView):
    # PUBLIC_INTERFACE
    def get(self):
        """
        Get members of a class.
        Query: class_id
        """
        class_id = request.args.get("class_id", type=int)
        if not class_id:
            return {"message": "class_id is required"}, 400
        members = get_class_members(class_id)
        return {"members": members}, 200

    # PUBLIC_INTERFACE
    def post(self):
        """
        Add a student to a class.
        Body: { class_id, user_id }
        """
        payload = request.get_json(force=True, silent=True) or {}
        errors = AddStudentSchema().validate(payload)
        if errors:
            return {"errors": errors}, 400
        out = add_student_to_class(payload["class_id"], payload["user_id"])
        return {"membership": out}, 201
