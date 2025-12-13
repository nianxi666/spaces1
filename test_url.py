from project import create_app
from flask import url_for

app = create_app()

with app.app_context():
    with app.test_request_context():
        try:
            url = url_for('results.my_results')
            print(f"URL generated successfully: {url}")
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
