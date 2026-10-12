"""Start the API:  python server.py   (then open the Next.js app on :3000)"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("scraper.api:app", host="127.0.0.1", port=8000, reload=False)
