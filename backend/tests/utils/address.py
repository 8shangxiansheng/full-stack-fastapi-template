from sqlmodel import Session

from app.models import Address, User


def create_random_address(db: Session, user: User, is_default: bool = False) -> Address:
    address = Address(
        user_id=user.id,
        receiver_name="张三",
        receiver_phone="13800000000",
        province="上海市",
        city="上海市",
        district="浦东新区",
        detail="世纪大道 1 号",
        is_default=is_default,
    )
    db.add(address)
    db.commit()
    db.refresh(address)
    return address
