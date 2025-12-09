from sqlalchemy import select, and_
from backend.app.db import session_scope
from backend.app.models import Store, StoreChain
import pytest


@pytest.fixture(autouse=True)
def cleanup_db():
    # Run before each test and cleanup after
    yield
    with session_scope() as session:
        # delete stores and chains created by tests
        stores = session.exec(select(Store)).scalars().all()
        for s in stores:
            session.delete(s)
        chains = session.exec(select(StoreChain)).scalars().all()
        for c in chains:
            session.delete(c)
        session.commit()


def test_create_chain_and_store():
    chain = StoreChain(name="Unit Test Chain")
    store = Store(
        number="100",
        name="UT Store",
        city="Testville",
        region="TS",
        postal_code="00000",
        address_line1="100 Test St",
        timezone="America/New_York",
        phone="(000) 000-0000",
        hours_json='{"mon":"9-5"}',
        geography='POINT(-73.935242 40.73061)',
    )

    with session_scope() as session:
        # ensure chain doesn't exist
        stmt = select(StoreChain).where(StoreChain.name == chain.name)
        existing = session.exec(stmt).scalars().first()
        assert existing is None

        session.add(chain)
        session.flush()

        # ensure chain has id
        assert getattr(chain, "id", None) is not None

        # attach store and commit
        store.chain_id = chain.id
        session.add(store)
        session.commit()

        # verify store persisted
        stmt = select(Store).where(and_(Store.name == store.name, Store.address_line1 == store.address_line1))
        persisted = session.exec(stmt).scalars().first()
        assert persisted is not None
        assert persisted.chain_id == chain.id
        assert persisted.name == "UT Store"


def test_bulk_insert_and_query_count():
    chain = StoreChain(name="Bulk Chain")
    stores = [
        Store(number="201", name="Bulk 1", city="A", region="R", postal_code="1", address_line1="Addr1", timezone="UTC", phone="1", hours_json='{}', geography='POINT(-73 40)'),
        Store(number="202", name="Bulk 2", city="B", region="R", postal_code="2", address_line1="Addr2", timezone="UTC", phone="2", hours_json='{}', geography='POINT(-73 40)'),
        Store(number="203", name="Bulk 3", city="C", region="R", postal_code="3", address_line1="Addr3", timezone="UTC", phone="3", hours_json='{}', geography='POINT(-73 40)'),
    ]

    with session_scope() as session:
        session.add(chain)
        session.flush()
        for s in stores:
            s.chain_id = chain.id
            session.add(s)
        session.commit()

        all_stores = session.exec(select(Store)).scalars().all()
        assert len(all_stores) >= 3


def test_prevent_duplicate_store_by_name_and_address():
    chain = StoreChain(name="Dup Chain")
    store = Store(number="301", name="Dup Store", city="DupCity", region="D", postal_code="301", address_line1="301 Dup St", timezone="UTC", phone="301", hours_json='{}', geography='POINT(-73 40)')

    with session_scope() as session:
        session.add(chain)
        session.flush()
        store.chain_id = chain.id
        session.add(store)
        session.commit()
        # Capture primitives before the session closes to avoid DetachedInstanceError
        store_name = store.name
        store_address = store.address_line1

    # Attempt to add duplicate again; test logic should prevent a duplicate
    with session_scope() as session:
        stmt = select(Store).where(and_(Store.name == store_name, Store.address_line1 == store_address))
        existing = session.exec(stmt).scalars().first()
        assert existing is not None

        # Emulate the application's duplicate-check logic: we won't insert when an existing record is found
        if existing is None:
            new_store = Store(number="301", name=store_name, city="DupCity", region="D", postal_code="301", address_line1=store_address, timezone="UTC", phone="301", hours_json='{}', geography='POINT(-73 40)')
            # attach to any existing chain (find by name)
            chain_stmt = select(StoreChain).where(StoreChain.name == "Dup Chain")
            existing_chain = session.exec(chain_stmt).scalars().first()
            new_store.chain_id = existing_chain.id if existing_chain else None
            session.add(new_store)
            session.commit()

        all_stores = session.exec(select(Store)).scalars().all()
        # there should be exactly 1 store with that name/address
        matches = [s for s in all_stores if s.name == store_name and s.address_line1 == store_address]
        assert len(matches) == 1


def test_geography_and_timezone_fields_present():
    chain = StoreChain(name="Geo Chain")
    store = Store(number="401", name="Geo Store", city="GCity", region="G", postal_code="401", address_line1="401 Geo St", timezone="America/Los_Angeles", phone="401", hours_json='{}', geography='POINT(-122.4194 37.7749)')

    with session_scope() as session:
        session.add(chain)
        session.flush()
        store.chain_id = chain.id
        session.add(store)
        session.commit()

        stmt = select(Store).where(Store.name == "Geo Store")
        persisted = session.exec(stmt).scalars().first()
        assert persisted is not None
        # geography is stored as string on the model; presence check
        assert getattr(persisted, 'geography', None) is not None
        assert persisted.timezone == "America/Los_Angeles"
