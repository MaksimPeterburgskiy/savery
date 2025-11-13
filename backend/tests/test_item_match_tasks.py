"""End-to-end tests for the item match worker tasks."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID, uuid4

from sqlmodel import select

from backend.app.db import session_scope
from backend.app.models import (
    ItemMatch,
    ItemMatchCandidate,
    Job,
    JobStage,
    JobStatus,
    ListItem,
    PlanSelectedStore,
    Product,
    RoutePlan,
    ShoppingList,
    Store,
    StoreChain,
    StoreProduct,
)
from backend.workers.tasks.item_matches import (
    create_item_match_candidates,
    fanout_candidates_to_item_matches,
)


def _delete_entities(entity_ids: dict[type, list[UUID]]) -> None:
    """Remove the created test rows in dependency order."""

    order = [
        ItemMatch,
        ItemMatchCandidate,
        PlanSelectedStore,
        StoreProduct,
        Job,
        RoutePlan,
        ListItem,
        ShoppingList,
        Store,
        StoreChain,
        Product,
    ]

    with session_scope() as session:
        for model in order:
            for entity_id in entity_ids.get(model, []):
                instance = session.get(model, entity_id)
                if instance is not None:
                    session.delete(instance)


def test_create_item_match_candidates_generates_unique_candidates() -> None:
    """The MATCH task should insert one candidate per matching product and clean up old rows."""

    entity_ids: dict[type, list[UUID]] = defaultdict(list)

    client_id = f"client-{uuid4()}"
    item_name = "organic milk"
    sku_counter = 0

    def new_sku() -> str:
        nonlocal sku_counter
        sku_counter += 1
        return f"SKU-{sku_counter}-{uuid4()}"

    with session_scope() as session:
        chain = StoreChain(name=f"Chain {uuid4()}")
        session.add(chain)
        session.flush()
        entity_ids[StoreChain].append(chain.id)

        store_a = Store(
            chain_id=chain.id,
            name="Test Store A",
            number="100",
            address_line1="1 Main St",
            city="Testville",
            region="TS",
            postal_code="12345",
            country_code="US",
            timezone="UTC",
            phone="555-0001",
        )
        session.add(store_a)
        session.flush()
        entity_ids[Store].append(store_a.id)

        store_b = Store(
            chain_id=chain.id,
            name="Test Store B",
            number="200",
            address_line1="2 Main St",
            city="Testville",
            region="TS",
            postal_code="12345",
            country_code="US",
            timezone="UTC",
            phone="555-0002",
        )
        session.add(store_b)
        session.flush()
        entity_ids[Store].append(store_b.id)

        product_milk = Product(
            brand="Brand",
            name="Organic Whole Milk",
            upc=str(uuid4()),
        )
        product_oatmilk = Product(
            brand="Brand",
            name="Organic Oat Milk",
            upc=str(uuid4()),
        )
        product_irrelevant = Product(
            brand="Brand",
            name="Organic Bananas",
            upc=str(uuid4()),
        )
        session.add(product_milk)
        session.add(product_oatmilk)
        session.add(product_irrelevant)
        session.flush()
        entity_ids[Product].extend(
            [product_milk.id, product_oatmilk.id, product_irrelevant.id]
        )
        product_milk_id = product_milk.id
        product_oatmilk_id = product_oatmilk.id

        store_products = [
            StoreProduct(
                store_id=store_a.id,
                product_id=product_milk.id,
                external_sku=new_sku(),
            ),
            StoreProduct(
                store_id=store_b.id,
                product_id=product_milk.id,
                external_sku=new_sku(),
            ),
            StoreProduct(
                store_id=store_a.id,
                product_id=product_oatmilk.id,
                external_sku=new_sku(),
            ),
            StoreProduct(
                store_id=store_a.id,
                product_id=product_irrelevant.id,
                external_sku=new_sku(),
            ),
        ]
        session.add_all(store_products)
        session.flush()
        entity_ids[StoreProduct].extend(sp.id for sp in store_products)

        shopping_list = ShoppingList(client_id=client_id, title="Test List")
        session.add(shopping_list)
        session.flush()
        entity_ids[ShoppingList].append(shopping_list.id)

        list_item = ListItem(
            list_id=shopping_list.id,
            position=1,
            item_name=item_name,
            raw_text_item="2 x organic milk",
        )
        session.add(list_item)
        session.flush()
        entity_ids[ListItem].append(list_item.id)

        route_plan = RoutePlan(list_id=shopping_list.id, client_id=client_id)
        session.add(route_plan)
        session.flush()
        entity_ids[RoutePlan].append(route_plan.id)
        route_plan_id = route_plan.id

        selections = [
            PlanSelectedStore(plan_id=route_plan.id, store_id=store_a.id),
            PlanSelectedStore(plan_id=route_plan.id, store_id=store_b.id),
        ]
        session.add_all(selections)
        session.flush()
        entity_ids[PlanSelectedStore].extend(sel.id for sel in selections)

        existing_candidate = ItemMatchCandidate(
            plan_id=route_plan.id,
            list_item_id=list_item.id,
            product_id=product_irrelevant.id,
            score=10.0,
        )
        session.add(existing_candidate)
        session.flush()
        entity_ids[ItemMatchCandidate].append(existing_candidate.id)
        existing_candidate_id = existing_candidate.id

        job = Job(plan_id=route_plan.id, stage=JobStage.MATCH)
        session.add(job)
        session.flush()
        entity_ids[Job].append(job.id)
        job_id = job.id

    result = create_item_match_candidates.run(job_id=str(job_id))
    assert result == {"job_id": str(job_id)}

    with session_scope() as session:
        refreshed_job = session.get(Job, job_id)
        assert refreshed_job is not None
        assert refreshed_job.status is JobStatus.SUCCESS
        assert refreshed_job.progress_total == 1
        assert refreshed_job.progress_current == 1

        candidates = session.exec(
            select(ItemMatchCandidate).where(ItemMatchCandidate.plan_id == route_plan_id)
        ).all()
        candidate_ids = {candidate.id for candidate in candidates}
        entity_ids[ItemMatchCandidate].extend(
            cid for cid in candidate_ids if cid not in entity_ids[ItemMatchCandidate]
        )

        product_ids = {candidate.product_id for candidate in candidates}

        assert product_ids == {product_milk_id, product_oatmilk_id}
        assert existing_candidate_id not in candidate_ids
        assert all(candidate.score == 100 for candidate in candidates)

    _delete_entities(entity_ids)


def test_create_item_match_candidates_handles_branded_and_unbranded_items() -> None:
    """MATCH task should surface branded and generic options for every list item across stores."""

    entity_ids: dict[type, list[UUID]] = defaultdict(list)

    client_id = f"client-{uuid4()}"
    sku_counter = 0

    def new_sku() -> str:
        nonlocal sku_counter
        sku_counter += 1
        return f"SKU-{sku_counter}-{uuid4()}"

    with session_scope() as session:
        chain = StoreChain(name=f"Chain {uuid4()}")
        session.add(chain)
        session.flush()
        entity_ids[StoreChain].append(chain.id)

        hannaford = Store(
            chain_id=chain.id,
            name="Hannaford",
            number="101",
            address_line1="101 Market St",
            city="Townsville",
            region="TS",
            postal_code="10001",
            country_code="US",
            timezone="UTC",
            phone="555-1010",
        )
        pricechopper = Store(
            chain_id=chain.id,
            name="PriceChopper",
            number="202",
            address_line1="202 Market St",
            city="Townsville",
            region="TS",
            postal_code="10001",
            country_code="US",
            timezone="UTC",
            phone="555-2020",
        )
        session.add_all([hannaford, pricechopper])
        session.flush()
        entity_ids[Store].extend([hannaford.id, pricechopper.id])

        product_philly = Product(
            brand="Philidelphia",
            name="Philidelphia Cream Cheese",
            upc=str(uuid4()),
        )
        product_store_generic = Product(
            brand="Hannaford",
            name="Store Brand Cream Cheese",
            upc=str(uuid4()),
        )
        product_other_store_generic = Product(
            brand="PriceChopper",
            name="Store 2 Brand Cream Cheese",
            upc=str(uuid4()),
        )
        product_green_onion_h = Product(
            brand="Hannaford",
            name="Green Onion (Hannaford)",
            upc=str(uuid4()),
        )
        product_green_onion_pc = Product(
            brand="PriceChopper",
            name="Green Onion (PriceChopper)",
            upc=str(uuid4()),
        )
        product_org_green_onion_h = Product(
            brand="Hannaford",
            name="Organic Green Onion (Hannaford)",
            upc=str(uuid4()),
        )
        product_org_green_onion_pc = Product(
            brand="PriceChopper",
            name="Organic Green Onion (PriceChopper)",
            upc=str(uuid4()),
        )
        product_irrelevant = Product(
            brand="Other",
            name="Strawberry Jam",
            upc=str(uuid4()),
        )
        session.add_all(
            [
                product_philly,
                product_store_generic,
                product_other_store_generic,
                product_green_onion_h,
                product_green_onion_pc,
                product_org_green_onion_h,
                product_org_green_onion_pc,
                product_irrelevant,
            ]
        )
        session.flush()
        entity_ids[Product].extend(
            [
                product_philly.id,
                product_store_generic.id,
                product_other_store_generic.id,
                product_green_onion_h.id,
                product_green_onion_pc.id,
                product_org_green_onion_h.id,
                product_org_green_onion_pc.id,
                product_irrelevant.id,
            ]
        )

        store_products = [
            StoreProduct(
                store_id=hannaford.id,
                product_id=product_philly.id,
                external_sku=new_sku(),
            ),
            StoreProduct(
                store_id=pricechopper.id,
                product_id=product_philly.id,
                external_sku=new_sku(),
            ),
            StoreProduct(
                store_id=hannaford.id,
                product_id=product_store_generic.id,
                external_sku=new_sku(),
            ),
            StoreProduct(
                store_id=pricechopper.id,
                product_id=product_other_store_generic.id,
                external_sku=new_sku(),
            ),
            StoreProduct(
                store_id=hannaford.id,
                product_id=product_green_onion_h.id,
                external_sku=new_sku(),
            ),
            StoreProduct(
                store_id=pricechopper.id,
                product_id=product_green_onion_pc.id,
                external_sku=new_sku(),
            ),
            StoreProduct(
                store_id=hannaford.id,
                product_id=product_org_green_onion_h.id,
                external_sku=new_sku(),
            ),
            StoreProduct(
                store_id=pricechopper.id,
                product_id=product_org_green_onion_pc.id,
                external_sku=new_sku(),
            ),
        ]
        session.add_all(store_products)
        session.flush()
        entity_ids[StoreProduct].extend(sp.id for sp in store_products)

        shopping_list = ShoppingList(client_id=client_id, title="Grocery List")
        session.add(shopping_list)
        session.flush()
        entity_ids[ShoppingList].append(shopping_list.id)

        list_item_cream = ListItem(
            list_id=shopping_list.id,
            position=1,
            item_name="cream cheese",
            raw_text_item="cream cheese",
        )
        list_item_brand = ListItem(
            list_id=shopping_list.id,
            position=2,
            item_name="Philidelphia Cream Cheese",
            raw_text_item="Philidelphia Cream Cheese",
        )
        list_item_green = ListItem(
            list_id=shopping_list.id,
            position=3,
            item_name="green onion",
            raw_text_item="green onion",
        )
        list_item_org_green = ListItem(
            list_id=shopping_list.id,
            position=4,
            item_name="Organic green onion",
            raw_text_item="Organic green onion",
        )
        session.add_all(
            [list_item_cream, list_item_brand, list_item_green, list_item_org_green]
        )
        session.flush()
        entity_ids[ListItem].extend(
            [
                list_item_cream.id,
                list_item_brand.id,
                list_item_green.id,
                list_item_org_green.id,
            ]
        )

        route_plan = RoutePlan(list_id=shopping_list.id, client_id=client_id)
        session.add(route_plan)
        session.flush()
        entity_ids[RoutePlan].append(route_plan.id)
        route_plan_id = route_plan.id

        selections = [
            PlanSelectedStore(plan_id=route_plan.id, store_id=hannaford.id),
            PlanSelectedStore(plan_id=route_plan.id, store_id=pricechopper.id),
        ]
        session.add_all(selections)
        session.flush()
        entity_ids[PlanSelectedStore].extend(sel.id for sel in selections)

        job = Job(plan_id=route_plan.id, stage=JobStage.MATCH)
        session.add(job)
        session.flush()
        entity_ids[Job].append(job.id)
        job_id = job.id

        list_item_ids = {
            list_item_cream.id: {
                product_philly.name,
                product_store_generic.name,
                product_other_store_generic.name,
            },
            list_item_brand.id: {product_philly.name},
            list_item_green.id: {
                product_green_onion_h.name,
                product_green_onion_pc.name,
                product_org_green_onion_h.name,
                product_org_green_onion_pc.name,
            },
            list_item_org_green.id: {
                product_org_green_onion_h.name,
                product_org_green_onion_pc.name,
            },
        }

    result = create_item_match_candidates.run(job_id=str(job_id))
    assert result == {"job_id": str(job_id)}

    with session_scope() as session:
        refreshed_job = session.get(Job, job_id)
        assert refreshed_job is not None
        assert refreshed_job.status is JobStatus.SUCCESS
        assert refreshed_job.progress_total == 4
        assert refreshed_job.progress_current == 4

        candidates = session.exec(
            select(ItemMatchCandidate).where(ItemMatchCandidate.plan_id == route_plan_id)
        ).all()
        assert len(candidates) == 10

        by_item: dict[UUID, list[ItemMatchCandidate]] = defaultdict(list)
        for candidate in candidates:
            by_item[candidate.list_item_id].append(candidate)
            assert candidate.score == 100

        for item_id, expected_names in list_item_ids.items():
            assert item_id in by_item
            observed_names = {
                session.get(Product, candidate.product_id).name for candidate in by_item[item_id]
            }
            assert observed_names == expected_names

    _delete_entities(entity_ids)


def test_fanout_candidates_to_item_matches_creates_matches_for_selected_stores() -> None:
    """The FANOUT task should materialize item matches for every selected store."""

    entity_ids: dict[type, list[UUID]] = defaultdict(list)

    client_id = f"client-{uuid4()}"
    sku_counter = 0

    def new_sku() -> str:
        nonlocal sku_counter
        sku_counter += 1
        return f"SKU-{sku_counter}-{uuid4()}"

    with session_scope() as session:
        chain = StoreChain(name=f"Chain {uuid4()}")
        session.add(chain)
        session.flush()
        entity_ids[StoreChain].append(chain.id)

        store_a = Store(
            chain_id=chain.id,
            name="Fanout Store A",
            number="300",
            address_line1="3 Main St",
            city="Fanout",
            region="FO",
            postal_code="54321",
            country_code="US",
            timezone="UTC",
            phone="555-1001",
        )
        store_b = Store(
            chain_id=chain.id,
            name="Fanout Store B",
            number="400",
            address_line1="4 Main St",
            city="Fanout",
            region="FO",
            postal_code="54321",
            country_code="US",
            timezone="UTC",
            phone="555-1002",
        )
        session.add(store_a)
        session.add(store_b)
        session.flush()
        entity_ids[Store].extend([store_a.id, store_b.id])
        store_a_id = store_a.id
        store_b_id = store_b.id

        product_milk = Product(brand="Brand", name="Organic Whole Milk", upc=str(uuid4()))
        product_oatmilk = Product(brand="Brand", name="Organic Oat Milk", upc=str(uuid4()))
        product_juice = Product(brand="Brand", name="Organic Orange Juice", upc=str(uuid4()))
        session.add(product_milk)
        session.add(product_oatmilk)
        session.add(product_juice)
        session.flush()
        entity_ids[Product].extend([product_milk.id, product_oatmilk.id, product_juice.id])

        store_products = [
            StoreProduct(
                store_id=store_a.id,
                product_id=product_milk.id,
                external_sku=new_sku(),
            ),
            StoreProduct(
                store_id=store_b.id,
                product_id=product_milk.id,
                external_sku=new_sku(),
            ),
            StoreProduct(
                store_id=store_b.id,
                product_id=product_oatmilk.id,
                external_sku=new_sku(),
            ),
            StoreProduct(
                store_id=store_a.id,
                product_id=product_juice.id,
                external_sku=new_sku(),
            ),
        ]
        session.add_all(store_products)
        session.flush()
        entity_ids[StoreProduct].extend(sp.id for sp in store_products)

        shopping_list = ShoppingList(client_id=client_id, title="Fanout List")
        session.add(shopping_list)
        session.flush()
        entity_ids[ShoppingList].append(shopping_list.id)

        list_item = ListItem(
            list_id=shopping_list.id,
            position=1,
            item_name="organic milk",
            raw_text_item="1 organic milk",
        )
        session.add(list_item)
        session.flush()
        entity_ids[ListItem].append(list_item.id)

        route_plan = RoutePlan(list_id=shopping_list.id, client_id=client_id)
        session.add(route_plan)
        session.flush()
        entity_ids[RoutePlan].append(route_plan.id)
        route_plan_id = route_plan.id

        selections = [
            PlanSelectedStore(plan_id=route_plan.id, store_id=store_a.id),
            PlanSelectedStore(plan_id=route_plan.id, store_id=store_b.id),
        ]
        session.add_all(selections)
        session.flush()
        entity_ids[PlanSelectedStore].extend(sel.id for sel in selections)

        candidate_milk = ItemMatchCandidate(
            plan_id=route_plan.id,
            list_item_id=list_item.id,
            product_id=product_milk.id,
            score=95.0,
        )
        candidate_oatmilk = ItemMatchCandidate(
            plan_id=route_plan.id,
            list_item_id=list_item.id,
            product_id=product_oatmilk.id,
            score=90.0,
        )
        candidate_rejected = ItemMatchCandidate(
            plan_id=route_plan.id,
            list_item_id=list_item.id,
            product_id=product_juice.id,
            score=50.0,
            rejected_by_user=True,
        )
        session.add(candidate_milk)
        session.add(candidate_oatmilk)
        session.add(candidate_rejected)
        session.flush()
        entity_ids[ItemMatchCandidate].extend(
            [candidate_milk.id, candidate_oatmilk.id, candidate_rejected.id]
        )
        candidate_milk_id = candidate_milk.id
        candidate_oatmilk_id = candidate_oatmilk.id
        candidate_rejected_id = candidate_rejected.id

        preexisting_match = ItemMatch(
            plan_id=route_plan.id,
            list_item_id=list_item.id,
            store_id=store_a.id,
            item_match_candidate_id=candidate_milk.id,
            store_product_id=store_products[0].id,
            price_entry_id=None,
        )
        session.add(preexisting_match)
        session.flush()
        entity_ids[ItemMatch].append(preexisting_match.id)
        preexisting_match_id = preexisting_match.id

        job = Job(plan_id=route_plan.id, stage=JobStage.FANOUT)
        session.add(job)
        session.flush()
        entity_ids[Job].append(job.id)
        job_id = job.id

    result = fanout_candidates_to_item_matches.run(job_id=str(job_id))
    assert result == {"job_id": str(job_id)}

    with session_scope() as session:
        refreshed_job = session.get(Job, job_id)
        assert refreshed_job is not None
        assert refreshed_job.status is JobStatus.SUCCESS
        assert refreshed_job.progress_total == 2
        assert refreshed_job.progress_current == 2

        matches = session.exec(
            select(ItemMatch).where(ItemMatch.plan_id == route_plan_id)
        ).all()
        match_ids = {match.id for match in matches}
        entity_ids[ItemMatch].extend(
            mid for mid in match_ids if mid not in entity_ids[ItemMatch]
        )

        assert len(matches) == 3

        by_candidate: dict[UUID, list[ItemMatch]] = defaultdict(list)
        for match in matches:
            by_candidate[match.item_match_candidate_id].append(match)
            assert match.price_entry_id is None

        assert {match.store_id for match in by_candidate[candidate_milk_id]} == {
            store_a_id,
            store_b_id,
        }
        assert len(by_candidate[candidate_oatmilk_id]) == 1
        assert by_candidate[candidate_oatmilk_id][0].store_id == store_b_id
        assert candidate_rejected_id not in by_candidate
        assert preexisting_match_id not in match_ids

    _delete_entities(entity_ids)


def test_fanout_candidates_handles_branded_and_store_specific_products() -> None:
    """FANOUT task should create matches for each store that stocks a chosen product."""

    entity_ids: dict[type, list[UUID]] = defaultdict(list)

    client_id = f"client-{uuid4()}"
    sku_counter = 0

    def new_sku() -> str:
        nonlocal sku_counter
        sku_counter += 1
        return f"SKU-{sku_counter}-{uuid4()}"

    with session_scope() as session:
        chain = StoreChain(name=f"Chain {uuid4()}")
        session.add(chain)
        session.flush()
        entity_ids[StoreChain].append(chain.id)

        hannaford = Store(
            chain_id=chain.id,
            name="Hannaford",
            number="101",
            address_line1="101 Market St",
            city="Townsville",
            region="TS",
            postal_code="10001",
            country_code="US",
            timezone="UTC",
            phone="555-1010",
        )
        pricechopper = Store(
            chain_id=chain.id,
            name="PriceChopper",
            number="202",
            address_line1="202 Market St",
            city="Townsville",
            region="TS",
            postal_code="10001",
            country_code="US",
            timezone="UTC",
            phone="555-2020",
        )
        session.add_all([hannaford, pricechopper])
        session.flush()
        entity_ids[Store].extend([hannaford.id, pricechopper.id])
        hannaford_id = hannaford.id
        pricechopper_id = pricechopper.id

        product_philly = Product(
            brand="Philidelphia",
            name="Philidelphia Cream Cheese",
            upc=str(uuid4()),
        )
        product_store_generic = Product(
            brand="Hannaford",
            name="Store Brand Cream Cheese",
            upc=str(uuid4()),
        )
        product_other_store_generic = Product(
            brand="PriceChopper",
            name="Store 2 Brand Cream Cheese",
            upc=str(uuid4()),
        )
        session.add_all(
            [product_philly, product_store_generic, product_other_store_generic]
        )
        session.flush()
        entity_ids[Product].extend(
            [product_philly.id, product_store_generic.id, product_other_store_generic.id]
        )

        philly_store_products = [
            StoreProduct(
                store_id=hannaford.id,
                product_id=product_philly.id,
                external_sku=new_sku(),
            ),
            StoreProduct(
                store_id=pricechopper.id,
                product_id=product_philly.id,
                external_sku=new_sku(),
            ),
        ]
        hannaford_generic_sp = StoreProduct(
            store_id=hannaford.id,
            product_id=product_store_generic.id,
            external_sku=new_sku(),
        )
        pricechopper_generic_sp = StoreProduct(
            store_id=pricechopper.id,
            product_id=product_other_store_generic.id,
            external_sku=new_sku(),
        )
        session.add_all(philly_store_products + [hannaford_generic_sp, pricechopper_generic_sp])
        session.flush()
        entity_ids[StoreProduct].extend(
            sp.id for sp in philly_store_products + [hannaford_generic_sp, pricechopper_generic_sp]
        )

        shopping_list = ShoppingList(client_id=client_id, title="Fanout List")
        session.add(shopping_list)
        session.flush()
        entity_ids[ShoppingList].append(shopping_list.id)

        list_item = ListItem(
            list_id=shopping_list.id,
            position=1,
            item_name="cream cheese",
            raw_text_item="cream cheese",
        )
        session.add(list_item)
        session.flush()
        entity_ids[ListItem].append(list_item.id)

        route_plan = RoutePlan(list_id=shopping_list.id, client_id=client_id)
        session.add(route_plan)
        session.flush()
        entity_ids[RoutePlan].append(route_plan.id)
        route_plan_id = route_plan.id

        selections = [
            PlanSelectedStore(plan_id=route_plan.id, store_id=hannaford.id),
            PlanSelectedStore(plan_id=route_plan.id, store_id=pricechopper.id),
        ]
        session.add_all(selections)
        session.flush()
        entity_ids[PlanSelectedStore].extend(sel.id for sel in selections)

        candidate_philly = ItemMatchCandidate(
            plan_id=route_plan.id,
            list_item_id=list_item.id,
            product_id=product_philly.id,
            score=100.0,
        )
        candidate_hannaford_generic = ItemMatchCandidate(
            plan_id=route_plan.id,
            list_item_id=list_item.id,
            product_id=product_store_generic.id,
            score=100.0,
        )
        candidate_pricechopper_generic = ItemMatchCandidate(
            plan_id=route_plan.id,
            list_item_id=list_item.id,
            product_id=product_other_store_generic.id,
            score=100.0,
        )
        session.add_all(
            [candidate_philly, candidate_hannaford_generic, candidate_pricechopper_generic]
        )
        session.flush()
        entity_ids[ItemMatchCandidate].extend(
            [candidate_philly.id, candidate_hannaford_generic.id, candidate_pricechopper_generic.id]
        )
        candidate_philly_id = candidate_philly.id
        candidate_hannaford_generic_id = candidate_hannaford_generic.id
        candidate_pricechopper_generic_id = candidate_pricechopper_generic.id

        job = Job(plan_id=route_plan.id, stage=JobStage.FANOUT)
        session.add(job)
        session.flush()
        entity_ids[Job].append(job.id)
        job_id = job.id

        expected_store_products = {
            candidate_philly_id: {sp.id for sp in philly_store_products},
            candidate_hannaford_generic_id: {hannaford_generic_sp.id},
            candidate_pricechopper_generic_id: {pricechopper_generic_sp.id},
        }

    result = fanout_candidates_to_item_matches.run(job_id=str(job_id))
    assert result == {"job_id": str(job_id)}

    with session_scope() as session:
        refreshed_job = session.get(Job, job_id)
        assert refreshed_job is not None
        assert refreshed_job.status is JobStatus.SUCCESS
        assert refreshed_job.progress_total == 3
        assert refreshed_job.progress_current == 3

        matches = session.exec(
            select(ItemMatch).where(ItemMatch.plan_id == route_plan_id)
        ).all()
        assert len(matches) == 4

        by_candidate: dict[UUID, list[ItemMatch]] = defaultdict(list)
        for match in matches:
            by_candidate[match.item_match_candidate_id].append(match)
            assert match.price_entry_id is None
            assert match.store_product_id in expected_store_products[match.item_match_candidate_id]

        assert {match.store_id for match in by_candidate[candidate_philly_id]} == {
            hannaford_id,
            pricechopper_id,
        }
        assert len(by_candidate[candidate_hannaford_generic_id]) == 1
        assert by_candidate[candidate_hannaford_generic_id][0].store_id == hannaford_id
        assert len(by_candidate[candidate_pricechopper_generic_id]) == 1
        assert (
            by_candidate[candidate_pricechopper_generic_id][0].store_id
            == pricechopper_id
        )

    _delete_entities(entity_ids)
