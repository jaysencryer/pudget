# Financial Tracker

This is Financial Tracker, my Final Project for CS50.

It is a web-based application that allows you to track your regular outgoings and income from your bank account.
Once configured it can show you in simple, uncomplicated terms how much money you are able to spend before your next pay check.
It uses the Model-view-controller form of design.
The model is an SQLlite3 database which stores users, accounts (in this initial version limited to one primary account), income and outgoings.
The view uses Jinja templates via Flask, HTML, CSS (including bootstrap) and a couple of JavaScript functions.
The controller is written in Python using the Flask Framework.


My goal for this project was to replace an increasingly complex Google Sheets budget spreadsheet that I have created over the years.
Although it makes sense to me it is over-complicated and not easily accessible to anyone else who may desire a similar functionality.
For example, my wife has asked on numerous occasions to be able to just open it up and see how much money she can spend at any one time.
This software is designed to do just that, (once configured!).

A user can login and immediately see how much money they have left to spend in their current pay period.
The pay period shown is adaptive dependent on which of their incomes pays the most over a month (as most large outgoings are usually monthly).
This enables them to see at a glance (after updating the balance to reflect the actual money in their bank) how much money they can spend.

The outgoings are categorized to enable an easy view of what things are able to be sacrificed (such as entertainment), or flexible (groceries).

My goal is to continue to develop this software outside of CS50 to make it a powerful budgeting tool, and eventually convert it to an app,
possible linking to a users actual bank account to allow real time balance updates and outgoing tracking.

Jaysen Cryer 11/30/2020

[Demonstration Video](https://youtu.be/ULhXgYUXYYw)
