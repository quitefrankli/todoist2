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


class DataInterface:
    def load_data(self, user: User) -> TopLevelData:
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