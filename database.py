import sys
import sqlite3
import os
from datetime import datetime
import uuid
import csv
import calendar

# --- Database Functions ---

def get_data_file_path(filename):
    """ 
    Get the absolute path to the data file, works for both script and executable.
    It resolves the path relative to the project root, not the current file's directory.
    """
    # Go up two directories from 'app/core' to get to the project root
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, filename)

DATABASE_FILE = get_data_file_path("task_manager.db")

def connect_db():
    """Establishes a connection to the database."""
    conn = sqlite3.connect(DATABASE_FILE, timeout=10) 
    conn.row_factory = sqlite3.Row # Allows accessing columns by name
    return conn

def create_tables():
    """Creates the necessary tables if they don't already exist."""
    conn = connect_db()
    cursor = conn.cursor()
    
    # --- Enable Foreign Key support ---
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # --- Tasks Table (MODIFIED) ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY, description TEXT NOT NULL, status TEXT NOT NULL,
        date_added TEXT NOT NULL, deadline TEXT, priority TEXT, category TEXT,
        notes TEXT, date_completed TEXT, schedule_event_id TEXT,
        created_by_automation_id TEXT,
        show_mode TEXT DEFAULT 'auto' NOT NULL,  /* 'auto' or 'always_pending' */
        parent_task_id TEXT, /* <-- NEW COLUMN FOR SUB-TASKS */
        FOREIGN KEY (parent_task_id) REFERENCES tasks (id) ON DELETE CASCADE
    )""")
    # --- Daily Notes Table ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daily_notes (date TEXT PRIMARY KEY, content TEXT NOT NULL)
    """)
    # --- Schedule Events Table (For Daily Schedule View) ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS schedule_events (
        id TEXT PRIMARY KEY, date TEXT NOT NULL, start_time TEXT NOT NULL,
        end_time TEXT NOT NULL, title TEXT NOT NULL, color TEXT
    )""")

    # --- App State Table (For Automation logic) ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS app_state (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""")
    cursor.execute("INSERT OR IGNORE INTO app_state (key, value) VALUES ('last_automation_run_date', '1970-01-01')")
    cursor.execute("INSERT OR IGNORE INTO app_state (key, value) VALUES ('theme', 'system')")
    cursor.execute("INSERT OR IGNORE INTO app_state (key, value) VALUES ('pomodoro_work_min', '25')")
    cursor.execute("INSERT OR IGNORE INTO app_state (key, value) VALUES ('pomodoro_short_break_min', '5')")
    cursor.execute("INSERT OR IGNORE INTO app_state (key, value) VALUES ('pomodoro_long_break_min', '15')")
    cursor.execute("INSERT OR IGNORE INTO app_state (key, value) VALUES ('pomodoro_sessions', '4')")
    cursor.execute("INSERT OR IGNORE INTO app_state (key, value) VALUES ('user_name', '')")

    # --- Calendar Events Table (For Monthly Rota/Events) ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS calendar_events (
        id TEXT PRIMARY KEY,
        date TEXT NOT NULL,
        title TEXT NOT NULL,
        start_time TEXT,
        end_time TEXT
    )""")

    # --- Automations Table (The Triggers) ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS automations (
        id TEXT PRIMARY KEY,
        trigger_title TEXT NOT NULL UNIQUE,
        rule_name TEXT
    )""")

    # --- Automation Actions Table (The Actions) ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS automation_actions (
        id TEXT PRIMARY KEY,
        automation_id TEXT NOT NULL,
        action_type TEXT NOT NULL, 
        param1 TEXT, 
        param2 TEXT, 
        param3 TEXT,
        FOREIGN KEY (automation_id) REFERENCES automations (id) ON DELETE CASCADE
    )""")
    
    # --- Task Show Dates Table (for recurring tasks) ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS task_show_dates (
        task_id TEXT NOT NULL,
        show_date TEXT NOT NULL,
        FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE,
        PRIMARY KEY (task_id, show_date)
    )""")
    
    # --- Task Completion Log Table (for recurring tasks) ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS task_completion_log (
        task_id TEXT NOT NULL,
        completion_date TEXT NOT NULL,
        FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE,
        PRIMARY KEY (task_id, completion_date)
    )""")
    
    # --- Knowledge Base Table ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS knowledge_base (
        id TEXT PRIMARY KEY,
        parent_id TEXT,
        title TEXT NOT NULL,
        content TEXT,
        FOREIGN KEY (parent_id) REFERENCES knowledge_base (id) ON DELETE CASCADE
    )""")

    
    conn.commit()
    conn.close()

# ========== Task Functions ==========
def add_task(task_data):
    """ Adds a new task, returns the new task's ID. (MODIFIED) """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO tasks (id, description, status, date_added, deadline, priority, category, notes, created_by_automation_id, show_mode, parent_task_id) 
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
                   (task_data['id'], task_data['description'], 'pending', task_data['date_added'], 
                    task_data['deadline'], task_data['priority'], task_data['category'], 
                    task_data['notes'], task_data.get('created_by_automation_id'),
                    task_data.get('show_mode', 'auto'), task_data.get('parent_task_id'))) # <-- ADDED
    conn.commit()
    conn.close()
    return task_data['id'] 

def get_tasks(status="pending"):
    """ Gets all TOP-LEVEL pending tasks. (MODIFIED) """
    conn = connect_db()
    cursor = conn.cursor()
    # This now *only* gets parent tasks (or standalone tasks)
    cursor.execute("SELECT * FROM tasks WHERE status = ? AND parent_task_id IS NULL ORDER BY date_added", (status,))
    tasks = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tasks
    
def get_all_tasks():
    """ Fetches all tasks regardless of status. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks ORDER BY date_added")
    tasks = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tasks

# --- NEW FUNCTION for sub-tasks ---
def get_sub_tasks(parent_task_id, status="all"):
    """ Gets all sub-tasks for a given parent task_id. """
    conn = connect_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM tasks WHERE parent_task_id = ? ORDER BY date_added"
    params = [parent_task_id]
    
    if status != "all":
        query = "SELECT * FROM tasks WHERE parent_task_id = ? AND status = ? ORDER BY date_added"
        params.append(status)
        
    cursor.execute(query, tuple(params))
    tasks = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tasks

# --- NEW FUNCTION for sub-tasks ---
def get_pending_subtask_count(task_id):
    """ Returns the number of pending sub-tasks for a given task. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE parent_task_id = ? AND status = 'pending'", (task_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0
    
# --- NEW FUNCTION for Today Dashboard fix ---
def get_task_by_id(task_id):
    """ Gets a single task by its ID. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# --- NEW FUNCTION for Schedule Dialog fix ---
def get_all_pending_tasks():
    """ Gets all pending tasks, including parents and sub-tasks. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE status = 'pending' ORDER BY date_added",)
    tasks = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tasks

def get_task_by_automation_id(automation_id):
    """ Finds the first task that was created by a specific automation rule. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE created_by_automation_id = ? AND status = 'pending' LIMIT 1", (automation_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_completed_tasks_for_date(date_str):
    """ Gets all tasks completed on a specific date. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE date_completed = ? ORDER BY priority", (date_str,))
    tasks = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tasks


def get_tasks_for_month(year, month):
    start_date = f"{year}-{month:02d}-01"
    last_day = calendar.monthrange(year, month)[1]
    end_date = f"{year}-{month:02d}-{last_day:02d}"
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE deadline IS NOT NULL AND deadline BETWEEN ? AND ? ORDER BY deadline", (start_date, end_date))
    tasks = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tasks

def update_task_status(task_id, new_status, date_completed=None):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = ?, date_completed = ? WHERE id = ?", (new_status, date_completed, task_id))
    conn.commit()
    conn.close()

def update_task_details(task_id, description, priority, category, deadline, notes, show_mode):
    conn = connect_db() 
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE tasks 
    SET description = ?, priority = ?, category = ?, deadline = ?, notes = ?, show_mode = ?
    WHERE id = ?
    """, (description, priority, category, deadline, notes, show_mode, task_id))
    conn.commit()
    conn.close()

def delete_task(task_id):
    conn = connect_db()
    conn.execute("PRAGMA foreign_keys = ON;") # Ensure cascade delete is on
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

def link_task_to_event(task_id, event_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET schedule_event_id = ? WHERE id = ?", (event_id, task_id))
    conn.commit()
    conn.close()

def unlink_task_from_event(task_id, event_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET schedule_event_id = NULL WHERE id = ? AND schedule_event_id = ?", (task_id, event_id))
    conn.commit()
    conn.close()
    
def unlink_all_tasks_from_event(event_id, db_conn=None):
    """ Sets schedule_event_id to NULL for all tasks linked to the given event_id. """
    manage_connection = db_conn is None
    conn = db_conn if db_conn else connect_db()
    
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE tasks SET schedule_event_id = NULL WHERE schedule_event_id = ?", (event_id,))
        if manage_connection:
            conn.commit()
    except Exception as e:
        print(f"Error unlinking tasks: {e}")
        raise 
    finally:
        if manage_connection:
            conn.close()


def get_tasks_for_event(event_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE schedule_event_id = ?", (event_id,))
    tasks = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tasks

def get_tasks_by_deadline(date_str):
    """ Gets all pending tasks with a deadline of today. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE deadline = ? AND status = 'pending'", (date_str,))
    tasks = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tasks

def get_tasks_by_show_date(date_str):
    """ Gets all tasks scheduled to 'show on' today. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.* FROM tasks t
        JOIN task_show_dates tsd ON t.id = tsd.task_id
        WHERE tsd.show_date = ?
    """, (date_str,))
    tasks = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tasks

def get_tasks_always_pending():
    """ Gets all tasks set to 'always_pending' that are not completed. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE show_mode = 'always_pending' AND status = 'pending'")
    tasks = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tasks

def is_task_logged_complete(task_id, date_str):
    """ Checks if a recurring task was logged as complete for today. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM task_completion_log WHERE task_id = ? AND completion_date = ?", (task_id, date_str))
    row = cursor.fetchone()
    conn.close()
    return row is not None

# --- Task Show Date Functions ---
def add_task_show_date(task_id, show_date, db_conn=None):
    """ Links a task to a specific date to show on the 'Today' view. """
    manage_connection = db_conn is None
    conn = db_conn if db_conn else connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO task_show_dates (task_id, show_date) VALUES (?, ?)", (task_id, show_date))
        if manage_connection:
            conn.commit()
    except Exception as e:
         print(f"Error adding task show date: {e}")
         if manage_connection: conn.rollback()
         raise
    finally:
        if manage_connection:
            conn.close()

def get_show_dates_for_task(task_id):
    """ Gets all 'show_date' strings for a given task_id. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT show_date FROM task_show_dates WHERE task_id = ? ORDER BY show_date", (task_id,))
    dates = [row['show_date'] for row in cursor.fetchall()]
    conn.close()
    return dates

def remove_task_show_date(task_id, show_date):
    """ Removes a specific 'show_date' link from a task. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM task_show_dates WHERE task_id = ? AND show_date = ?", (task_id, show_date))
    conn.commit()
    conn.close()


# --- Task Completion Log Functions ---
def log_task_completion(task_id, completion_date, db_conn=None):
    """ Logs that a task was completed on a specific date. """
    manage_connection = db_conn is None
    conn = db_conn if db_conn else connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("REPLACE INTO task_completion_log (task_id, completion_date) VALUES (?, ?)", (task_id, completion_date))
        if manage_connection:
            conn.commit()
    except Exception as e:
         print(f"Error logging task completion: {e}")
         if manage_connection: conn.rollback()
         raise
    finally:
        if manage_connection:
            conn.close()

def remove_task_completion_log(task_id, completion_date, db_conn=None):
    """ Removes a completion log entry (if user unchecks a daily task). """
    manage_connection = db_conn is None
    conn = db_conn if db_conn else connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM task_completion_log WHERE task_id = ? AND completion_date = ?", (task_id, completion_date))
        if manage_connection:
            conn.commit()
    except Exception as e:
         print(f"Error removing task completion log: {e}")
         if manage_connection: conn.rollback()
         raise
    finally:
        if manage_connection:
            conn.close()

# ========== Daily Notes Functions ==========
def save_daily_note(date, content):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO daily_notes (date, content) VALUES (?, ?)", (date, content))
    conn.commit()
    conn.close()

def get_daily_note(date):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM daily_notes WHERE date = ?", (date,))
    row = cursor.fetchone()
    conn.close()
    return row['content'] if row else None

def get_all_daily_notes():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM daily_notes ORDER BY date DESC")
    notes = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return notes

# ========== Schedule Event Functions ==========
def add_schedule_event(event_data):
    """ Adds a new schedule event, returns the new event's ID. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO schedule_events (id, date, start_time, end_time, title, color) VALUES (?, ?, ?, ?, ?, ?)",
                   (event_data['id'], event_data['date'], event_data['start_time'], event_data['end_time'], event_data['title'], event_data.get('color')))
    conn.commit()
    conn.close()
    return event_data['id']

def get_schedule_events_for_date(date):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM schedule_events WHERE date = ? ORDER BY start_time", (date,))
    events = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return events

def get_schedule_event_by_id(event_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM schedule_events WHERE id = ?", (event_id,))
    row = cursor.fetchone()
    event = dict(row) if row else None
    conn.close()
    return event

def update_schedule_event(event_id, event_data):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE schedule_events SET date = ?, start_time = ?, end_time = ?, title = ?, color = ? WHERE id = ?",
                   (event_data['date'], event_data['start_time'], event_data['end_time'], event_data['title'], event_data.get('color'), event_id))
    conn.commit()
    conn.close()

def delete_schedule_event(event_id):
    """Deletes an event and unlinks associated tasks within a single transaction."""
    conn = connect_db()
    conn.execute("PRAGMA foreign_keys = ON;") # Ensure cascade delete is on
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM schedule_events WHERE id = ?", (event_id,))
        unlink_all_tasks_from_event(event_id, db_conn=conn) 
        conn.commit()
    except Exception as e:
        print(f"Error deleting event, rolling back: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
        
# ========== App State Functions ==========

def get_app_state(key):
    """ Gets a value from the app_state table. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM app_state WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else None

def set_app_state(key, value):
    """ Sets a value in the app_state table. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO app_state (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

# ========== Calendar Event (Rota) Functions ==========

def add_calendar_event(event_data):
    """ Adds a new event to the monthly calendar_events table. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO calendar_events (id, date, title, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
                   (event_data['id'], event_data['date'], event_data['title'], 
                    event_data.get('start_time'), event_data.get('end_time')))
    conn.commit()
    conn.close()

def get_calendar_events_for_date(date):
    """ Fetches all calendar_events for a specific date. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM calendar_events WHERE date = ? ORDER BY start_time, title", (date,))
    events = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return events

def get_calendar_events_for_month(year, month):
    """ Fetches all calendar_events within a given month and year. """
    start_date = f"{year}-{month:02d}-01"
    last_day = calendar.monthrange(year, month)[1]
    end_date = f"{year}-{month:02d}-{last_day:02d}"
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM calendar_events WHERE date BETWEEN ? AND ? ORDER BY date, start_time, title", (start_date, end_date))
    events = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return events

def update_calendar_event(event_id, new_title, start_time, end_time):
    """ Updates the title and times of a specific calendar_event. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE calendar_events SET title = ?, start_time = ?, end_time = ? WHERE id = ?", 
                   (new_title, start_time, end_time, event_id))
    conn.commit()
    conn.close()

def delete_calendar_event(event_id):
    """ Deletes a specific event from the calendar_events table. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()

# ========== Automation Functions ==========

def save_automation_rule(automation_id, rule_name, trigger_title, actions_list):
    """ Saves (inserts or updates) a rule and its actions in a transaction. """
    conn = connect_db()
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    try:
        if automation_id is None:
            automation_id = str(uuid.uuid4())
            cursor.execute("INSERT INTO automations (id, rule_name, trigger_title) VALUES (?, ?, ?)",
                           (automation_id, rule_name, trigger_title))
        else:
            cursor.execute("UPDATE automations SET rule_name = ?, trigger_title = ? WHERE id = ?",
                           (rule_name, trigger_title, automation_id))
            cursor.execute("DELETE FROM automation_actions WHERE automation_id = ?", (automation_id,))
        
        for action in actions_list:
            action['automation_id'] = automation_id
            if 'id' not in action:
                 action['id'] = str(uuid.uuid4())
            add_automation_action(action, db_conn=conn)
        
        conn.commit()
    except Exception as e:
        print(f"Error saving automation rule: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def get_automations():
    """ Fetches all automation rules. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM automations ORDER BY rule_name")
    rules = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rules
    
def get_automation_rule_details(automation_id):
    """ Fetches the main rule and all its actions. """
    rule = None
    actions = []
    
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM automations WHERE id = ?", (automation_id,))
    row = cursor.fetchone()
    if row:
        rule = dict(row)
        cursor.execute("SELECT * FROM automation_actions WHERE automation_id = ?", (automation_id,))
        actions = [dict(row) for row in cursor.fetchall()]
        rule['actions'] = actions
    
    conn.close()
    return rule


def delete_automation_rule(automation_id):
    """ Deletes an automation rule and all its associated actions. """
    conn = connect_db()
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM automations WHERE id = ?", (automation_id,))
        conn.commit()
    except Exception as e:
        print(f"Error deleting automation: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def add_automation_action(action_data, db_conn=None):
    """ Adds an action to a specific automation rule. Can use existing connection. """
    manage_connection = db_conn is None
    conn = db_conn if db_conn else connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO automation_actions (id, automation_id, action_type, param1, param2, param3)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (action_data['id'], action_data['automation_id'], action_data['action_type'],
              action_data['param1'], action_data.get('param2'), action_data.get('param3')))
        if manage_connection:
            conn.commit()
    except Exception as e:
         print(f"Error adding action: {e}")
         if manage_connection: conn.rollback()
         raise
    finally:
        if manage_connection:
            conn.close()

def get_actions_for_automation(automation_id):
    """ Fetches all actions for a specific automation rule. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM automation_actions WHERE automation_id = ?", (automation_id,))
    actions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return actions
    
def get_automation_by_trigger(trigger_title):
    """ Fetches an automation rule by its trigger title. """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM automations WHERE trigger_title = ?", (trigger_title,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None
    
# ========== Knowledge Base Functions ==========

def add_kb_topic(title, parent_id=None):
    """Adds a new topic to the knowledge base."""
    conn = connect_db()
    cursor = conn.cursor()
    new_id = str(uuid.uuid4())
    cursor.execute("INSERT INTO knowledge_base (id, parent_id, title, content) VALUES (?, ?, ?, ?)",
                   (new_id, parent_id, title, ""))
    conn.commit()
    conn.close()
    return new_id

def get_kb_topics_by_parent(parent_id=None):
    """Fetches all topics under a given parent (or root topics if None)."""
    conn = connect_db()
    cursor = conn.cursor()
    if parent_id is None:
        cursor.execute("SELECT * FROM knowledge_base WHERE parent_id IS NULL ORDER BY title")
    else:
        cursor.execute("SELECT * FROM knowledge_base WHERE parent_id = ? ORDER BY title", (parent_id,))
    topics = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return topics

def update_kb_topic_note(topic_id, content):
    """Saves the note content for a specific topic."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE knowledge_base SET content = ? WHERE id = ?", (content, topic_id))
    conn.commit()
    conn.close()
    
def get_kb_topic_note(topic_id):
    """Retrieves the note content for a specific topic."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM knowledge_base WHERE id = ?", (topic_id,))
    row = cursor.fetchone()
    conn.close()
    return row['content'] if row else ""

def delete_kb_topic(topic_id):
    """Deletes a topic and all its children (thanks to CASCADE)."""
    conn = connect_db()
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM knowledge_base WHERE id = ?", (topic_id,))
    conn.commit()
    conn.close()
