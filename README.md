# telegram-budget-app
An intuitive budget app built on python, using a combination of SQL and text files to store data and having an easy to navigate front end consisting of buttons to create and delete categories, record transactions, categorize transactions and delete transactions.
## How do I use it?
Get your API token from botfather on telegram, create a .env file and store it inside of this file, now you'll have to host it.

I host mine on a Raspberry Pi 3b+ and haven't experienced any issues.
That's it, no creating and configuring databases (the code does it for you). No creating files or further setup on the hosting side.

You can now start the bot by sending it a /start, and configure everything you want to do via the "Setup" button on the main menu.
## How is the data being stored?
The transactions (and your budget ammounts per category) are being stored via an sqllite database, all further configuration files are being stored through text files, including your categories, your budget start/end day.
## How can I see what's going on?
Easy, tap the summarize button to get a quick overview of how much you've spent on all your categories (since the last budget start day) and how much is left.
## Why use it?
With an intuitive and easy to use interface, recording transactions are much simpler, rather than having a budget app try to record the transactions, categorizing them wrong and now you have to spend 10 minutes getting them into the right category OR having to open a spreadsheet, record all transactions which you'll fall behind on after a week, and then frantically go through your bank statements to figure out what you haven't recorded yet.
## Great for analysis
Simply export the data as a CSV, and import it into a reporting tool of your choice, should that be an excel spreadsheet or a power BI report. You can see what was happening when, and with a ton of simplicity and build out your own visualizations. Do what works for you.