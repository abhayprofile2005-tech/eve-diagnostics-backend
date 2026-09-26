from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app import schemas
from app.database import get_db
from app.deps import get_current_user
from app.models import DiagnosticCentre, DiagnosticTest, User

router = APIRouter(tags=["diagnostic centres"])


@router.post(
    "/centres/",
    response_model=schemas.CentreOut,
    status_code=status.HTTP_201_CREATED,
)
def create_centre(
    payload: schemas.CentreCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    Any authenticated user may register a centre. There is no separate
    admin/staff role in this assignment's scope (see README > Assumptions);
    in production this would be restricted to a staff/admin role.
    """
    centre = DiagnosticCentre(name=payload.name, location=payload.location)
    db.add(centre)
    db.commit()
    db.refresh(centre)
    return centre


@router.get("/centres/", response_model=List[schemas.CentreOut])
def list_centres(db: Session = Depends(get_db)):
    return db.query(DiagnosticCentre).options(joinedload(DiagnosticCentre.tests)).all()


@router.get("/centres/{centre_id}", response_model=schemas.CentreOut)
def get_centre(centre_id: int, db: Session = Depends(get_db)):
    centre = (
        db.query(DiagnosticCentre)
        .options(joinedload(DiagnosticCentre.tests))
        .filter(DiagnosticCentre.id == centre_id)
        .first()
    )
    if not centre:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centre not found")
    return centre


@router.post(
    "/centres/{centre_id}/tests/",
    response_model=schemas.TestOut,
    status_code=status.HTTP_201_CREATED,
)
def add_test_to_centre(
    centre_id: int,
    payload: schemas.TestCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    centre = db.query(DiagnosticCentre).filter(DiagnosticCentre.id == centre_id).first()
    if not centre:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centre not found")

    test = DiagnosticTest(centre_id=centre.id, name=payload.name, price=payload.price)
    db.add(test)
    db.commit()
    db.refresh(test)
    return test


@router.get("/tests/", response_model=List[schemas.TestOut])
def list_tests(centre_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(DiagnosticTest)
    if centre_id is not None:
        query = query.filter(DiagnosticTest.centre_id == centre_id)
    return query.all()
