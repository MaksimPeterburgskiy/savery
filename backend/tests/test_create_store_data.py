from uuid import UUID, uuid4

from sqlalchemy import and_, select

from backend.app.db import session_scope
from backend.app.models import Store, StoreChain
from backend.workers.tasks.scraping import scrape_hannaford
import pytest
from fastapi.testclient import TestClient

@pytest.fixture()
def client() -> TestClient:
    with TestClient(create_app()) as c:
        yield c

def cleanup_store_data(id) -> None:
    with session_scope() as session:
        # Delete store by id
        statement = select(Store).where(Store.id == id)
        store = session.exec(statement).scalars().first()
        if store:
            session.delete(store)
            session.commit()

def cleanup_store_chain_data(id : UUID) -> None:
    with session_scope() as session:
        # Delete any stores belonging to the chain
        stores = session.exec(select(Store).where(Store.chain_id == id)).scalars().all()
        for store in stores:
            session.delete(store)

        # Then delete the chain itself
        statement = select(StoreChain).where(StoreChain.id == id)
        store_chain = session.exec(statement).scalars().first()
        if store_chain:
            session.delete(store_chain)
  

def test_add_store_chain() -> None:
    id = uuid4()   
    chain = StoreChain(
        id=id,
        name="Test Chain",
    )
    
    with session_scope() as session:
        # Check if the store chain already exists
        statement = select(StoreChain).where(
            and_(
                StoreChain.id == chain.id,
                StoreChain.name == chain.name,
            )
        )
        existing_chain = session.exec(statement).scalars().first()
        if existing_chain is None:
            session.add(chain)
        session.flush()
    cleanup_store_chain_data(id)
    
def test_add_single_store() -> None:
    store = Store(
        
        id=UUID("123e4567-e89b-12d3-a456-426614174000"),
        number="001",
        chain_id=UUID("123e4567-e89b-12d3-a456-426614174001"),
        name="Test Store",
        city="Test City",
        region="Test Region",
        postal_code="12345",
        address_line1="123 Test St, Test City, TS 12345",
        latitude=40.7128,
        timezone="America/New_York",
        phone="(123) 456-7890",
        hours_json='{"mon":"8am-9pm","tue":"8am-9pm","wed":"8am-9pm","thu":"8am-9pm","fri":"8am-10pm","sat":"8am-10pm","sun":"8am-8pm"}',
        longitude=-74.0060,
        geography='POINT(-74.0060 40.7128)',
    )

    with session_scope() as session:
        # Check if the store already exists
        statement = select(Store).where(
            and_(
                Store.id == store.id,
                Store.chain_id == store.chain_id,
                Store.name == store.name,
                Store.address_line1 == store.address_line1,
            )
        )
        existing_store = session.exec(statement).scalars().first()
        if existing_store is None:
            session.add(store)
            session.commit()

    cleanup_store_data(store.id)
    

def test_create_store_data() -> None:
    stores = scrape_hannaford()
    
    #make sure store chains exist
    with session_scope() as session:
        statement = select(StoreChain).where(StoreChain.name == "Hannaford")
        existing_chain = session.exec(statement).scalars().first()
        if existing_chain is None:
            hannaford_chain = StoreChain(
                id=UUID("11111111-1111-1111-1111-111111111111"),
                name="Hannaford",
            )
            session.add(hannaford_chain)
            session.commit()
    
    with session_scope() as session:
        for store in stores:
            # Check if the store already exists
            statement = select(Store).where(
                and_(
                    Store.client_id == "hannaford",
                    Store.store_chain_id == store.store_chain_id,
                    Store.name == store.name,
                    Store.address == store.address,
                )
            )
            existing_store = session.exec(statement).scalars().first()
            if existing_store is None:
                session.add(store)
        session.commit()
    
    
    def test_store_count() -> None:
        with session_scope() as session:
            statement = select(Store).where(Store.client_id == "hannaford")
            store_count = session.exec(statement).scalars().all()
            assert len(store_count) >= 10  # Assuming we expect at least 10 stores