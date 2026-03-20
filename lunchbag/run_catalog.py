import sys
import os
sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
))

from dotenv import load_dotenv
load_dotenv()

from lunchbag.tools.catalog_writer_tool import CatalogWriterTool

print("\n" + "="*50)
print("  THE LUNCHBAGS — CATALOG WRITER")
print("="*50 + "\n")

tool   = CatalogWriterTool()
result = tool._run()
print(result)

print("\n" + "="*50)
print("  Catalog saved to:")
print("  asset_library/catalog.json")
print("="*50 + "\n")
