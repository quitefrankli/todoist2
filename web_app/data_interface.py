import boto3
import logging
import json
import random
import string
import os
import shutil

from botocore.exceptions import ClientError
from pathlib import Path
from datetime import datetime
from typing import *

from web_app.users import User
from web_app.constants import PROJECT_LOCAL_SAVE_DIRECTORY


BACKUPS_DIRECTORY = PROJECT_LOCAL_SAVE_DIRECTORY.parent / "backups"
USERS_FILE = PROJECT_LOCAL_SAVE_DIRECTORY / "users.json"

def _get_data_file(user: User) -> Path:
    return PROJECT_LOCAL_SAVE_DIRECTORY / user.folder / "data.json"

def _get_backup_dir(user: User) -> Path:
    return PROJECT_LOCAL_SAVE_DIRECTORY / user.folder / "backups"

def _generate_random_string() -> str:
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for _ in range(10))
    return result_str

class _S3Client:
    BUCKET_NAME = 'todoist2'
    
    def __init__(self) -> None:
        ACCESS_KEY = os.environ["AWS_ACCESS_KEY_ID"]
        SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
        self.s3_client = boto3.client('s3', 
                                      aws_access_key_id=ACCESS_KEY, 
                                      aws_secret_access_key=SECRET_ACCESS_KEY)

    @staticmethod
    def _get_s3_path(file: Path) -> str:
        return str(file.relative_to(PROJECT_LOCAL_SAVE_DIRECTORY).as_posix())

    def download_file(self, file: Path) -> None:
        logging.info(f"Downloading {self._get_s3_path(file)} from s3 to {file}")
        if not file.parent.exists():
            file.parent.mkdir(exist_ok=True, parents=True)
        try:
            self.s3_client.download_file(self.BUCKET_NAME, self._get_s3_path(file), str(file))
        except ClientError as e:
            if e.response['Error']['Code'] == "404":
                logging.warning(f"File {file} not found in s3")
            else:
                raise

    def upload_file(self, file: Path) -> None:
        logging.info(f"Uploading {self._get_s3_path(file)} to s3 from {file}")
        self.s3_client.upload_file(str(file), self.BUCKET_NAME, self._get_s3_path(file))

class _DebugS3Client:
    def download_file(self, file: Path) -> None:
        pass

    def upload_file(self, file: Path) -> None:
        pass

class DataInterface:
    @classmethod
    def create_instance(cls, debug: bool) -> 'DataInterface':
        cls._instance = DataInterface(debug)
    
    @classmethod
    def instance(cls) -> 'DataInterface':
        return cls._instance

    def __init__(self, debug: bool) -> None:
        # don't really need to use s3 if we keep everything on ec2
        self.online_syncer = _DebugS3Client() # if debug else _S3Client()
    
    def load_users(self) -> Dict[str, User]:
        self.online_syncer.download_file(USERS_FILE)

        if not USERS_FILE.exists():
            return {}

        with open(USERS_FILE, 'r') as file:
            users_data: list = json.load(file)
            users = [User.from_dict(user) for user in users_data]

        return {user.id: user for user in users}

    def save_users(self, users: List[User]) -> None:
        USERS_FILE.parent.mkdir(exist_ok=True, parents=True)
        with open(USERS_FILE, 'w', encoding='utf-8') as file:
            json.dump([user.to_dict() for user in users], file, indent=4)
        self.online_syncer.upload_file(USERS_FILE)

    def generate_new_user(self, username: str, password: str) -> User:
        users = self.load_users()
        used_folders = {user.folder for user in users.values()}
        for _ in range(100):
            folder = _generate_random_string()
            if folder not in used_folders:
                return User(username, password, folder)
        raise RuntimeError("Could not generate unique folder")

    def load_data(self, rel_path: Path) -> any:
        path = PROJECT_LOCAL_SAVE_DIRECTORY / rel_path
        self.online_syncer.download_file(path)
        if not path.exists():
            return TopLevelData(goals={}, edited=datetime.now())
        
        with open(data_file, 'r') as file:
            data = json.load(file)

        return TopLevelData(**data)
            
    def save_data(self, data: TopLevelData, user: User) -> None:
        data_file = _get_data_file(user)
        data_file.parent.mkdir(exist_ok=True, parents=True)
        with open(data_file, 'w', encoding='utf-8') as file:
            file.write(data.model_dump_json(indent=4))
        self.online_syncer.upload_file(data_file)

    def backup_data(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        new_backup = BACKUPS_DIRECTORY / timestamp
        shutil.copytree(PROJECT_LOCAL_SAVE_DIRECTORY, new_backup)
        # TODO: zip the backup and upload to s3
        # self.online_syncer.upload_file(new_backup)