"""Store data ingestion and pricing tasks."""

from __future__ import annotations
import timezonefinder
import json
from celery import shared_task

from playwright.sync_api import sync_playwright

hannaford_states = ["NY", "ME", "NH", "VT", "MA"]
price_chopper_states = ["NY", "VT", "MA", "CT", "PA", "NH"]
class Store:
    id: str
    name: str
    address_line_1: str
    address_line_2: str
    phone: str
    city: str
    region: str
    zip_code: str
    latitude: float
    longitude: float
    timezone: str
    hours : json

    def __init__(self, id: str, name: str, address_line_1: str, address_line_2: str, phone: str, country_code: str, city: str, region: str, zip_code: str,
                 latitude: float, longitude: float, timezone: str, hours: json) -> None:
        self.id = id
        self.name = name
        self.address_line_1 = address_line_1
        self.address_line_2 = address_line_2
        self.phone = phone
        self.city = city
        self.region = region
        self.country_code = country_code
        self.zip_code = zip_code
        self.latitude = latitude
        self.longitude = longitude
        self.timezone = timezone
        self.hours = hours


    def __str__(self) -> str:
        return f"Store(id = {self.id}, name = {self.name}, address_line_1 = {self.address_line_1}, address_line_2 = {self.address_line_2}, phone = {self.phone}, country = {self.country_code}, city = {self.city}, region = {self.region}, zip_code = {self.zip_code}, latitude = {self.latitude}, longitude = {self.longitude}, timezone = {self.timezone}, hours = {self.hours})"

class StoreProduct:
    brand = str
    name = str
    upc = str
    



@shared_task(name="workers.scraping.scrape_hannaford_stores")
def scrape_hannaford() -> None:

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
        
        context.close()
        browser.close()
        return stores


def get_store_data_hannaford(page, url: str, city_name: str, hannaford_state: str) -> Store:
    page.goto(url)
    name = page.locator("[class=Core-storeName]").inner_text().strip()    
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
        id=url.split("/")[-1],
        name=name,
        address_line_1=address_line_1,
        address_line_2="",
        phone=phone,
        city=url.split("/")[4],
        region=url.split("/")[3].upper(),
        zip_code=zip_code,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        hours = hours,
        country_code="US"
    )
    print(store)
    print("-----")
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
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3")
        page = context.new_page()

        page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})

        # Navigate to Hannaford online shopping page
        page.goto("https://www.hannaford.com/departments/")
        #get all departments
        department_container = page.locator(".dept-list.row")
        departments = department_container.locator("a")
        dept_count = departments.count()
        print(f"Found {dept_count} departments.")
        for i in range(dept_count):
            page.goto("https://www.hannaford.com/departments/")

            department = departments.nth(i)
            dept_name = department.locator(".thumb-text").inner_text().strip()
            dept_url = department.get_attribute("href")
            print(f"Scraping department {i+1} of {dept_count}: {dept_name}")
            print("URL: ", f"https://www.hannaford.com{dept_url}")
            page.goto(f"https://www.hannaford.com{dept_url}")

            #find every sub-department
            sub_dept_container = page.locator("")

        context.close()
        browser.close()


if __name__ == "__main__":
    scrape_hannaford()
  #  scrape_price_chopper()
 #   scrape_hannaford_items()