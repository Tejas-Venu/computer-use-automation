from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from html import escape

app = FastAPI(title="Mock Banking Application")

MEMBERS = {
    "12345": {
        "name": "Alex Morgan",
        "savings_balance": "2450.75",
    },
    "67890": {
        "name": "Jordan Lee",
        "savings_balance": "8150.20",
    },
}


def page(content: str) -> HTMLResponse:
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Bank Administration</title>
        <style>
            body {{
                font-family: Arial;
                max-width: 750px;
                margin: 60px auto;
            }}
            input, button {{
                padding: 10px;
                margin: 8px 0;
            }}
            .error {{ color: darkred; }}
        </style>
    </head>
    <body>
        <h1>Bank Administration Portal</h1>
        {content}
    </body>
    </html>
    """)


@app.get("/", response_class=HTMLResponse)
def home():
    return page("""
        <h2>Member Search</h2>
        <form action="/search" method="post">
            <label>Member ID</label>
            <input name="member_id" required>
            <button type="submit">Search</button>
        </form>
    """)


@app.post("/search", response_class=HTMLResponse)
def search(member_id: str = Form(...)):
    member = MEMBERS.get(member_id)

    if not member:
        return page(
            '<p class="error">Member not found</p>'
            '<a href="/">Back to search</a>'
        )

    safe_id = escape(member_id, quote=True)
    safe_name = escape(member["name"])

    return page(f"""
        <h2>Search Results</h2>
        <p>Member: {safe_name}</p>
        <a href="/members/{safe_id}">Open Details</a>
    """)


@app.get("/members/{member_id}", response_class=HTMLResponse)
def member_details(member_id: str):
    member = MEMBERS.get(member_id)

    if not member:
        return page('<p class="error">Member not found</p>')

    return page(f"""
        <h2>Member Details</h2>
        <p>Member ID: {escape(member_id)}</p>
        <p>Name: {escape(member["name"])}</p>
        <p>Savings Balance:
            ${escape(member["savings_balance"])}
        </p>
        <p>Account Status: Active</p>
    """)