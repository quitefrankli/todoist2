import yaml
import os
import json

from datetime import datetime
from pathlib import Path
from typing import *

from desktop_app.goal import Goal


SAVE_DIRECTORY = Path.home() if os.name == 'nt' else '/tmp'

class Backend:
    SAVE_FILE = f"{SAVE_DIRECTORY}/.todoist2_goals.yaml"
    BACKUP_DIR = f"{SAVE_DIRECTORY}/.todoist2_backup"

    def __init__(self) -> None:
        self.goals: Dict[int, Goal] = self.load_goals()
        self._global_goal_id = max(self.goals.values(), key=lambda goal: goal.id).id
        
        # setup parenting
        for goal in self.goals.values():
            if goal.parent != -1:
                parent = self.get_goal(goal.parent)
                parent.children.append(goal.id)

    def generate_next_goal_id(self) -> int:
        self._global_goal_id += 1
        return self._global_goal_id

    def add_goal(self, goal: Goal) -> int:
        assert(goal.id == -1)
        goal.id = self.generate_next_goal_id()
        self.goals[goal.id] = goal
        self.save_goals()
        
        return goal.id

    def delete_goal(self, goal_id: int) -> None:
        del self.goals[goal_id]
        self.save_goals()

    def _goals_to_obj(self):
        data = {
            'goals': [goal.to_dict() for goal in self.goals.values()],
            'edited': int(self.get_datetime_str())
        }
        return data

    def save_goals(self, file_path: str = SAVE_FILE) -> None:
        Path(file_path).parent.mkdir(exist_ok=True, parents=True)
        with open(file_path, 'w') as file:
            yaml.dump(self._goals_to_obj(), file)

    def load_goals(self) -> Dict[int, Goal]:
        try:
            with open(self.SAVE_FILE, 'r') as file:
                data = yaml.safe_load(file)
                return { goal['id']: Goal.from_dict(goal) for goal in data['goals'] }
        except FileNotFoundError:
            return []
        
    def backup_goals(self) -> str:
        backup = f"{self.BACKUP_DIR}/{self.get_datetime_str()}.yaml"
        self.save_goals(backup)
        return backup

    def get_datetime_str(self) -> str:
        return datetime.now().strftime("%Y%m%d%H%M%S")

    def toggle_goal_state(self, goal_id: int) -> None:
        goal = self.goals[goal_id]
        goal.state = not goal.state
        if goal.state:
            goal.metadata.completion_date = datetime.now()
        else:
            goal.metadata.completion_date = None
        self.save_goals()

    def unparent_goal(self, goal_id: int) -> None:
        goal = self.get_goal(goal_id)
        if goal.parent != -1:
            parent = self.get_goal(goal.parent)
            parent.children = list(filter(lambda id: id != goal_id, parent.children))
            goal.parent = -1
            self.save_goals()

    def remove_goal_from_hierarchy(self, goal_id: int) -> None:
        goal = self.get_goal(goal_id)
        if goal.parent != -1:
            parent = self.get_goal(goal.parent)
            parent.children = list(filter(lambda id: id != goal_id, parent.children))
            goal.parent = -1

        for child_id in goal.children:
            child = self.get_goal(child_id)
            child.parent = -1
        self.save_goals()

    def setup_parent(self, child_id: int, parent_id: int) -> None:
        if parent_id == child_id:
            return None

        child = self.get_goal(child_id)
        parent = self.get_goal(parent_id)
        if child_id in parent.children: # already tied to parent
            return None
        
        # edge case where parent is a child of child
        if parent.parent == child_id:
            return None

        # first remove the goal from its current parent
        if child.parent != -1:
            curr_goal_parent = self.get_goal(child.parent)
            curr_goal_parent.children = list(filter(lambda id: id != child_id, curr_goal_parent.children))

        # then add it to the new parent
        parent.children.append(child_id)
        child.parent = parent.id
        self.save_goals()
    
    def delete_goal(self, goal_id: int) -> None:
        self.remove_goal_from_hierarchy(goal_id)
        del self.goals[goal_id]
        self.save_goals()

    def get_goals(self) -> List[Goal]:
        return list(self.goals.values())
    
    def get_goal(self, goal_id: int) -> Goal:
        return self.goals[goal_id]
    
    def get_goals_json(self) -> str:
        return json.dumps(self._goals_to_obj())