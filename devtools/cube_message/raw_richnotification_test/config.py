"""Local defaults for raw richnotification test payloads.

Edit these values for quick local runs. Do not commit real tokens.
"""

TIMEOUT_SECONDS = 10.0

# richnotification.header
HEADER_FROM = ""
HEADER_TOKEN = ""
HEADER_FROMUSERNAME = ("ITC OSS",)
HEADER_TO_UNIQUENAME = "your.cube.id"
HEADER_TO_CHANNELID = ""

# richnotification.content[].process
PROCESS_CALLBACKTYPE = "url"
PROCESS_CALLBACKADDRESS = ""
