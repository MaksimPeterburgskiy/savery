from uuid import UUID, uuid4

from sqlalchemy import and_, select

from backend.app.db import session_scope
from backend.app.models import Store, StoreChain
from backend.workers.tasks.scraping import scrape_hannaford
import pytest
from fastapi.testclient import TestClient



def cleanup_store_chain_data() -> None:
    with session_scope() as session:

        # Delete any stores belonging to the chain
        stores = session.exec(select(Store)).scalars().all()
        for store_ in stores:
            session.delete(store_)

        # Then delete the chain itself
        statement = select(StoreChain)
        store_chain = session.exec(statement).scalars().first()
        if store_chain:
            session.delete(store_chain)
        session.commit()

def test_add_store_chain() -> None:
    chain = StoreChain(
        name="Test Chain",
    )
    
    with session_scope() as session:
        # Check if the store chain already exists
        statement = select(StoreChain).where(
                StoreChain.name == chain.name,
        )
        existing_chain = session.exec(statement).scalars().first()
        if existing_chain is None:
            session.add(chain)
        session.flush()
    # pass the primitive id (not the detached model instance) so cleanup
    # doesn't try to access attributes on a detached StoreChain instance
    cleanup_store_chain_data()
    
def test_add_single_store() -> None:

    chain = StoreChain(
        name="Test Chain",
    )
    store = Store(
        number="001",
        name="Test Store",
        city="Test City",
        region="Test Region",
        postal_code="12345",
        address_line1="123 Test St, Test City, TS 12345",
        timezone="America/New_York",
        phone="(123) 456-7890",
        hours_json='{"mon":"8am-9pm","tue":"8am-9pm","wed":"8am-9pm","thu":"8am-9pm","fri":"8am-10pm","sat":"8am-10pm","sun":"8am-8pm"}',
        geography='POINT(-74.0060 40.7128)',
    )
    
    with session_scope() as session:
        statement = select(StoreChain).where(
                StoreChain.name == chain.name,
        )
        existing_chain = session.exec(statement).scalars().first()
        if existing_chain is None:
            session.add(chain)
        
        # Check if the store already exists
        statement = select(Store).where(
            and_(
                Store.chain_id == existing_chain.id,
                Store.name == store.name,
                Store.address_line1 == store.address_line1,
            )
        )
        existing_store = session.exec(statement).scalars().first()
        if existing_store is None:
            session.add(store)
        session.flush()
    
    cleanup_store_chain_data()



def test_create_store_data() -> None:
    stores = scrape_hannaford()
    #make sure store chains exist
    with session_scope() as session:
        statement = select(StoreChain).where(StoreChain.name == "Hannaford")
        existing_chain = session.exec(statement).scalars().first()
        if existing_chain is None:
            hannaford_chain = StoreChain(
                name="Hannaford",
            )
            session.add(hannaford_chain)
            session.commit()
    with session_scope() as session:
        statement = select(StoreChain).where(StoreChain.name == "Hannaford")
        existing_chain = session.exec(statement).scalars().first()
        for store in stores:
            store.chain_id = existing_chain.id
            # Check if the store already exists
            print(store.number)
            statement = select(Store).where(
                and_(
                    Store.name == store.name,
                    Store.chain_id == store.chain_id,
                )
            )
            existing_store = session.exec(statement).scalars().first()
            if existing_store is None:
                session.add(store)
            session.flush() 
        session.commit()
    cleanup_store_chain_data()
    
