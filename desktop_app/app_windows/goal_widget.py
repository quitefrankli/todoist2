import tkinter

from tkinter import Frame, Label, Button, Checkbutton, Message
from tkinter.scrolledtext import ScrolledText
from typing import *
from datetime import datetime, timedelta
from tkcalendar import Calendar

from playsound import playsound
from desktop_app.client import ClientV2
from desktop_app.goal import Goal
from desktop_app.helpers import select_date
from desktop_app.app_windows.goals_window import GoalsWindow


class GoalDetailsWindow(tkinter.Toplevel):
    WINDOW_WIDTH = 400
    WINDOW_HEIGHT = 300
    GOAL_NAME_FONT = 'Helvetica 12 bold'
    GOAL_NAME_CHAR_ACROSS = 350
    GOAL_DESCRIPTION_FONT = 'Helvetica 10'

    def toggle_backlog(self) -> None:
        self.goal.backlogged = not self.goal.backlogged
        self.need_saving = True
        self.need_refresh = True
        self.close_window()

    def toggle_daily(self) -> None:
        if self.is_daily:
            self.goal.daily = Goal.NULL_DATE
            self.need_saving = True
            self.need_refresh = True
            self.close_window()
            return
        
        selected_date = select_date(self)
        if selected_date is None:
            return
        self.goal.daily = datetime(selected_date.year, selected_date.month, selected_date.day, hour=9)
        self.need_saving = True
        self.need_refresh = True

    def unparent(self) -> None:
        self.client.unparent_goal(self.goal.id)
        self.need_refresh = True
        self.close_window()

    def rename_goal(self) -> None:
        top = tkinter.Toplevel(self)
        top.geometry(f"200x200+{self.winfo_rootx()}+{self.winfo_rooty()}")
        top.title("Rename Goal")
        goal_name = tkinter.StringVar()
        Label(top, text='Enter New Goal Name').pack()
        new_goal_entry = tkinter.Entry(top, textvariable=goal_name)
        new_goal_entry.focus()
        new_goal_entry.pack()
        def close_window():
            if goal_name.get() and goal_name.get() != self.goal.name:
                self.goal.name = goal_name.get()
                self.need_saving = True
                self.refresh_all()
            top.destroy()

        top.bind('<Return>', lambda _: close_window())
        top.bind('<Escape>', lambda _: top.destroy())
        Button(top, text="Ok", command=close_window).pack()

    def close_window(self) -> None:
        new_description = self.description.get("1.0", tkinter.END)
        new_description = new_description.rstrip()
        self.need_saving = self.need_saving or self.goal.description != new_description
        self.goal.description = new_description
        if self.need_saving:
            self.client.need_saving = True
        if self.need_refresh:
            self.refresh_all()    
        self.destroy()

    def __init__(self, 
                 master: tkinter.Misc, 
                 client: ClientV2, 
                 goal_id: int, 
                 goals_window: GoalsWindow,
                 refresh_all: Callable) -> None:
        super().__init__(master)
        self.need_refresh = False
        self.need_saving = False
        self.client = client
        self.goal = self.client.fetch_goal(goal_id)
        self.is_daily = self.goal.daily.date() == datetime.now().date()
        self.is_backlogged = self.goal.backlogged
        self.goals_window = goals_window
        self.refresh_all = refresh_all

        self.geometry(
            f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}+{self.master.winfo_rootx()}+{self.master.winfo_rooty()}")
        self.title("Goal Details")

        Message(self, 
                text=self.goal.name, 
                font=self.GOAL_NAME_FONT,
                anchor='w',
                justify=tkinter.LEFT,
                width=self.GOAL_NAME_CHAR_ACROSS).pack(padx=3, pady=3)
        self.description = ScrolledText(self, wrap=tkinter.WORD, width=40, height=6)
        self.description.pack()
        self.description.insert(tkinter.INSERT, self.goal.description)
        self.description.focus()
        
        self.custom_buttons_frame = Frame(self)
        self.custom_buttons_frame.pack(padx=10, pady=3)

        self.make_daily_button = Button(
            self.custom_buttons_frame, 
            text="Schedule", 
            command=self.toggle_daily)
        self.make_daily_button.pack(padx=1, side=tkinter.LEFT)
        self.backlog_button = Button(
            self.custom_buttons_frame,
            text="Backlog",
            command=self.toggle_backlog)
        self.backlog_button.pack(padx=1, side=tkinter.LEFT)
        self.unparent_button = Button(
            self.custom_buttons_frame, 
            text="Unparent", 
            command=self.unparent)
        self.unparent_button.pack(padx=1, side=tkinter.LEFT)
        self.remove_from_daily_button = Button(
            self.custom_buttons_frame,
            text="Unschedule",
            command=self.toggle_daily)
        self.remove_from_daily_button.pack(padx=1, side=tkinter.LEFT)
        self.remove_from_backlog_button = Button(
            self.custom_buttons_frame,
            text="Remove from Backlog",
            command=self.toggle_backlog)
        self.remove_from_backlog_button.pack(padx=1, side=tkinter.LEFT)
        self.rename_button = Button(
            self.custom_buttons_frame,
            text="Rename",
            command=self.rename_goal)
        self.rename_button.pack(padx=1, side=tkinter.LEFT)
        
        self.bind('<Escape>', lambda _: self.close_window())
        button = Button(self, 
                        text="Ok", 
                        command=self.close_window)
        button.pack(pady=5, side=tkinter.TOP)

class GoalWidget(Frame):
    WIDTH = 500
    GOALS_CANVAS_WIDTH = int(WIDTH * 4/5)
    GOAL_ENTRY_HEIGHT = 25
    GOAL_ENTRY_FONT = 'Helvetica 9'

    def __init__(self, 
                 parent_widget: Any, 
                 goals_window: GoalsWindow, 
                 goal: Goal, 
                 client: ClientV2, 
                 x_val: int, 
                 y_val: int,
                 details_window_cls: GoalDetailsWindow = GoalDetailsWindow,
                 disable_dragging: bool = False):
        super().__init__(parent_widget)
        self.client = client
        self.goals_window = goals_window
        self.x_val = x_val
        self.y_val = y_val
        self.goal = goal
        self.disable_dragging = disable_dragging
        self.details_window_cls = details_window_cls
        self._drag_start = datetime.now()

        self.construct_row()

    def construct_row(self):
        x_padding = 2
        y_padding = 0

        label_frame = Frame(self, width=self.GOALS_CANVAS_WIDTH-80, height=self.GOAL_ENTRY_HEIGHT)
        label_frame.pack(side=tkinter.LEFT)
        label_frame.pack_propagate(False) # Stops child widgets of label_frame from resizing it
        
        def toggle_collapse():
            if not self.goal.children:
                return
            self.goal.collapsed = not self.goal.collapsed
            self.client.need_saving = True
            self.goals_window.refresh_goals_canvas()
        
        collapse_button = Button(label_frame, 
                                 text='>' if self.goal.children else '', 
                                 command=toggle_collapse,
                                 width=1)
        collapse_button.pack(side=tkinter.LEFT, padx=(x_padding+self.x_val, 0))

        label_window = Label(label_frame, 
                             text=self.goal.name, 
                             font=self.GOAL_ENTRY_FONT, 
                             anchor='w', 
                             name=str(self.goal.id))
        label_window.pack(side=tkinter.LEFT)

        label_window.bind('<Button-1>', self.on_lclick)
        if not self.disable_dragging:
            label_window.bind('<B1-Motion>', self.on_drag_motion)
            label_window.bind('<ButtonRelease-1>', self.on_drag_end)
        DELETE_BUTTON_OFFSET = 40
        CHECK_BOX_RIGHT_OFFSET = DELETE_BUTTON_OFFSET + self.GOAL_ENTRY_HEIGHT
        self._tkinter_state = tkinter.BooleanVar(value=self.goal.state)

        self.delete_button = Button(self,
                               text='delete',
                               command=lambda goal_id=self.goal.id: self.goals_window.delete_goal(goal_id))
        self.delete_button.pack(side=tkinter.RIGHT)
        self.check_button = Checkbutton(self,
                                   variable=self._tkinter_state,
                                   onvalue=True,
                                   offvalue=False,
                                   command=lambda goal_id=self.goal.id: self.toggle_goal_state(goal_id))
        self.check_button.pack(side=tkinter.RIGHT)
    
    def toggle_goal_state(self, goal_id: int):
        if self._tkinter_state.get():
            playsound('data/fx1.wav', block=False)
        self.client.toggle_goal_state(goal_id)
        self.goals_window.refresh_all_goal_windows()

    def is_double_click(self) -> bool:
        return datetime.now() - self._drag_start < timedelta(milliseconds=200)

    def on_lclick(self, event: tkinter.Event):
        if self.is_double_click():
            self.details_window = self.details_window_cls(self, 
                                                          self.client, 
                                                          self.goal.id, 
                                                          self.goals_window,
                                                          self.goals_window.refresh_all_goal_windows)
        elif not self.disable_dragging:
            self.lift()
            self._drag_start_x, self._drag_start_y = event.x, event.y
        self._drag_start = datetime.now()
    
    def on_drag_motion(self, event: tkinter.Event):
        if self.is_double_click():
            return
        x = self.winfo_x() - self._drag_start_x + event.x
        y = self.winfo_y() - self._drag_start_y + event.y
        self.place(x=x, y=y)

    def on_drag_end(self, event: tkinter.Event):
        if self.is_double_click():
            return
        self.place_forget()
        goal_id = self.master.winfo_containing(*self.master.winfo_pointerxy()).winfo_name()
        # check if goal_id is actually an int
        try:
            goal_id = int(goal_id)
        except ValueError:
            self.goals_window.refresh_goals_canvas()
            return
        
        self.goals_window.setup_parent(self.goal.id, goal_id)