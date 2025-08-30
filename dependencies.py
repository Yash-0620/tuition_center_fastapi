from fastapi import Request, Depends, HTTPException
from sqlmodel import Session, select
from models import User
from db import get_session


def get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    username = request.cookies.get("username")
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user")

    return user