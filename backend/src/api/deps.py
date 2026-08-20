from typing import Any

from sqlalchemy.orm import Query, Session

from ..db.models import GoldenCustomer, RoleEnum, User


def scope_golden_customers(query: Query, user: User, db: Session) -> Query:
    if user.role == RoleEnum.ADMIN:
        return query
    if user.role == RoleEnum.MANAGER:
        rm_ids = [u.id for u in db.query(User).filter(User.manager_id == user.id).all()] + [user.id]
        return query.filter(GoldenCustomer.rm_id.in_(rm_ids))
    return query.filter(GoldenCustomer.rm_id == user.id)


def mask_pii(value: Any) -> Any:
    if value is None:
        return None
    value = str(value)
    return value if len(value) <= 4 else "*" * (len(value) - 4) + value[-4:]


def can_unmask(user: User, unmask: bool) -> bool:
    return user.role == RoleEnum.ADMIN and unmask
