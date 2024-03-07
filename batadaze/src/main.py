import logging
import os
from threading import current_thread

from dotenv import load_dotenv
from sqlalchemy import select, delete, create_engine
from sqlalchemy.orm import sessionmaker

from batadaze.src.models import User_, Video, Playlist, Playlist_User, Playlist_Video, Base

logger = logging.getLogger("DB Connector")

logger.setLevel(logging.INFO)

handler = logging.StreamHandler()

handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))

logger.addHandler(handler)

load_dotenv()

db_host = os.getenv('POSTGRES_HOST')
db_port = os.getenv('POSTGRES_PORT')
db_user = os.getenv('POSTGRES_USER')
db_pass = os.getenv('POSTGRES_PASSWORD')
db_name = os.getenv('POSTGRES_DB')

_engines = dict()


def get_local():
    thread = current_thread()
    key = str(id(thread))
    if key not in _engines.keys():
        logger.info(f"New engine generating for {key}")
        _engine = create_engine(
            url=f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}",
            echo=False,
        )
        _sessionmaker = sessionmaker(_engine)
        _engines[key] = [_engine, _sessionmaker]
    return _engines[key]


class DB:
    @staticmethod
    def create_tables():
        engine = get_local()[0]
        with engine.begin() as conn:
            #  conn.run_sync(Base.metadata.drop_all) # for tests
            Base.metadata.create_all(conn)

    @staticmethod
    def select_users():
        with get_local()[1]() as session:
            query = select(User_)
            result = session.execute(query)
            users = result.scalars().all()
        return users

    @staticmethod
    def select_videos():
        with get_local()[1]() as session:
            query = select(Video)
            result = session.execute(query)
            videos = result.scalars().all()
        return videos

    @staticmethod
    def select_playlists():
        with get_local()[1]() as session:
            query = select(Playlist.id)
            result = session.execute(query)
            playlists = result.scalars().all()
        return playlists

    @staticmethod
    def add_user(chat: int):
        with get_local()[1]() as session:
            new_user = User_(id=chat)
            session.add(new_user)
            session.flush()
            session.commit()

    @staticmethod
    def add_video(video, file=None):
        with get_local()[1]() as session:
            new_video = Video(id=video, file_id=file)
            session.add(new_video)
            session.flush()
            session.commit()

    @staticmethod
    def add_playlist_user(chat, playlist):
        with get_local()[1]() as session:
            new_playlist_user = Playlist_User(id_playlist=playlist, id_chat=chat)
            session.add(new_playlist_user)
            session.flush()
            session.commit()

    @staticmethod
    def add_playlist_video(video_id, playlist_id):
        logger.info(f"Add playlist_video: {video_id}, {playlist_id}")
        with get_local()[1]() as session:
            new_playlist_video = Playlist_Video(id_playlist=playlist_id, id_video=video_id)
            session.add(new_playlist_video)
            session.flush()
            session.commit()

    @staticmethod
    def add_playlist(name):
        with get_local()[1]() as session:
            new_playlist = Playlist(id=name)
            session.add(new_playlist)
            session.flush()
            session.commit()

    @staticmethod
    def get_subscribed_users(playlist):
        with get_local()[1]() as session:
            query = (select(Playlist_User.id_chat).select_from(Playlist_User)).where(
                Playlist_User.id_playlist == playlist)
            result = session.execute(query)
            users = result.scalars().all()
        return users

    @staticmethod
    def get_all_videos(playlist):
        with get_local()[1]() as session:
            query = (select(Playlist_Video.id_video).select_from(Playlist_Video)).where(
                Playlist_Video.id_playlist == playlist)
            result = session.execute(query)
            videos = result.scalars().all()
        return videos

    @staticmethod
    def delete_user(chat):
        with get_local()[1]() as session:
            query = (delete(User_).where(User_.id == chat))
            session.execute(query)
            session.flush()
            session.commit()

    @staticmethod
    def delete_video(video):
        with get_local()[1]() as session:
            query = (delete(Video).where(Video.id == video))
            session.execute(query)
            session.flush()
            session.commit()

    @staticmethod
    def delete_playlist(key):
        with get_local()[1]() as session:
            query = (delete(Playlist).where(Playlist.id == key))
            session.execute(query)
            session.flush()
            session.commit()

    @staticmethod
    def delete_playlist_video(playlist, video):
        with get_local()[1]() as session:
            query = (delete(Playlist_Video).where(Playlist_Video.id_video == video).where(
                Playlist_Video.id_playlist == playlist))
            session.execute(query)
            session.flush()
            session.commit()

    @staticmethod
    def delete_playlist_user(playlist, chat):
        with get_local()[1]() as session:
            query = (
                delete(Playlist_User).where(Playlist_User.id_chat == chat).where(Playlist_User.id_playlist == playlist))
            session.execute(query)
            session.flush()
            session.commit()

    @staticmethod
    def update_video(id: str, new_file_id: str):
        with get_local()[1]() as session:
            changable = session.get(Video, id)
            changable.file_id = new_file_id
            session.commit()

    @staticmethod
    def get_video(id: str):
        with get_local()[1]() as session:
            target = session.get(Video, id)
        return target

    @staticmethod
    def get_user(id: int):
        with get_local()[1]() as session:
            target = session.get(User_, id)
        return target

    @staticmethod
    def get_playlist(id: str):
        with get_local()[1]() as session:
            target = session.get(Playlist, id)
        return target


# example of using
def test():
    DB.create_tables()

    DB.add_user(123)
    DB.add_user(124)
    DB.add_user(125)
    DB.select_users()

    DB.add_video("cat", "youtube")
    DB.add_video("dog", "youtube")
    DB.add_video("fail", "youtube")
    DB.select_videos()

    DB.add_playlist("agil")
    DB.add_playlist("amirov")
    DB.add_playlist("roma")

    DB.add_playlist_user('agil', 123)
    DB.add_playlist_user("amirov", 123)
    DB.add_playlist_user('agil', 124)
    DB.add_playlist_user("roma", 125)
    DB.get_subscribed_users(123)

    DB.add_playlist_video('agil', "cat")
    DB.add_playlist_video('agil', "dog")
    DB.add_playlist_video('agil', "fail")
    DB.add_playlist_video("amirov", "cat")
    DB.add_playlist_video("amirov", "dog")
    DB.add_playlist_video("amirov", "fail")
    DB.add_playlist_video("roma", "cat")
    DB.add_playlist_video("roma", "dog")
    DB.add_playlist_video("roma", "fail")
    DB.get_all_videos("amirov")

    DB.delete_user(123)
    DB.delete_video("cat")

    DB.delete_playlist("roma")
    DB.delete_playlist_video('agil', "dog")


def init():
    DB.add_user(1)


DB.create_tables()

if __name__ == '__main__':
    # test()
    init()
