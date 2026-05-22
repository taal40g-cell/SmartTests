from passlib.context import CryptContext
from passlib.exc import UnknownHashError



# ==============================
# Password Hashing Context
# ==============================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ==============================
# Password Helpers
# ==============================
def hash_password(password: str) -> str:
    """Hash a plain password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against its hashed value.
    Supports multiple hash formats (via passlib).
    """
    try:
        return pwd_context.verify(password, hashed_password)
    except UnknownHashError:
        return False

