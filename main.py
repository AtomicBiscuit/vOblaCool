from urllib.parse import urlparse

from pytube import YouTube
from pytube import extract
from pytube.exceptions import RegexMatchError

#
# DOMAIN = config('domain')
#
# ans = req.post(f'https://{DOMAIN}/api/download-complete',
#                    json={'message_id': 221, 'chat_id': 853352009, 'data': "message.text"})
# print(ans)

url = urlparse('https://www.youtube.com/watch?v=NBCS3BsuwTA')
print(YouTube('https://m.youtube.com/watch?v=NBCS3BsuwTA').watch_url)



test_urls = [
    'http://www.youtube.com/watch?v=5Y6HSHwhVlY',
    'http://youtu.be/5Y6HSHwhVlY',
    'http://www.youtube.com/embed/5Y6HSHwhVlY?rel=0" frameborder="0"',
    'https://www.youtube-nocookie.com/v/5Y6HSHwhVlY?version=3&amp;hl=en_US',
    'http://www.youtube.com/',
    'http://www.youtube.com/?feature=ytca'
]
for test in test_urls:
    print(validate_youtube(test))
