"""Expose crawler for ImmoWelt"""
import re
import datetime
import hashlib

from flathunter.idmaintainer import IdMaintainer
from flathunter.logging import logger
from flathunter.abstract_crawler import Crawler

from flathunter.crawl_reference_sqm_price import crawl_ref_sqm_price


class CrawlImmowelt(Crawler):
    """Implementation of Crawler interface for ImmoWelt"""

    URL_PATTERN = re.compile(r'https://www\.immowelt\.de')

    def __init__(self, config):
        super().__init__(config)
        self.config = config

    def get_expose_details(self, expose):
        """Loads additional details for an expose by processing the expose detail URL"""
        soup = self.get_page(expose['url'])
        date = datetime.datetime.now().strftime("%2d.%2m.%Y")

        immo_div = soup.find("app-estate-object-informations")
        if immo_div is not None:
            immo_div = soup.find("div", {"class": "equipment ng-star-inserted"})
            if immo_div is not None:
                details = immo_div.find_all("p")

                for detail in details:
                    if detail.text.strip() == "Bezug":
                        date = detail.findNext("p").text.strip()
                        no_exact_date_given = re.match(
                          r'.*sofort.*|.*Nach Vereinbarung.*',
                          date,
                          re.MULTILINE|re.DOTALL|re.IGNORECASE
                        )
                        if no_exact_date_given:
                            date = datetime.datetime.now().strftime("%2d.%2m.%Y")
                        break
        expose['from'] = date
        return expose

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

    # pylint: disable=too-many-locals
    def extract_data(self, soup):
        """Extracts all exposes from a provided Soup object"""
        entries = []
        soup = soup.find("main")

        try:
            title_elements = soup.find_all("h2")
        except AttributeError:
            return entries
        expose_ids = soup.find_all("a", id=True)

        for idx, title_el in enumerate(title_elements):
            try:
                price = expose_ids[idx].find(
                    "div", attrs={"data-test": "price"}).text
            except IndexError:
                price = ""

            try:
                size = expose_ids[idx].find(
                    "div", attrs={"data-test": "area"}).text
            except IndexError:
                size = ""

            try:
                rooms = expose_ids[idx].find(
                    "div", attrs={"data-test": "rooms"}).text
            except IndexError:
                rooms = ""

            url = expose_ids[idx].get("href")

            picture = expose_ids[idx].find("picture")
            image = None
            if picture:
                src = picture.find("source")
                if src:
                    image = src.get("data-srcset")

            try:
                address = expose_ids[idx].find(
                    "div", attrs={"class": re.compile("IconFact.*")}
                  )
                address = address.find("span").text
            except IndexError:
                address = ""

            processed_id = int(
              hashlib.sha256(expose_ids[idx].get("id").encode('utf-8')).hexdigest(), 16
            ) % 10**16

            price_float = float(re.sub("[. €]", "", price).strip())
            size_float = float(re.sub(" m²", "", size).strip())
            sqm_price = round(price_float / size_float)

            # only crawl for reference sqm price if id has not yet been processed as the crawling takes a lot of time.
            # due to only unprocessed ids being added to the database, setting dummy values does not replace the values
            # that are already in the exposes db
            if self.is_processed(processed_id):
                (ref_address, sqm_price_ref_address, sqm_price_times_ref_sqm_price) = self.qry_refs(processed_id)
                logger.info(f"Found reference information for id {processed_id}. Skipping crawling for references.")
            else:
                sqm_price_ref_address, ref_address = crawl_ref_sqm_price(address) if address != "" else (-1, "")
                if (sqm_price_ref_address, ref_address) == (-1, ""):
                    sqm_price_times_ref_sqm_price = -1.0
                else:
                    sqm_price_times_ref_sqm_price = round(sqm_price / sqm_price_ref_address, 3)

            details = {
                'id': processed_id,
                'url': url,
                'image': image,
                'title': title_el.text.strip(),
                'address': address,
                'crawler': self.get_name(),
                'price': price,
                'price_float': price_float,
                'size': size,
                'size_float': size_float,
                'rooms': rooms,
                'sqm_price': sqm_price,
                'sqm_price_ref_address': sqm_price_ref_address,
                'ref_address': ref_address,
                'sqm_price_times_ref_sqm_price': sqm_price_times_ref_sqm_price,
            }
            entries.append(details)

        logger.debug('Number of entries found: %d', len(entries))

        return entries
