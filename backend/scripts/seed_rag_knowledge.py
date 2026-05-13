#!/usr/bin/env python3
"""
Seed RAG knowledge base with French agricultural best practices.

This script populates rag_documents and rag_chunks tables with high-quality French knowledge
about post-harvest and pre-harvest agricultural practices specific to the cooperative context.

Usage:
    python backend/scripts/seed_rag_knowledge.py

Run this after alembic migrations to populate the knowledge base for testing/demo.
"""

import hashlib
import sys
import uuid
from datetime import datetime

sys.path.insert(0, "/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project")
sys.path.insert(0, "/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend")

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import engine
from app.models.rag import RAGChunk, RAGDocument
from app.models.cooperative import Cooperative
from app.services.rag_embeddings import embed_texts


# French knowledge content organized by topic
KNOWLEDGE_DOCUMENTS = [
    {
        "title": "Séchage — réduction des pertes",
        "source_type": "knowledge_base",
        "source_table": "agricultural_knowledge",
        "source_record_ref": "drying_loss_reduction",
        "language": "fr",
        "stage": "drying",
        "topic": "loss_reduction",
        "product": ["mango", "peanut", "millet"],
        "chunks": [
            {
                "content": "Le séchage est une étape critique pour réduire les pertes post-récolte. "
                "L'humidité relative doit être maintenue entre 60-70% pour éviter la pourriture et le sur-séchage. "
                "Une température de 30-40°C est idéale pour la plupart des fruits tropicaux. "
                "Le temps de séchage varie selon le produit : 5-7 jours pour la mangue, 10-14 jours pour l'arachide. "
                "Une perte normale est de 10-15% du poids initial. Si elle dépasse 20%, vérifiez l'humidité ambiante."
            },
            {
                "content": "Pour réduire les pertes durant le séchage : "
                "1. Utilisez des bâches ou des séchoirs couverts pour contrôler l'humidité. "
                "2. Aérez régulièrement pour éviter la condensation et la moisissure. "
                "3. Inspectez quotidiennement pour détecter les fruits abîmés. "
                "4. Retournez les fruits tous les 2-3 jours pour un séchage homogène. "
                "5. Utilisez du sel de maïs ou du charbon pour absorber l'humidité excessive. "
                "6. Installez un hygromètre pour monitorer précisément l'humidité."
            },
        ]
    },
    {
        "title": "Tri — bonnes pratiques pour la mangue",
        "source_type": "knowledge_base",
        "source_table": "agricultural_knowledge",
        "source_record_ref": "sorting_mango_best_practices",
        "language": "fr",
        "stage": "sorting",
        "topic": "quality",
        "product": ["mango"],
        "chunks": [
            {
                "content": "Le tri est essentiel pour garantir la qualité finale et réduire les pertes. "
                "Classez les mangues selon trois grades : "
                "Grade A (fruits sans défaut, lisses, couleur uniforme) - Premium. "
                "Grade B (petits défauts cosmétiques, trace légère) - Standard. "
                "Grade C (défauts importants, taches, écorchures) - Transformation. "
                "Éliminez systématiquement les fruits pourris, blessés ou moisis."
            },
            {
                "content": "Procédure optimale de tri pour la mangue : "
                "1. Réalisez un pré-tri pour enlever les fruits abîmés (réduction de perte 3-5%). "
                "2. Utilisez une table de tri avec bonne lumière naturelle. "
                "3. Travaillez en équipes de 3-4 personnes par table pour qualité constante. "
                "4. Temps de tri ne doit pas dépasser 15 secondes par fruit. "
                "5. Pesez chaque grade pour documenter les rendements. "
                "6. Une perte acceptable au tri est 5-8% (fruits éliminés)."
            },
        ]
    },
    {
        "title": "Emballage et conditionnement",
        "source_type": "knowledge_base",
        "source_table": "agricultural_knowledge",
        "source_record_ref": "packaging_conditioning",
        "language": "fr",
        "stage": "packaging",
        "topic": "quality",
        "product": ["mango", "peanut", "millet"],
        "chunks": [
            {
                "content": "Un bon emballage prévient la dégradation et réduit les pertes en transport. "
                "Pour les fruits frais : utilisez des caisses en bois aérées ou en carton ondulé. "
                "Pour l'arachide et le millet : utilisez des sacs tissés ou en papier épais. "
                "Tout emballage doit être propre, sec et sans odeurs suspectes. "
                "Ajoutez du papier ou du charbon absorbant pour limiter l'humidité. "
                "Une perte acceptable à l'emballage est 1-2%."
            },
            {
                "content": "Bonnes pratiques d'emballage : "
                "1. Placez les fruits délicats au centre, protégés par les fruits plus robustes. "
                "2. Ne surcharger pas les caisses (maximum 20 kg par caisse pour la mangue). "
                "3. Fermez les emballages doucement pour éviter les écrasements. "
                "4. Appliquez des étiquettes avec la date, le grade et le produit. "
                "5. Stockez les emballages fermés à l'ombre et en lieu sec. "
                "6. Pour l'export, utilisez du papier protecteur entre les fruits."
            },
        ]
    },
    {
        "title": "Bilan matière — suivi des pertes",
        "source_type": "knowledge_base",
        "source_table": "agricultural_knowledge",
        "source_record_ref": "material_balance_tracking",
        "language": "fr",
        "stage": "general",
        "topic": "material_balance",
        "product": ["mango", "peanut", "millet"],
        "chunks": [
            {
                "content": "Le bilan matière est l'outil clé pour identifier les pertes à chaque étape. "
                "Formule : Quantité entrante = Quantité sortante + Pertes + Résidus. "
                "Exemple pour 100 kg de mangue : "
                "Entrée : 100 kg (brute). "
                "Nettoyage : 97 kg (perte 3%). "
                "Séchage : 82 kg (perte 15%, attendu 10-15%). "
                "Tri : 76 kg (perte 8%, Grade A à B à C). "
                "Emballage : 74 kg (perte 2%, produit fini). "
                "Perte totale : 26 kg (26%) dont 22 kg expliquées et 4 kg anomalies."
            },
            {
                "content": "Comment utiliser le bilan matière : "
                "1. Enregistrez le poids à chaque étape de transformation. "
                "2. Calculez les pertes par étape : (Qté_entrée - Qté_sortie) / Qté_entrée * 100. "
                "3. Comparez avec les pertes normales attendues (benchmarks). "
                "4. Investiguer si pertes réelles > attendues + 5%. "
                "5. Documentez les causes (moisissure, écrasement, casse, évaporation). "
                "6. Mettez à jour les procédures pour réduire les pertes futures."
            },
        ]
    },
    {
        "title": "Post-récolte — flux de transformation",
        "source_type": "knowledge_base",
        "source_table": "agricultural_knowledge",
        "source_record_ref": "post_harvest_flow",
        "language": "fr",
        "stage": "post_harvest",
        "topic": "traceability",
        "product": ["mango", "peanut", "millet"],
        "chunks": [
            {
                "content": "La transformation post-récolte suit un flux standardisé pour chaque produit. "
                "Pour la MANGUE : Réception → Nettoyage → Séchage → Tri → Emballage → Stockage. "
                "Pour l'ARACHIDE : Réception → Séchage → Épiuchage → Tri → Conditionnement → Stockage. "
                "Pour le MILLET : Réception → Séchage → Décorticage → Tri → Conditionnement → Stockage. "
                "À chaque étape, enregistrez : heure, opérateur, quantité entrante, quantité sortante, défauts observés."
            },
            {
                "content": "Importance de la traçabilité post-récolte : "
                "1. Chaque lot doit avoir un code unique (ex: MANG-20250512-001). "
                "2. Documentez la source (vendeur, village, date de livraison). "
                "3. Enregistrez chaque transformation avec responsable et heure. "
                "4. En cas de problème qualité, tracez le produit jusqu'à la source. "
                "5. Conservez les documents au moins 2 ans. "
                "6. Partagez les données avec les producteurs pour amélioration continue."
            },
        ]
    },
    {
        "title": "Pré-récolte — suivi des parcelles",
        "source_type": "knowledge_base",
        "source_table": "agricultural_knowledge",
        "source_record_ref": "pre_harvest_parcel_tracking",
        "language": "fr",
        "stage": "pre_harvest",
        "topic": "preharvest",
        "product": ["mango", "peanut", "millet"],
        "chunks": [
            {
                "content": "Le suivi pré-récolte détermine la qualité finale des fruits/grains. "
                "Pour chaque parcelle, suivez : "
                "1. Variété et date de plantation. "
                "2. Date du dernier traitement phytosanitaire (type et dose). "
                "3. État actuel (nombre de fruits/régimes, % floraison, signes de maladie). "
                "4. Prévision de récolte (date estimée et quantité attendue). "
                "5. Besoins d'entretien urgent (taille, arrosage, fertilisation). "
                "6. Risques identifiés (maladie, ravageurs, sécheresse)."
            },
            {
                "content": "Préparation optimale avant récolte : "
                "1. Inspectez les fruits 1-2 semaines avant récolte prévue. "
                "2. Éliminez les fruits pourris, malades ou infestés avant maturité. "
                "3. Assurez-vous que l'équipe de récolte est bien formée. "
                "4. Préparez les caisses, les outils et le transport la veille. "
                "5. Vérifiez la météo (évitez récoltez en forte pluie ou chaleur extrême). "
                "6. Retirez les fruits mûrs tous les 3-4 jours pour encourager la continuite."
            },
        ]
    },
]


def get_cooperative_id(db: Session) -> uuid.UUID | None:
    """Get the first cooperative ID or a demo ID if none exist."""
    coop = db.query(Cooperative).first()
    if coop:
        return coop.id
    print("⚠️  No cooperative found. Using demo UUID.")
    return uuid.uuid4()


def generate_deterministic_embedding(text: str, dimensions: int = 1536) -> list[float]:
    """Generate a deterministic pseudo-embedding from text hash."""
    hash_obj = hashlib.sha256(text.encode())
    hash_hex = hash_obj.hexdigest()
    # Convert hash to vector by expanding 64 hex chars to 1536 dimensions
    embedding = []
    for i in range(dimensions):
        char_idx = (i * 2) % len(hash_hex)
        byte_val = int(hash_hex[char_idx:char_idx+2], 16) / 255.0
        # Normalize to ~[-1, 1] for more realistic embeddings
        embedding.append((byte_val - 0.5) * 2)
    return embedding


def seed_rag_knowledge(db: Session, cooperative_id: uuid.UUID) -> None:
    """Seed RAG knowledge base with French agricultural best practices."""
    print(f"🌱 Starting RAG knowledge seed for cooperative {cooperative_id}...")
    
    # Collect all chunk texts for batch embedding
    all_texts_to_embed = []
    text_to_chunk_info = {}  # Map text to document/chunk info
    
    for doc_info in KNOWLEDGE_DOCUMENTS:
        for chunk_info in doc_info["chunks"]:
            text = chunk_info["content"]
            all_texts_to_embed.append(text)
            text_to_chunk_info[text] = (doc_info, chunk_info)
    
    # Try to embed using the configured provider, fallback to deterministic
    try:
        print(f"🔌 Attempting to embed {len(all_texts_to_embed)} chunks...")
        embeddings = embed_texts(all_texts_to_embed)
        print(f"✅ Successfully embedded {len(embeddings)} chunks")
    except Exception as e:
        print(f"⚠️  Embedding service unavailable ({e}). Using deterministic embeddings.")
        embeddings = [generate_deterministic_embedding(text) for text in all_texts_to_embed]
    
    # Create documents and chunks
    created_count = 0
    skipped_count = 0
    
    for doc_info in KNOWLEDGE_DOCUMENTS:
        # Check if document already exists
        source_ref = doc_info["source_record_ref"]
        existing = db.query(RAGDocument).filter(
            RAGDocument.cooperative_id == cooperative_id,
            RAGDocument.source_record_ref == source_ref,
        ).first()
        
        if existing:
            print(f"⏭️  Skipping {doc_info['title']} (already exists)")
            skipped_count += 1
            continue
        
        # Create document
        content_for_hash = " ".join(chunk["content"] for chunk in doc_info["chunks"])
        content_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()[:16]
        
        doc = RAGDocument(
            cooperative_id=cooperative_id,
            source_type=doc_info["source_type"],
            source_table=doc_info["source_table"],
            source_record_ref=doc_info["source_record_ref"],
            title=doc_info["title"],
            content_hash=content_hash,
            metadata_json={
                "language": doc_info.get("language", "fr"),
                "stage": doc_info.get("stage"),
                "topic": doc_info.get("topic"),
                "products": doc_info.get("product", []),
            },
        )
        db.add(doc)
        db.flush()  # Get the doc ID before creating chunks
        
        # Create chunks
        for chunk_idx, chunk_info in enumerate(doc_info["chunks"]):
            text = chunk_info["content"]
            # Find corresponding embedding
            embedding = embeddings[all_texts_to_embed.index(text)]
            
            chunk = RAGChunk(
                document_id=doc.id,
                cooperative_id=cooperative_id,
                chunk_index=chunk_idx,
                content=text,
                embedding=embedding,
                metadata_json={
                    "language": "fr",
                    "stage": doc_info.get("stage"),
                    "topic": doc_info.get("topic"),
                    "products": doc_info.get("product", []),
                    "document_title": doc_info["title"],
                }
            )
            db.add(chunk)
        
        print(f"✨ Created document: {doc_info['title']} ({len(doc_info['chunks'])} chunks)")
        created_count += 1
    
    # Commit all changes
    db.commit()
    print(f"\n✅ RAG seed complete!")
    print(f"   📊 Created: {created_count} documents")
    print(f"   ⏭️  Skipped: {skipped_count} documents (already exist)")
    print(f"   📝 Total chunks: {sum(len(doc['chunks']) for doc in KNOWLEDGE_DOCUMENTS)}")


if __name__ == "__main__":
    print("🚀 RAG Knowledge Base Seeding\n")
    
    try:
        with Session(engine) as db:
            coop_id = get_cooperative_id(db)
            seed_rag_knowledge(db, coop_id)
            print("\n✅ Success! RAG knowledge base is ready.")
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
