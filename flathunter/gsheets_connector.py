import string
import gspread


def append_to_google_sheet(values_to_insert_in_row: list):
    # replace list of images, index 5 in list
    if isinstance(values_to_insert_in_row[5], list):
        values_to_insert_in_row[5] = ('\n'.join(values_to_insert_in_row[5]
                                                if values_to_insert_in_row[5] != '' and values_to_insert_in_row[5] != []
                                                else '')
                                      ).strip()

    # authorization
    g_client = gspread.service_account(filename='flathunter-368110-21b2028eae29.json')
    # get spreadsheet
    sh = g_client.open_by_key(key='1clpPMPRfydfVZBX190cSyJOPEbvJ9gRJzU84pIvoADQ')
    ws = sh.worksheet(title='Wohnungen')

    ws.append_row(values=values_to_insert_in_row, table_range='A1')

    row_count = len(ws.get_all_values())
    col_count = string.ascii_uppercase[len(values_to_insert_in_row) - 1]

    ws.set_basic_filter(name=f'A1:{col_count}{row_count}')


if __name__ == "__main__":
    values = [
        11,
        "2022-11-09 16:13:06.076400",
        "CrawlEbayKleinanzeigen",
        "Vermietete 3-Zimmerwohnung mit Hobbyraum im Dach",
        "https://www.ebay-kleinanzeigen.de/s-anzeige/vermietete-3-zimmerwohnung-mit-hobbyraum-im-dach/1796670608-196-9663",
        ["im1", "im2", "im3"],
        369004,
        127.02,
        "10553 Mitte - Tiergarten Reuchlinstraße 2,",
        2905,
        -1,
        "N/A",
        -2905
        ]
    append_to_google_sheet(values_to_insert_in_row=values)
