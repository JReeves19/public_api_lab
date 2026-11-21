import typer
import requests
import json

app = typer.Typer()
BASE_URL = "http://localhost:8000"

def print_response(response):
    try:
        print(f"Status Code: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
    except ValueError:
        print(f"Status Code: {response.status_code}")
        print(response.text)

@app.command()
def get_book(isbn:str, 
             username: str = typer.Option(..., "--username"),
             password: str = typer.Option(..., "--password"),
             min_year:int | None = typer.Option(None, "--min-year")):
    """Fetch book details by ISBN."""
    try:
        response = requests.get(f"{BASE_URL}/book/{isbn}", auth=(username,password))

        if response.status_code != 200:
            print_response(response)
            return

        if min_year is not None:
            result = response.json()
            book = result["data"]
            publication_year = int(book["publish_date"][:4])

            if publication_year < min_year:
                typer.echo(f"Book publication year {publication_year} is earlier than the minimum year {min_year}")
                return

        print_response(response)

    except requests.RequestException as e:
        typer.echo(f"Error: Failed to connect to server - {str(e)}")

@app.command("search-title")
def search_title(title:str):
    """Search for books by title"""
    try:
        response = requests.get(f"{BASE_URL}/books/search", params={"title":title})
        print_response(response)
    except requests.RequestException as e:
        typer.echo(f"Error: Failed to connect to server - {str(e)}")

@app.command("get-bulk")
def get_bulk(isbns: list[str] = typer.Argument(...)):
    """Fetch multiple books by ISBN"""
    try:
        response = requests.post(f"{BASE_URL}/books/bulk", json=isbns)
        print_response(response)
    except requests.RequestException as e:
        typer.echo(f"Error: Failed to connect to server - {str(e)}")

if __name__ == "__main__":
    app()