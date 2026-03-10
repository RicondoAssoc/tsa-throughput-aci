import pandas as pd
import logging
import pdfplumber
from urllib.parse import urlparse
from pathlib import Path
import os
import re
import requests
from requests.exceptions import RequestException 
from typing import Optional, List
from tqdm import tqdm

def _safe_filename(name: Optional[str], fallback: str = "download.pdf") -> str:
    # basic safety: ensure we have a filename and it ends with .pdf
    if not name:
        name = fallback
    name = os.path.basename(name)
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name

class TsaExtract:
    def __init__(self, temp_path: str):
        if (not os.access(temp_path, os.W_OK)):
            logging.warning(f"Unable to write to {temp_path}")
        else:
            self.temp_path = temp_path

    def extract_file(self, url: str) -> pd.DataFrame:
        pdf_path: Optional[Path] = None

        try:
            with requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                downloaded = 0

                cd = r.headers.get("content-disposition")
                filename = None
                if cd:
                    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd, flags=re.IGNORECASE)
                    filename = match.group(1) if match else None
                if not filename:
                    filename = os.path.basename(urlparse(url).path)

                filename = _safe_filename(filename, fallback="download.pdf")
                pdf_path = Path(self.temp_path) / filename
                pdf_path.parent.mkdir(parents=True, exist_ok=True)

                with open(pdf_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            print(f"\r{downloaded}/{total} bytes", end="")

        except RequestException:
            pass

        all_tables: List[pd.DataFrame] = []

        with pdfplumber.open(str(pdf_path)) as pdf:
            total_pages = len(pdf.pages)
            headers = None  # will store header row from first table

            for page_num, page in enumerate(
                tqdm(pdf.pages, total=total_pages, desc="Extracting PDF pages"),
                start=1
            ):
                table = page.extract_table()
                df = pd.DataFrame(table)

                # Set headers from the first detected table
                if headers is None:
                    headers = df.iloc[0].tolist()
                    df = df.iloc[1:].reset_index(drop=True)
                    df.columns = headers
                else:
                    try:
                        # Subsequent tables use same header
                        df = df.iloc[1:].reset_index(drop=True)
                        df.columns = headers[:len(df.columns)]
                    except:
                        # Create image of the page
                        im = page.to_image(resolution=300)
                        im.draw_rects(page.rects)
                

                        # Save to disk
                        im.save("debug_tables.png")

                all_tables.append(df)

        return pd.concat(all_tables, ignore_index=True).ffill() if all_tables else pd.DataFrame()
    
def main():
    ex = TsaExtract("./temp")
    results = ex.extract_file("https://www.tsa.gov/sites/default/files/foia-readingroom/tsa-throughput-data-to-february-1-2026-to-february-7-2026.pdf")



    results.to_csv("./pdf_contents.csv", index=False)
    

if __name__=="__main__":
    main()