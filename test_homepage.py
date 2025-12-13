from project import create_app

app = create_app()

with app.test_client() as client:
    try:
        response = client.get('/')
        print(f"Status Code: {response.status_code}")
        if response.status_code != 200:
            print(f"Response data: {response.data[:500]}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
