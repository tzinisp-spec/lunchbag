from lunchbag.tools.catalog_utils import sync_catalog

# Update the catalog and print results
images = sync_catalog()
print(f"Catalog refreshed from disk: {len(images)} images found.")
