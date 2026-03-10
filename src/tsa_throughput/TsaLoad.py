import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import random
import time
import re
from TsaDateParse import find_dates

class TsaFileLoader:
    def __init__(self, url: str):
        self.url = url

    def get_list(self) -> pd.DataFrame:
        """
        Retreives the list of TSA Throughput data files from the FOIA Reading Room and builds a pandas DataFrame
        containing the URL, File Title, and date range of the data (Start Date, End Date) derived from the file
        title. It also includes a boolean indicator column if the word "Throughput" appears in the title.

        Note, there are a variety of formats used to encode date ranges, and there is known overlap between files.

        Applications consuming this output will need to verify the date ranges contained in any downloaded files in 
        addition to resolving overlap.

        @returns DataFrame
        """

        request_url = self.url
        file_data = []
        current_page = 1
        last_page = None

        while request_url:
            print(f'Loading {current_page} of {last_page if last_page else "Unknown"}')
            response = requests.get(request_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            data = [(current_page, urljoin(request_url, link['href']), link.getText(strip=True)) for link in soup.find_all("a", class_ = "foia-reading-link")]
            file_data.extend(data)

            next_link = soup.find("a", attrs={"title":"Go to next page"})
            
            if current_page == 1:
                last_page = int(soup.find("a", attrs={"title": "Go to last page"}).getText(strip=True))
                print(f"Last page of results is {last_page}")

            if next_link:
                request_url = urljoin(request_url, next_link['href'])
            else:
                request_url = None

            current_page += 1

            # Random sleep to rate limit
            delay = random.randint(0, 3)
            print(f'Waiting {delay} seconds...')
            time.sleep(delay)

        # Make the initial request
        df = pd.DataFrame(file_data, columns=["Page", "URL", "Title"])

        # Break out the start and end date if possible
        def extract_dates(title):
            results = find_dates(title)
            if not results:
                return pd.Series([None, None])
            
            dates = [dt for dt in results[:2]]
            while len(dates) < 2:
                dates.append(None)
            
            return pd.Series(dates)


        df[['Date From', 'Date To']] = df['Title'].apply(extract_dates)
        df['Throughput'] = df['Title'].apply(lambda x: True if re.search("throughput", x, flags=re.IGNORECASE) else False)

        return df
    




def main():
    loader = TsaFileLoader("https://www.tsa.gov/foia/readingroom?title=&field_foia_tax_category_target_id=1132&page=0")
    results = loader.get_list()



    results.to_csv("./results.csv", index=False)
    

if __name__=="__main__":
    main()