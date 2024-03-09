import logging
import os
from threading import current_thread

from dotenv import load_dotenv
from sqlalchemy import select, delete, create_engine
from sqlalchemy.orm import sessionmaker

from models import User_, Video, Playlist, Playlist_User, Playlist_Video, Base

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
        logger.info(f"New engine is being generated for {key}")
        _engine = create_engine(
            url=f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}",
            echo=False,
        )
        _sessionmaker = sessionmaker(_engine)
        _engines[key] = [_engine, _sessionmaker]
    return _engines[key]


class DB:
    @staticmethod
    def create_tables() -> None:
        '''creates database tables for current engine'''
        logger.info("Creating tables")

        engine = get_local()[0]
        with engine.begin() as conn:
            # Base.metadata.drop_all(conn) # for tests
            Base.metadata.create_all(conn)

    @staticmethod
    def select_users() -> list:
        '''returns list of User_ class objects'''
        logger.info("Getting list of users")

        with get_local()[1]() as session:
            query = select(User_)
            result = session.execute(query)
            users = result.scalars().all()
        return users

    @staticmethod
    def select_videos() -> list:
        '''returns list of Video class objects'''
        logger.info("Getting list of videos")

        with get_local()[1]() as session:
            query = select(Video)
            result = session.execute(query)
            videos = result.scalars().all()
        return videos

    @staticmethod
    def select_playlists() -> list:
        '''returns list of Playlist class objects'''
        logger.info("Getting list of playlists")

        with get_local()[1]() as session:
            query = select(Playlist.id)
            result = session.execute(query)
            playlists = result.scalars().all()
        return playlists

    @staticmethod
    def add_user(chat: int) -> None:
        '''Adds new user to out database.

        Arguments:
            chat -- id of user (primary key)
        '''
        logger.info(f"Adding new user: {chat}")

        with get_local()[1]() as session:
            new_user = User_(id=chat)
            session.add(new_user)
            session.flush()
            session.commit()

    @staticmethod
    def add_video(video: str, file: str = None) -> None:
        '''Adds new video to out database.

        Arguments:
            video -- id of video (primary key)

            file -- path of video (default = None)

        Return value:
            None 
        '''
        logger.info(f"Adding new video: {video}, {file}")

        with get_local()[1]() as session:
            new_video = Video(id=video, file_id=file)
            session.add(new_video)
            session.flush()
            session.commit()

    @staticmethod
    def add_playlist(name: str, platform: str, status: bool = False) -> None:
        '''Adds new playlist to out database.

        Arguments:
            name -- name of playlist (primary key)

            platform -- platform from which videos for this playlist are downloaded
            
            status -- shows is it updating right now (default = False)

        Return value:
            None 
        '''
        logger.info(f"Adding new playlist: {name} from {platform}")

        with get_local()[1]() as session:
            new_playlist = Playlist(id=name, host = platform, is_updating = status)
            session.add(new_playlist)
            session.flush()
            session.commit()

    @staticmethod
    def add_playlist_user(chat: int, playlist: str) -> None:
        '''Adds new playlist user to out database.

        Arguments:
            chat -- new user of playlist (primary key)

            playlist -- name of users playlist (primary key)
            
        Return value:
            None 
        '''
        logger.info(f"Adding new playlist user: user {chat} to playlist {playlist}")

        with get_local()[1]() as session:
            new_playlist_user = Playlist_User(id_playlist=playlist, id_chat=chat)
            session.add(new_playlist_user)
            session.flush()
            session.commit()

    @staticmethod
    def add_playlist_video(video_id: str, playlist_id: str) -> None:
        '''Adds new playlist video to out database.

        Arguments:
            video_id -- new video of playlist (primary key)

            playlist_id -- name of users playlist (primary key)
            
        Return value:
            None 
        '''
        logger.info(f"Adding new playlist video: {video_id} to playlist {playlist_id}")

        with get_local()[1]() as session:
            new_playlist_video = Playlist_Video(id_playlist=playlist_id, id_video=video_id)
            session.add(new_playlist_video)
            session.flush()
            session.commit()

    @staticmethod
    def get_subscribed_users(playlist: str) -> list:
        '''Gets all users who are subscribed to this playlist.

        Arguments:
            playlist -- name of playlist
        
        Return value:
            list of user_id  
        '''
        logger.info(f"Getting all playlist {playlist} users")

        with get_local()[1]() as session:
            query = (select(Playlist_User.id_chat).select_from(Playlist_User)).where(
                Playlist_User.id_playlist == playlist)
            result = session.execute(query)
            users = result.scalars().all()
        return users

    @staticmethod
    def get_all_videos(playlist: str) -> list:
        '''Gets all videos of chosen playlist.

        Arguments:
            playlist -- name of playlist
        
        Return value:
            list of video_id
        '''
        logger.info(f"Getting all playlist {playlist} videos")

        with get_local()[1]() as session:
            query = (select(Playlist_Video.id_video).select_from(Playlist_Video)).where(
                Playlist_Video.id_playlist == playlist)
            result = session.execute(query)
            videos = result.scalars().all()
        return videos

    @staticmethod
    def delete_user(chat: int) -> None:
        '''Deletes unsubscribed user.

        Arguments:
            chat -- name of user
        
        Return value:
            None
        '''
        logger.info(f"Deleting user {chat}")

        with get_local()[1]() as session:
            query = (delete(User_).where(User_.id == chat))
            session.execute(query)
            session.flush()
            session.commit()

    @staticmethod
    def delete_video(video: str) -> None:
        '''Deletes useless video.

        Arguments:
            video -- name of video
        
        Return value:
            None
        '''
        logger.info(f"Deleting video {video}")

        with get_local()[1]() as session:
            query = (delete(Video).where(Video.id == video))
            session.execute(query)
            session.flush()
            session.commit()

    @staticmethod
    def delete_playlist(key: str) -> None:
        '''Deletes useless playlist.

        Arguments:
            key -- name of playlist
        
        Return value:
            None
        '''
        logger.info(f"Deleting playlist {key}")

        with get_local()[1]() as session:
            query = (delete(Playlist).where(Playlist.id == key))
            session.execute(query)
            session.flush()
            session.commit()

    @staticmethod
    def delete_playlist_video(playlist: str, video: str) -> None:
        '''Deletes video from target playlist.

        Arguments:
            playlist -- name of playlist

            video -- name of video
        
        Return value:
            None
        '''
        logger.info(f"Deleting video {video} from playlist {playlist}")

        with get_local()[1]() as session:
            query = (delete(Playlist_Video).where(Playlist_Video.id_video == video).where(
                Playlist_Video.id_playlist == playlist))
            session.execute(query)
            session.flush()
            session.commit()

    @staticmethod
    def delete_playlist_user(playlist: str, chat: int) -> None:
        '''Removes access of user to target playlist.

        Arguments:
            playlist -- name of playlist

            chat -- user
        
        Return value:
            None
        '''
        logger.info(f"Deleting user {chat} from playlist {playlist}")

        with get_local()[1]() as session:
            query = (
                delete(Playlist_User).where(Playlist_User.id_chat == chat).where(Playlist_User.id_playlist == playlist))
            session.execute(query)
            session.flush()
            session.commit()

    @staticmethod
    def update_video(id: str, new_file_id: str) -> None:
        '''Changes file_id of video.

        Arguments:
            id -- id of video

            new_file_id -- new value of file_id
        
        Return value:
            None
        '''
        logger.info(f"Changing file_id of video {id} to {new_file_id}")

        with get_local()[1]() as session:
            changable = session.get(Video, id)
            changable.file_id = new_file_id
            session.commit()

    @staticmethod
    def update_playlist_status(id: str, status: bool) -> None:
        '''Changes status of playlist.

        Arguments:
            id -- id of playlist

            status -- current (new) status
        
        Return value:
            None
        '''
        logger.info(f"Changing status of playlist {id}")

        with get_local()[1]() as session:
            changable = session.get(Playlist, id)
            changable.is_updating = status
            session.commit()

    @staticmethod
    def get_video(id: str) -> Video:
        '''Gets video info by id.

        Arguments:
            id -- id of video
        
        Return value:
            class Video object
        '''
        logger.info(f"getting video {id} info")

        with get_local()[1]() as session:
            target = session.get(Video, id)
        return target

    @staticmethod
    def get_playlist(id: str) -> Playlist:
        '''Gets playlist info by id.

        Arguments:
            id -- id of playlist
        
        Return value:
            class Playlist object
        '''
        logger.info(f"getting playlist {id} info")

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

    DB.add_playlist("agil", "youtube")
    DB.add_playlist("amirov", "youtube")
    DB.add_playlist("roma", "youtube")

    DB.add_playlist_user(123, 'agil')
    DB.add_playlist_user(123, "amirov")
    DB.add_playlist_user(124, 'agil')
    DB.add_playlist_user(125, "roma")
    print(DB.get_subscribed_users('agil'))

    DB.add_playlist_video('cat', "agil")
    DB.add_playlist_video("dog", 'agil')
    DB.add_playlist_video("fail", 'agil')
    DB.add_playlist_video("cat", "amirov")
    DB.add_playlist_video("dog", "amirov")
    DB.add_playlist_video("fail", "amirov")
    DB.add_playlist_video("cat", "roma")
    DB.add_playlist_video("dog", "roma")
    DB.add_playlist_video("fail", "roma")
    DB.get_all_videos("amirov")

    DB.delete_user(123)
    DB.delete_video("cat")

    DB.delete_playlist("roma")
    DB.delete_playlist_video('agil', "dog")


def init():
    DB.add_user(1)
    DB.add_user(2)
    DB.add_video("roma")
    DB.add_video("neroma", "ahil")
    print(DB.select_users())
    
    

DB.create_tables()

if __name__ == '__main__':
    # test()
    init()