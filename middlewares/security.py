from fastapi.security import OAuth2PasswordBearer
from fastapi import HTTPException, Depends
import jwt
from core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def authenticate_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")