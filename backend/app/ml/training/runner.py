from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.ml.training.trainer import train_models


def run_training():
    db: Session = SessionLocal()
    try:
        result = train_models(db, run_name="container-startup")
        print(f"ML training completed. Model version: {result['model_version']}")
    finally:
        db.close()


if __name__ == "__main__":
    run_training()
