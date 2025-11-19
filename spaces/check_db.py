import sqlite3
import json

try:
    con = sqlite3.connect("instance/database.sqlite")
    cur = con.cursor()
    # Correctly query the database based on the schema in database.py
    res = cur.execute("SELECT value FROM app_data WHERE key = 'main_db'")
    row = res.fetchone()

    if row:
        json_data_str = row[0]
        data = json.loads(json_data_str)

        articles = data.get("articles", {})
        print(f"Found {len(articles)} articles.")
        for article_id, article_data in articles.items():
            print(f"--- Article ID: {article_id} ---")
            print(f"Title: {article_data.get('title')}")
            content_len = len(article_data.get('content', ''))
            print(f"Content length: {content_len}")
            if content_len < 200: # Print short content for verification
                 print(f"Content: {article_data.get('content')}")
            print("-" * (len(article_id) + 20))
    else:
        print("No data found for key 'main_db'.")

    con.close()
except Exception as e:
    print(f"An error occurred: {e}")