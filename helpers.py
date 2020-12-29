from functools import wraps
from flask import session, redirect
import sqlite3
from datetime import date
import datetime
import calendar
from application import db

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def sql_parse(cursor):
    """
    Parses a SELECT statment from sqlite3 and returns a list conataining a dictionary for each row.
    """
    result = []

    data = cursor.fetchall()

    for rows in data:
        c = 0
        res_dic = {}

        for columns in rows:
            res_dic[cursor.description[c][0]] = columns
            c += 1

        result.append(res_dic)
    return result

def get_next_payday(payday, freq):
    """
    Takes the payday entered when income added, and computes the next pay date
    """
    y, m, d = (int(i) for i in payday.split('-'))
    pay_date = datetime.date(y, m, d)

    full_freq = freq.split("-")

    # Monthly
    if full_freq[0] == "monthly":

        # increment month, check for rollover to January
        m +=1
        if m > 12:
            m = 1
            y += 1

        # Monthly pay has four options

        # monthly-date (pay is always on a specific date e.g. 5th of month)
        if full_freq[1] == "date":
            d = int(full_freq[2])

        # monthly-first (pay is always on first occurance of specified day in a month e.g. first fri)
        if full_freq[1] == "first":
            weekday = int(full_freq[2])
            d = findfirst(weekday, m, y)

        # monthly-last (pay is always on last occurance of specified day e.g. last fri)
        if full_freq[1] == "last":
            weekday = int(full_freq[2])
            d = findlast(weekday, m, y)

        # monthly-lastday (pay is always on the last weekday of the month)
        if full_freq[1] == "lastday":
            d = calendar.monthrange(y, m)[1]
            if datetime.date(y,m,d).weekday() > 4:
                diffy = datetime.date(y,m,d).weekday() - 4
                d -= diffy

        next_date = datetime.date(y,m,d)

    # Bi-Weekly
    if full_freq[0]  == "biweekly":
        next_date = pay_date + datetime.timedelta(weeks=2)

    # Semi Monthly 1st and 15th
    if full_freq[0] == "semimonthly":
        if full_freq[1] == "115":
            # determine whether current payday is 1st or 15th

            # if the 1st fell on a weekend, the pay date day could be the last day of the previous month or the 2nd
            if pay_date.day <= 2:
                # set date to 15th
                d = 15
            elif pay_date.day >= 28:
                # pay day was end of the previous month
                # set date to 15th next month
                m += 1
                d = 15
            else:
                # return the 1st of the following month
                m += 1
                d = 1
        elif full_freq[1] == "15last":
            # Semi Monthly 15th and last day
            # determine whether the paydate is the 15th or last

            if pay_date.day >= 14 and pay_date.day <= 16:
                d = calendar.monthrange(y, m)[1]
            else:
                m += 1
                d = 15

        if m > 12:
            # new month fell into a new year
            m = 1
            y += 1

        next_date = datetime.date(y, m, d)

    # Weekly
    if full_freq[0] == "weekly":
        next_date = pay_date + datetime.timedelta(weeks=1)

    # quarterly
    if full_freq[0] == "quarterly":
        m += 3
        if m > 12:
            m = m - 12
            y += 1
        next_date = datetime.date(y,m,d)

    if next_date <= date.today():
        # the date entered was ages ago - let's get the next date!
        next_date = get_next_payday(next_date.strftime("%Y-%m-%d"), freq)

    return next_date

def make_datetime(date_string):
    """ Converts a date string in format YYYY-mm-dd to a datetime date """
    y, m, d = (int(i) for i in date_string.split('-'))
    return datetime.date(y, m, d)



def findfirst( weekday, month, year):
    """
    Finds the first occurance of day (0-6) in the specified month of the specified year.
    Returns day of month
    """
    search_date = datetime.date(year, month, 1)
    for i in range(7):
        if search_date.weekday() == weekday:
            return search_date.day
        else:
            search_date += datetime.timedelta(days=1)



def findlast( weekday, month, year):
    """
    Finds the last occurance of day (0-6) in the specified month of the specified year
    Returns day of month
    """
    last_day = calendar.monthrange(year, month)[1]
    search_date = datetime.date(year, month, last_day)
    for i in range(last_day, last_day - 7, -1):
        if search_date.weekday() == weekday:
            return search_date.day
        else:
            search_date -= datetime.timedelta(days=1)

def wknd_adjust(date):
    """
    Adjust a date to a weekday.
    Friday if date falls on Saturday, Monday if date falls on Sunday
    """
    if date.weekday() == 5:
            # Saturday! set date to Friday
            date -= datetime.timedelta(days=1)
    elif date.weekday() == 6:
            # Sunday! set date to Monday
            date += datetime.timedelta(days=1)

    return date


def get_primary_income(user_id):
    # get users primary account
    cur = db.execute("SELECT id, name, balance FROM accounts WHERE user_id = :user_id AND category='Primary'", {"user_id": user_id})
    accounts = sql_parse(cur)[0]

    # get biggest monthly income
    cur = db.execute('''SELECT id, amount FROM income WHERE user_id = :user_id AND freq LIKE 'monthly%' AND amount=
        (SELECT MAX(amount) FROM income WHERE freq LIKE 'monthly%' AND acc_id = :pri_acc)''', {"user_id":user_id, "pri_acc":accounts["id"]})
    big_monthly = sql_parse(cur)

    if big_monthly:
        big_mon_money = float(big_monthly[0]["amount"])
    else:
        big_mon_money = 0

    # get biggest bi-weekly income
    cur = db.execute('''SELECT id, amount FROM income WHERE user_id = :user_id AND freq='biweekly' AND amount=
        (SELECT MAX(amount) FROM income WHERE freq='biweekly' AND acc_id= :pri_acc)''',
        {"user_id":user_id, "pri_acc":accounts["id"]})
    big_biweek = sql_parse(cur)

    if big_biweek:
        # get amount per month
        big_bi_money = (float(big_biweek[0]["amount"]) * 26) / 12
    else:
        big_bi_money = 0

    # get biggest semi-monthly income
    cur = db.execute('''SELECT id, amount FROM income WHERE user_id = :user_id AND freq LIKE 'semimonthly%' AND amount=
        (SELECT MAX(amount) FROM income WHERE freq LIKE 'semimonthly%' AND acc_id= :pri_acc)''',
        {"user_id":user_id, "pri_acc":accounts["id"]})
    big_semi = sql_parse(cur)

    if big_semi:
        # get amount per month
        big_semi_money = (float(big_semi[0]["amount"]) * 2)
    else:
        big_semi_money = 0

    if big_mon_money + big_semi_money + big_bi_money == 0:
        # looks like we have no primary account yet
        return ""

    # find which of these incomes pays the most per month
    if big_mon_money >= big_bi_money and big_mon_money >= big_semi_money:
        # monthly is the biggest
        in_id = big_monthly[0]["id"]
    elif big_bi_money >= big_semi_money:
        # biweekly is the biggest
        in_id = big_biweek[0]["id"]
    else:
        # semi-monthly is biggest
        in_id = big_semi[0]["id"]

    # return the income pays the most into the primary account
    cur = db.execute("SELECT name, amount, payday, freq FROM income WHERE id = :in_id AND user_id=:user_id",
        {"in_id":in_id, "user_id":user_id})

    prime_income = sql_parse(cur)

    return prime_income

def get_transactions(table, start_date, end_date, account, user_id):
    # which table are we accessing to set correct transaction date
    if table == "outgoings":
        t_date = "due"
        order = "ORDER by category DESC, amount DESC"
    elif table == "income":
        t_date = "payday"
        order = "ORDER by freq, amount DESC"

    sql_string = '''SELECT name, amount, category, {1}, id, freq FROM {0}
        WHERE acc_id = :acc_id AND user_id = :user_id
        AND {1} >= :start_date AND {1} < :end_date {2}'''.format(table, t_date, order)

    cur = db.execute(sql_string, {"acc_id": account["id"], "user_id": user_id,
        "start_date": start_date.strftime("%Y-%m-%d"), "end_date": end_date.strftime("%Y-%m-%d")})
    return sql_parse(cur)

def set_transaction(table, **fields):
    # SET fields
    if "amount" in fields:
        set_data = "amount = :amount"
    elif "t_date" in fields:
        if table == "income":
            set_data = "payday = :t_date"
        elif table == "outgoings":
            set_data = "due = :t_date"
    elif "freq" in fields:
        set_data = "freq = :freq"
    elif "balance" in fields:
        set_data = "balance = :balance"

    # WHERE fields
    if "t_id" in fields:
        where_data = "id = :t_id "
    elif "name" in fields:
        where_data = "name = :name "
    elif "user_id" in fields:
        where_data = "user_id = :user_id "
    elif "acc_id" in fields:
        where_data = "acc_id = :acc_id"

    sql_string = "UPDATE {0} SET {1} WHERE {2}".format(table, set_data, where_data)

    # print( sql_string, fields)

    db.execute(sql_string, fields)
    db.commit()


def get_total(table, start_date, end_date, account, user_id):
    if table == "outgoings":
        t_date = "due"
    elif table == "income":
        t_date = "payday"
    sql_string = "SELECT SUM(amount) FROM {0} WHERE acc_id = :acc_id AND user_id = :user_id AND {1} >= :start_date AND {1} < :end_date".format(table,t_date)
    cur = db.execute(sql_string, {"acc_id": account["id"], "user_id":user_id, "start_date": start_date.strftime("%Y-%m-%d"), "end_date": end_date.strftime("%Y-%m-%d")})
    tot = sql_parse(cur)[0]["SUM(amount)"]

    if not tot:
        tot = 0

    return tot
