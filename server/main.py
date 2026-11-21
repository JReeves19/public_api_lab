from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
from pydantic import BaseModel
import requests
import re
from datetime import datetime

app = FastAPI()
security = HTTPBasic()
USERNAME = "user"
PASSWORD = "pass"

# Define response model
class Book(BaseModel):
    title: str
    author: str
    publish_date: str
    isbn: str

class BookCache(BaseModel):
    cached: bool
    data: Book

book_cache: dict[str, Book] = {}

# RegEx for ISBN-10 or ISBN-13 validation
ISBN_REGEX = r"^(?:\d{10}|\d{13})$"

def validate_isbn(isbn:str) -> bool:
    return bool(re.match(ISBN_REGEX, isbn))

def parse_date(date_str:str) -> str:
    formats = (
        "%Y-%m-%d",
        "%Y-%m",
        "%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%B %Y",
        "%b %Y"
    )

    parsed_date = None
    for fmt in formats:
        try:
            parsed_date = datetime.strptime(date_str.strip(), fmt)
            break
        except ValueError:
            continue

    if parsed_date is None:
        raise HTTPException(status_code=400, detail="Invalid publication date")

    current_year = datetime.now().year
    if parsed_date.year < 1800 or parsed_date.year > current_year:
        raise HTTPException(status_code=400, detail=f"Publication year must be between 1800 and {current_year}")

    return parsed_date.strftime("%Y-%m-%d")
        

@app.get("/book/{isbn}", response_model=BookCache)
async def get_book_by_isbn(isbn:str, credentials: HTTPBasicCredentials = Depends(security)) -> BookCache:
    username = secrets.compare_digest(credentials.username, USERNAME)
    password = secrets.compare_digest(credentials.password, PASSWORD)

    if not (username and password):
        raise HTTPException(
            status_code=401, 
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"}
            )
    
    # Validate ISBN
    if not validate_isbn(isbn):
        raise HTTPException(status_code=400, detail="Invalid ISBN format (must be 10 or 13 digits)")

    if isbn in book_cache:
        return BookCache(cached=True, data=book_cache[isbn])

    # Fetch from Open Library API
    try:
        url = f"http://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        # Check if book data exists
        book_key = f"ISBN:{isbn}"
        if book_key not in data:
            raise HTTPException(status_code=404, detail="Book not found")

        book_data = data[book_key]
        title = book_data.get("title", "Unknown")
        authors = book_data.get("authors", [{"name": "Unknown"}])[0]["name"]
        publish_date = parse_date(book_data.get("publish_date", "Unknown"))

        book =  Book(
                title=title,
                author=authors,
                publish_date=publish_date,
                isbn=isbn
        )

        book_cache[isbn] = book
        return BookCache(
            cached=False,
            data=book
        )
    
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error fetching book data: {str(e)}")

@app.post("/books/bulk")
async def get_books_bulk(isbns:list[str]):
    results = []

    for isbn in isbns:
        try:
            if not validate_isbn(isbn):
                results.append({"isbn": isbn, "error": "Invalid ISBN format"})
                continue

            if isbn in book_cache:
                results.append({
                    "isbn": isbn,
                    "cached": True,
                    "data": book_cache[isbn]
                })
                continue

            url = f"http://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            book_key = f"ISBN:{isbn}"
            if book_key not in data:
                results.append({"isbn": isbn, "error": "Book not found"})
                continue

            book_data = data[book_key]
            authors = book_data.get("authors", [])
            author = authors[0]["name"] if authors else "Unknown"

            book = Book(
                title=book_data.get("title", "Unknown"),
                author=author,
                publish_date=parse_date(book_data.get("publish_date", "Unknown")),
                isbn=isbn
            )

            book_cache[isbn] = book
            results.append({
                "isbn": isbn,
                "cached": False,
                "detail": book
            })

        except HTTPException as e:
            results.append({
                "isbn": isbn,
                "error": e.detail
            })

        except requests.RequestException as e:
            results.append({
                "isbn": isbn,
                "error": f"Error fetching book data: {e}"
            })

    return results

@app.get("/books/search", response_model= list[Book])
async def search_books(title:str):
    url = "https://openlibrary.org/search.json"

    try:
        response = requests.get(
            url,
            params={
                "q": title,
                "limit": 5,
                "fields": "title,author_name,first_publish_year,isbn",
            }
        )
        response.raise_for_status()
        data = response.json()

        books = []
        for book in data.get("docs", [])[:5]:
            authors = book.get("author_name", [])
            isbns = book.get("isbn", [])

            books.append(
                Book(
                    title=book.get("title","Unknown"),
                    author=authors[0],
                    publish_date=str(book.get("first_publish_year", "Unknown")),
                    isbn=isbns[0] 
                )
            )

        return books

    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Error fetching book data: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)