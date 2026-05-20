#!/usr/bin/env python3
"""Quick schema introspection."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import inspect, text
from app.db.session import SessionLocal

db = SessionLocal()
engine = db.get_bind()
inspector = inspect(engine)

tables = ['stocks', 'batches', 'post_harvest_steps', 'pre_harvest_steps', 'parcels']

for table_name in tables:
    if table_name in inspector.get_table_names():
        print(f"\n{table_name}:")
        columns = inspector.get_columns(table_name)
        for col in columns:
            print(f"  - {col['name']}: {col['type']}")
    else:
        print(f"\n{table_name}: NOT FOUND")

db.close()
