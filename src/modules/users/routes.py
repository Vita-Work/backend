from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_db_session
from src.modules.auth.dependencies import AuthContext, require_admin
from src.modules.users.schemas import CreateUserRequest, UserResponse
from src.modules.users.use_cases.create_user import UserEmailAlreadyExistsError, create_user
from src.modules.users.use_cases.get_user import get_user

router = APIRouter(prefix="/users", tags=["users"])
db_session_dependency = Depends(get_db_session)
admin_dependency = Depends(require_admin)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user_route(
    payload: CreateUserRequest,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> UserResponse:
    """Create a user for local development and MVP flows."""
    try:
        user = await create_user(
            session=session,
            email=payload.email,
            full_name=payload.full_name,
            timezone=payload.timezone,
            locale=payload.locale,
        )
    except UserEmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists.",
        ) from exc

    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_route(
    user_id: UUID,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> UserResponse:
    """Fetch a user by identifier."""
    user = await get_user(session=session, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    return UserResponse.model_validate(user)
