"""Expose crawler for Ebay Kleinanzeigen"""
import re
import datetime

from flathunter.crawl_reference_sqm_price import crawl_ref_sqm_price
from flathunter.idmaintainer import IdMaintainer
from flathunter.logging import logger
from flathunter.abstract_crawler import Crawler

class CrawlEbayKleinanzeigen(Crawler):
    """Implementation of Crawler interface for Ebay Kleinanzeigen"""

    URL_PATTERN = re.compile(r'https://www\.ebay-kleinanzeigen\.de')
    MONTHS = {
        "Januar": "01",
        "Februar": "02",
        "März": "03",
        "April": "04",
        "Mai": "05",
        "Juni": "06",
        "Juli": "07",
        "August": "08",
        "September": "09",
        "Oktober": "10",
        "November": "11",
        "Dezember": "12"
    }

    def __init__(self, config):
        super().__init__(config)
        self.config = config

    def get_page(self, search_url, driver=None, page_no=None):
        """Applies a page number to a formatted search URL and fetches the exposes at that page"""
        return self.get_soup_from_url(search_url)

    def is_processed(self, expose_id):
        """Returns true if an expose has already been processed"""
        logger.debug('is_processed(%d)', expose_id)
        cur = IdMaintainer(db_name=f'{self.config.database_location()}/processed_ids.db').get_connection().cursor()
        cur.execute('SELECT id FROM processed WHERE id = ?', (expose_id,))
        row = cur.fetchone()
        return row is not None

    def qry_refs(self, expose_id) -> tuple:
        """Returns tuple(ref_address, sqm_price_ref_address, sqm_price_times_ref_sqm_price)"""
        logger.debug(
            'Get reference address, reference sqm price and sqm_price_times_ref_sqm_price from db for ', expose_id
        )
        cur = IdMaintainer(db_name=f'{self.config.database_location()}/processed_ids.db').get_connection().cursor()
        cur.execute('''
                    SELECT id, ref_address, sqm_price_ref_address, sqm_price_times_ref_sqm_price  
                    FROM exposes 
                    WHERE id = ?
                    ''',
                    (expose_id,)
                    )
        row = cur.fetchone()
        return row[1:]

    def get_expose_details(self, expose):
        soup = self.get_page(expose['url'])
        for detail in soup.find_all('li', {"class": "addetailslist--detail"}):
            if re.match(r'Verfügbar ab', detail.text):
                date_string = re.match(r'(\w+) (\d{4})', detail.text)
                if date_string is not None:
                    expose['from'] = "01." + self.MONTHS[date_string[1]] + "." + date_string[2]
        if 'from' not in expose:
            expose['from'] = datetime.datetime.now().strftime('%02d.%02m.%Y')
        return expose

    # pylint: disable=too-many-locals
    def extract_data(self, soup):
        """Extracts all exposes from a provided Soup object"""
        entries = []
        soup = soup.find(id="srchrslt-adtable")

        try:
            title_elements = soup.find_all(lambda e: e.has_attr('class')
                                           and 'ellipsis' in e['class'])
        except AttributeError:
            return entries

        expose_ids = soup.find_all("article", class_="aditem")

        for idx, title_el in enumerate(title_elements):
            try:
                price = expose_ids[idx].find(
                    class_="aditem-main--middle--price-shipping--price").text.strip()
                price_float = float(re.sub("[ .€VB]", "", price).strip())
                tags = expose_ids[idx].find_all(class_="simpletag tag-small")
                url = "https://www.ebay-kleinanzeigen.de" + title_el.get("href")
                address = self.load_address(url)
                #address = expose_ids[idx].find("div", {"class": "aditem-main--top--left"})
                image_element = expose_ids[idx].find("div", {"class": "galleryimage-element"})
            except AttributeError as error:
                logger.warning("Unable to process eBay expose: %s", str(error))
                continue

            if image_element is not None:
                image = image_element["data-imgsrc"]
            else:
                image = None




            # original
            # address = address.text.strip()
            # address = address.replace('\n', ' ').replace('\r', '')
            # address = " ".join(address.split())

            try:
                rooms = re.match(r'(\d+)', tags[1].text)[1]
            except (IndexError, TypeError):
                rooms = ""
            try:
                size = tags[0].text
                size_float = float(re.sub(" m²", "", size).strip().replace(",", "."))
                sqm_price = round(price_float / size_float)
            except (IndexError, TypeError):
                size = ""
                size_float = -1
                sqm_price = -1

            # only crawl for reference sqm price if id has not yet been processed as the crawling takes a lot of time.
            # due to only unprocessed ids being added to the database, setting dummy values does not replace the values
            # that are already in the exposes db
            id_str = expose_ids[idx].get("data-adid")
            #logger.info(f'{id_str=}, {type(id_str)}')
            if self.is_processed(id_str):
                (ref_address, sqm_price_ref_address, sqm_price_times_ref_sqm_price) = self.qry_refs(id_str)
                logger.info(f"Found reference information for id {id_str}. Skipping crawling for references.")
            else:
                sqm_price_ref_address, ref_address = crawl_ref_sqm_price(address) if address != "" else (-1, "")
                if (sqm_price_ref_address, ref_address) == (-1, ""):
                    sqm_price_times_ref_sqm_price = -1.0
                else:
                    sqm_price_times_ref_sqm_price = round(sqm_price / sqm_price_ref_address, 3)

            details = {
                'id': id_str,
                'image': image,
                'url': url,
                'title': title_el.text.strip(),
                'price': price,
                'price_float': price_float,
                'size': size,
                'size_float': size_float,
                'rooms': rooms,
                'address': address,
                'crawler': self.get_name(),
                'sqm_price': sqm_price,
                'sqm_price_ref_address': sqm_price_ref_address,
                'ref_address': ref_address,
                'sqm_price_times_ref_sqm_price': sqm_price_times_ref_sqm_price,
            }
            entries.append(details)

        logger.debug('Number of entries found: %d', len(entries))

        return entries

    def load_address(self, url) -> str:
        """Extract address from expose itself"""
        expose_soup = self.get_page(url)
        try:
            street_raw = expose_soup.find(id="street-address").text
        except AttributeError:
            street_raw = ""
        try:
            address_raw = expose_soup.find(id="viewad-locality").text
        except AttributeError:
            address_raw = ""
        address = address_raw.strip().replace("\n", "") + " " + street_raw.strip()

        return address.strip()
