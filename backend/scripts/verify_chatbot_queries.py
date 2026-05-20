#!/usr/bin/env python3
"""
Verify chatbot queries against actual database to diagnose answer quality issues.
Checks if data exists for each user question and compares with chatbot responses.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text
from app.db.session import SessionLocal
from app.core.config import settings

def verify_queries():
    """Verify each user question against the database."""
    
    db = SessionLocal()
    results = []
    
    print("=" * 100)
    print("CHATBOT QUERY VERIFICATION AGAINST DATABASE")
    print("=" * 100)
    print()
    
    # Q1: "Quel est le stock actuel par produit ?"
    print("\n[Q1] Quel est le stock actuel par produit ?")
    print("-" * 100)
    try:
        query = """
        SELECT 
            product_id,
            SUM(quantity_on_hand) as total_quantity,
            COUNT(DISTINCT location_id) as locations
        FROM stocks
        WHERE quantity_on_hand > 0
        GROUP BY product_id
        ORDER BY total_quantity DESC;
        """
        result = db.execute(text(query)).fetchall()
        if result:
            print(f"✅ DATA EXISTS: {len(result)} products with stock")
            for row in result[:5]:
                print(f"   Product {row[0]}: {row[1]} units across {row[2]} locations")
        else:
            print("❌ NO DATA: stocks table is empty")
        results.append(("Q1 - Stock par produit", len(result) if result else 0, "✅ DATA" if result else "❌ NO DATA"))
    except Exception as e:
        print(f"❌ QUERY ERROR: {str(e)}")
        results.append(("Q1 - Stock par produit", 0, f"❌ ERROR: {str(e)[:50]}"))
    
    # Q2: "Quels sont les lots post-récolte disponibles dans cette coopérative ?"
    print("\n[Q2] Quels sont les lots post-récolte disponibles dans cette coopérative ?")
    print("-" * 100)
    try:
        query = """
        SELECT 
            b.batch_id,
            b.product_id,
            COALESCE(phs.weight_loss_percent, 0) as loss_percent,
            COALESCE((100 - phs.weight_loss_percent), 100) as efficiency_percent
        FROM batches b
        LEFT JOIN post_harvest_steps phs ON b.batch_id = phs.batch_id
        ORDER BY loss_percent DESC
        LIMIT 10;
        """
        result = db.execute(text(query)).fetchall()
        if result:
            print(f"✅ DATA EXISTS: {len(result)} post-harvest batches")
            for row in result[:5]:
                print(f"   {row[0]}: {row[1]} - Loss: {row[2]:.1f}% - Efficiency: {row[3]:.1f}%")
        else:
            print("❌ NO DATA: no post-harvest batches")
        results.append(("Q2 - Lots post-récolte", len(result) if result else 0, "✅ DATA" if result else "❌ NO DATA"))
    except Exception as e:
        print(f"❌ QUERY ERROR: {str(e)}")
        results.append(("Q2 - Lots post-récolte", 0, f"❌ ERROR: {str(e)[:50]}"))
    
    # Q3/Q4: "Quels lots ont les pertes les plus élevées ?"
    print("\n[Q3/Q4] Quels lots ont les pertes les plus élevées ?")
    print("-" * 100)
    try:
        query = """
        SELECT 
            b.batch_id,
            b.product_id,
            COALESCE(phs.weight_loss_percent, 0) as loss_percent,
            COALESCE((100 - phs.weight_loss_percent), 100) as efficiency_percent
        FROM batches b
        LEFT JOIN post_harvest_steps phs ON b.batch_id = phs.batch_id
        WHERE phs.weight_loss_percent IS NOT NULL
        ORDER BY loss_percent DESC
        LIMIT 10;
        """
        result = db.execute(text(query)).fetchall()
        if result:
            print(f"✅ DATA EXISTS: {len(result)} batches with loss data")
            for row in result[:5]:
                print(f"   {row[0]}: {row[1]} - Loss: {row[2]:.1f}% - Efficiency: {row[3]:.1f}%")
        else:
            print("❌ NO DATA: no batches with post-harvest loss data")
        results.append(("Q3/Q4 - Pertes élevées", len(result) if result else 0, "✅ DATA" if result else "❌ NO DATA"))
    except Exception as e:
        print(f"❌ QUERY ERROR: {str(e)}")
        results.append(("Q3/Q4 - Pertes élevées", 0, f"❌ ERROR: {str(e)[:50]}"))
    
    # Q5: "Quels lots ont le plus grand écart entre entrée et sortie ?"
    print("\n[Q5] Quels lots ont le plus grand écart entre entrée et sortie ?")
    print("-" * 100)
    try:
        query = """
        SELECT 
            b.batch_id,
            b.product_id,
            b.quantity_in,
            b.quantity_out,
            (b.quantity_in - b.quantity_out) as gap,
            CASE WHEN b.quantity_in > 0 
                 THEN ((b.quantity_in - b.quantity_out) / b.quantity_in * 100)
                 ELSE 0 
            END as gap_percent
        FROM batches b
        WHERE b.quantity_in > 0
        ORDER BY gap DESC
        LIMIT 10;
        """
        result = db.execute(text(query)).fetchall()
        if result:
            print(f"✅ DATA EXISTS: {len(result)} batches with entry/exit gap")
            for row in result[:5]:
                print(f"   {row[0]}: {row[1]} - Gap: {row[4]} ({row[5]:.1f}%)")
        else:
            print("❌ NO DATA: no batches with quantity_in")
        results.append(("Q5 - Écart entrée/sortie", len(result) if result else 0, "✅ DATA" if result else "❌ NO DATA"))
    except Exception as e:
        print(f"❌ QUERY ERROR: {str(e)}")
        results.append(("Q5 - Écart entrée/sortie", 0, f"❌ ERROR: {str(e)[:50]}"))
    
    # Q6: "Quelles sont les étapes pré-récolte enregistrées ?"
    print("\n[Q6] Quelles sont les étapes pré-récolte enregistrées ?")
    print("-" * 100)
    try:
        query = """
        SELECT 
            COUNT(DISTINCT phs.process_step_id) as total_steps,
            COUNT(DISTINCT phs.parcel_id) as parcels_with_steps,
            COUNT(DISTINCT phs.step_type) as step_types
        FROM pre_harvest_steps phs;
        """
        result = db.execute(text(query)).fetchone()
        if result and result[0] > 0:
            print(f"✅ DATA EXISTS:")
            print(f"   Total steps: {result[0]}")
            print(f"   Parcels with steps: {result[1]}")
            print(f"   Step types: {result[2]}")
            results.append(("Q6 - Étapes pré-récolte", result[0], "✅ DATA"))
        else:
            print("❌ NO DATA: pre_harvest_steps table is empty")
            results.append(("Q6 - Étapes pré-récolte", 0, "❌ NO DATA"))
    except Exception as e:
        print(f"❌ QUERY ERROR: {str(e)}")
        results.append(("Q6 - Étapes pré-récolte", 0, f"❌ ERROR: {str(e)[:50]}"))
    
    # Check batches table size
    print("\n" + "=" * 100)
    print("DATABASE TABLE SUMMARY")
    print("=" * 100)
    
    tables_to_check = [
        ('batches', 'SELECT COUNT(*) FROM batches'),
        ('stocks', 'SELECT COUNT(*) FROM stocks'),
        ('post_harvest_steps', 'SELECT COUNT(*) FROM post_harvest_steps'),
        ('pre_harvest_steps', 'SELECT COUNT(*) FROM pre_harvest_steps'),
        ('parcels', 'SELECT COUNT(*) FROM parcels'),
    ]
    
    for table_name, query_str in tables_to_check:
        try:
            count = db.execute(text(query_str)).scalar()
            print(f"  {table_name}: {count} rows")
        except Exception as e:
            print(f"  {table_name}: ERROR - {str(e)[:50]}")
    
    db.close()
    
    # Summary
    print("\n" + "=" * 100)
    print("SUMMARY - QUERY VERIFICATION")
    print("=" * 100)
    print(f"\n{'Question':<40} | {'Records':<10} | Status")
    print("-" * 100)
    for question, count, status in results:
        print(f"{question:<40} | {count:<10} | {status}")
    
    print("\n" + "=" * 100)
    print("ANALYSIS")
    print("=" * 100)
    
    has_data = [r for r in results if '✅ DATA' in r[2]]
    no_data = [r for r in results if '❌ NO DATA' in r[2]]
    
    print(f"\n✅ Queries WITH data: {len(has_data)}")
    for q, _, _ in has_data:
        print(f"   - {q}")
    
    print(f"\n❌ Queries with NO data: {len(no_data)}")
    for q, _, _ in no_data:
        print(f"   - {q}")
    
    if no_data:
        print("\n⚠️  ISSUE: Chatbot is being asked for data that doesn't exist in the database!")
        print("   → This explains why responses return 'Donnée indisponible'")
        print("   → Database needs to be populated with test data for these queries")

if __name__ == '__main__':
    verify_queries()
