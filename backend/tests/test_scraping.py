from backend.workers.tasks.scraping import scrape_hannaford, scrape_price_chopper



def test_scrape_price_chopper() -> None:
    stores = scrape_price_chopper()
    assert len(stores) > 0
