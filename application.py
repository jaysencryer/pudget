"""
Financial Tracker.  Code name Pudget
application.py configures the app, opens up an sqlite3 database (and creates it if it doesn't exist)
"""

import os
from tempfile import mkdtemp
from flask import Flask, session
from flask_session.__init__ import Session
import sqlite3

app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)



db = sqlite3.connect("pudget.db", check_same_thread=False)

# users
db.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    name TEXT NOT NULL,
    username TEXT NOT NULL UNIQUE,
    hash TEXT NOT NULL);''')

# accounts
db.execute('''CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    balance REAL NOT NULL,
    user_id INTEGER NOT NULL);''')

# outgoings
db.execute('''CREATE TABLE IF NOT EXISTS outgoings (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    amount REAL NOT NULL,
    due DATE NOT NULL,
    freq TEXT NOT NULL,
    acc_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL)''')

# income
db.execute('''CREATE TABLE IF NOT EXISTS income (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT,
    amount REAL NOT NULL,
    payday DATE NOT NULL,
    freq TEXT NOT NULL,
    acc_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL)''')

db.commit()

# global variables
FREQUENCY = [
                {"value":"monthly-date-", "text":"Monthly (date e.g 5th)"},
                {"value":"monthly-first-", "text":"Monthly (first specific day)"},
                {"value":"monthly-last-", "text":"Monthly (last specific day)"},
                {"value":"monthly-lastday-", "text":"Monthly (last weekday)"},
                {"value":"semimonthly-115", "text":"Semi-Monthly (1st & 15th)"},
                {"value":"semimonthly-15last", "text":"Semi-Monthly (15th & last)"},
                {"value":"biweekly", "text":"Bi-Weekly (every two weeks)"},
                {"value":"weekly", "text":"Weekly"},
                {"value":"quarterly", "text":"Quarterly"}
            ]

CATEGORY = [
            {"value":"utility", "text":"Utility"},
            {"value":"housing", "text":"Housing"},
            {"value":"transport", "text":"Transportation"},
            {"value":"food", "text":"Groceries & Household staples"},
            {"value":"education", "text":"Education"},
            {"value":"childcare", "text":"Child care"},
            {"value":"repayment", "text":"Loan/Credit Card payment"},
            {"value":"entertainment", "text":"Entertainment"},
            {"value":"other", "text":"Other"},
        ]


@app.context_processor
def utility_processor():
    def format_money(amount,currency='$'):
        return '{1}{0:.2f}'.format(amount,currency)
    return dict(format_money=format_money)


import views
