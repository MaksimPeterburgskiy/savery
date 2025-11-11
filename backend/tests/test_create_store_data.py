from uuid import UUID, uuid4

from sqlalchemy import and_, select

from backend.app.db import session_scope
from backend.app.models import Store, StoreChain
from backend.workers.tasks.scraping import scrape_hannaford
import pytest



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
                Store.name == store.name,
                Store.address_line1 == store.address_line1,
            )
        )
        existing_store = session.exec(statement).scalars().first()
        existing_chain_stmt = select(StoreChain).where(
                StoreChain.name == "Test Chain"
        )
        existing_chain = session.exec(existing_chain_stmt).scalars().first()
        if existing_store is None:
            store.chain_id = existing_chain.id
            session.add(store)
        session.flush()
    
    cleanup_store_chain_data()


def test_add_multiple_stores() -> None:

    chain = StoreChain(
        name="Test Chain",
    )
    stores = [
        Store(
            number="001",
            name="Test Store 1",
            city="Test City",
            region="Test Region",
            postal_code="12345",
            address_line1="123 Test St, Test City, TS 12345",
            timezone="America/New_York",
            phone="(123) 456-7890",
            hours_json='{"mon":"8am-9pm","tue":"8am-9pm","wed":"8am-9pm","thu":"8am-9pm","fri":"8am-10pm","sat":"8am-10pm","sun":"8am-8pm"}',
            geography='POINT(-74.0060 40.7128)',
        ),
        Store(
            number="002",
            name="Test Store 2",
            city="Another City",
            region="Another Region",
            postal_code="67890",
            address_line1="456 Another St, Another City, AR 67890",
            timezone="America/New_York",
            phone="(987) 654-3210",
            hours_json='{"mon":"9am-10pm","tue":"9am-10pm","wed":"9am-10pm","thu":"9am-10pm","fri":"9am-11pm","sat":"9am-11pm","sun":"9am-9pm"}',
            geography='POINT(-73.935242 40.730610)',
        ),
    ]
    
    with session_scope() as session:
        statement = select(StoreChain).where(
                StoreChain.name == chain.name,
        )
        existing_chain = session.exec(statement).scalars().first()
        if existing_chain is None:
            session.add(chain)
        existing_chain_stmt = select(StoreChain).where(
                StoreChain.name == "Test Chain"
        )
        existing_chain = session.exec(existing_chain_stmt).scalars().first()
        for store in stores:
            # Check if the store already exists
            statement = select(Store).where(
                and_(
                    Store.name == store.name,
                    Store.address_line1 == store.address_line1,
                )
            )
            existing_store = session.exec(statement).scalars().first()
            if existing_store is None:
                store.chain_id = existing_chain.id
                session.add(store)
        session.commit()
        # Verify that both stores were added
        all_stores = session.exec(select(Store)).scalars().all()
        assert len(all_stores) >= 2  
    cleanup_store_chain_data()
    
    
    
def test_add_multiple_chains() -> None:

    chains = [
        StoreChain(
            name="Test Chain 1",
        ),
        StoreChain(
            name="Test Chain 2",
        ),
    ]
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
        for chain in chains:
            # Check if the store chain already exists
            statement = select(StoreChain).where(
                    StoreChain.name == chain.name,
            )
            existing_chain = session.exec(statement).scalars().first()
            if existing_chain is None:
                session.add(chain)
        session.flush()
        
        existing_chain_stmt = select(StoreChain).where(
                StoreChain.name == "Test Chain 1"
        )
        existing_chain = session.exec(existing_chain_stmt).scalars().first()
        
        # Check if the store already exists
        statement = select(Store).where(
            and_(
                Store.name == store.name,
                Store.address_line1 == store.address_line1,
            )
        )
        existing_store = session.exec(statement).scalars().first()
        if existing_store is None:
            store.chain_id = existing_chain.id
            session.add(store)
        session.flush()


        assert len(session.exec(select(StoreChain)).scalars().all()) == 2
    cleanup_store_chain_data()
    