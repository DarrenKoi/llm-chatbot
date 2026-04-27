"""Local defaults for raw richnotification test payloads.

Edit these values for quick local runs. Do not commit real tokens.
"""

TIMEOUT_SECONDS = 10.0

# richnotification.header
HEADER_FROM = ""
HEADER_TOKEN = ""
# 단일 문자열을 넣으면 5개 슬롯이 모두 같은 값으로 채워진다.
# 언어별로 다른 이름이 필요하면 ("KO이름", "EN이름", ...) 형태의 튜플로 적는다.
HEADER_FROMUSERNAME = "ITC OSS"
HEADER_TO_UNIQUENAME = "your.cube.id"
HEADER_TO_CHANNELID = ""

# richnotification.content[].process
PROCESS_CALLBACKTYPE = "url"
PROCESS_CALLBACKADDRESS = ""
