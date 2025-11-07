"""Store data ingestion and pricing tasks."""

from __future__ import annotations
import timezonefinder
import json
from celery import shared_task
from celery.utils.log import get_task_logger

from geoalchemy2 import Geography
from playwright.sync_api import sync_playwright
from backend.app.db import session_scope
from backend.app.models import Store, StoreChain


hannaford_states = ["NY", "ME", "NH", "VT", "MA"]
price_chopper_states = ["NY", "VT", "MA", "CT", "PA", "NH"]

class StoreProduct:
    brand = str
    name = str
    upc = str
    weight = str
    price = float

# module-level task logger
logger = get_task_logger(__name__)



@shared_task(bind=True, name="workers.scraping.scrape_hannaford_stores")
def scrape_hannaford(self=None, *args, **kwargs) -> None:

    stores = []
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3")
        page = context.new_page()

        page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
    

        for hannaford_state in hannaford_states:
            page.goto(f"https://stores.hannaford.com/{hannaford_state.lower()}")

            #scrape each city page for stores
            city_list = page.locator("[class=Directory-listLinks]")
            count = city_list.count()
            cities = city_list.locator("li a")
            
            count = cities.count()
            
            for i in range(count):
                page.goto(f"https://stores.hannaford.com/{hannaford_state.lower()}")

                print(f"Scraping city {i+1} of {count} in {hannaford_state}")
                city = cities.nth(i)
                
                city_name = city.inner_text().strip()
                city_url = city.get_attribute("href")
                if not city_url.endswith(tuple(str(n) for n in range(10))):
                    page.goto(f"https://stores.hannaford.com/{city_url}")
                    stores_in_city = page.locator("[class=Directory-listTeaser]")
                    store_count = stores_in_city.count()
                    for i in range(store_count):
                        page.goto(f"https://stores.hannaford.com/{city_url}")
                        store = stores_in_city.nth(i)
                        store_url = store.locator("[class=Teaser-titleLink]").get_attribute("href").lstrip(".")
                        full_store_url = f"https://stores.hannaford.com{store_url}"
                        store_data = get_store_data_hannaford(page, full_store_url, city_name, hannaford_state)
                        stores.append(store_data)
                    
                else:
                    store = get_store_data_hannaford(page, f"https://stores.hannaford.com/{city_url}", city_name, hannaford_state)

                    stores.append(store)
                if len(stores) == 10:
                    with session_scope() as session:
                        #add hannaford store chain if it doesn't exist
                        chain = StoreChain(
                            name="Hannaford",
                        )
                        statement = session.query(StoreChain).filter(StoreChain.name == chain.name)
                        existing_chain = session.exec(statement).scalars().first()
                        if existing_chain is None:
                            session.add(chain)
                            session.commit()
                        #get the id of the chain
                        statement = session.query(StoreChain).filter(StoreChain.name == "Hannaford")
                        existing_chain = session.exec(statement).scalars().first()
                        
                        for store in stores:
                            store.chain_id = existing_chain.id
                            session.add(store)
                        session.commit()
                    return stores
        context.close()
        browser.close()
        
        with session_scope() as session:
            #add hannaford store chain if it doesn't exist
            chain = StoreChain(
                name="Hannaford",
            )
            statement = session.query(StoreChain).filter(StoreChain.name == chain.name)
            existing_chain = session.exec(statement).scalars().first()
            if existing_chain is None:
                session.add(chain)
                session.commit()
            for store in stores:
                store.chain_id = existing_chain.id
                session.add(store)
            session.commit()
        return stores


def get_store_data_hannaford(page, url: str, city_name: str, hannaford_state: str) -> Store:
    page.goto(url)
    print(url)
    name = page.locator("[class=Core-storeName]").inner_text().strip()    
    number = url.split("/")[-1]
    address_list = page.locator("[class=c-bread-crumbs-list]")
    address_line_1 = address_list.locator("li").nth(-1).inner_text().strip()
    addresswrapper = page.locator("div.Core-addressWrapper")
    zip_code = addresswrapper.locator(".Address-field.Address-postalCode").inner_text().strip()
    core_contact= page.locator("[class=Core-contact]")
    phone = core_contact.locator(".Phone-display.Phone-display--withLink").nth(0).inner_text().strip()    
    lat_long_json = json.loads(page.locator("[class=js-map-data]").inner_text().strip())
    latitude = lat_long_json.get("latitude")
    longitude = lat_long_json.get("longitude")
    tf = timezonefinder.TimezoneFinder()
    timezone = tf.timezone_at(lng=longitude, lat=latitude)
    
    #find the hours and store them in a json object
    hours_whole_json = json.loads(page.locator("[class=js-hours-config]").nth(0).inner_text().strip())
    hours = hours_whole_json.get("hours")    
    store = Store(
        chain_id=None,
        name=name,
        external_ref=number,
        number=number,
        address_line1=address_line_1,
        city=city_name,
        region=hannaford_state,
        postal_code=zip_code,
        country_code="US",
        timezone=timezone,
        hours_json=hours,
        phone=phone,
        geography=f'POINT({longitude} {latitude})'
        
    )

    return store



@shared_task(name="workers.scraping.scrape_price_chopper")
def scrape_price_chopper() -> None:
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3")
        page = context.new_page()

        page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})

        for price_chopper_state in price_chopper_states:
            page.goto(f"https://www.pricechopper.com/stores/{price_chopper_state.lower()}")

            #get all cities in the state
            cities_list_location = page.locator("[class=locations-list-container]")
            map_list= cities_list_location.locator("[class=map-list ]")
            print(map_list)
            cities = map_list.locator("li")
            count = cities.count()
            print(count)
            for i in range(count):
                city = map_list.nth(i)
                city_url = city.locator("a").get_attribute("href")
                page.goto(city_url)
                #get all stores in the city
            break


@shared_task(name="workers.scraping.scrape_hannaford_items")
def scrape_hannaford_items() -> None:
    items = []
    with sync_playwright() as p:
        print("Scraping Hannaford items...")
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3")
        page = context.new_page()

        page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})

        # Navigate to Hannaford online shopping page
        page.goto("https://www.hannaford.com/departments/")
        #get all departments, these are located in divs with class main-nav-menu-level-3
        departments = page.locator("[class=main-nav-menu-level-3]")
        
        for department_index in range(departments.count()):
            #go to each departments subdepartments
            department = departments.nth(department_index)
            subdepartments = department.locator("li")
            print(f"Scraping department {department_index} of {departments.count()}")
            for subdepartment_index in range(1, subdepartments.count()):
                #go to each subdepartments and get items
                
                subdepartment = subdepartments.nth(subdepartment_index)
                subdepartment_url = subdepartment.locator("a").get_attribute("href")
                print(f"  Scraping subdepartment {subdepartment_index+1} of {subdepartments.count()}")
                print("URL: ", f"https://www.hannaford.com{subdepartment_url}")
                page.goto(f"https://www.hannaford.com{subdepartment_url}")
                
                #now get all items on the page
                #press the load more button until it is no longer available
                while True:
                    try:
                        load_more_button = page.locator("#see-more-btn").nth(0)
                        if load_more_button.is_visible():
                            print("Clicking load more button")
                            load_more_button.click()
                            page.wait_for_timeout(2000)  # wait for 2 seconds for items to load
                        else:
                            print("No more load more button visible")
                            break
                    except:
                        break
                 
                 #items are stored 
                items = page.locator(".plp_thumb_wrap.product-impressions")
                item_count = items.count()
                print(f"Found {item_count} items in subdepartment {subdepartment_index+1} of {subdepartments.count()}")
                for item_index in range(item_count):
                    item = items.nth(item_index)
                    item_name=item.get_attribute("data-name")
                    print("  Item Name: ", item_name)
        context.close()
        browser.close()




def add_stores_to_db(stores: list[Store]) -> None:
    #add the stores to the database
    with session_scope() as session:
        for store in stores:
            session.add(store)
        session.commit()



@shared_task(bind=True, name="workers.scraping.test_celery")
def test_celery(self) -> str:
    # Log a message that includes the Celery-assigned task id for traceability
    logger.info("test_celery task executed (task_id=%s)", getattr(self.request, "id", None))
    return "Celery is working!"

if __name__ == "__main__":
   stores_ = scrape_hannaford()
   print(f"Scraped {len(stores_)} stores from Hannaford")
   #add_stores_to_db(stores_)
  #  scrape_price_chopper()
  # scrape_hannaford_items()
