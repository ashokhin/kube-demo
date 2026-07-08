from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import select

from src.config import settings
from src.models import Order

# create_async_engine creates a connection pool shared across all requests.
# echo=False suppresses SQL logging in production; set to True locally for debugging.
engine = create_async_engine(settings.database_url, echo=False)

# async_sessionmaker is a factory that produces AsyncSession objects.
# expire_on_commit=False keeps ORM objects usable after commit without re-querying.
# This matters here because we return the Order object and read its id after commit.
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def create_order(customer_id: str, product_id: str, quantity: int) -> Order:
    async with SessionLocal() as session:
        order = Order(customer_id=customer_id, product_id=product_id, quantity=quantity)
        session.add(order)
        await session.commit()
        return order


async def get_order(order_id: str) -> Order | None:
    async with SessionLocal() as session:
        result = await session.execute(select(Order).where(Order.id == order_id))
        return result.scalar_one_or_none()


async def check_db_connection() -> bool:
    # Used by the /readyz probe to verify the DB is reachable.
    # select(1) is the lightest possible query — no table access.
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
        return True
    except Exception:
        return False
