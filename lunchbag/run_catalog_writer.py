import os
from dotenv import load_dotenv
from lunchbag.tools.catalog_writer_tool import CatalogWriterTool

load_dotenv()

print("\n" + "="*50)
print("  ORPINA — CATALOG WRITER")
print("="*50 + "\n")

tool   = CatalogWriterTool()
report = tool._run()
print(report)

print("\n" + "="*50)
print("  Report saved to:")
print("  asset_library/catalog.json")
print("="*50 + "\n")
