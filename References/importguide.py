# Ensure that you use a valid string representation of the path
# Add the "Usable" folder to the system path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../Usable'))

# Import whatever
import url_scraper






# Exmaple use, uncomment to test
#storage = [
#    "Tattoo Collectors",
#    "Van Gogh Museum",
#    "Nederlandse Spoorweg",
#    "Phillips",
#    "Samyang"
#]

# Use the url_scraper's url_builder function
#url_scraper.url_builder(storage, "test_output")
