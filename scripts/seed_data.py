"""
Optional convenience script: populates a couple of diagnostic centres and
tests so you can try booking/payment flows in Swagger UI immediately after
starting the app, without creating them by hand first.

Usage:
    python -m scripts.seed_data
"""

from app.database import Base, SessionLocal, engine
from app.models import DiagnosticCentre, DiagnosticTest

Base.metadata.create_all(bind=engine)


def run():
    db = SessionLocal()
    try:
        if db.query(DiagnosticCentre).count() > 0:
            print("Centres already exist -- skipping seed.")
            return

        city = DiagnosticCentre(name="City Diagnostics", location="Prayagraj")
        metro = DiagnosticCentre(name="Metro Health Labs", location="Delhi")
        db.add_all([city, metro])
        db.flush()  # assigns ids without committing yet

        db.add_all(
            [
                DiagnosticTest(centre_id=city.id, name="Complete Blood Count", price=500),
                DiagnosticTest(centre_id=city.id, name="Lipid Profile", price=800),
                DiagnosticTest(centre_id=metro.id, name="Thyroid Panel", price=650),
                DiagnosticTest(centre_id=metro.id, name="COVID-19 RT-PCR", price=900),
            ]
        )
        db.commit()
        print("Seeded 2 centres and 4 diagnostic tests.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
