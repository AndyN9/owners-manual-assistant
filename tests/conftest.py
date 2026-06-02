import tempfile
from pathlib import Path

import pytest

from manuals_app.db import init_db


@pytest.fixture
def db_path():
    path = tempfile.mktemp(suffix=".db")
    yield Path(path)
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def populated_db(db_path):
    conn = init_db(str(db_path))
    conn.execute("INSERT INTO documents (filename, category) VALUES (?,?)", ("car.pdf", "Automotive"))
    car_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute("INSERT INTO documents (filename, category) VALUES (?,?)", ("washer.pdf", "Appliances"))
    was_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    chunks = [
        (car_id, "Engine > Oil Change", "Use 5W-30 oil. Drain plug: 30 Nm."),
        (car_id, "Engine > Spark Plugs", "Gap: 1.1mm. Torque: 20 Nm."),
        (car_id, "Maintenance Schedule", "Every 10,000 km change the oil."),
        (was_id, "Installation", "Level the washer before use."),
        (was_id, "Troubleshooting", "If machine shakes, check leveling feet."),
    ]
    for doc_id, heading, content in chunks:
        conn.execute(
            "INSERT INTO document_chunks (document_id, heading_path, content_markdown) VALUES (?, ?, ?)",
            (doc_id, heading, content),
        )
    conn.commit()
    conn.close()
    return db_path
