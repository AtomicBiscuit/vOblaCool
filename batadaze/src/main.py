import logging
import os
from threading import current_thread

from dotenv import load_dotenv
from sqlalchemy import select, delete, create_engine
from sqlalchemy.exc import OperationalError
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
create_tables = os.getenv('CREATE_TABLES', False)

_engines = dict()


def get_local():
    thread = current_thread()
    key = str(id(thread))
    if key not in _engines.keys():
        logger.info(f"New engine is being generated for {key}")
        _engine = create_engine(
            url=f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}",
            echo=False,
            pool_pre_ping=True,
        )
        _sessionmaker = sessionmaker(_engine)
        _engines[key] = [_engine, _sessionmaker]
    return _engines[key]


class DB:
    """
    """

    @staticmethod
    def create_tables() -> None:
        """creates database tables for current engine"""
        logger.info("Creating tables")

        engine = get_local()[0]
        with engine.begin() as conn:
            # Base.metadata.drop_all(conn) # for tests
            Base.metadata.create_all(conn)

    @staticmethod
    def select_users() -> list:
        """returns list of `User_ class` objects"""
        logger.info("Getting list of users")

        with get_local()[1]() as session:
            query = select(User_)
            result = session.execute(query)
            users = result.scalars().all()
        return users

    @staticmethod
    def select_videos() -> list:
        """returns list of Video class objects"""
        logger.info("Getting list of videos")

        with get_local()[1]() as session:
            query = select(Video)
            result = session.execute(query)
            videos = result.scalars().all()
        return videos

    @staticmethod
    def select_playlists() -> list:
        """returns list of Playlist class objects"""
        logger.info("Getting list of playlists")

        with get_local()[1]() as session:
            query = select(Playlist)
            result = session.execute(query)
            playlists = result.scalars().all()
        return playlists

    @staticmethod
    def add_user(chat: int) -> None:
        """Adds new user in database.

        :param chat: id of user (primary key)
        """
        logger.info(f"Adding new user: {chat}")

        with get_local()[1]() as session:
            new_user = User_(id=chat)
            session.add(new_user)
            session.flush()
            session.commit()

    @staticmethod
    def add_video(video: str, file: str = None) -> None:
        """Adds new video to out database.

        :param video: id of video (primary key)
        :param file: path of video (default = None)
        """
        logger.info(f"Adding new video: {video}, {file}")

        with get_local()[1]() as session:
            new_video = Video(id=video, file_id=file)
            session.add(new_video)
            session.flush()
            session.commit()

    @staticmethod
    def add_playlist(name: str, platform: str, status: bool = False) -> None:
        """Adds new playlist to out database.

        :param name: name of playlist (primary key)
        :param platform: platform from which videos for this playlist are downloaded
        :param status: shows is it updating right now (default = False)
        """
        logger.info(f"Adding new playlist: {name} from {platform}")

        with get_local()[1]() as session:
            new_playlist = Playlist(id=name, host=platform, is_updating=status)
            session.add(new_playlist)
            session.flush()
            session.commit()

    @staticmethod
    def add_playlist_user(chat: int, playlist: str) -> None:
        """Adds new playlist user to out database.

        :param chat: new user of playlist (primary key)
        :param playlist: name of users playlist (primary key)
        """
        logger.info(f"Adding new playlist user: user {chat} to playlist {playlist}")

        with get_local()[1]() as session:
            new_playlist_user = Playlist_User(id_playlist=playlist, id_chat=chat)
            session.add(new_playlist_user)
            session.flush()
            session.commit()

    @staticmethod
    def add_playlist_video(video_id: str, playlist_id: str) -> None:
        """Adds new playlist video to out database.

        :param video_id: new video of playlist (primary key)
        :param playlist_id: name of users playlist (primary key)
        """
        logger.info(f"Adding new playlist video: {video_id} to playlist {playlist_id}")

        with get_local()[1]() as session:
            new_playlist_video = Playlist_Video(id_playlist=playlist_id, id_video=video_id)
            session.add(new_playlist_video)
            session.flush()
            session.commit()

    @staticmethod
    def get_subscribed_users(playlist: str) -> list:
        """Gets all users who are subscribed to this playlist.

        :param playlist: name of playlist

        :return: list of user_id
        """
        logger.info(f"Getting all playlist {playlist} users")

        with get_local()[1]() as session:
            query = (select(Playlist_User.id_chat).select_from(Playlist_User)).where(
                Playlist_User.id_playlist == playlist)
            result = session.execute(query)
            users = result.scalars().all()
        return users

    @staticmethod
    def get_all_videos(playlist: str) -> list:
        """Gets all videos of chosen playlist.

        :param playlist: name of playlist

        :return: list of video_id
        """
        logger.info(f"Getting all playlist {playlist} videos")

        with get_local()[1]() as session:
            query = (select(Playlist_Video.id_video).select_from(Playlist_Video)).where(
                Playlist_Video.id_playlist == playlist)
            result = session.execute(query)
            videos = result.scalars().all()
        return videos

    @staticmethod
    def delete_user(chat: int) -> None:
        """Deletes unsubscribed user.

        :param chat: name of user
        """
        logger.info(f"Deleting user {chat}")

        with get_local()[1]() as session:
            query = (delete(User_).where(User_.id == chat))
            session.execute(query)
            session.flush()
            session.commit()

    @staticmethod
    def delete_video(video: str) -> None:
        """Deletes useless video.

        :param video: name of video
        """
        logger.info(f"Deleting video {video}")

        with get_local()[1]() as session:
            query = (delete(Video).where(Video.id == video))
            session.execute(query)
            session.flush()
            session.commit()

    @staticmethod
    def delete_playlist(key: str) -> None:
        """Deletes useless playlist.

        :param key: name of playlist
        """
        logger.info(f"Deleting playlist {key}")

        with get_local()[1]() as session:
            query = (delete(Playlist).where(Playlist.id == key))
            session.execute(query)
            session.flush()
            session.commit()

    @staticmethod
    def delete_playlist_video(playlist: str, video: str) -> None:
        """Deletes video from target playlist.

        :param playlist: name of playlist
        :param video: name of video
        """
        logger.info(f"Deleting video {video} from playlist {playlist}")

        with get_local()[1]() as session:
            query = (delete(Playlist_Video).where(Playlist_Video.id_video == video).where(
                Playlist_Video.id_playlist == playlist))
            session.execute(query)
            session.flush()
            session.commit()

    @staticmethod
    def delete_playlist_user(playlist: str, chat: int) -> None:
        """Removes access of user to target playlist.

        :param playlist: name of playlist
        :param chat: user
        """
        logger.info(f"Deleting user {chat} from playlist {playlist}")

        with get_local()[1]() as session:
            query = (
                delete(Playlist_User).where(Playlist_User.id_chat == chat).where(Playlist_User.id_playlist == playlist))
            session.execute(query)
            session.flush()
            session.commit()

    @staticmethod
    def update_video(id: str, new_file_id: str) -> None:
        """Changes file_id of video.

        :param id: id of video
        :param new_file_id: new value of file_id
        """
        logger.info(f"Changing file_id of video {id} to {new_file_id}")

        with get_local()[1]() as session:
            changable = session.get(Video, id)
            changable.file_id = new_file_id
            session.commit()

    @staticmethod
    def update_playlist_status(id: str, status: bool) -> None:
        """Changes status of playlist.

        :param id: id of playlist
        :param status: current (new) status
        """
        logger.info(f"Changing status of playlist {id}")

        with get_local()[1]() as session:
            changable = session.get(Playlist, id)
            changable.is_updating = status
            session.commit()

    @staticmethod
    def get_user(id: str) -> Video:
        """Gets user info by id.

        :param id: id of user

        :return: class User object
        """
        logger.info(f"getting user {id} info")

        with get_local()[1]() as session:
            target = session.get(User_, id)
        return target

    @staticmethod
    def get_video(id: str) -> Video:
        """Gets video info by id.

        :param id: id of video

        :return: class Video object
        """
        logger.info(f"getting video {id} info")

        with get_local()[1]() as session:
            target = session.get(Video, id)
        return target

    @staticmethod
    def get_playlist(id: str) -> Playlist:
        """Gets playlist info by id.

        :param id: id of playlist

        :return: class Playlist object
        """
        logger.info(f"getting playlist {id} info")

        with get_local()[1]() as session:
            target = session.get(Playlist, id)
        return target


def init():
    DB.add_user(1)
    DB.add_user(2)
    DB.add_video("roma")
    DB.add_video("neroma", "ahil")
    print(DB.select_users())


if create_tables == 'True':
    try:
        DB.create_tables()
    except OperationalError as e:
        logger.error(e)

if __name__ == '__main__':
    # test()
    init()
