import io
import sqlite3

def connectDataBase(db = "nostraFinance.db"):
        # Connects to DB returns dicts
        con = sqlite3.connect(db)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        
        return con