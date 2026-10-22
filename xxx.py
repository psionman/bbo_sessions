import re

source_title = "#1 Phoinix 15 October 2025"
club_name = re.sub(r"^#\d+\s*", "", source_title)
club_name = re.sub(r"\s+\d{1,2} \w+ \d{4}$", "", club_name)
print(club_name)
