import os
from unittest import TestCase
from unittest.mock import patch, Mock, MagicMock

from src.worker.worker import Worker, loaders

sep = os.sep


def mock_to_dict(mock: MagicMock):
    return mock | {}


class BaseWorker(TestCase):
    hosting = None

    def setUp(self):
        self.client = Worker

    @staticmethod
    def get_locals():
        obj = [MagicMock(), MagicMock(), MagicMock()]
        return obj

    def base_download(self, local_mock, req_post_mock, url, error, body, pre_logic=None, post_logic=None):
        payload = {
            'url': url,
            'hosting': self.hosting
        }
        mocks = self.get_locals()
        local_mock.return_value = mocks
        if pre_logic:
            pre_logic(mocks)
        self.client.download(payload)
        req_post_mock.assert_called_once_with(
            f"http://{loaders[self.hosting]['host']}:{loaders[self.hosting]['port']}/api/download",
            json={'url': payload['url']},
            timeout=1000
        )
        if error:
            mocks[0].send_video.assert_not_called()
        else:
            mocks[0].send_video.assert_called_once()
        mocks[2].basic_publish.assert_called_once_with(
            exchange='',
            routing_key='answer_queue',
            body=payload | body
        )
        if post_logic:
            post_logic(mocks)


class WorkerYoutubeTestCase(BaseWorker):
    hosting = 'youtube'

    @patch('json.dumps', side_effect=mock_to_dict)
    @patch('src.worker.worker.get_local')
    @patch('requests.post', return_value=Mock(status_code=200, text=os.path.dirname(os.path.abspath(__file__)) + f'{sep}data{sep}video.mp4'))
    def test_youtube_download(self, req_post_mock: Mock, local_mock: Mock, json_dumps_mock: Mock):
        def _pre(mocks):
            mocks[0].send_video.return_value.video.file_id = '7986223'

        self.base_download(
            local_mock,
            req_post_mock,
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ&pp=ygULcmljayBhc3RsZXk%3D',
            False,
            {'file_id': '7986223', 'error_code': None},
            _pre
        )

    @patch('json.dumps', side_effect=mock_to_dict)
    @patch('src.worker.worker.get_local')
    @patch('requests.post', return_value=Mock(status_code=200, text=os.path.dirname(os.path.abspath(__file__)) + f'{sep}data{sep}no_video.mp4'))
    def test_youtube_incorrect_download(self, req_post_mock: Mock, local_mock: Mock, json_dumps_mock: Mock):
        self.base_download(
            local_mock,
            req_post_mock,
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ&pp=ygULcmljayBhc3RsZXk%3D',
            True,
            {'file_id': None, 'error_code': 500},
        )

    @patch('json.dumps', side_effect=mock_to_dict)
    @patch('src.worker.worker.get_local')
    @patch('requests.post', return_value=Mock(status_code=413))
    def test_youtube_download_error(self, req_post_mock: Mock, local_mock: Mock, json_dumps_mock: Mock):
        self.base_download(
            local_mock,
            req_post_mock,
            'https://www.youtube.com/watch?v=777777777777777777777777777777',
            True,
            {'file_id': None, 'error_code': req_post_mock.return_value.status_code},
        )


class WorkerVkTestCase(BaseWorker):
    hosting = 'vk'

    @patch('json.dumps', side_effect=mock_to_dict)
    @patch('src.worker.worker.get_local')
    @patch('requests.post', return_value=Mock(status_code=200, text=os.path.dirname(os.path.abspath(__file__)) + f'{sep}data{sep}video.mp4'))
    def test_vk_download(self, req_post_mock: Mock, local_mock: Mock, json_dumps_mock: Mock):
        def _pre(mocks):
            mocks[0].send_video.return_value.video.file_id = '704977679_456239136'

        self.base_download(
            local_mock,
            req_post_mock,
            'https://vk.com/video?q=бэбэй%20жестко%20спел%20русская%20дорога&z=video704977679_456239136%2Fpl_cat_trends',
            False,
            {'file_id': '704977679_456239136', 'error_code': None},
            _pre
        )

    @patch('json.dumps', side_effect=mock_to_dict)
    @patch('src.worker.worker.get_local')
    @patch('requests.post', return_value=Mock(status_code=200, text=os.path.dirname(os.path.abspath(__file__)) + f'{sep}data{sep}no_video.mp4'))
    def test_vk_incorrect_download(self, req_post_mock: Mock, local_mock: Mock, json_dumps_mock: Mock):
        self.base_download(
            local_mock,
            req_post_mock,
            'https://vk.com/video?q=бэбэй%20жестко%20спел%20русская%20дорога&z=video704977679_36%2Fpl_cat_trendsD',
            True,
            {'file_id': None, 'error_code': 500},
        )

    @patch('json.dumps', side_effect=mock_to_dict)
    @patch('src.worker.worker.get_local')
    @patch('requests.post', return_value=Mock(status_code=400))
    def test_youtube_download_error(self, req_post_mock: Mock, local_mock: Mock, json_dumps_mock: Mock):
        self.base_download(
            local_mock,
            req_post_mock,
            'https://vk.com/video?z=video704977679_36',
            True,
            {'file_id': None, 'error_code': req_post_mock.return_value.status_code},
        )