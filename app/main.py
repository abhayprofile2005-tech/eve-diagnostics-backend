from fastapi import FastAPI

from app.database import Base, engine
from app.routers import auth, bookings, centres, payments

# For this assignment's scope, tables are created directly from the models
# at startup rather than via Alembic migrations (see README > Assumptions
# and "what I'd improve" for the production alternative).
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EVE Healthcare - Diagnostics Booking API",
    description=(
        "Backend service for diagnostic test bookings and simulated payments."
    ),
    version="1.0.0",
)

app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(bookings.router)
app.include_router(payments.router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
