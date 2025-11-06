from typing import Any, Dict, List, Optional

from .db import execute_query, sse_broker


# PUBLIC_INTERFACE
def upsert_user(email: str, name: str, role: str) -> Dict[str, Any]:
    """Create or update user; returns user dict."""
    execute_query(
        """
        INSERT INTO users (email, name, role)
        VALUES (%s, %s, %s)
        ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name, role = EXCLUDED.role
        """,
        (email, name, role),
        fetch="none",
    )
    rows, cols = execute_query("SELECT id, email, name, role FROM users WHERE email=%s", (email,))
    if rows:
        r = rows[0]
        return dict(zip(cols or [], r))
    return {}


# PUBLIC_INTERFACE
def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Fetch a user by email."""
    rows, cols = execute_query("SELECT id, email, name, role FROM users WHERE email=%s", (email,))
    if rows:
        return dict(zip(cols or [], rows[0]))
    return None


# PUBLIC_INTERFACE
def create_class(name: str, teacher_id: int) -> Dict[str, Any]:
    """Create a class."""
    rows, cols = execute_query(
        "INSERT INTO classes (name, teacher_id) VALUES (%s, %s) RETURNING id, name, teacher_id",
        (name, teacher_id),
        fetch="one",
    )
    if rows:
        data = dict(zip(cols or [], rows[0]))
        sse_broker.publish("class_created", data)
        return data
    return {}


# PUBLIC_INTERFACE
def list_classes_for_teacher(teacher_id: int) -> List[Dict[str, Any]]:
    """List classes managed by a teacher."""
    rows, cols = execute_query(
        "SELECT id, name, teacher_id FROM classes WHERE teacher_id=%s ORDER BY id DESC",
        (teacher_id,),
    )
    return [dict(zip(cols or [], r)) for r in rows]


# PUBLIC_INTERFACE
def add_student_to_class(class_id: int, user_id: int) -> Dict[str, Any]:
    """Add a student to class membership."""
    execute_query(
        "INSERT INTO class_members (class_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (class_id, user_id),
        fetch="none",
    )
    data = {"class_id": class_id, "user_id": user_id}
    sse_broker.publish("class_member_added", data)
    return data


# PUBLIC_INTERFACE
def get_class_members(class_id: int) -> List[Dict[str, Any]]:
    """Return list of students in a class."""
    rows, cols = execute_query(
        """
        SELECT u.id as user_id, u.name, u.email, u.role
        FROM class_members cm
        JOIN users u ON u.id = cm.user_id
        WHERE cm.class_id=%s
        ORDER BY u.name
        """,
        (class_id,),
    )
    return [dict(zip(cols or [], r)) for r in rows]


# PUBLIC_INTERFACE
def mark_attendance(class_id: int, user_id: int, status: str) -> Dict[str, Any]:
    """Insert an attendance record and broadcast."""
    rows, cols = execute_query(
        """
        INSERT INTO attendance (class_id, user_id, status)
        VALUES (%s, %s, %s)
        RETURNING id, class_id, user_id, status, ts
        """,
        (class_id, user_id, status),
        fetch="one",
    )
    if rows:
        data = dict(zip(cols or [], rows[0]))
        sse_broker.publish("attendance_marked", data)
        return data
    return {}


# PUBLIC_INTERFACE
def get_attendance_for_class(class_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    """Recent attendance events for a class."""
    rows, cols = execute_query(
        """
        SELECT a.id, a.class_id, a.user_id, a.status, a.ts, u.name as user_name
        FROM attendance a
        JOIN users u ON u.id = a.user_id
        WHERE a.class_id=%s
        ORDER BY a.ts DESC
        LIMIT %s
        """,
        (class_id, limit),
    )
    return [dict(zip(cols or [], r)) for r in rows]


# PUBLIC_INTERFACE
def get_attendance_summary_for_user(user_id: int) -> Dict[str, Any]:
    """Return counts by status for a user."""
    rows, cols = execute_query(
        """
        SELECT status, COUNT(*) as count
        FROM attendance
        WHERE user_id=%s
        GROUP BY status
        """,
        (user_id,),
    )
    summary = {r[0]: r[1] for r in rows}
    return {"user_id": user_id, "summary": summary}
