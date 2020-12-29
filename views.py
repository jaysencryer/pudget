"""
Routes and for the flask application.
"""


from flask import render_template, redirect, request, session
from application import app, db, FREQUENCY, CATEGORY
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import login_required, sql_parse, get_next_payday, wknd_adjust, get_primary_income, make_datetime, get_transactions, get_total, set_transaction
import sqlite3

from datetime import date
from datetime import datetime as DateTime
import datetime
import calendar

@app.route("/", methods=["GET", "POST"])
@app.route("/home")
@login_required
def home():
    """
    Renders the index page.
    If user has not set-up an account or income they will be redirected to the /profile page
    """

    # set active page variable for navigation template
    active_page = {}
    active_page["home"] = "active"

    # Get user name
    cur = db.execute("SELECT name FROM users WHERE id = :user_id", {"user_id": session["user_id"]})
    name = sql_parse(cur)[0]["name"]

    # Get primary account info
    cur = db.execute("SELECT name,balance,id FROM accounts WHERE user_id = :user_id AND category = 'Primary'", {"user_id": session["user_id"]})
    pri_account = sql_parse(cur)

    if not pri_account:
        # First time login, redirect to set up profile
        return redirect("/profile")

    # we want the primary account as a dictionary
    pri_account = pri_account[0]

    # get primary income information - specifically the payday and frequency
    # this is the highest income from the users account
    pri_income = get_primary_income(session["user_id"])
    if not pri_income:
        # no primary income?  send to profile set up
        return redirect("/profile")


    # find out the last time the user logged in
    cur = db.execute("SELECT last_login FROM users WHERE id = :user_id", {"user_id":session["user_id"]})
    last_login = make_datetime(sql_parse(cur)[0]["last_login"])


    # Let's make sure all the income that should have come in since last login and today has
    income = get_transactions("income", last_login, date.today(), pri_account, session["user_id"])
    outgoings = get_transactions("outgoings", last_login, date.today(), pri_account, session["user_id"])


    if request.method == "GET" and (income or outgoings):
            # There has been income or outgoings that should have cleared since last login, process them
            return render_template('confirm_income.html', income=income, outgoings=outgoings, active_page=active_page)
    elif request.method == "POST":

        # income/outgoing since last login is confirmed - let's change the date on those incomes
        for pay in income:
            check_name = "pay{}".format(pay['id'])
            if request.form.get(check_name) == "confirmed":
                # user confirmed the income

                # advance the payday for that income
                next_payday = get_next_payday(pay["payday"], pay["freq"])
                set_transaction("income", t_id=pay["id"], t_date=next_payday.strftime("%Y-%m-%d"))

                # increase balance by the income amount
                pri_account["balance"] += pay["amount"]
                set_transaction("accounts",balance=pri_account["balance"], t_id=pri_account["id"])


        for out in outgoings:
            check_name = "out{}".format(out['id'])
            if request.form.get(check_name) == "confirmed":
                # user confirmed the outgoing
                next_payday = get_next_payday(out["due"], out["freq"])
                set_transaction("outgoings", t_id=out["id"], t_date=next_payday.strftime("%Y-%m-%d"))

                # decrease balance by the outgoing amount

                pri_account["balance"] -= out["amount"]

                set_transaction("accounts", balance=pri_account["balance"], t_id=pri_account["id"])

    # all things are set -now update last login date
    db.execute("UPDATE users SET last_login=:today WHERE id = :user_id", {"today": date.today().strftime("%Y-%m-%d"), "user_id":session["user_id"]})
    db.commit()


    #***************************************************#
    #                                                   #
    #   This section calculates the pay period          #
    #   and gathers income and outgoings still valid    #
    #                                                   #
    #***************************************************#

    # pay date of primary income
    pay_date = make_datetime(pri_income[0]["payday"])

    if date.today() < pay_date:
        # the payday is after today, therfore it IS the next payday
        next_payday = pay_date
    else:
        # we have passed the payday - so calculate the next payday
        next_payday = get_next_payday(pri_income[0]["payday"],pri_income[0]["freq"])

    # adjust for the raw date falling on a weekend
    next_payday = wknd_adjust(next_payday)

    # get total income and outgoings
    tot_income = get_total("income", last_login, next_payday, pri_account, session["user_id"])
    tot_out = get_total("outgoings", last_login, next_payday, pri_account, session["user_id"])

    # Calculate free (or fun) money
    free_money = pri_account["balance"] + tot_income - tot_out

    return render_template('index.html', year=DateTime.now().year, name=name, pri_account=pri_account, money_in = tot_income,
        money_out = tot_out, free_money=free_money, next_pay_date=next_payday, active_page = active_page )


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    active_page = {}
    active_page["register"] = "active"

    # based on CS50 pset8 finance solution

    # Forget any prior user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Check fields are not blank
        if not request.form.get("name") or not request.form.get("username") or not request.form.get("password") or not request.form.get("confirmation"):
            return render_template("register.html", error="All fields must be completed", active_page=active_page)

        # check username is unique
        username = request.form.get("username");
        cur = db.execute("SELECT * FROM users WHERE username = :username", {"username": username})
        rows = cur.fetchall()

        if len(rows) == 1:
            return render_template("register.html", error="Username already exists", active_page=active_page)
        else:
            # username does not exist let's add it but first...
            # Check password matches confirmation
            if request.form.get("password") != request.form.get("confirmation"):
                return render_template("register.html", error="Password and Confirmation do not match", active_page=active_page)
            # add username and hash of password to db
            name = request.form.get("name")
            hash = generate_password_hash(request.form.get("password"))
            db.execute("INSERT INTO users (name, username, hash) VALUES (:name, :username, :hash)",
            {"name": name, "username": username, "hash": hash})
            db.commit()
            return redirect("/login")
    else:
        # serve up the register form
        return render_template("register.html", active_page=active_page)

@app.route('/login', methods=["GET", "POST"])
def login():
    """Logs user in."""
    active_page = {}
    active_page["login"] = "active"

    if request.method == "POST":
        # Check fields are not blank
        if not request.form.get("username") or not request.form.get("password"):
            return render_template("login.html", error="All fields must be completed", active_page=active_page)
        username = request.form.get("username")

        cur = db.execute("SELECT * FROM users WHERE username = :username", {"username": username})
        rows = sql_parse(cur)

        print(rows, len(rows))

        if len(rows) == 0 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            # username not found, or password does not match
            return render_template("login.html", error="Invalid Username or Password.", active_page=active_page)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    else:
        # GET method used
        return render_template("login.html", active_page=active_page)

@app.route("/profile", methods=["GET", "POST"] )
@login_required
def profile():
    """Edit or configure a users financial profile"""

    # set active page for navigation
    active_page = {}
    active_page["profile"] = "active"

    """
    profile.html lists a users accounts/income and outgoings.
    If the user has none, it gives them the opportunity to add a primary account.
    """

    if request.method == "POST":

        # user has either Deleted an income or outgoing, or configured their initial account

        if "in_delete" in request.form or "out_delete" in request.form:
            if "in_delete" in request.form:

                # income deleted

                t_id = request.form["in_delete"].strip("in")    # which income id?
                table = "income"

            elif "out_delete" in request.form:

                # outgoing deleted

                t_id = request.form["out_delete"].strip("out")  # which outgoing?
                table = "outgoings"

            # delete the income/outgoing
            sql_string = "DELETE FROM {} WHERE id = :id".format(table)
            db.execute(sql_string, {"id":t_id})
            db.commit()

            return redirect("/profile")


        # a new account has been added

        name = request.form.get("name")
        balance = float(request.form.get("balance"))

        if not name or not balance:
            # missing information in the form
            return render_template("profile.html", error="You must complete entire form to configure an account", active_page=active_page)

        # add the account to the database
        db.execute("INSERT INTO accounts (name, balance, category, user_id) VALUES (:name, :balance, 'Primary', :user_id)",
            {"name": name, "balance": balance, "user_id": session["user_id"]})
        db.commit()

        return redirect("/profile")

    else:
        # GET method only used

        #
        # load up all incoming and outgoing and update the next transaction date based on todays date
        #
        cur = db.execute("SELECT name, balance FROM accounts WHERE category='Primary' AND user_id = :user_id", {"user_id": session["user_id"]})
        pri_account = sql_parse(cur)

        if not pri_account:
            # no account set up - feed profile.html the necessary info
            return render_template("profile.html", active_page=active_page, pri_account="")

        pri_account = pri_account[0]

        # first check we have a primary income
        pri_income = get_primary_income(session["user_id"])

        if not pri_income:
            # no income setup!
            return render_template("profile.html", active_page=active_page, pri_account = pri_account, income = "")

        cur = db.execute("SELECT name,amount,due,freq,id,category FROM outgoings WHERE user_id = :user_id ORDER BY category, amount DESC", {"user_id": session["user_id"]})
        outgoings = sql_parse(cur)

        for out in outgoings:
            # if we've passed the due date set the new due date
            if date.today() > make_datetime(out["due"]):
                next_duedate = get_next_payday(out["due"], out["freq"])
            else:
                next_duedate = make_datetime(out["due"])
            out["due"] = wknd_adjust(next_duedate)

        # get monthly outgoings
        cur = db.execute("SELECT SUM(amount) FROM outgoings WHERE user_id = :user_id AND freq LIKE 'monthly%'", {"user_id": session["user_id"]})
        monthly_total = sql_parse(cur)[0]["SUM(amount)"]
        if not monthly_total:
            monthly_total = 0

        # get bi-weekly outgoings
        cur = db.execute("SELECT SUM(amount) FROM outgoings WHERE user_id = :user_id AND freq = 'biweekly'",
            {"user_id": session["user_id"]})
        biweek_total = sql_parse(cur)[0]["SUM(amount)"]
        if not biweek_total:
            biweek_total = 0

        # get semi-monthly outgoings
        cur = db.execute("SELECT SUM(amount) FROM outgoings WHERE user_id = :user_id AND freq LIKE 'semimonthly%'",
            {"user_id": session["user_id"]})
        semi_total = sql_parse(cur)[0]["SUM(amount)"]
        if not semi_total:
            semi_total = 0


        # get any weekly outgoings
        cur = db.execute("SELECT SUM(amount) FROM outgoings WHERE user_id = :user_id AND freq = 'weekly'", {"user_id": session["user_id"]})
        weekly_total = sql_parse(cur)[0]["SUM(amount)"]
        if not weekly_total:
            weekly_total = 0

        # get quarterly outgoings
        cur = db.execute("SELECT SUM(amount) FROM outgoings WHERE user_id = :user_id AND freq = 'quarterly'", {"user_id": session["user_id"]})
        quarterly_total = sql_parse(cur)[0]["SUM(amount)"]
        if quarterly_total:
            monthly_total += quarterly_total / 3


        out_total = round(monthly_total + ((26 * biweek_total) / 12) + ( 2 * semi_total ) + ( 4 * weekly_total ),2)

        # get all income
        cur = db.execute("SELECT name,amount,payday,freq,id FROM income WHERE user_id = :user_id ORDER BY freq, amount DESC", {"user_id": session["user_id"]})
        income = sql_parse(cur)

        for inc in income:
            # adjust pay date if we've passed the pay date
            if date.today() > make_datetime(inc["payday"]):
                next_payday = get_next_payday(inc["payday"],inc["freq"])
            else:
                next_payday = make_datetime(inc["payday"])

            inc["payday"] = wknd_adjust(next_payday)

        # get monthly income
        cur = db.execute("SELECT SUM(amount) FROM income WHERE user_id = :user_id AND freq LIKE 'monthly%'", {"user_id": session["user_id"]})
        monthly_total = sql_parse(cur)[0]["SUM(amount)"]
        if not monthly_total:
            monthly_total = 0

        # get bi-weekly income
        cur = db.execute("SELECT SUM(amount) FROM income WHERE user_id = :user_id AND freq = 'biweekly'",
            {"user_id": session["user_id"]})
        biweek_total = sql_parse(cur)[0]["SUM(amount)"]
        if not biweek_total:
            biweek_total = 0

        # get semi-monthly income
        cur = db.execute("SELECT SUM(amount) FROM income WHERE user_id = :user_id AND freq LIKE 'semimonthly%'",
            {"user_id": session["user_id"]})
        semi_total = sql_parse(cur)[0]["SUM(amount)"]
        if not semi_total:
            semi_total = 0


        # get weekly income
        cur = db.execute("SELECT SUM(amount) FROM income WHERE user_id = :user_id AND freq = 'weekly'", {"user_id": session["user_id"]})
        weekly_total = sql_parse(cur)[0]["SUM(amount)"]
        if not weekly_total:
            weekly_total = 0

        # get quarterly income
        # very unlikely - but have to cover it
        cur = db.execute("SELECT SUM(amount) FROM income WHERE user_id = :user_id AND freq = 'quarterly'", {"user_id": session["user_id"]})
        quarterly_total = sql_parse(cur)[0]["SUM(amount)"]
        if quarterly_total:
            monthly_total += quarterly_total / 3



        in_total = round(monthly_total + ((26 * biweek_total) / 12) + ( 2 * semi_total ) + ( 4 * weekly_total ),2)

        return render_template("profile.html", pri_account=pri_account, outgoings=outgoings,
            out_total=out_total, income=income, in_total=in_total, active_page=active_page)

@app.route("/logout")
@login_required
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/income", methods=["GET", "POST"] )
@login_required
def income():
    """ Add income to the users profile """

    active_page = {}
    # /income does not have it's own selectable tab/nav button, so we make profile the active tab as this is where you access it from
    active_page["profile"] = "active"


    cur = db.execute("SELECT id, name FROM accounts WHERE user_id = :user_id", {"user_id":session["user_id"]})
    accounts = sql_parse(cur)

    if request.method == "POST":
        # add the income to the database
        # first check for empty fields!
        if not request.form.get("name") or not request.form.get("amount") or not request.form.get("payday"):
            # some field was not completed
            return render_template("income.html", error="Not all required fields were completed", accounts=accounts, active_page=active_page, frequency=FREQUENCY)

        # get form data in an easier to manipulate way
        name = request.form.get("name")
        amount = float(request.form.get("amount"))
        acc_id = request.form.get("account")
        payday = request.form.get("payday")

        # check that the pay frequency was not compromised by hackers!
        freq_invalid = True
        for freq in FREQUENCY:
            if freq["value"] == request.form.get("frequency"):
                freq_invalid = False
                break

        if freq_invalid:
            # frequency hacked - make it monthly
            frequency = "monthly-date-".split("-")
        else:
            # otherwise use selected frequency
            frequency = request.form.get("frequency").split("-")

        if frequency[0] == "monthly":
            if frequency[1] == "date":
                suffix = payday.split("-")[2]

            elif frequency[1] == "first" or frequency[1] == "last":
                y, m, d = (int(i) for i in payday.split('-'))
                pay_date = datetime.date(y, m, d)
                suffix = pay_date.weekday()

            else:
                suffix = ''

            freq = "{prefix}-{mid}-{suffix}".format(prefix = frequency[0], mid = frequency[1], suffix = suffix)
        else:
            freq = request.form.get("frequency")

        # Add income to db
        db.execute('''INSERT INTO income (name, amount, payday, freq, acc_id, user_id)
            VALUES (:name, :amount, :payday, :freq, :acc_id, :user_id)''',
            {"name":name, "amount":amount, "payday":payday, "freq":freq, "acc_id":acc_id, "user_id":session["user_id"]})
        db.commit()

        return redirect("/profile")
    else:

        return render_template("income.html", accounts=accounts, active_page=active_page, frequency=FREQUENCY)


@app.route("/outgoings", methods=["GET", "POST"] )
@login_required
def outgoings():
    """ Add outgoings to the users profile """

    active_page = {}
    # outgoings does not have it's own tab so set profile as active page
    active_page["profile"] = "active"

    if request.method == "POST":
        # add the outgoing to the database
        # first check for empty fields!
        if not request.form.get("name") or not request.form.get("amount") or not request.form.get("duedate"):
            return render_template("outgoings.html", error="Not all required fields were completed", active_page=active_page, frequency=FREQUENCY, category=CATEGORY)

        name = request.form.get("name")
        amount = float(request.form.get("amount"))

        cat_invalid = True
        for cat in CATEGORY:
            if cat["value"] == request.form.get("category"):
                cat_invalid = False
                break

        if cat_invalid:
            #category hacked - make it other
            category = "misc"
        else:
            # otherwise use selected category
            category = request.form.get("category")

        if category == "other":
            if not request.form.get("othertext"):
                return render_template("outgoings.html", error="Category 'Other' selected no text entered", active_page=active_page, frequency=FREQUENCY, category=CATEGORY)
            else:
                category = request.form.get("othertext")

        acc_id = request.form.get("account")
        duedate = request.form.get("duedate")

        # check that the pay frequency was not compromised by hackers!
        freq_invalid = True
        for freq in FREQUENCY:
            if freq["value"] == request.form.get("frequency"):
                freq_invalid = False
                break

        if freq_invalid:
            # frequency hacked - make it monthly
            frequency = "monthly-date-".split("-")
        else:
            # otherwise use selected frequency
            frequency = request.form.get("frequency").split("-")

        if frequency[0] == "monthly":
            if frequency[1] == "date":
                suffix = duedate.split("-")[2]

            elif frequency[1] == "first" or frequency[1] == "last":
                y, m, d = (int(i) for i in duedate.split('-'))
                pay_date = datetime.date(y, m, d)
                suffix = pay_date.weekday()

            else:
                suffix = ''

            freq = "{prefix}-{mid}-{suffix}".format(prefix = frequency[0], mid = frequency[1], suffix = suffix)
        else:
            freq = request.form.get("frequency")


        db.execute('''INSERT INTO outgoings (name, category, amount, due, freq, acc_id, user_id)
            VALUES (:name, :category, :amount, :duedate, :freq, :acc_id, :user_id)''',
            {"name":name, "category":category, "amount":amount, "duedate":duedate, "freq":freq, "acc_id":acc_id, "user_id":session["user_id"]})
        db.commit()
        return redirect("/profile")
    else:
        cur = db.execute("SELECT id, name FROM accounts WHERE user_id = :user_id", {"user_id":session["user_id"]})
        accounts = sql_parse(cur)
        return render_template("outgoings.html", accounts = accounts, active_page=active_page, frequency=FREQUENCY, category=CATEGORY)


@app.route("/advanced", methods=["GET","POST"])
@login_required
def advanced():
    """
    Show current balance, outgoings and income before next pay date
    """
    active_page = {}
    active_page["advanced"] = "active"


    # Get primary account info
    cur = db.execute("SELECT name,balance,id FROM accounts WHERE user_id = :user_id AND category = 'Primary'", {"user_id": session["user_id"]})
    pri_account = sql_parse(cur)

    if not pri_account:
        return redirect("/profile")

    pri_income = get_primary_income(session["user_id"])

    if not pri_income:
        return redirect("/profile")

    pri_account = pri_account[0]

    # get any past due income
    cur = db.execute("SELECT name, amount, category, payday, id, freq FROM income WHERE payday < :today AND user_id = :user_id",
        {"today": date.today().strftime("%Y-%m-%d"), "user_id": session["user_id"]})
    past_in = sql_parse(cur)
    cur = db.execute("SELECT SUM(amount) FROM income WHERE payday < :today AND user_id = :user_id",
        {"today": date.today().strftime("%Y-%m-%d"), "user_id": session["user_id"]})
    past_in_tot = sql_parse(cur)
    past_in_tot = past_in_tot[0]["SUM(amount)"]
    if not past_in_tot:
        past_in_tot = 0



    # get any past due outgoings
    cur = db.execute("SELECT name, amount, category, due, id, freq FROM outgoings WHERE due < :today AND user_id = :user_id",
        {"today": date.today().strftime("%Y-%m-%d"), "user_id": session["user_id"]})
    past_out = sql_parse(cur)
    cur = db.execute("SELECT SUM(amount) FROM outgoings WHERE due < :today AND user_id = :user_id",
        {"today": date.today().strftime("%Y-%m-%d"), "user_id": session["user_id"]})
    past_out_tot = sql_parse(cur)
    past_out_tot = past_out_tot[0]["SUM(amount)"]
    if not past_out_tot:
        past_out_tot = 0

    if request.method == "POST" and past_in:
        # We confirmed some income
        # sets the due/pay dates to next pay/due
        changed = False
        for pay in past_in:
            check_name = "in{}".format(pay['id'])
            if request.form.get(check_name) == "confirmed":
                next_payday = get_next_payday(pay["payday"], pay["freq"])
                set_transaction("income", t_id=pay["id"], t_date=next_payday.strftime("%Y-%m-%d"))
                pri_account["balance"] += pay["amount"]
                set_transaction("accounts", balance=pri_account["balance"], user_id=session["user_id"])
                changed = True
        if changed:
            cur = db.execute("SELECT name, amount, category, payday, id, freq FROM income WHERE payday < :today AND user_id = :user_id",
                {"today": date.today().strftime("%Y-%m-%d"), "user_id": session["user_id"]})
            past_in = sql_parse(cur)


    if request.method == "POST" and past_out:
        changed = False
        for out in past_out:
            check_name = "out{}".format(out['id'])
            if request.form.get(check_name) == "confirmed":
                next_payday = get_next_payday(out["due"], out["freq"])
                set_transaction("outgoings", t_id=out["id"], t_date=next_payday.strftime("%Y-%m-%d"))
                pri_account["balance"] -= out["amount"]
                set_transaction("accounts", balance=pri_account["balance"], user_id=session["user_id"])
                changed = True
        if changed:
            cur = db.execute("SELECT name, amount, category, due, id, freq FROM outgoings WHERE due < :today AND user_id = :user_id",
                {"today": date.today().strftime("%Y-%m-%d"), "user_id": session["user_id"]})
            past_out = sql_parse(cur)



    pay_date = make_datetime(pri_income[0]["payday"])

    for freq in FREQUENCY:
        value = freq["value"].split("-")
        in_freq = pri_income[0]["freq"].split("-")

        if len(in_freq) == 2 and len(value) == 2:
            # semi-monthly
            if value[0] == in_freq[0] and value[1] == in_freq[1]:
                pay_period = freq["text"]
        elif len(in_freq) == 3 and len(value) == 3:
            # monthly
            pay_period = "Monthly"
        elif len(in_freq) == 1 and len(value) == 1:
            if value[0] == in_freq[0]:
                pay_period = freq["text"]

    if date.today() < pay_date:
        next_payday = pay_date
    else:
        next_payday = get_next_payday(pri_income[0]["payday"],pri_income[0]["freq"])

    next_payday = wknd_adjust(next_payday)

    two_paydays = get_next_payday(next_payday.strftime("%Y-%m-%d"),pri_income[0]["freq"])
    two_paydays = wknd_adjust(two_paydays)



    # get all income into primary account between now and next payday
    income = get_transactions("income", date.today(), next_payday, pri_account, session["user_id"])
    # total $ amount of income
    tot_income = get_total("income", date.today(), next_payday, pri_account, session["user_id"])
    tot_income += past_in_tot

    # get all income into primary account between next payday and the one after
    next_in = get_transactions("income", next_payday, two_paydays, pri_account, session["user_id"])
    next_tot_in = get_total("income", next_payday, two_paydays, pri_account, session["user_id"])


    # get all outgoings from primary account between now and next payday
    outgoings = get_transactions("outgoings", date.today(), next_payday, pri_account, session["user_id"])
    # total $ amount of those outgoings
    tot_out = get_total("outgoings", date.today(), next_payday, pri_account, session["user_id"])
    tot_out += past_out_tot

    # get all outgoings from primary account between next payday and the one after
    next_out = get_transactions("outgoings", next_payday, two_paydays, pri_account, session["user_id"])
    next_tot_out = get_total("outgoings", next_payday, two_paydays, pri_account, session["user_id"])

    cur = db.execute("SELECT name, balance, category FROM accounts WHERE user_id = :user_id ORDER BY category, balance",
        {"user_id":session["user_id"]})
    accounts = sql_parse(cur)


    if request.method == "POST" and request.form.get("update"):
        # An outgoing or income has been confirmed
        if income:
            changed = False
            for inc in income:
                check_name = "in{}".format(inc["id"])
                if request.form.get(check_name) == "paid":
                    new_tdate = get_next_payday(inc["payday"], inc["freq"])
                    set_transaction("income", t_id=inc["id"], t_date=new_tdate.strftime("%Y-%m-%d"))
                    changed = True
            if changed:
                income = get_transactions("income", date.today(), next_payday, pri_account, session["user_id"])
                tot_income = get_total("income", date.today(), next_payday, pri_account, session["user_id"])
                tot_income += past_in_tot

        if outgoings:
            changed = False
            for out in outgoings:
                check_name = "out{}".format(out["id"])

                if request.form.get(check_name) == "paid":
                    new_tdate = get_next_payday(out["due"], out["freq"])
                    set_transaction("outgoings", t_id=out["id"], t_date=new_tdate.strftime("%Y-%m-%d"))
                    changed = True

            if changed:
                outgoings = get_transactions("outgoings", date.today(), next_payday, pri_account, session["user_id"])
                tot_out = get_total("outgoings", date.today(), next_payday, pri_account, session["user_id"])
                tot_out += past_out_tot


    if request.method == "POST" and request.form.get("next_update"):
        if next_in:
            changed = False
            for inc in next_in:
                check_name = "in{}".format(inc["id"])
                if request.form.get(check_name) == "paid":

                    new_tdate = get_next_payday(inc["payday"], inc["freq"])

                    set_transaction("income", t_id=inc["id"], t_date=new_tdate.strftime("%Y-%m-%d"))
                    changed = True
            if changed:
                next_in = get_transactions("income", next_payday, two_paydays, pri_account, session["user_id"])
                next_tot_in = get_total("income", next_payday, two_paydays, pri_account, session["user_id"])

        if next_out:
            changed = False
            for out in next_out:
                check_name = "out{}".format(out["id"])
                if request.form.get(check_name) == "paid":
                    new_tdate = get_next_payday(out["due"], out["freq"])
                    set_transaction("outgoings", t_id=out["id"], t_date=new_tdate.strftime("%Y-%m-%d"))
                    changed = True
            if changed:
                next_out = get_transactions("outgoings", next_payday, two_paydays, pri_account, session["user_id"])
                next_tot_out = get_total("outgoings", next_payday, two_paydays, pri_account, session["user_id"])

    fun_money = pri_account["balance"] + tot_income - tot_out

    next_fun_money = fun_money + next_tot_in - next_tot_out

    return render_template("advanced.html", accounts=accounts, income=income,
        next_in=next_in, outgoings=outgoings, next_out=next_out,
        fun_money=fun_money, next_fun_money=next_fun_money, active_page=active_page,
        next_payday=next_payday, past_in=past_in, past_out=past_out,
        pay_period=pay_period, today=date.today())

@app.route("/balance_update", methods=["POST"])
@login_required
def balance_update():
    """
    Allow the user to adjust the balance of their primary account.
    """
    redir_url = "/{}".format(request.form.get("source_url"))

    # this route should only be triggered with a post, but let's check anyway
    if not request.method == "POST" or not request.form.get("new_bal"):
        # someone tried to navigate here - or deleted their balance - send them back to advanced

        return redirect(redir_url)
    else:
        # let's update the balance on their account
        new_balance = float(request.form.get("new_bal"))

        cur = db.execute("SELECT id, name, balance FROM accounts WHERE user_id = :user_id AND category='Primary'", {"user_id": session["user_id"]})
        pri_acc = sql_parse(cur)[0]

        set_transaction("accounts",balance=new_balance, t_id=pri_acc["id"])

        return redirect(redir_url)
