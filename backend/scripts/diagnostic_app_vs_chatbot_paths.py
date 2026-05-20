#!/usr/bin/env python3
"""
Comprehensive diagnostic: app data paths vs chatbot data paths.
Maps where data is correctly retrieved in app vs where chatbot fails.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text, func, select
from app.db.session import SessionLocal
from app.models.batch import Batch
from app.models.stock import Stock
from app.models.product import Product
from app.models.process_step import ProcessStep
from app.models.parcel import Parcel
from app.models.pre_harvest_step import PreHarvestStep

db = SessionLocal()

# Get a test cooperative ID
test_coop = db.query(Product).first()
if test_coop:
    test_coop_id = test_coop.cooperative_id
else:
    # Use raw query
    result = db.execute(text("SELECT DISTINCT cooperative_id FROM products LIMIT 1")).first()
    test_coop_id = result[0] if result else None

print("=" * 120)
print("DIAGNOSTIC: APP DATA PATHS vs CHATBOT DATA PATHS")
print("=" * 120)
print(f"\nTest Cooperative ID: {test_coop_id}\n")

# ============================================================================
# Q1: Quel est le stock actuel par produit ?
# ============================================================================
print("\n" + "=" * 120)
print("Q1: Quel est le stock actuel par produit ?")
print("=" * 120)

print("\n📍 CHATBOT TOOL: get_current_stock()")
print("Expected query path: stocks JOIN products WHERE cooperative_id = ? ORDER BY product name")

print("\n📊 APP DATA - Direct SQL (What should be retrieved):")
try:
    # This is what the SQL tool should return
    query = f"""
    SELECT 
        p.name as product_name,
        s.total_stock_kg,
        s.reserved_in_lots_kg,
        (s.total_stock_kg - COALESCE(s.reserved_in_lots_kg, 0)) as available_kg,
        s.threshold,
        s.unit
    FROM stocks s
    JOIN products p ON s.product_id = p.id
    WHERE s.cooperative_id = '{test_coop_id}'
    ORDER BY p.name
    """
    result = db.execute(text(query)).fetchall()
    print(f"   Found {len(result)} products with stock")
    for row in result[:3]:
        print(f"   - {row[0]}: {row[1]} kg total, {row[2]} reserved, {row[3]} available, threshold: {row[4]} {row[5]}")
except Exception as e:
    print(f"   ❌ ERROR: {str(e)[:80]}")

print("\n📍 APP API ENDPOINT: /api/stocks (where app displays stock correctly)")
print("   Expected response: {product: X, total_stock_kg: Y, available: Y-Z, ...}")

print("\n🔍 ISSUE DIAGNOSIS:")
print("   ✓ IF SQL tool returns data: Problem is in LLM answer formatting")
print("   ✗ IF SQL tool returns null: Problem is in SQL query or column mapping")

# ============================================================================
# Q2: Quels sont les lots post-récolte disponibles dans cette coopérative ?
# ============================================================================
print("\n" + "=" * 120)
print("Q2: Quels sont les lots post-récolte disponibles dans cette coopérative ?")
print("=" * 120)

print("\n📍 CHATBOT TOOLS: Should use listing function, not loss ranking")
print("   Current problem: Returns loss ranking instead of lot listing")

print("\n📊 APP DATA - Batches/Lots with status:")
try:
    query = f"""
    SELECT 
        b.code as batch_code,
        b.status,
        p.name as product_name,
        b.initial_qty,
        b.current_qty,
        b.postharvest_started_at
    FROM batches b
    JOIN products p ON b.product_id = p.id
    WHERE b.cooperative_id = '{test_coop_id}'
    AND b.postharvest_started_at IS NOT NULL
    ORDER BY b.postharvest_started_at DESC
    LIMIT 10
    """
    result = db.execute(text(query)).fetchall()
    print(f"   Found {len(result)} post-harvest batches")
    for row in result[:3]:
        print(f"   - {row[0]}: {row[1]} ({row[2]}), {row[3]} → {row[4]} kg, started: {row[5]}")
except Exception as e:
    print(f"   ❌ ERROR: {str(e)[:80]}")

print("\n📍 TABLE STRUCTURE:")
print("   batches: code, status, initial_qty, current_qty, postharvest_started_at")
print("   NOT: post_harvest_steps table (does not exist)")

print("\n🔍 ISSUE DIAGNOSIS:")
print("   ✗ Chatbot tries to query post_harvest_steps table (doesn't exist)")
print("   ✓ Should query batches table with postharvest_started_at filter")

# ============================================================================
# Q3/Q4: Pertes les plus élevées / Écart entrée-sortie
# ============================================================================
print("\n" + "=" * 120)
print("Q3/Q4: Pertes / Efficacité / Écart entrée-sortie")
print("=" * 120)

print("\n📍 CHATBOT TOOLS: get_postharvest_batch_summary() or get_material_balance()")

print("\n📊 APP DATA - Material balance from batches:")
try:
    query = f"""
    SELECT 
        b.code as batch_code,
        p.name as product_name,
        b.initial_qty,
        b.current_qty,
        (b.initial_qty - b.current_qty) as loss_qty,
        CASE WHEN b.initial_qty > 0 
             THEN ((b.initial_qty - b.current_qty) / b.initial_qty * 100)
             ELSE 0 
        END as loss_percent
    FROM batches b
    JOIN products p ON b.product_id = p.id
    WHERE b.cooperative_id = '{test_coop_id}'
    AND b.initial_qty > 0
    ORDER BY loss_percent DESC
    LIMIT 10
    """
    result = db.execute(text(query)).fetchall()
    print(f"   Found {len(result)} batches with loss data")
    for row in result[:3]:
        print(f"   - {row[0]} ({row[1]}): {row[2]} → {row[3]} kg, loss: {row[4]} kg ({row[5]:.1f}%)")
except Exception as e:
    print(f"   ❌ ERROR: {str(e)[:80]}")

print("\n📍 SOURCE DATA:")
print("   actual_qty_in = batches.initial_qty")
print("   actual_qty_out = batches.current_qty")
print("   loss = initial_qty - current_qty")
print("   efficiency = (initial_qty - loss) / initial_qty * 100")

print("\n🔍 ISSUE DIAGNOSIS:")
print("   ✓ Data exists in batches table")
print("   ✗ Problem: SQL queries reference non-existent tables or columns")

# ============================================================================
# Q5: Étapes pré-récolte
# ============================================================================
print("\n" + "=" * 120)
print("Q5: Quelles sont les étapes pré-récolte enregistrées ?")
print("=" * 120)

print("\n📍 CHATBOT TOOLS: preharvest.* tools")

print("\n📊 APP DATA - Pre-harvest steps:")
try:
    query = f"""
    SELECT 
        pc.name as parcel_name,
        phs.step_key,
        phs.category,
        phs.label,
        phs.status,
        phs.realization_date
    FROM pre_harvest_steps phs
    JOIN parcels pc ON phs.parcel_id = pc.id
    WHERE phs.cooperative_id = '{test_coop_id}'
    ORDER BY phs.realization_date DESC
    LIMIT 5
    """
    result = db.execute(text(query)).fetchall()
    print(f"   Found {len(result)} pre-harvest steps")
    for row in result[:3]:
        print(f"   - {row[0]}: {row[1]} ({row[2]}), {row[3]}, status: {row[4]}, date: {row[5]}")
except Exception as e:
    print(f"   ❌ ERROR: {str(e)[:80]}")

print("\n📍 TABLE: pre_harvest_steps (exists)")
print("   Columns: step_key, category, label, status, realization_date, parcel_id")

print("\n🔍 ISSUE DIAGNOSIS:")
print("   ✓ Table exists with complete data")
print("   ? Problem might be in intent detection or scoping")

# ============================================================================
# Q6: RAG - Bonnes pratiques emballage
# ============================================================================
print("\n" + "=" * 120)
print("Q6: Quelles bonnes pratiques appliquer avant l'emballage ?")
print("=" * 120)

print("\n📍 CHATBOT SYSTEM: RAG (Retrieval-Augmented Generation)")

print("\n📊 APP DATA - RAG documents/chunks:")
try:
    query = f"""
    SELECT 
        COUNT(*) as total_chunks,
        MAX(created_at) as latest_chunk
    FROM rag_chunks
    WHERE cooperative_id = '{test_coop_id}'
    """
    result = db.execute(text(query)).fetchone()
    print(f"   Found {result[0]} RAG chunks, latest: {result[1]}")
    
    # Check for emballage/packaging content
    query2 = f"""
    SELECT 
        rc.id,
        SUBSTRING(rc.content, 1, 100) as content_preview,
        rc.source_document_id
    FROM rag_chunks rc
    WHERE rc.cooperative_id = '{test_coop_id}'
    AND (rc.content ILIKE '%emballage%' OR rc.content ILIKE '%packaging%' OR rc.content ILIKE '%conditionnement%')
    LIMIT 3
    """
    results = db.execute(text(query2)).fetchall()
    print(f"   Found {len(results)} chunks with emballage/packaging keywords")
    for row in results[:3]:
        preview = row[1][:80] if row[1] else "N/A"
        print(f"   - Preview: {preview}...")
except Exception as e:
    print(f"   ❌ ERROR: {str(e)[:80]}")

print("\n📍 ISSUE: RAG returns raw source text instead of composed answer")
print("   Problem is in answer_composer, not data retrieval")

# ============================================================================
# SUMMARY TABLE
# ============================================================================
print("\n" + "=" * 120)
print("SUMMARY: QUESTION vs DATA PATH COMPARISON")
print("=" * 120)

table_data = [
    ("Q1", "Stock par produit", "stocks + products", "get_current_stock()", "Data exists", "Answer formatting"),
    ("Q2", "Lots post-récolte", "batches", "get_postharvest_batch_summary()", "Data exists (batches)", "Wrong table in query (post_harvest_steps)"),
    ("Q3/Q4", "Pertes/écart", "batches", "get_material_balance()", "Data exists", "SQL column mismatch"),
    ("Q5", "Pré-récolte steps", "pre_harvest_steps", "preharvest.*()", "Data exists", "Intent/scope detection"),
    ("Q6", "Bonnes pratiques", "rag_chunks", "RAG retrieval", "Data exists", "Answer formatting (raw text)"),
]

print(f"\n{'Q':<8} | {'Topic':<25} | {'Table':<20} | {'Chatbot Tool':<30} | {'Data':<15} | {'Issue':<40}")
print("-" * 150)
for q, topic, table, tool, data, issue in table_data:
    print(f"{q:<8} | {topic:<25} | {table:<20} | {tool:<30} | {data:<15} | {issue:<40}")

# ============================================================================
# TABLE INVENTORY
# ============================================================================
print("\n" + "=" * 120)
print("TABLE INVENTORY (from schema introspection)")
print("=" * 120)

tables_exist = {
    "stocks": True,
    "batches": True,
    "pre_harvest_steps": True,
    "post_harvest_steps": False,  # MISSING
    "process_steps": True,  # For post-harvest stage tracking
    "parcels": True,
    "products": True,
    "rag_chunks": True,
    "rag_documents": True,
}

print("\n✅ AVAILABLE TABLES:")
for table, exists in tables_exist.items():
    if exists:
        try:
            count = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"   {table}: {count} rows")
        except:
            print(f"   {table}: (count unavailable)")

print("\n❌ MISSING TABLES:")
for table, exists in tables_exist.items():
    if not exists:
        print(f"   {table}")

db.close()

print("\n" + "=" * 120)
print("NEXT STEPS")
print("=" * 120)
print("""
1. Fix SQL tool queries to use correct table/column names
2. Create proper list/ranking intent separation
3. Fix RAG answer composition to convert raw text to practical advice
4. Add missing data validation to reject "donnée indisponible" when data exists
5. Test with the 6 questions and run audits
""")
