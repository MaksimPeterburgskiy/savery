"""Store data ingestion and pricing tasks."""

from __future__ import annotations

from typing import Any
import json
from celery import shared_task



from playwright.sync_api import sync_playwright

hannaford_states = ["NY", "ME", "NH", "VT", "MA"]

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

    def __init__(self, id: str, name: str, address_line_1: str, address_line_2: str, phone: str, city: str, region: str, zip_code: str,
                 latitude: float, longitude: float, timezone: str, hours: json) -> None:
        self.id = id
        self.name = name
        self.address_line_1 = address_line_1
        self.address_line_2 = address_line_2
        self.phone = phone
        self.city = city
        self.region = region
        self.zip_code = zip_code
        self.latitude = latitude
        self.longitude = longitude
        self.timezone = timezone
        self.hours = hours


    def __str__(self) -> str:
        return f"Store(id={self.id}, name={self.name}, address_line_1={self.address_line_1}, address_line_2={self.address_line_2}, phone={self.phone}, city={self.city}, region={self.region}, zip_code={self.zip_code}, latitude={self.latitude}, longitude={self.longitude}, timezone={self.timezone}, hours={self.hours})"
@shared_task(name="workers.scraping.scrape_hannaford_stores")
def main() -> None:

    stores = []
    # Use the synchronous Playwright API. No asyncio event loop required.
    with sync_playwright() as p:
        # launch the Firefox browser 
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3")
        page = context.new_page()

        page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
    

        title = page.title()
        print(f"Page title: {title}")
        for hannaford_state in hannaford_states:
            page.goto(f"https://stores.hannaford.com/{hannaford_state.lower()}")
            title = page.title()
            print(f"Page title for {hannaford_state}: {title}")

            #scrape each city page for stores
            city_list = page.locator("[class=Directory-listLinks]")
            print(city_list)
            count = city_list.count()
            cities = city_list.locator("li a")
            
            count = cities.count()
            print(count)
            for i in range(count):
                city = cities.nth(i)
                city_name = city.inner_text().strip()
                city_url = city.get_attribute("href")
               # print(f"City: {city_name}, URL: {city_url}")
                #check if the city has multiple stores, if it does, the url will not end in a 4 digit number
                if not city_url.endswith(tuple(str(n) for n in range(10))):
                    print(f"Multiple stores in {city_name}, skipping for now.")
                else:
                    print(f"https://stores.hannaford.com/{city_url}")
                    store = get_store_data(page, f"https://stores.hannaford.com/{city_url}", city_name, hannaford_state)

                    stores.append(store)
                    break
            break
        
        
        
        context.close()
        browser.close()
        return stores


def get_store_data(page, url: str, city_name: str, hannaford_state: str) -> Store:
    page.goto(url)
    #what we need to get: store name, address, phone number, hours, latitude, longitude, 
    name = page.locator("[class=Core-storeName]").inner_text().strip()
    
    address_list = page.locator("[class=c-bread-crumbs-list]")
    address_line_1 = address_list.locator("li").nth(-1).inner_text().strip()
    addresswrapper = page.locator("div.Core-addressWrapper")
    zip_code = addresswrapper.locator(".Address-field.Address-postalCode").inner_text().strip()
    
    
    core_contact= page.locator("[class=Core-contact]")
    phone = core_contact.locator("[class=Core-storeContact]").inner_text().strip()
    print(phone)
   # hours = page.locator("div.StoreDetails-hours").inner_text().strip()
    
    lat_long_json = json.loads(page.locator("[class=js-map-data]").inner_text().strip())
    print(lat_long_json)
    latitude = lat_long_json.get("latitude")
    longitude = lat_long_json.get("longitude")
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
        timezone="",
        #hours=json.loads(hours)
        hours = json.loads("{}")
    )
    print(store)
    print("-----")
    return store


if __name__ == "__main__":
    main()